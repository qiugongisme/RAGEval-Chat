# CLAUDE.md

## Project
RAGEval-Chat — 基于 RAG 技术的智能问答与检索质量评估系统。

## Tech Stack
- **Backend**: Python 3.12 + FastAPI
- **Frontend**: Vue 3 + Naive UI + Vite
- **Vector DB**: Milvus 2.5.4 (混合检索: dense + sparse, BGEM3, RRF 融合)
- **LLM**: DeepSeek / 通义千问
- **RAG**: LangChain 0.3.17
- **Deploy**: Docker Compose

## Commands

### Backend
```bash
# 启动开发服务器（热重载）
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 启动生产
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install     # 首次或新增依赖时
npm run dev     # 开发模式 (Vite HMR)
```

### Docker
```bash
docker compose up -d    # 启动全部服务 (Milvus + 后端 + 前端)
docker compose down     # 停止
docker compose logs -f  # 查看日志
```

### RAG 初始化
```bash
# 初始化 Milvus + 混合检索（首次部署后执行）
python application.py -b

# CLI 问答模式（不启动 web）
python application.py -s
```

### 依赖管理
```bash
pip install -r requirements.txt     # Python 依赖
cd frontend && npm install          # 前端依赖
```

## Project Structure
```
api/            — FastAPI 路由层
  main.py       — 应用入口, lifespan, CORS, 路由注册
  routers/      — chat.py, knowledge_bases.py, models.py, sessions.py
src/            — RAG 核心逻辑
  loader.py     — PDF/DOCX 文档加载
  splitter.py   — 文本分块
  chain.py      — QA Chain + HyDE Chain
  retriever.py  — Milvus 检索器（稠密/混合）
  prompt.py     — 提示词模板
  re_rank.py    — 重排序
  callback.py   — 流式输出回调
  utils.py      — Milvus 工具类 + 嵌入缓存
frontend/       — Vue 3 前端
  src/views/    — Chat.vue, KnowledgeBase.vue, KBDetail.vue, Layout.vue, ModelManage.vue
  src/api/      — API 封装
config.py       — 全局配置（分块、嵌入、索引、检索参数）
application.py  — CLI 入口（初始化 Milvus + 问答）
```

## Key Config (config.py)
- Chunk: 500 tokens, overlap 100
- Embed: BAAI/bge-base-zh-v1.5 (cpu)
- Search: hybrid (dense + sparse), RRF rerank
- Collection: RAG_PART_NFRA_HYBRID

## Coding Conventions
- Python: 函数/方法名 snake_case, 类名 PascalCase
- Vue: Options API 风格, 文件名 PascalCase
- API 路由: `/api/v1/{resource}`, RESTful
- 配置文件集中管理: 所有魔数/参数放 config.py，不散落在业务代码中
