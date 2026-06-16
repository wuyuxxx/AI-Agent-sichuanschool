"""暖心倾听心理咨询专家 — 去诊断化共情舒缓"""

import logging
from typing import AsyncGenerator, Dict, Any, List

from backend.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class MentalHealthExpert(BaseAgent):
    """
    暖心倾听心理咨询专家
    模型: Mimo-v2.5（高信息熵、强共情，无需大参数模型）
    边界: 禁止使用诊断词汇，只做情绪减压与导流
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._safety_template = (
            "同学，我能感受到你现在的心情不太好。如果你愿意的话，我一直在这里陪着你倾听。\n\n"
            "同时我也想提醒你，学校的心理咨询中心有非常专业的老师，他们能给你更好的帮助：\n"
            "📍 教学楼B座201 · 心理咨询中心\n"
            "📞 学校24小时心理守护热线：XXXX-XXXXXX\n\n"
            "你不需要一个人面对这些，我们一起想办法，好吗？"
        )

    def system_prompt(self) -> str:
        return (
            "【角色定位】你是校园智能系统的「暖心倾听心理咨询专家」。你的定位是无条件的情绪减压阀与导流员。\n"
            "【绝对红线】\n"
            "1. 禁止使用任何精神医学诊断词汇：绝对不能说出「抑郁症」「焦虑症」「人格障碍」「双向情感障碍」「PTSD」「精神分裂」等诊断标签。\n"
            "2. 禁止给对方贴标签或下结论。\n"
            "3. 禁止建议停药、改药或替代医疗方案。\n"
            "【你的工作】\n"
            "1. 积极关注：无条件接纳对方的情绪表达。\n"
            "2. 倾听共情：用温暖、平和、非指导性的语言回应。\n"
            "3. 温柔导流：在建立信任后，温和推荐学校心理咨询中心的线下资源。\n"
            "4. 保持简短：用2-4句话回应，不要长篇大论。\n"
            "【语气风格】温暖、耐心、平和，像一个大三的暖心学长/学姐。"
        )

    async def process(self, user_input: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        history = context.get("history", [])
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.system_prompt()},
        ]
        for h in history[-4:]:  # 最近 2 轮对话
            messages.append(h)
        messages.append({"role": "user", "content": user_input})

        # 检查是否触发灰度降级
        degraded = context.get("degraded", False)
        if degraded:
            yield self._safety_template
            return

        try:
            async for chunk in self._stream_chat(messages):
                yield chunk
        except Exception:
            logger.warning("Mimo-v2.5 连接失败，降级至安全模板响应")
            yield self._safety_template
