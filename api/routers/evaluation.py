import asyncio
import json
import logging
import os
import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from config import config
from evaluation.runner import run_evaluation, load_test_set_from_xlsx
from evaluation.schemas import (
    EvalReport,
    EvalConfig,
    RetrievalStrategy,
    TestSet,
)

logger = logging.getLogger(__name__)

router = APIRouter()

EVALS_FILE = os.path.join(config.DATA_DIR, "evaluations.json")
TEST_SETS_FILE = os.path.join(config.DATA_DIR, "test_sets.json")
TEST_SETS_DIR = os.path.join(config.DATA_DIR, "test_sets")


# ─── JSON 文件读写 ───

_json_lock = threading.Lock()


def _read_json(filepath: str) -> list:
    with _json_lock:
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)


def _write_json(filepath: str, data: list):
    with _json_lock:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _find_eval(eval_id: str) -> Optional[dict]:
    evals = _read_json(EVALS_FILE)
    for e in evals:
        if e["id"] == eval_id:
            return e
    return None


def _save_eval(record: dict):
    evals = _read_json(EVALS_FILE)
    for i, e in enumerate(evals):
        if e["id"] == record["id"]:
            evals[i] = record
            _write_json(EVALS_FILE, evals)
            return
    evals.append(record)
    _write_json(EVALS_FILE, evals)


# ─── 正在运行的任务 ───

_running_tasks: dict = {}


# ─── 请求/响应模型 ───

class CreateEvalRequest(BaseModel):
    kb_id: str = Field(..., description="知识库 ID")
    test_set_id: str = Field(..., description="测试集 ID")
    strategy: RetrievalStrategy = Field(default=RetrievalStrategy.hybrid, description="检索策略")
    top_k: int = Field(default=3, ge=1, le=20, description="Top-K")


class EvalListResponse(BaseModel):
    id: str
    kb_id: str
    kb_name: str
    test_set_id: str
    test_set_name: str
    strategy: str
    top_k: int
    status: str
    metrics: dict
    progress_current: int = 0
    progress_total: int = 0
    created_at: str
    finished_at: str = ""


class TestSetResponse(BaseModel):
    id: str
    name: str
    description: str
    sheet_names: List[str]
    file_name: str
    count: int
    created_at: str


# ─── 测试集管理 ───

@router.get("/test-sets", response_model=List[TestSetResponse])
async def list_test_sets():
    """获取所有测试集"""
    records = _read_json(TEST_SETS_FILE)
    return records


@router.post("/test-sets/upload", response_model=TestSetResponse, status_code=201)
async def upload_test_set(file: UploadFile = File(...)):
    """上传 xlsx 测试集"""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    os.makedirs(TEST_SETS_DIR, exist_ok=True)
    ts_id = f"ts_{uuid.uuid4().hex[:8]}"

    # 保存文件
    save_name = f"{ts_id}_{file.filename}"
    save_path = os.path.join(TEST_SETS_DIR, save_name)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # 解析并统计
    test_set = load_test_set_from_xlsx(save_path)

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": ts_id,
        "name": os.path.splitext(file.filename)[0],
        "description": "",
        "sheet_names": test_set.sheet_names,
        "file_name": save_name,
        "file_path": save_path,
        "count": test_set.count,
        "created_at": now,
    }

    records = _read_json(TEST_SETS_FILE)
    records.append(record)
    _write_json(TEST_SETS_FILE, records)

    logger.info(f"测试集上传成功: {save_name} ({test_set.count} 条)")
    return record


@router.delete("/test-sets/{ts_id}", status_code=204)
async def delete_test_set(ts_id: str):
    """删除测试集"""
    records = _read_json(TEST_SETS_FILE)
    ts = next((r for r in records if r["id"] == ts_id), None)
    if ts is None:
        raise HTTPException(status_code=404, detail=f"测试集 {ts_id} 不存在")

    # 删除物理文件
    file_path = ts.get("file_path", "")
    if file_path and os.path.isfile(file_path):
        os.remove(file_path)

    records = [r for r in records if r["id"] != ts_id]
    _write_json(TEST_SETS_FILE, records)


# ─── 评估运行 ───

@router.post("/evaluations", status_code=201)
async def create_evaluation(req: CreateEvalRequest):
    """创建并启动评估任务（异步）"""
    # 验证知识库
    kbs = _read_json(os.path.join(config.DATA_DIR, "knowledge_bases.json"))
    kb = next((k for k in kbs if k["id"] == req.kb_id), None)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"知识库 {req.kb_id} 不存在")

    # 验证测试集
    test_sets = _read_json(TEST_SETS_FILE)
    ts = next((t for t in test_sets if t["id"] == req.test_set_id), None)
    if ts is None:
        raise HTTPException(status_code=404, detail=f"测试集 {req.test_set_id} 不存在")

    # 创建评估记录
    eval_id = f"eval_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": eval_id,
        "kb_id": req.kb_id,
        "kb_name": kb.get("name", ""),
        "test_set_id": req.test_set_id,
        "test_set_name": ts.get("name", ""),
        "strategy": req.strategy.value,
        "top_k": req.top_k,
        "status": "running",
        "collection_name": kb.get("collection_name", ""),
        "metrics": {"total": 0, "hit_count": 0, "recall": 0.0, "mrr": 0.0},
        "details": [],
        "error_message": "",
        "progress_current": 0,
        "progress_total": ts.get("count", 0),
        "created_at": now,
        "finished_at": "",
    }
    _save_eval(record)

    # 放入独立线程执行，避免阻塞 asyncio 事件循环
    task = asyncio.create_task(asyncio.to_thread(_run_eval_sync, eval_id, req, kb, ts))
    _running_tasks[eval_id] = task

    return {"id": eval_id, "status": "running"}


@router.get("/evaluations", response_model=List[EvalListResponse])
async def list_evaluations():
    """获取历史评估列表"""
    evals = _read_json(EVALS_FILE)
    # 按创建时间倒序
    evals.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return evals


@router.get("/evaluations/{eval_id}")
async def get_evaluation(eval_id: str):
    """获取评估报告详情"""
    record = _find_eval(eval_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"评估 {eval_id} 不存在")
    return record


@router.delete("/evaluations/{eval_id}", status_code=204)
async def delete_evaluation(eval_id: str):
    """删除评估记录"""
    evals = _read_json(EVALS_FILE)
    filtered = [e for e in evals if e["id"] != eval_id]
    if len(filtered) == len(evals):
        raise HTTPException(status_code=404, detail=f"评估 {eval_id} 不存在")
    _write_json(EVALS_FILE, filtered)


@router.get("/evaluations/{eval_id}/compare/{eval_id2}")
async def compare_evaluations(eval_id: str, eval_id2: str):
    """对比两次评估结果"""
    e1 = _find_eval(eval_id)
    e2 = _find_eval(eval_id2)
    if e1 is None:
        raise HTTPException(status_code=404, detail=f"评估 {eval_id} 不存在")
    if e2 is None:
        raise HTTPException(status_code=404, detail=f"评估 {eval_id2} 不存在")
    return {"eval_1": e1, "eval_2": e2}


# ─── 异步执行任务 ───

def _run_eval_sync(eval_id: str, req: CreateEvalRequest, kb: dict, ts: dict):
    """后台执行评估（独立线程，不阻塞 asyncio 事件循环）"""
    try:
        # 加载测试集
        file_path = ts.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            raise ValueError(f"测试集文件不存在: {file_path}")

        test_set = load_test_set_from_xlsx(file_path)
        test_set.id = ts["id"]
        test_set.name = ts.get("name", "")

        # 进度回调：每次处理一条题目时更新 JSON 记录
        def progress_callback(current: int, total: int):
            record = _find_eval(eval_id)
            if record:
                record["progress_current"] = current
                record["progress_total"] = total
                _save_eval(record)

        # 构建配置并执行
        eval_config = EvalConfig(
            kb_id=req.kb_id,
            test_set_id=req.test_set_id,
            strategy=req.strategy,
            top_k=req.top_k,
        )
        report = run_evaluation(
            eval_config=eval_config,
            test_set=test_set,
            kb_name=kb.get("name", ""),
            collection_name=kb.get("collection_name", ""),
            progress_callback=progress_callback,
        )

        # 更新到数据库
        now = datetime.now(timezone.utc).isoformat()
        record = _find_eval(eval_id)
        if record:
            record["status"] = report.status
            record["metrics"] = report.metrics.model_dump()
            record["details"] = [d.model_dump() for d in report.details]
            record["error_message"] = report.error_message
            record["progress_current"] = report.metrics.total
            record["progress_total"] = report.metrics.total
            record["finished_at"] = now
            _save_eval(record)

        logger.info(f"评估 {eval_id} 完成，状态={report.status}")

    except Exception:
        logger.exception(f"评估 {eval_id} 异常")
        now = datetime.now(timezone.utc).isoformat()
        record = _find_eval(eval_id)
        if record:
            record["status"] = "failed"
            record["error_message"] = traceback.format_exc()
            record["finished_at"] = now
            _save_eval(record)
    finally:
        _running_tasks.pop(eval_id, None)
