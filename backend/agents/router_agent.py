"""路由中枢智能体 — Mimo-v2.5 意图分类器"""

from typing import AsyncGenerator, Dict, Any

from backend.agents.base import BaseAgent


class IntentRouter(BaseAgent):
    """
    路由中枢智能体
    模型: Mimo-v2.5（极速低成本）
    职责: 仅输出分流标签，不处理具体业务。
    """

    def system_prompt(self) -> str:
        return (
            "【角色定位】你是一个校园智能系统的意图路由分类器，运行在 Mimo-v2.5 极速模型上。\n"
            "【核心规则】你只负责输出一个分类标签，不能输出任何其他内容。\n"
            "【分类标签】\n"
            "1. [POLICY] — 学生询问学籍管理、考试政策、补考重修、毕业要求等政策类问题。\n"
            "2. [MENTAL] — 学生表达负面情绪、心理困扰、人际压力、焦虑抑郁等需要心理支持的内容。\n"
            "3. [ACADEMIC] — 学生要求查询课表、选课、退课、查成绩、抢课等教务操作类需求。\n"
            "4. [GREETING] — 简单问候、打招呼、无实际意图的闲聊。\n"
            "【输出格式】仅输出方括号标签，例如 [POLICY]，严禁附带任何解释。"
        )

    async def process(self, user_input: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """路由智能体不处理具体业务，直接用 classify 分类后返回标签"""
        label = await self.classify(user_input)
        yield label

    async def classify(self, user_input: str) -> str:
        """异步分类：先尝试关键词（零延迟），未命中再调 LLM"""
        # 优先使用关键词匹配（零网络开销）
        keyword_result = self._classify_simple(user_input)
        if keyword_result != "[GREETING]" or self._is_short_greeting(user_input):
            return keyword_result

        # 关键词未命中（即非明确分类的日常询问），调 Mimo 做语义分类
        try:
            messages = [
                {"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": user_input},
            ]
            result = await self._non_stream_chat(messages, timeout=8.0)
            result = result.strip()
            if result in ("[POLICY]", "[MENTAL]", "[ACADEMIC]", "[GREETING]"):
                return result
        except Exception:
            pass
        return self._classify_simple(user_input)

    @staticmethod
    def _is_short_greeting(text: str) -> bool:
        """是否为短问候（让这些走 Mimo 以支持多语言/变体）"""
        short = {"你好", "嗨", "hi", "hello", "hey", "在吗", "在", "您好", "hello world"}
        return text.strip().lower() in short or len(text.strip()) <= 2

    @staticmethod
    def _classify_simple(user_input: str) -> str:
        """基于规则的快速分类兜底"""
        text = user_input

        # 心理类
        mental_keywords = [
            "难过", "伤心", "焦虑", "害怕", "孤独", "绝望", "失眠", "烦躁",
            "压力", "累", "没意思", "无聊", "难受", "崩溃", "抑郁",
            "心理", "心理咨询", "情绪", "心情不好", "不开心", "烦",
            "倾听", "心理老师", "心理中心",
        ]
        if any(kw in text for kw in mental_keywords):
            return "[MENTAL]"

        # 政策类
        policy_keywords = [
            "政策", "规定", "手册", "学分", "毕业", "补考", "重修", "挂科",
            "不及格", "考勤", "旷课", "请假", "学位", "选修", "必修",
        ]
        if any(kw in text for kw in policy_keywords):
            return "[POLICY]"

        # 教务类
        academic_keywords = [
            "选课", "退课", "查成绩", "课表", "课程", "排课", "抢课",
            "报名", "考试安排",
        ]
        if any(kw in text for kw in academic_keywords):
            return "[ACADEMIC]"

        return "[GREETING]"
