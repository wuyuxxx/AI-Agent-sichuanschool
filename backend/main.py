"""FastAPI 主入口 — 校园自适应多智能体系统"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.config import config
from backend.core.trie_filter import CrisisTrieFilter
from backend.core.session_memory import SessionMemory
from backend.core.rag_pipeline import RAGPipeline
from backend.core.affective_guardrail import AffectiveGuardrail
from backend.agents.router_agent import IntentRouter
from backend.agents.mental_health_agent import MentalHealthExpert
from backend.agents.academic_exec_agent import AcademicExecutive
from backend.agents.policy_audit_agent import PolicyAuditor
from backend.agents.shadow_evaluator_agent import ShadowEvaluator
from backend.api.routes import router as api_router
from backend.db.mysql_models import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
# 压制 httpx 请求日志噪音
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------
# 全局组件引用
# ----------------------------------------------------------------
db_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global db_session_factory

    logger.info("🚀 校园自适应多智能体系统启动中...")

    # 1. 初始化 MySQL
    try:
        mysql_dsn = (
            f"mysql+pymysql://{config.mysql.user}:{config.mysql.password}"
            f"@{config.mysql.host}:{config.mysql.port}/{config.mysql.database}"
            f"?charset=utf8mb4"
        )
        engine = create_engine(mysql_dsn, pool_size=config.mysql.pool_size, max_overflow=5)
        init_db(engine)
        db_session_factory = sessionmaker(bind=engine)
        logger.info("✅ MySQL 连接成功")
    except Exception as e:
        logger.warning(f"⚠️ MySQL 连接失败（可后续重试）: {e}")
        db_session_factory = None

    # 2. 初始化 Redis
    session_mem = SessionMemory(config.redis)
    try:
        await session_mem.connect()
        app.state.session_memory = session_mem
        logger.info("✅ Redis 连接成功")
    except Exception as e:
        logger.warning(f"⚠️ Redis 连接失败（可使用本地回退）: {e}")
        app.state.session_memory = session_mem

    # 3. 初始化 Trie 危机过滤
    trie = CrisisTrieFilter(config.crisis_keywords)
    app.state.trie_filter = trie
    logger.info("✅ Trie 危机过滤引擎就绪")

    # 4. 初始化情感监控
    affective = AffectiveGuardrail(config.affective)
    app.state.affective_guardrail = affective
    logger.info("✅ 情感监控引擎就绪")

    # 5. 初始化 RAG 流水线
    rag = RAGPipeline(config.rag, config.chroma)
    app.state.rag_pipeline = rag
    logger.info("✅ RAG 流水线就绪")

    # 6. 初始化智能体
    app.state.router_agent = IntentRouter(
        name="IntentRouter",
        model_endpoint=config.model.mimo_endpoint,
        model_name=config.model.mimo_model,
        api_key=config.model.mimo_api_key,
    )
    app.state.mental_agent = MentalHealthExpert(
        name="MentalHealthExpert",
        model_endpoint=config.model.mimo_endpoint,
        model_name=config.model.mimo_model,
        api_key=config.model.mimo_api_key,
    )
    app.state.academic_agent = AcademicExecutive(
        name="AcademicExecutive",
        model_endpoint=config.model.deepseek_endpoint,
        model_name=config.model.deepseek_model,
        api_key=config.model.deepseek_api_key,
        db_session_factory=db_session_factory,
    )
    app.state.policy_agent = PolicyAuditor(
        name="PolicyAuditor",
        model_endpoint=config.model.deepseek_endpoint,
        model_name=config.model.deepseek_model,
        api_key=config.model.deepseek_api_key,
        rag_pipeline=rag,
    )
    app.state.shadow_agent = ShadowEvaluator(
        name="ShadowEvaluator",
        model_endpoint=config.model.deepseek_endpoint,
        model_name=config.model.deepseek_model,
        api_key=config.model.deepseek_api_key,
        db_session_factory=db_session_factory,
    )
    logger.info("✅ 多智能体系统就绪")

    # 注入到 routes
    import backend.api.routes as routes
    routes.trie_filter = trie
    routes.session_memory = session_mem
    routes.affective_guardrail = affective
    routes.rag_pipeline = rag
    routes.router_agent = app.state.router_agent
    routes.mental_agent = app.state.mental_agent
    routes.academic_agent = app.state.academic_agent
    routes.policy_agent = app.state.policy_agent

    logger.info(f"🎯 系统启动完成！监听端口 {config.port}")
    yield

    # 关闭
    await session_mem.close()
    logger.info("系统已关闭")


# ----------------------------------------------------------------
# FastAPI 应用
# ----------------------------------------------------------------
app = FastAPI(
    title="校园自适应多智能体系统（Autonomous Adaptive Campus Agent Hub）",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（必须在静态文件挂载之前）
app.include_router(api_router, prefix="/api/v1")

# 前端静态文件服务
import os
_frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
logger.info(f"前端目录: {_frontend_dir} (存在={os.path.isdir(_frontend_dir)})")

if os.path.isdir(_frontend_dir):
    # 保持与 HTML 中相对路径一致
    app.mount("/css", StaticFiles(directory=os.path.join(_frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(_frontend_dir, "js")), name="js")

# 根路径返回 index.html（始终注册）
@app.get("/")
async def serve_frontend():
    idx = os.path.join(_frontend_dir, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return {"error": "frontend not found"}

@app.get("/index.html")
async def serve_frontend_index():
    idx = os.path.join(_frontend_dir, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return {"error": "frontend not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=config.host, port=config.port, reload=False)
