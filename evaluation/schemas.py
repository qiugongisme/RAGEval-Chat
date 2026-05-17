from __future__ import annotations

import enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ─── 检索策略枚举 ───

class RetrievalStrategy(str, enum.Enum):
    dense = "dense"
    hybrid = "hybrid"


# ─── 评估配置 ───

class EvalConfig(BaseModel):
    """评估运行配置"""
    kb_id: str = Field(..., description="知识库 ID")
    test_set_id: str = Field(..., description="测试集 ID")
    strategy: RetrievalStrategy = Field(default=RetrievalStrategy.hybrid, description="检索策略")
    top_k: int = Field(default=3, ge=1, le=20, description="检索返回数量")


# ─── 评估结果（每个问题一条） ───

class EvalItemResult(BaseModel):
    """单条问题的评估结果"""
    question: str
    expected_source: str
    expected_answer: str
    hit: bool
    rank: int = 0
    matched_chunk: str = ""
    score: float = 0.0


# ─── 评估报告 ───

class EvalMetrics(BaseModel):
    total: int = 0
    hit_count: int = 0
    recall: float = 0.0
    mrr: float = 0.0


class EvalReport(BaseModel):
    """完整的评估报告"""
    id: str
    kb_id: str
    kb_name: str = ""
    test_set_id: str
    test_set_name: str = ""
    strategy: str
    top_k: int
    status: str = "running"
    metrics: EvalMetrics = Field(default_factory=EvalMetrics)
    details: List[EvalItemResult] = Field(default_factory=list)
    collection_name: str = ""
    error_message: str = ""
    created_at: str = ""


# ─── 测试集 ───

class TestSetItem(BaseModel):
    question: str
    answer: str
    source: str


class TestSet(BaseModel):
    """测试集"""
    id: str
    name: str
    description: str = ""
    sheet_names: List[str] = Field(default_factory=list)
    items: List[TestSetItem] = Field(default_factory=list)
    file_name: str = ""
    count: int = 0
    created_at: str = ""
