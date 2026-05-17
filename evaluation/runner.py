"""评估执行引擎：统一调度不同检索策略并计算指标"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

# 抑制 HuggingFace 模型加载的进度条和 tokenizer 噪音
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import pandas as pd
from pymilvus import Collection

from config import config
from evaluation.metrics import compute_metrics
from evaluation.schemas import (
    EvalConfig,
    EvalItemResult,
    EvalReport,
    TestSet,
    TestSetItem,
    RetrievalStrategy,
)
from src.retriever import (
    MilvusRetriever,
    milvus_hybrid_retrieve,
)
from src.utils import MilvusUtils, get_cached_embedder

logger = logging.getLogger(__name__)


# ─── 测试集加载 ───

def load_test_set_from_xlsx(file_path: str) -> TestSet:
    """从 xlsx 文件加载测试集（支持多 sheet，格式：问题 | 答案 | 来源）"""
    xl = pd.ExcelFile(file_path)
    sheet_names = xl.sheet_names
    all_items: List[TestSetItem] = []

    for sheet_name in sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        cols = df.columns
        q_col, a_col, s_col = cols[0], cols[1] if len(cols) > 1 else "", cols[2] if len(cols) > 2 else ""

        for _, row in df.iterrows():
            question = str(row[q_col]).strip() if pd.notna(row[q_col]) else ""
            answer = str(row[a_col]).strip() if a_col and pd.notna(row[a_col]) else ""
            source = str(row[s_col]).strip() if s_col and pd.notna(row[s_col]) else ""
            if not question:
                continue
            all_items.append(TestSetItem(question=question, answer=answer, source=source))

    return TestSet(
        id="",
        name="",
        items=all_items,
        sheet_names=sheet_names,
        count=len(all_items),
    )


# ─── 条款提取（复用现有逻辑） ───

def _extract_tiao(text: str) -> str:
    """提取第一个 '第X条' 模式"""
    m = re.search(r"第\S*条", text)
    return m.group() if m else ""


def _extract_tiao_list(text: str) -> set:
    """提取所有 '第X条' 模式"""
    return set(re.findall(r"第(?:[一二三四五六七八九]?[千百十]?[百十]?[一二三四五六七八九]?|十)条", text))


# ─── 检测 collection 是否支持 hybrid ───

def _collection_has_hybrid_fields(collection: Collection | None) -> bool:
    """检查 collection 是否有 dense_vector / sparse_vector 字段"""
    if collection is None:
        return False
    try:
        schema = collection.schema
        field_names = [f.name for f in schema.fields]
        return "dense_vector" in field_names and "sparse_vector" in field_names
    except Exception:
        return False


# ─── 单个问题的检索与判定 ───

def _eval_single_question(
    question: str,
    item: TestSetItem,
    retriever: MilvusRetriever,
    collection: Collection | None,
    strategy: RetrievalStrategy,
    top_k: int,
) -> EvalItemResult:
    """对单个问题进行检索并判定是否命中"""
    expected_source = item.source.strip()
    expected_tiao = _extract_tiao(expected_source)

    actual_strategy = strategy
    if strategy == RetrievalStrategy.hybrid and not _collection_has_hybrid_fields(collection or retriever.collection):
        logger.warning("collection 不支持 hybrid 检索（缺少 dense_vector/sparse_vector 字段），降级为 dense")
        actual_strategy = RetrievalStrategy.dense
        # 同步更新 retriever 内部状态，避免 _get_relevant_documents 仍走 hybrid 分支
        retriever.search_type = "dense"
        if not retriever.embedder:
            retriever.embedder = get_cached_embedder("." + config.EMBEDDINGS_CACHE_PATH)

    if actual_strategy == RetrievalStrategy.hybrid:
        # 复用 retriever 初始化时已创建的 bgem3_ef，避免每题重复加载模型
        hits = milvus_hybrid_retrieve(
            collection=collection or retriever.collection,
            bgem3_ef=retriever.bgem3_ef,
            query=question,
            k=top_k,
            nprobe=retriever.nprobe,
        )
    else:
        hits = retriever._get_relevant_documents(question, run_manager=None)

    # 遍历结果判定
    for rank, hit in enumerate(hits, start=1):
        chunk_text = hit.entity.get("text") if hasattr(hit, "entity") else getattr(hit, "text", "")
        chunk_tiaos = _extract_tiao_list(str(chunk_text))

        if expected_tiao and expected_tiao in chunk_tiaos:
            return EvalItemResult(
                question=question,
                expected_source=expected_source,
                expected_answer=item.answer,
                hit=True,
                rank=rank,
                matched_chunk=chunk_text[:120],
                score=round(float(hit.distance), 4) if hasattr(hit, "distance") else 0.0,
            )

    # 未命中
    return EvalItemResult(
        question=question,
        expected_source=expected_source,
        expected_answer=item.answer,
        hit=False,
    )


# ─── 评估执行入口 ───

def run_evaluation(
    eval_config: EvalConfig,
    test_set: TestSet,
    kb_name: str = "",
    collection_name: str = "",
    progress_callback=None,
) -> EvalReport:
    """执行一次完整的评估流程"""
    report = EvalReport(
        id="",
        kb_id=eval_config.kb_id,
        kb_name=kb_name,
        test_set_id=eval_config.test_set_id,
        test_set_name=test_set.name,
        strategy=eval_config.strategy.value,
        top_k=eval_config.top_k,
        status="running",
        collection_name=collection_name,
    )

    try:
        logger.info(
            f"开始评估: kb={eval_config.kb_id}, "
            f"strategy={eval_config.strategy.value}, top_k={eval_config.top_k}, "
            f"questions={test_set.count}"
        )

        # 初始化检索器
        retriever = MilvusRetriever(
            search_type=eval_config.strategy.value,
            collection_name=collection_name,
        )

        # 混合检索需要额外的 collection 引用
        collection = None
        if eval_config.strategy == RetrievalStrategy.hybrid:
            milvus_util = MilvusUtils()
            collection = milvus_util.get_collection(collection_name)

        # 逐条评估
        details: List[EvalItemResult] = []
        processed = 0
        total = test_set.count
        for item in test_set.items:
            if not item.question.strip():
                continue
            processed += 1
            if progress_callback:
                progress_callback(processed, total)
            result = _eval_single_question(
                question=item.question,
                item=item,
                retriever=retriever,
                collection=collection,
                strategy=eval_config.strategy,
                top_k=eval_config.top_k,
            )
            details.append(result)

        # 计算指标
        metrics = compute_metrics(details, top_k=eval_config.top_k)
        report.metrics = metrics
        report.details = details
        report.status = "done"

        logger.info(
            f"评估完成: recall={metrics.recall:.2%}, "
            f"mrr={metrics.mrr:.4f}, "
            f"hit={metrics.hit_count}/{metrics.total}"
        )

    except Exception as e:
        logger.exception("评估执行异常")
        report.status = "failed"
        report.error_message = str(e)

    return report
