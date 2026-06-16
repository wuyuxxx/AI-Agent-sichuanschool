"""FastAPI API 路由 — SSE 流式交互"""

import json
import logging
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from backend.config import config
from backend.core.trie_filter import CrisisTrieFilter
from backend.core.rag_pipeline import RAGPipeline
from backend.core.session_memory import SessionMemory
from backend.core.affective_guardrail import AffectiveGuardrail
from backend.agents.router_agent import IntentRouter
from backend.agents.mental_health_agent import MentalHealthExpert
from backend.agents.academic_exec_agent import AcademicExecutive
from backend.agents.policy_audit_agent import PolicyAuditor

logger = logging.getLogger(__name__)

router = APIRouter()

# ----------------------------------------------------------------
# 全局组件（由 main.py 注入）
# ----------------------------------------------------------------
trie_filter: CrisisTrieFilter = None
session_memory: SessionMemory = None
affective_guardrail: AffectiveGuardrail = None
rag_pipeline: RAGPipeline = None
router_agent: IntentRouter = None
mental_agent: MentalHealthExpert = None
academic_agent: AcademicExecutive = None
policy_agent: PolicyAuditor = None

# 危机拦截静态文本
CRISIS_RESPONSE = (
    "⚠️【校园心理健康中心 · 24小时生命守护红线】\n\n"
    "同学！请停下你正在想的事情，听我说：你的生命对我们、对这个世界都极其重要！\n"
    "你现在正在经历的巨大痛苦和黑暗，我们看见了。请让我们拉住你，你绝对不是一个人在面对。\n\n"
    "请不要关闭这个界面，并立刻做出以下行动：\n"
    "1. 拿起电话，直接拨打学校24小时心理守护热线：XXXX-XXXXXX\n"
    "2. 随时可以直接推门来到【教学楼B座201】的心理咨询中心\n\n"
    "我会在这里一直陪着你。"
)

# 低置信度兜底
LOW_CONFIDENCE_FALLBACK = (
    "抱歉，我目前检索到的信息不足以准确回答你的问题。"
    "建议你联系辅导员或前往教务处办公室咨询。"
)


# ----------------------------------------------------------------
# 请求/响应模型
# ----------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str = ""
    message: str


class ChatResponse(BaseModel):
    session_id: str
    status: str


# ----------------------------------------------------------------
# 流式生成器
# ----------------------------------------------------------------
async def _stream_chat(session_id: str, user_message: str) -> AsyncGenerator[str, None]:
    """核心流式处理逻辑"""

    # 1. 第一防线：Trie 树危机词拦截
    if trie_filter.contains_crisis(user_message):
        yield json.dumps({"type": "crisis", "content": CRISIS_RESPONSE}, ensure_ascii=False)

        # 异步写入失败日志
        try:
            await session_memory.push_message(session_id, "user", user_message)
            await session_memory.push_message(session_id, "assistant", CRISIS_RESPONSE)
        except Exception:
            pass
        return

    # 2. 保存用户消息到历史
    await session_memory.push_message(session_id, "user", user_message)

    # 3. 获取历史上下文
    history = await session_memory.get_history(session_id)

    # 4. 情感审计（第三道防线前置检查）
    affective_history = await session_memory.get_affective_history(session_id, window=config.affective.window_size)
    report = affective_guardrail.analyze(affective_history)
    degraded = report.needs_degradation

    if report.needs_alert:
        logger.warning(f"情感预警 [session={session_id}]: avg={report.avg_score:.2f}, slope={report.slope:.2f}")

    # 5. 路由分流
    intent = await router_agent.classify(user_message)

    # 6. 按意图分流
    full_response = ""
    try:
        if intent == "[POLICY]":
            async for chunk in policy_agent.process(user_message, {
                "history": history,
                "degraded": degraded,
            }):
                full_response += chunk
                yield json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)

        elif intent == "[MENTAL]":
            async for chunk in mental_agent.process(user_message, {
                "history": history,
                "degraded": degraded,
            }):
                full_response += chunk
                yield json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)

        elif intent == "[ACADEMIC]":
            async for chunk in academic_agent.process(user_message, {
                "history": history,
            }):
                full_response += chunk
                yield json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)

        else:  # [GREETING] 及兜底
            # 简单问候用固定回复，日常问答走 DeepSeek 深度思考
            short_greetings = {"你好", "嗨", "hi", "hello", "hey", "在吗", "在", "您好"}
            if user_message.strip().lower() in short_greetings or len(user_message.strip()) <= 2:
                greeting = "你好呀！我是智汇校园助手，有什么可以帮你的吗？你可以问我关于学籍政策、选课事务，或者只是找我聊聊天。😊"
                full_response = greeting
                yield json.dumps({"type": "chunk", "content": greeting}, ensure_ascii=False)
            else:
                # 把历史上下文传入，让 AI 知道之前聊了什么
                today = __import__('datetime').datetime.now().strftime('%Y-%m-%d')
                messages = [
                    {"role": "system", "content": f"你是一个友好的智汇校园助手，请用中文简洁自然地回答用户的日常问题。如果涉及日期计算，请基于当前日期 {today} 回答。"},
                ]
                for h in history[-6:]:
                    messages.append(h)
                messages.append({"role": "user", "content": user_message})
                async for chunk in policy_agent.chat(messages):
                    full_response += chunk
                    yield json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Agent 处理异常: {e}", exc_info=True)
        yield json.dumps({"type": "error", "content": "抱歉，系统暂时出了点小问题，请稍后再试。"}, ensure_ascii=False)
        full_response = "系统内部错误"

    # 7. 保存 AI 回复
    await session_memory.push_message(session_id, "assistant", full_response)

    # 8. 结束标记
    yield json.dumps({"type": "done"}, ensure_ascii=False)


# ----------------------------------------------------------------
# API 端点
# ----------------------------------------------------------------
@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """获取会话历史"""
    try:
        history = await session_memory.get_history(session_id)
        return {"history": history}
    except Exception as e:
        logger.error(f"获取历史失败: {e}")
        return {"history": []}


@router.post("/chat")
async def chat(req: ChatRequest):
    """流式对话接口"""
    session_id = req.session_id or str(uuid.uuid4())

    return EventSourceResponse(
        _stream_chat(session_id, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "campus-agent-hub"}


@router.post("/reset")
async def reset_session(session_id: str):
    """重置会话"""
    try:
        await session_memory.set_session(session_id, {"reset": "true"})
    except Exception:
        pass
    return {"status": "reset", "session_id": session_id}
