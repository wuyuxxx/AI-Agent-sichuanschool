智汇工商 —— 校园自适应多智能体系统
校园政策问答与心理危机干预助手。多 Agent 路由 + RAG 检索 + 情感护栏。

架构
用户 → 前端(SSE) → Router Agent
                     ├→ Academic Exec Agent   (学业事务)
                     ├→ Mental Health Agent   (心理支持)
                     ├→ Policy Audit Agent    (政策查询)
                     └→ Shadow Evaluator      (质量评估)
技术栈
后端: Python 3.8+ / FastAPI / SSE 流式
前端: HTML5 + CSS3 + Vanilla JS
数据库: MySQL 8.x + Redis 7.x
向量检索: ChromaDB + sentence-transformers + BM25 混合排序
AI 模型: DeepSeek Chat / Mimo V2.5 (OpenAI 兼容)
快速开始
# 1. 安装依赖
cd backend && pip install -r requirements.txt

# 2. 设置环境变量
export MIMO_API_KEY="sk-xxx"
export DEEPSEEK_API_KEY="sk-xxx"
export MYSQL_ROOT_PASSWORD="root"

# 3. 初始化向量库
python -m backend.db.seed_chroma

# 4. 启动
uvicorn backend.main:app --host 0.0.0.0 --port 8000
前端直接浏览器打开 frontend/index.html 即可。

核心功能
模块	说明
学业 Agent	培养方案、选课、成绩、竞赛事务
心理 Agent	共情对话 + SCL-90 量表评估
政策 Agent	RAG 检索校规政策，含引用溯源
情感护栏	多轮情感恶化检测，高危熔断直连心理中心
敏感词过滤	Trie 树实时拦截 + 危机降级接管
