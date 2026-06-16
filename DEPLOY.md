# 智汇工商 · 校园自适应多智能体系统 部署文档

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | HTML5 + CSS3 + Vanilla JS (SSE 流式) |
| 后端 | Python 3.8+ / FastAPI + Uvicorn |
| 数据库 | MySQL 8.x + Redis 7.x |
| 向量库 | ChromaDB + sentence-transformers |
| AI 模型 | DeepSeek Chat / Mimo V2.5 (OpenAI 兼容) |

## 快速启动

### 1. 配置环境变量

```bash
# 后端配置（建议写入 .env 或 export，不要硬编码）
export MIMO_API_KEY="sk-xxx"
export DEEPSEEK_API_KEY="sk-xxx"
export MYSQL_HOST="localhost"
export MYSQL_ROOT_PASSWORD="root"
export REDIS_HOST="localhost"
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 初始化向量库

```bash
python -m backend.db.seed_chroma
```

### 4. 启动

```bash
# 后端
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 前端（直接浏览器打开或 Nginx 托管）
open frontend/index.html
```

## 核心模块

| 模块 | 路径 | 功能 |
|------|------|------|
| 路由分发 | `backend/api/routes.py` | FastAPI 端点，SSE 流式聊天 |
| 多 Agent | `backend/agents/` | 学业/心理/政策/路由/影子评估 Agent |
| 情感护栏 | `backend/core/affective_guardrail.py` | 多轮情感恶化检测、危机熔断 |
| 敏感词过滤 | `backend/core/trie_filter.py` | 基于 Trie 树的高危词实时拦截 |
| RAG 检索 | `backend/core/rag_pipeline.py` | BM25 + 向量检索 RRf 融合排序 |
| 会话记忆 | `backend/core/session_memory.py` | Redis 存储对话上下文 |

## 安全注意

- API Key 通过**环境变量**注入，勿提交硬编码密钥
- 情感护栏支持 Webhook 推送心理中心告警
- 敏感词库替换为数据库/配置驱动，勿硬编码在源码中
