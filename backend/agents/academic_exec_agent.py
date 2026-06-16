"""教务数据执行官 — Function Calling + MySQL 事务操控"""

import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.agents.base import BaseAgent
from backend.db.mysql_models import Student, Course, StudentCourse


class AcademicExecutive(BaseAgent):
    """
    教务数据执行官
    模型: DeepSeek-V4-Flash（零容错、强结构化）
    工具: MySQL 事务执行接口
    """

    def __init__(self, *args, db_session_factory=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_session_factory = db_session_factory

    def system_prompt(self) -> str:
        return (
            "【角色定位】你是校园智能系统的「教务数据执行官」。你负责将自然语言转化为精确的数据库操作。\n"
            "【可用操作】\n"
            "1. 查询课程信息：根据课程名、教师等条件查询排课和容量\n"
            "2. 查询已选课程：查看某学生的选课列表\n"
            "3. 选课操作：为学生添加选课记录（需检查容量和冲突）\n"
            "4. 退课操作：取消学生的选课记录\n"
            "5. 查询成绩：查看学生的已修课程与成绩\n"
            "【执行规则】\n"
            "- 选课前必须检查课程容量（已选人数 < 总容量）\n"
            "- 防止重复选课\n"
            "- 退课后释放容量\n"
            "- 任何操作需要先确认学生身份\n"
            "- 如果缺少必要信息（学号等），请向用户询问\n"
            "【输出格式】先说明你要执行的操作，然后给出结果，语言简洁明了。"
        )

    def _general_system_prompt(self) -> str:
        """兜底通用提示词：当非教务查询被误路由至此，仍能以助手身份回答"""
        return (
            "你是一个友好的智汇校园助手。请用中文简洁、自然地回答用户的日常问题。\n"
            "你可以回答技术知识、校园生活、学习建议等各类问题。\n"
            "注意：如果用户明确要求进行选课、退课、查成绩、查课程等教务操作，引导其提供学号和课程名。"
        )

    async def process(self, user_input: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行教务操作：优先匹配数据库操作，兜底走 LLM 生成"""
        # 尝试匹配数据库操作
        db_result = await self._try_db_operation(user_input)
        if db_result:
            yield db_result
            return

        # 兜底：走 LLM 生成回复（带上历史上下文，使用通用提示词）
        history = context.get("history", [])
        messages = [
            {"role": "system", "content": self._general_system_prompt()},
        ]
        for h in history[-4:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_input})
        async for chunk in self._stream_chat(messages):
            yield chunk

    async def _try_db_operation(self, user_input: str) -> Optional[str]:
        """根据用户输入关键词尝试执行数据库操作"""
        text = user_input.strip()

        # 查询课程 → 提取关键词查 DB
        if any(kw in text for kw in ["查课", "有什么课", "课程查询", "查询课程", "课表"]):
            keyword = text
            for kw in ["查课", "有什么课", "课程查询", "查询课程", "课表", "课程"]:
                keyword = keyword.replace(kw, "")
            keyword = keyword.strip() or "计算机"
            return await self.query_courses(keyword)

        # 选课 → 需要学号和课程信息
        if any(kw in text for kw in ["选课", "报名", "选"]):
            return "请提供你的学号和想选的课程名称，我来帮你操作。"

        # 退课
        if any(kw in text for kw in ["退课", "取消选课", "退"]):
            return "请提供你的学号和想退的课程名称，我来帮你操作。"

        # 查成绩
        if "成绩" in text or "得分" in text or "分数" in text:
            return "请提供你的学号，我来查询你的成绩。"

        return None

    async def query_courses(self, keyword: str) -> str:
        """查询课程（由路由调度）"""
        if not self._db_session_factory:
            return "数据库未连接，无法查询。"
        session = self._db_session_factory()
        try:
            courses = session.query(Course).filter(
                Course.course_name.contains(keyword)
            ).all()
            if not courses:
                return f"未找到包含「{keyword}」的课程。"
            lines = ["📚 查询结果："]
            for c in courses:
                lines.append(
                    f"- {c.course_code} {c.course_name} | {c.teacher} | "
                    f"{c.schedule} @ {c.classroom} | 容量 {c.enrolled_count}/{c.total_capacity}"
                )
            return "\n".join(lines)
        finally:
            session.close()

    async def enroll_course(self, student_id: str, course_id: int) -> str:
        """选课（带容量校验与行锁）"""
        if not self._db_session_factory:
            return "数据库未连接。"
        session = self._db_session_factory()
        try:
            # 行锁锁定课程行
            course = session.query(Course).filter(Course.id == course_id).with_for_update().first()
            if not course:
                return "课程不存在。"
            if course.enrolled_count >= course.total_capacity:
                return f"❌ 课程 {course.course_name} 已满（{course.enrolled_count}/{course.total_capacity}）。"

            existing = session.query(StudentCourse).filter(
                StudentCourse.student_id == student_id,
                StudentCourse.course_id == course_id,
            ).first()
            if existing:
                return "❌ 你已经选过这门课了，不能重复选课。"

            enrollment = StudentCourse(student_id=student_id, course_id=course_id)
            course.enrolled_count += 1
            session.add(enrollment)
            session.commit()
            return f"✅ 选课成功！{course.course_name} 剩余容量 {course.total_capacity - course.enrolled_count} 人。"
        except Exception as e:
            session.rollback()
            return f"❌ 选课失败：{str(e)}"
        finally:
            session.close()

    async def drop_course(self, student_id: str, course_id: int) -> str:
        """退课（先锁 Course，再锁 StudentCourse，防止死锁）"""
        if not self._db_session_factory:
            return "数据库未连接。"
        session = self._db_session_factory()
        try:
            # 先锁 Course（与 enroll_course 锁顺序一致）
            course = session.query(Course).filter(Course.id == course_id).with_for_update().first()
            if not course:
                return "课程不存在。"

            enrollment = session.query(StudentCourse).filter(
                StudentCourse.student_id == student_id,
                StudentCourse.course_id == course_id,
                StudentCourse.status == "enrolled",
            ).with_for_update().first()
            if not enrollment:
                return "未找到选课记录。"

            enrollment.status = "dropped"
            if course.enrolled_count > 0:
                course.enrolled_count -= 1

            session.commit()
            return f"✅ 退课成功。"
        except Exception as e:
            session.rollback()
            return f"❌ 退课失败：{str(e)}"
        finally:
            session.close()
