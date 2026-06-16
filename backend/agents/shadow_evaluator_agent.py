"""离线反思学习引擎 — 深夜复盘与提示词增强"""

import json
import logging
from typing import AsyncGenerator, List, Dict, Any
from datetime import datetime

from backend.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ShadowEvaluator(BaseAgent):
    """
    离线反思学习引擎
    模型: DeepSeek-V4-Flash（强逻辑、深度反思）
    职责: 复盘失败案例，提炼 Few-Shot 指南，
          写入 adaptive_guides 表反哺系统提示词
    """

    def __init__(self, *args, db_session_factory=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_session_factory = db_session_factory

    def system_prompt(self) -> str:
        return (
            "【角色定位】你是校园智能系统的「离线反思学习引擎」。你的工作是在深夜系统空闲时，"
            "复盘白天产生的失败会话日志，提炼改进方案。\n"
            "【复盘流程】\n"
            "1. 分析失败案例的分类（RAG_BLIND / POOR_EXPERIENCE / EMOTION_ALERT）\n"
            "2. 理解用户真实需求 vs 系统给出的错误答复\n"
            "3. 提炼改进方案：如果是 RAG 盲区，需要补充什么检索词；如果体验差，需要调整什么话术\n"
            "4. 输出结构化的改善建议\n"
            "【输出格式】JSON 格式：\n"
            '{"scene_keywords": "场景触发词", "guide_text": "金牌话术指南", "agent_role": "目标智能体"}'
        )

    async def analyze_failure(self, failure: Dict[str, Any]) -> Dict[str, str]:
        """分析单条失败案例"""
        user_query = failure.get("user_query", "")
        ai_response = failure.get("ai_response", "")
        failure_type = failure.get("failure_type", "POOR_EXPERIENCE")

        prompt = (
            f"请分析以下失败案例并给出改进方案。\n\n"
            f"失败类型：{failure_type}\n"
            f"用户问题：{user_query}\n"
            f"AI回复：{ai_response}\n\n"
            "请严格按照 JSON 格式输出改进方案。"
        )

        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": prompt},
        ]

        raw = await self._non_stream_chat(messages)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            try:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                result = json.loads(raw[start:end])
            except (ValueError, json.JSONDecodeError):
                result = {
                    "scene_keywords": user_query[:50],
                    "guide_text": raw[:500],
                    "agent_role": "policy_auditor" if "RAG" in failure_type else "mental_health",
                }

        return result

    async def batch_analyze(self, failures: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """批量分析失败案例"""
        results = []
        for f in failures:
            try:
                guide = await self.analyze_failure(f)
                results.append(guide)
            except Exception as e:
                logger.error(f"分析失败案例时出错: {e}")
        return results

    async def reflect_and_enhance(self, failures: List[Dict[str, Any]]) -> str:
        """执行一夜复盘，返回总结报告"""
        if not failures:
            return "今夜无失败案例需要复盘，系统运行正常。"

        guides = await self.batch_analyze(failures)

        # 写入数据库
        if self._db_session_factory:
            session = self._db_session_factory()
            try:
                from backend.db.mysql_models import AdaptiveGuide
                for g in guides:
                    existing = session.query(AdaptiveGuide).filter(
                        AdaptiveGuide.scene_keywords == g.get("scene_keywords", ""),
                        AdaptiveGuide.is_active == 1,
                    ).first()
                    if not existing:
                        guide = AdaptiveGuide(
                            scene_keywords=g.get("scene_keywords", "")[:200],
                            guide_text=g.get("guide_text", ""),
                            agent_role=g.get("agent_role", "general"),
                        )
                        session.add(guide)
                session.commit()
                logger.info(f"✅ 已写入 {len(guides)} 条增强指南")
            except Exception as e:
                session.rollback()
                logger.error(f"写入增强指南失败: {e}")
            finally:
                session.close()

        report = (
            f"📊 深夜反思报告\n"
            f"分析案例数：{len(failures)}\n"
            f"生成指南数：{len(guides)}\n"
            f"时间：{datetime.utcnow().isoformat()}\n"
        )
        return report

    async def process(self, user_input: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """便于 FastAPI 调用的入口"""
        failures = context.get("failures", [])
        report = await self.reflect_and_enhance(failures)
        yield report
