"""SQLAlchemy MySQL 数据模型"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Student(Base):
    """学籍表"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), unique=True, nullable=False, comment="学号")
    name = Column(String(50), nullable=False, comment="姓名")
    major = Column(String(100), nullable=False, comment="专业")
    grade = Column(String(10), nullable=False, comment="年级，如 2023")
    gpa = Column(Float, default=0.0, comment="当前绩点")
    total_credits = Column(Float, default=0.0, comment="总修学分")

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Student {self.student_id} {self.name}>"


class Course(Base):
    """课程排课表"""
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_code = Column(String(20), unique=True, nullable=False, comment="课程代码")
    course_name = Column(String(100), nullable=False, comment="课程名")
    teacher = Column(String(50), nullable=False, comment="任课教师")
    schedule = Column(String(100), nullable=False, comment="上课时间")
    classroom = Column(String(50), nullable=False, comment="上课教室")
    total_capacity = Column(Integer, nullable=False, comment="总容量")
    enrolled_count = Column(Integer, default=0, comment="已选人数")

    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def available_slots(self) -> int:
        return self.total_capacity - self.enrolled_count

    def __repr__(self):
        return f"<Course {self.course_code} {self.course_name}>"


class StudentCourse(Base):
    """选课流水表"""
    __tablename__ = "student_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey("students.student_id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    status = Column(String(20), default="enrolled", comment="状态: enrolled/dropped/completed")

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course"),
        Index("idx_student", "student_id"),
        Index("idx_course", "course_id"),
    )

    student = relationship("Student", backref="enrollments")
    course = relationship("Course", backref="enrollments")


class AgentFailure(Base):
    """失败案例审计表 — 用于深夜反思引擎"""
    __tablename__ = "agent_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, comment="会话ID")
    user_query = Column(Text, nullable=False, comment="用户原话")
    ai_response = Column(Text, nullable=False, comment="AI回复")
    failure_type = Column(
        String(30), nullable=False,
        comment="失败分类: RAG_BLIND / POOR_EXPERIENCE / EMOTION_ALERT",
    )
    failure_detail = Column(Text, nullable=True, comment="失败详情")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_session", "session_id"),
        Index("idx_failure_type", "failure_type"),
    )


class AdaptiveGuide(Base):
    """动态少样本提示词增强表"""
    __tablename__ = "adaptive_guides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_keywords = Column(String(200), nullable=False, comment="场景关键词")
    guide_text = Column(Text, nullable=False, comment="金牌话术指南 / Few-Shot 示例")
    agent_role = Column(String(30), nullable=False, comment="目标智能体角色")
    is_active = Column(Integer, default=1, comment="是否启用")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db(engine):
    """初始化所有表"""
    Base.metadata.create_all(engine)
