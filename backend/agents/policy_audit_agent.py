"""学籍管理政策专家 — 高级 RAG 审计流水线"""

from typing import AsyncGenerator, Dict, Any, List

from backend.agents.base import BaseAgent
from backend.core.rag_pipeline import RAGPipeline


class PolicyAuditor(BaseAgent):
    """
    学籍管理政策专家
    模型: DeepSeek-V4-Flash（长文本依赖、严防幻觉）
    工具: RAG 检索流水线 + 会话上下文重写
    """

    def __init__(self, *args, rag_pipeline: RAGPipeline = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rag = rag_pipeline

    def system_prompt(self) -> str:
        return (
            "【角色定位】你是校园智能系统的「学籍管理政策专家」。你的回答必须严格基于召回的政策条款。\n"
            "【核心规则】\n"
            "1. 所有回答必须100%基于下方提供的政策条款原文。\n"
            "2. 必须在关键引用处标注出处，格式：[出处: 学生手册-章节名]\n"
            "3. 如果检索到的条款不足以回答学生问题，必须明确说「手册中未找到相关条款，建议咨询辅导员」。\n"
            "4. 禁止凭空编造政策、推测条款或给出个人建议。\n"
            "5. 回答要口语化、易懂，同时保持准确。\n"
            "【引用格式】每条引用以脚注形式置于句末，如「...取消考试资格[出处: 学生手册-第一章-总则与考勤规范]」。"
        )

    async def _rewrite_query(self, query: str, history: List[Dict[str, str]]) -> str:
        """基于历史上下文重写检索式"""
        if not history:
            return query

        recent = history[-4:]  # 最近几轮
        context_lines = []
        for msg in recent:
            role = "学生" if msg["role"] == "user" else "系统"
            context_lines.append(f"{role}: {msg['content']}")

        rewrite_prompt = (
            "你是一个检索查询重写助手。结合对话历史，将当前学生的问题改写为"
            "信息完整、适合向量检索的标准查询。只输出改写后的查询，不要解释。\n\n"
            "对话历史：\n" + "\n".join(context_lines) + "\n\n"
            f"当前问题：{query}\n\n"
            "改写后："
        )

        messages = [
            {"role": "system", "content": "你是一个专业的检索查询重写助手。"},
            {"role": "user", "content": rewrite_prompt},
        ]
        rewritten = await self._non_stream_chat(messages)
        return rewritten.strip() or query

    async def process(self, user_input: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        history = context.get("history", [])
        degraded = context.get("degraded", False)

        # 1. 会话上下文重写
        rewritten = await self._rewrite_query(user_input, history)
        yield f"[RAG 审计] 检索式重写完成，正在执行多路混合召回...\n"

        # 2. 执行混合检索
        rag_results = await self.rag.hybrid_search(rewritten, collection_type="policy")
        if not rag_results:
            # 使用原查询再试一次
            rag_results = await self.rag.hybrid_search(user_input, collection_type="policy")

        # 3. 置信度检查
        if not rag_results:
            yield "抱歉，我在政策手册中未检索到足够相关的内容。「没有相关条款」建议你联系辅导员或前往教务办公室咨询。"
            return

        # 4. 生成带引用的回答
        context_text = self.rag.format_citation(rag_results)
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": (
                f"请基于以下政策条款回答学生的问题。\n\n"
                f"【政策条款】\n{context_text}\n\n"
                f"【学生问题】{user_input}"
            )},
        ]

        yield f"[RAG 审计] 已召回 {len(rag_results)} 条相关条款，置信度通过。正在生成审计答复...\n"

        async for chunk in self._stream_chat(messages):
            yield chunk

        # 5. 追加引用来源
        sources = []
        for r in rag_results:
            meta = r.get("metadata", {})
            section = meta.get("section", "未知")
            ref = f"[出处: 学生手册-{section}]"
            if ref not in sources:
                sources.append(ref)

        if sources:
            yield "\n\n---\n📖 参考来源：\n" + "\n".join(sources)
