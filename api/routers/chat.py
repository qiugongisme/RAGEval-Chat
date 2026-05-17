import asyncio
import json
import logging
import os
from operator import itemgetter
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap
from langchain_community.chat_models import ChatTongyi
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel, Field

from config import config
from src.callback import OutCallbackHandler
from src.prompt import QUERY_PROMPT, GENERAL_CHAT_PROMPT
from src.retriever import MilvusRetriever, retrieved_deal

logger = logging.getLogger(__name__)

router = APIRouter()

# 加载环境变量（确保 API Keys 可用）
load_dotenv()

MODELS_FILE = os.path.join(config.DATA_DIR, "models.json")
KBS_FILE = os.path.join(config.DATA_DIR, "knowledge_bases.json")


def _read_json(filepath: str) -> list:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    model_id: str = Field(..., description="使用的模型 ID")
    kb_id: Optional[str] = Field(default=None, description="知识库 ID，不传则走通用对话")


def _create_model(provider: str, model_name: str, callbacks: list, api_key: str = ""):
    """根据提供商创建对应的 LangChain 模型实例"""
    if provider == "deepseek":
        kwargs = {"model": model_name, "streaming": True, "callbacks": callbacks}
        if api_key:
            kwargs["api_key"] = api_key
        return ChatDeepSeek(**kwargs)
    elif provider == "qwen":
        kwargs = {"model": model_name, "streaming": True, "callbacks": callbacks}
        if api_key:
            kwargs["api_key"] = api_key
        return ChatTongyi(**kwargs)
    else:
        raise ValueError(f"不支持的模型提供商: {provider}")


def _hits_to_chunks(hits: list) -> list[dict]:
    """将 Milvus Hits 转为可序列化的 chunk 字典列表"""
    chunks = []
    for hit in hits:
        text = hit.entity.get('text', '')
        metadata = hit.entity.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        source = metadata.get('source', '未知来源') if isinstance(metadata, dict) else str(metadata)
        chunks.append({
            "source": source,
            "text": text if text else '',
            "score": round(hit.distance, 4) if hasattr(hit, 'distance') else 0,
        })
    return chunks


async def _stream_events(request: ChatRequest) -> AsyncGenerator[str, None]:
    """生成 SSE 事件流"""
    try:
        # 1. 加载模型配置
        models = _read_json(MODELS_FILE)

        model_config = next((m for m in models if m["id"] == request.model_id), None)
        if model_config is None:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': f'模型 {request.model_id} 不存在'})}\n\n"
            return

        callback = OutCallbackHandler()
        model = _create_model(model_config["provider"], model_config["model_name"], [callback], model_config.get("api_key", ""))

        # 2. 分支：有知识库 → RAG 检索，无知识库 → 通用对话
        if request.kb_id:
            kbs = _read_json(KBS_FILE)
            kb = next((k for k in kbs if k["id"] == request.kb_id), None)
            if kb is None:
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': f'知识库 {request.kb_id} 不存在'})}\n\n"
                return

            idx_cfg = kb.get("index_config", {})
            retriever = MilvusRetriever(
                search_type="dense",
                collection_name=kb["collection_name"],
                nprobe=idx_cfg.get("nprobe"),
            )

            # 使用知识库自定义提示词，未设置则用默认 QUERY_PROMPT
            kb_prompt_template = kb.get("prompt_template", "").strip()
            if kb_prompt_template:
                prompt = PromptTemplate(
                    template=kb_prompt_template,
                    input_variables=["retrieve_context", "question"],
                )
            else:
                prompt = QUERY_PROMPT

            chain = (
                RunnableMap({
                    "retrieve_docs": itemgetter("question") | retriever,
                    "question": lambda x: x["question"],
                })
                | RunnableMap({
                    "retrieve_context": lambda x: retrieved_deal(x["retrieve_docs"]),
                    "retrieve_chunks": lambda x: _hits_to_chunks(x["retrieve_docs"]),
                    "question": lambda x: x["question"],
                })
                | RunnableMap({
                    "retrieve_context": lambda x: x["retrieve_context"],
                    "retrieve_chunks": lambda x: x["retrieve_chunks"],
                    "prompt": prompt,
                })
                | RunnableMap({
                    "retrieve_context": lambda x: x["retrieve_context"],
                    "retrieve_chunks": lambda x: x["retrieve_chunks"],
                    "answer": itemgetter("prompt") | model | StrOutputParser(),
                })
            )

            task = asyncio.create_task(chain.ainvoke({"question": request.question}))

            async for token in callback.aiter():
                yield f"event: token\ndata: {json.dumps({'type': 'token', 'token': token})}\n\n"

            result = await task

            yield (
                f"event: done\n"
                f"data: {json.dumps({
                    'type': 'done',
                    'answer': result['answer'],
                    'context': result['retrieve_context'],
                    'chunks': result.get('retrieve_chunks', []),
                }, ensure_ascii=False)}\n\n"
            )
        else:
            # 通用对话：不检索，直接调用模型
            chain = (
                RunnableMap({
                    "question": lambda x: x["question"],
                    "prompt": GENERAL_CHAT_PROMPT,
                })
                | RunnableMap({
                    "answer": itemgetter("prompt") | model | StrOutputParser(),
                })
            )

            task = asyncio.create_task(chain.ainvoke({"question": request.question}))

            async for token in callback.aiter():
                yield f"event: token\ndata: {json.dumps({'type': 'token', 'token': token})}\n\n"

            result = await task

            yield (
                f"event: done\n"
                f"data: {json.dumps({
                    'type': 'done',
                    'answer': result.get('answer', ''),
                    'context': '',
                }, ensure_ascii=False)}\n\n"
            )

    except ValueError as e:
        yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    except Exception as e:
        logger.exception("Chat stream 处理异常")
        yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': f'服务器内部错误: {str(e)}'})}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式对话：用户提问 → 检索知识库 → LLM 生成 → SSE 逐 token 返回"""
    return StreamingResponse(
        _stream_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
