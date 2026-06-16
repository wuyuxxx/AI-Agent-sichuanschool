"""系统全局配置"""

import os
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ModelConfig:
    """模型端点配置"""
    mimo_endpoint: str = "https://api.xiaomimimo.com/v1/chat/completions"
    mimo_model: str = "mimo-v2.5"
    mimo_api_key: str = os.getenv("MIMO_API_KEY", "")
    deepseek_endpoint: str = "https://api.deepseek.com/v1/chat/completions"
    deepseek_model: str = "deepseek-chat"
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")


@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    db: int = 0
    session_ttl: int = 604800  # 7 天
    password: str = os.getenv("REDIS_PASSWORD", "")


@dataclass
class MySQLConfig:
    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQL_ROOT_PASSWORD", "root")
    database: str = os.getenv("MYSQL_DATABASE", "campus_agent")
    pool_size: int = 10


@dataclass
class ChromaConfig:
    policy_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policy_chroma")
    mental_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mental_chroma")
    embedding_model: str = "all-MiniLM-L6-v2"


@dataclass
class RAGConfig:
    """RAG 检索参数"""
    top_k: int = 5
    confidence_threshold: float = 0.10  # 轻量嵌入下调整，正式模型可恢复至 0.65
    rrf_k: int = 60  # RRF 排序常数
    bm25_k1: float = 1.5
    bm25_b: float = 0.75


@dataclass
class AffectiveConfig:
    """情感监控参数"""
    window_size: int = 3  # 近 N 轮对话恶化
    threshold: float = -0.3  # 情感得分持续下降阈值
    alert_negative_score: float = -0.5  # 触发预警的绝对负向阈值


@dataclass
class AppConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    mysql: MySQLConfig = field(default_factory=MySQLConfig)
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    affective: AffectiveConfig = field(default_factory=AffectiveConfig)

    # FastAPI
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])

    # Trie 高危词库路径
    crisis_keywords: List[str] = field(default_factory=lambda: [
        "自杀", "自残", "想死", "割腕", "吞药", "烧炭", "跳楼",
        "撑不下去了想解脱", "离开世界", "我的猫以后拜托你了",
        "游戏账号送人", "交代后事", "写了封信在桌上",
        "谢谢你这段时间的陪伴再见", "天台风很大", "顶楼看风景",
        "桥上看水很凉", "湖边散步不想回来", "走上顶楼",
        "如果我消失了会怎么样", "要是能像睡着一样再也不醒来就好了",
        "想彻底解脱",
    ])


config = AppConfig()
