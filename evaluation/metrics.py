"""评估指标计算：召回率、MRR、Hit Rate"""

from typing import List

from evaluation.schemas import EvalItemResult, EvalMetrics


def compute_metrics(details: List[EvalItemResult], top_k: int = 3) -> EvalMetrics:
    """根据单条结果列表计算整体指标"""
    total = len(details)
    if total == 0:
        return EvalMetrics()

    hit_count = sum(1 for d in details if d.hit)
    recall = hit_count / total if total > 0 else 0.0

    # MRR: 对每个问题，如果命中则取 1/rank，否则为 0
    reciprocal_ranks = [
        1.0 / d.rank if d.hit and d.rank > 0 else 0.0
        for d in details
    ]
    mrr = sum(reciprocal_ranks) / total if total > 0 else 0.0

    return EvalMetrics(
        total=total,
        hit_count=hit_count,
        recall=round(recall, 4),
        mrr=round(mrr, 4),
    )
