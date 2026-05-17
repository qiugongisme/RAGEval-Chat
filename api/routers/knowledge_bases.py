import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File
from langchain_community.chat_models import ChatTongyi
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel, Field
from pymilvus import CollectionSchema, DataType, FieldSchema, utility

from config import config
from src.loader import load_documents_from_paths
from src.splitter import FileSplitter
from src.utils import get_cached_embedder, MilvusUtils

SUPPORTS_HYBRID = {"BAAI/bge-m3"}

logger = logging.getLogger(__name__)

router = APIRouter()

KBS_FILE = os.path.join(config.DATA_DIR, "knowledge_bases.json")
UPLOAD_ROOT = os.path.join(config.DATA_DIR, "uploads")


# ─── Pydantic Models ────────────────────────────────────────────────


class SplitConfig(BaseModel):
    separators: List[str] = Field(default=["第\\S*条"], description="切分分隔符（支持正则）")
    chunk_size: int = Field(default=500, ge=1, description="分块大小")
    chunk_overlap: int = Field(default=100, ge=0, description="重叠大小")


class IndexConfig(BaseModel):
    dense_index_type: str = Field(default="IVF_FLAT", description="密集向量索引类型")
    dense_metric: str = Field(default="IP", description="密集向量度量标准")
    nlist: int = Field(default=100, ge=1, description="聚类数目（IVF 系列索引使用）")
    nprobe: int = Field(default=10, ge=1, description="查询时聚类数目")
    M: int = Field(default=16, ge=4, description="HNSW M 参数（仅 HNSW 索引使用）")
    efConstruction: int = Field(default=200, ge=8, description="HNSW efConstruction 参数（仅 HNSW 索引使用）")
    sparse_index_type: str = Field(default="SPARSE_INVERTED_INDEX", description="稀疏向量索引类型")
    sparse_metric: str = Field(default="IP", description="稀疏向量度量标准")


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., description="知识库名称")
    description: str = Field(default="", description="知识库描述")
    embedding_model: str = Field(default="BAAI/bge-base-zh-v1.5", description="嵌入模型名称")
    split_config: SplitConfig = Field(default_factory=SplitConfig, description="切分配置")
    index_config: IndexConfig = Field(default_factory=IndexConfig, description="索引配置")
    prompt_template: str = Field(default="", description="自定义提示词模板，含 {retrieve_context} 和 {question} 占位符")


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    embedding_model: Optional[str] = Field(None, description="嵌入模型名称")
    split_config: Optional[SplitConfig] = Field(None, description="切分配置")
    index_config: Optional[IndexConfig] = Field(None, description="索引配置")
    prompt_template: Optional[str] = Field(None, description="自定义提示词模板")


class FileItem(BaseModel):
    id: str
    filename: str
    path: str
    size: int
    type: str


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str
    embedding_model: str
    hybrid_search: bool
    status: str  # empty | processing | ready | failed
    split_config: SplitConfig
    index_config: IndexConfig
    files: List[FileItem]
    collection_name: str
    doc_count: int
    chunk_count: int
    error_message: str = ""
    prompt_template: str = ""
    created_at: str
    updated_at: str


class KnowledgeBaseSummary(BaseModel):
    id: str
    name: str
    description: str
    embedding_model: str
    hybrid_search: bool
    status: str
    split_config: SplitConfig
    index_config: IndexConfig
    collection_name: str
    doc_count: int
    chunk_count: int
    file_count: int = 0
    error_message: str = ""
    prompt_template: str = ""
    created_at: str


class UploadFileResponse(BaseModel):
    id: str
    filename: str
    path: str
    size: int
    type: str


# ─── JSON 读写 ───────────────────────────────────────────────────────


def _read_kbs() -> list:
    with open(KBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_kbs(kbs: list):
    with open(KBS_FILE, "w", encoding="utf-8") as f:
        json.dump(kbs, f, ensure_ascii=False, indent=2)


def _migrate_kb_record(record: dict) -> dict:
    """迁移旧记录：补全新字段默认值"""
    if "status" not in record:
        record["status"] = "ready" if record.get("doc_count", 0) > 0 else "empty"
    if "split_config" not in record:
        record["split_config"] = {
            "separators": ["第\\S*条"],
            "chunk_size": config.FILE_CHUNK_SIZE,
            "chunk_overlap": config.FILE_CHUNK_OVERLAP,
        }
    if "files" not in record:
        record["files"] = []
    if "error_message" not in record:
        record["error_message"] = ""
    if "updated_at" not in record:
        record["updated_at"] = record.get("created_at", "")
    if "prompt_template" not in record:
        record["prompt_template"] = ""
    if "index_config" not in record:
        record["index_config"] = {
            "dense_index_type": config.INDEX_TYPE,
            "dense_metric": config.METRIC_TYPE,
            "nlist": config.NLIST,
            "nprobe": config.NPROBE,
            "M": 16,
            "efConstruction": 200,
            "sparse_index_type": config.SPARSE_INDEX_TYPE,
            "sparse_metric": config.SPARSE_METRIC_TYPE,
        }
    return record


def _find_kb(kb_id: str) -> Optional[dict]:
    kbs = _read_kbs()
    for kb in kbs:
        if kb["id"] == kb_id:
            return _migrate_kb_record(kb)
    return None


def _save_kb(kb: dict):
    kbs = _read_kbs()
    for i, k in enumerate(kbs):
        if k["id"] == kb["id"]:
            kbs[i] = kb
            _write_kbs(kbs)
            return
    kbs.append(kb)
    _write_kbs(kbs)


def _get_kb_upload_dir(kb_id: str) -> str:
    return os.path.join(UPLOAD_ROOT, kb_id)


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md'}


# ─── KB CRUD ────────────────────────────────────────────────────────


@router.get("", response_model=List[KnowledgeBaseSummary])
async def list_knowledge_bases():
    """获取所有知识库列表"""
    kbs = _read_kbs()
    result = []
    for kb in kbs:
        record = _migrate_kb_record(kb)
        record["file_count"] = len(record.get("files", []))
        result.append(record)
    return result


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    return kb


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(kb: KnowledgeBaseCreate):
    """创建知识库（仅元数据，状态为 empty）"""
    kb_id = f"kb_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    is_hybrid = kb.embedding_model in SUPPORTS_HYBRID

    record = {
        "id": kb_id,
        "name": kb.name,
        "description": kb.description,
        "embedding_model": kb.embedding_model,
        "hybrid_search": is_hybrid,
        "status": "empty",
        "split_config": kb.split_config.model_dump(),
        "index_config": kb.index_config.model_dump(),
        "files": [],
        "collection_name": kb_id,
        "doc_count": 0,
        "chunk_count": 0,
        "error_message": "",
        "prompt_template": kb.prompt_template,
        "created_at": now,
        "updated_at": now,
    }

    kbs = _read_kbs()
    kbs.append(record)
    _write_kbs(kbs)

    logger.info(f"知识库创建成功: {kb_id} ({'混合' if is_hybrid else '稠密'}检索)")
    return record


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(kb_id: str, update: KnowledgeBaseUpdate):
    """更新知识库元数据或切分配置"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    if update.name is not None:
        kb["name"] = update.name
    if update.description is not None:
        kb["description"] = update.description
    if update.embedding_model is not None:
        kb["embedding_model"] = update.embedding_model
        kb["hybrid_search"] = update.embedding_model in SUPPORTS_HYBRID
    if update.split_config is not None:
        kb["split_config"] = update.split_config.model_dump()
    if update.index_config is not None:
        kb["index_config"] = update.index_config.model_dump()
    if update.prompt_template is not None:
        kb["prompt_template"] = update.prompt_template

    kb["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_kb(kb)
    return kb


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge_base(kb_id: str):
    """删除知识库（含 Milvus collection 和上传文件）"""
    kbs = _read_kbs()
    kb = next((k for k in kbs if k["id"] == kb_id), None)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    # 删除 Milvus collection
    try:
        # 建立连接后操作
        MilvusUtils()
        if utility.has_collection(kb["collection_name"]):
            utility.drop_collection(kb["collection_name"])
            logger.info(f"已删除 Milvus collection: {kb['collection_name']}")
    except Exception as e:
        logger.error(f"删除 Milvus collection 失败: {e}")

    # 删除上传文件目录
    upload_dir = _get_kb_upload_dir(kb_id)
    if os.path.isdir(upload_dir):
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)
        logger.info(f"已删除上传文件目录: {upload_dir}")

    # 删除记录
    kbs = [k for k in kbs if k["id"] != kb_id]
    _write_kbs(kbs)


# ─── 文件管理 ────────────────────────────────────────────────────────


@router.get("/{kb_id}/files", response_model=List[FileItem])
async def list_kb_files(kb_id: str):
    """获取知识库的文件列表"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    return kb.get("files", [])


@router.post("/{kb_id}/files", response_model=UploadFileResponse, status_code=201)
async def upload_kb_file(kb_id: str, file: UploadFile = File(...)):
    """上传文件到知识库"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    if not _allowed_file(file.filename):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.filename}，支持 pdf/docx/doc/pptx/ppt/txt/md")

    file_id = uuid.uuid4().hex[:8]
    upload_dir = _get_kb_upload_dir(kb_id)
    os.makedirs(upload_dir, exist_ok=True)

    save_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(upload_dir, save_name)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
    file_item = {
        "id": file_id,
        "filename": file.filename,
        "path": save_path,
        "size": len(content),
        "type": ext,
    }

    # 更新 KB 记录
    kb["files"].append(file_item)
    kb["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_kb(kb)

    logger.info(f"文件上传成功: {save_name} ({len(content)} bytes) -> KB {kb_id}")
    return file_item


@router.delete("/{kb_id}/files/{file_id}", status_code=204)
async def delete_kb_file(kb_id: str, file_id: str):
    """删除知识库中的文件"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    file_item = next((f for f in kb["files"] if f["id"] == file_id), None)
    if file_item is None:
        raise HTTPException(status_code=404, detail=f"文件 {file_id} 不存在")

    # 删除物理文件
    if os.path.isfile(file_item["path"]):
        os.remove(file_item["path"])
        logger.info(f"已删除文件: {file_item['path']}")

    # 更新 KB 记录
    kb["files"] = [f for f in kb["files"] if f["id"] != file_id]
    kb["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_kb(kb)


# ─── 提交处理（后台异步） ─────────────────────────────────────────────


processing_tasks = {}  # kb_id -> asyncio.Task


@router.post("/{kb_id}/submit", status_code=202)
async def submit_knowledge_base(kb_id: str):
    """提交知识库处理任务（异步）"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    if kb["status"] == "processing":
        raise HTTPException(status_code=400, detail="知识库正在处理中，请等待完成")

    if not kb["files"]:
        raise HTTPException(status_code=400, detail="知识库中没有文件，请先上传文档")

    # 异步处理
    task = asyncio.create_task(_process_kb(kb_id))
    processing_tasks[kb_id] = task

    # 立即更新状态
    kb["status"] = "processing"
    kb["error_message"] = ""
    kb["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_kb(kb)

    return {"message": "知识库处理任务已提交", "kb_id": kb_id, "status": "processing"}


@router.get("/{kb_id}/status")
async def get_kb_processing_status(kb_id: str):
    """获取知识库处理状态"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    return {
        "id": kb_id,
        "status": kb["status"],
        "error_message": kb.get("error_message", ""),
        "doc_count": kb.get("doc_count", 0),
        "chunk_count": kb.get("chunk_count", 0),
    }


# ─── 提示词生成 ──────────────────────────────────────────────────────


@router.post("/{kb_id}/generate-prompt")
async def generate_kb_prompt(kb_id: str):
    """根据知识库信息，使用 LLM 生成自定义提示词模板"""
    kb = _find_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")

    MODELS_FILE = os.path.join(config.DATA_DIR, "models.json")
    try:
        with open(MODELS_FILE, "r", encoding="utf-8") as f:
            models = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        models = []

    if not models:
        raise HTTPException(status_code=400, detail="没有可用模型，请先在模型管理中添加模型")

    model_config = models[0]
    file_names = [f["filename"] for f in kb.get("files", [])]
    file_list_str = "\n".join(f"- {name}" for name in file_names) if file_names else "（暂无文档）"

    meta_prompt = f"""你是一个提示词工程专家。请根据以下知识库信息，为该知识库的 RAG 问答系统生成一个高质量的提示词模板。

知识库名称：{kb['name']}
知识库描述：{kb.get('description', '无')}
已上传文档列表：
{file_list_str}

要求：
1. 提示词必须包含 {{retrieve_context}} 和 {{question}} 这两个占位符，分别代表检索到的文档上下文和用户的问题
2. 提示词要体现该知识库的领域专业性
3. 指导 AI 模型基于检索内容回答，不要凭空编造
4. 如果检索内容不足以回答问题，应明确说明
5. 使用中文，简洁明了
6. 直接返回提示词模板内容，不要包含额外说明、不要用代码块包裹

请生成提示词模板："""

    try:
        provider = model_config["provider"]
        model_name = model_config["model_name"]
        api_key = model_config.get("api_key", "")

        if provider == "deepseek":
            kwargs = {"model": model_name, "temperature": 0.3}
            if api_key:
                kwargs["api_key"] = api_key
            llm = ChatDeepSeek(**kwargs)
        elif provider == "qwen":
            kwargs = {"model": model_name, "temperature": 0.3}
            if api_key:
                kwargs["api_key"] = api_key
            llm = ChatTongyi(**kwargs)
        else:
            raise ValueError(f"不支持的模型提供商: {provider}")

        from langchain_core.output_parsers import StrOutputParser
        chain = StrOutputParser()
        response = llm.invoke(meta_prompt)
        prompt_template = response.content if hasattr(response, 'content') else str(response)
        prompt_template = prompt_template.strip()

        # 清理可能的代码块包裹
        if prompt_template.startswith("```"):
            lines = prompt_template.split("\n")
            # 去掉第一行 ```... 和最后一行 ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            prompt_template = "\n".join(lines).strip()

        return {"prompt_template": prompt_template}
    except Exception as e:
        logger.exception("生成提示词失败")
        raise HTTPException(status_code=500, detail=f"生成提示词失败: {str(e)}")


async def _process_kb(kb_id: str):
    """后台处理知识库：加载 → 切分 → 嵌入 → 建索引"""
    try:
        logger.info(f"开始处理知识库: {kb_id}")

        # 重新读取最新 KB 记录
        kb = _find_kb(kb_id)
        if kb is None:
            logger.error(f"知识库 {kb_id} 不存在")
            return

        file_paths = [f["path"] for f in kb["files"]]
        split_config = kb["split_config"]
        collection_name = kb["collection_name"]

        # 1. 加载文档
        logger.info(f"[{kb_id}] 加载 {len(file_paths)} 个文档...")
        documents = load_documents_from_paths(file_paths)
        if not documents:
            raise ValueError("没有成功加载任何文档，请检查文件格式")
        logger.info(f"[{kb_id}] 成功加载 {len(documents)} 个文档")

        # 2. 切分
        logger.info(f"[{kb_id}] 切分文档 (separators={split_config['separators']}, "
                     f"chunk_size={split_config['chunk_size']}, overlap={split_config['chunk_overlap']})")
        texts = FileSplitter(
            separators=split_config["separators"],
            chunk_size=split_config["chunk_size"],
            chunk_overlap=split_config["chunk_overlap"],
        ).split_documents(documents)
        logger.info(f"[{kb_id}] 切分为 {len(texts)} 个文本块")

        # 3. 嵌入
        milvus_util = MilvusUtils()

        # 5. 删除旧的 Milvus collection（如有）
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            logger.info(f"[{kb_id}] 已删除旧的 collection: {collection_name}")

        is_hybrid = kb.get("hybrid_search", False) and kb.get("embedding_model", "") in SUPPORTS_HYBRID
        idx_cfg = kb.get("index_config", {})

        if is_hybrid:
            logger.info(f"[{kb_id}] 混合检索模式: 使用 BGEM3 生成稠密+稀疏向量...")
            from milvus_model.hybrid import BGEM3EmbeddingFunction
            bgem3_ef = BGEM3EmbeddingFunction(
                use_fp16=config.BGEM3_USE_FP16,
                device=config.BGEM3_DEVICE,
            )
            raw_text = [text.page_content for text in texts]
            texts_embeddings = bgem3_ef(raw_text)
            logger.info(f"[{kb_id}] 向量生成完成，密集向量维度：{bgem3_ef.dim['dense']}")

            # 创建 hybrid collection
            logger.info(f"[{kb_id}] 创建 hybrid collection...")
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name=config.DENSE_VECTOR_FIELD, dtype=DataType.FLOAT_VECTOR, dim=bgem3_ef.dim["dense"]),
                FieldSchema(name=config.SPARSE_VECTOR_FIELD, dtype=DataType.SPARSE_FLOAT_VECTOR),
            ]
            schema = CollectionSchema(fields=fields, description=kb["name"])
            collection = milvus_util.create_collection(
                collection_name=collection_name,
                schema=schema,
                consistency_level=config.CONSISTENCY_LEVEL,
            )

            # 建索引（使用 index_config 中的参数）
            dense_type = idx_cfg.get("dense_index_type", config.INDEX_TYPE)
            if dense_type == "HNSW":
                dense_index_params = {
                    "index_type": "HNSW",
                    "metric_type": idx_cfg.get("dense_metric", config.METRIC_TYPE),
                    "params": {
                        "M": idx_cfg.get("M", 16),
                        "efConstruction": idx_cfg.get("efConstruction", 200),
                    },
                }
            else:
                dense_index_params = {
                    "index_type": dense_type,
                    "metric_type": idx_cfg.get("dense_metric", config.METRIC_TYPE),
                    "params": {"nlist": idx_cfg.get("nlist", config.NLIST)},
                }
            collection.create_index(config.DENSE_VECTOR_FIELD, dense_index_params)
            sparse_index_params = {
                "index_type": idx_cfg.get("sparse_index_type", config.SPARSE_INDEX_TYPE),
                "metric_type": idx_cfg.get("sparse_metric", config.SPARSE_METRIC_TYPE),
            }
            collection.create_index(config.SPARSE_VECTOR_FIELD, sparse_index_params)

            # 插入数据
            data = [
                raw_text,
                [text.metadata for text in texts],
                texts_embeddings["dense"],
                texts_embeddings["sparse"],
            ]
            collection.insert(data)
            logger.info(f"[{kb_id}] 已插入 {len(raw_text)} 条向量数据（混合检索）")
        else:
            logger.info(f"[{kb_id}] 稠密检索模式: 生成向量嵌入...")
            embeddings = get_cached_embedder()
            raw_text = [text.page_content for text in texts]
            vectors = embeddings.embed_documents(raw_text)
            vectors = np.array(vectors, dtype=np.float32)
            logger.info(f"[{kb_id}] 嵌入向量维度: {vectors.shape}")

            # 创建 dense-only collection
            logger.info(f"[{kb_id}] 创建 collection...")
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name=config.EMBEDDING_FIELD_NAME, dtype=DataType.FLOAT_VECTOR, dim=vectors.shape[1]),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields=fields, description=kb["name"])

            collection = milvus_util.create_collection(
                collection_name=collection_name,
                schema=schema,
            )

            # 插入数据
            data = [
                raw_text,
                vectors.tolist(),
                [text.metadata for text in texts],
            ]
            collection.insert(data)

            # 建索引（使用 index_config 中的参数）
            dense_type = idx_cfg.get("dense_index_type", config.INDEX_TYPE)
            if dense_type == "HNSW":
                index_params = {
                    "index_type": "HNSW",
                    "metric_type": idx_cfg.get("dense_metric", config.METRIC_TYPE),
                    "params": {
                        "M": idx_cfg.get("M", 16),
                        "efConstruction": idx_cfg.get("efConstruction", 200),
                    },
                }
            else:
                index_params = {
                    "index_type": dense_type,
                    "metric_type": idx_cfg.get("dense_metric", config.METRIC_TYPE),
                    "params": {"nlist": idx_cfg.get("nlist", config.NLIST)},
                }
            collection.create_index(config.EMBEDDING_FIELD_NAME, index_params)

        collection.load()
        logger.info(f"[{kb_id}] 索引构建完成")

        # 9. 更新 KB 记录
        kb = _find_kb(kb_id)
        if kb:
            kb["status"] = "ready"
            kb["doc_count"] = len(documents)
            kb["chunk_count"] = len(raw_text)
            kb["error_message"] = ""
            kb["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_kb(kb)
            logger.info(f"知识库 {kb_id} 处理完成: {len(documents)} 文档, {len(raw_text)} 块")

    except Exception as e:
        logger.exception(f"知识库 {kb_id} 处理失败")
        kb = _find_kb(kb_id)
        if kb:
            kb["status"] = "failed"
            kb["error_message"] = str(e)
            kb["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_kb(kb)
