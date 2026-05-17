import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config


def ensure_json_file(file_path: str, default_content: list):
    """确保 JSON 文件存在，不存在则创建"""
    path = Path(file_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_content, ensure_ascii=False, indent=2), encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 加载环境变量
    load_dotenv()

    # 确保数据目录和配置文件存在
    os.makedirs(config.DATA_DIR, exist_ok=True)
    ensure_json_file(os.path.join(config.DATA_DIR, "models.json"), [])
    ensure_json_file(os.path.join(config.DATA_DIR, "knowledge_bases.json"), [])
    ensure_json_file(os.path.join(config.DATA_DIR, "sessions.json"), [])

    yield


app = FastAPI(
    title="智能问答系统 API",
    description="国家金融监督管理总局政策法规 RAG 问答系统后端接口",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "nfra-rag-api"}


# 注册路由（延迟导入避免启动时的循环依赖）
from api.routers import models, knowledge_bases, chat, sessions, evaluation

app.include_router(models.router, prefix="/api/v1/models", tags=["模型管理"])
app.include_router(knowledge_bases.router, prefix="/api/v1/knowledge-bases", tags=["知识库管理"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["会话管理"])
app.include_router(evaluation.router, prefix="/api/v1", tags=["评估管理"])
