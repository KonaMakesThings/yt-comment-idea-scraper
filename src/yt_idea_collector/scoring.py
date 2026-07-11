from __future__ import annotations

import math
from statistics import mean

from .models import Baseline, Classification, Comment, Score


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.5
    below = sum(v < value for v in values)
    equal = sum(v == value for v in values)
    return (below + 0.5 * equal) / len(values)


def performance_indices(rows: list[Baseline]) -> dict[str, float]:
    if not rows:
        return {}
    fields = (
        ("views", 0.40), ("watch_minutes", 0.25),
        ("average_view_percentage", 0.15), ("subscribers_gained", 0.10),
        ("likes", 0.04), ("comments", 0.04), ("shares", 0.02),
    )
    distributions = {field: [getattr(row, field) for row in rows] for field, _ in fields}
    return {
        row.video.id: sum(weight * _percentile(getattr(row, field), distributions[field]) for field, weight in fields)
        for row in rows
    }


def score_idea(classification: Classification, comment: Comment, rows: list[Baseline]) -> Score:
    indices = performance_indices(rows)
    overall = mean(indices.values()) if indices else 0.5
    topic_key = classification.topic.strip().casefold()
    comparable = [row for row in rows if row.topic.strip().casefold() == topic_key]
    strong_evidence = len(comparable) >= 3
    topic_score = mean(indices[row.video.id] for row in comparable) if strong_evidence else overall
    recent_rows = sorted(rows, key=lambda row: row.video.published_at, reverse=True)[:10]
    recent_score = mean(indices[row.video.id] for row in recent_rows) if recent_rows else overall
    confidence_signal = {"High": 0.9, "Medium": 0.65, "Low": 0.4}.get(classification.confidence, 0.5)
    engagement_signal = min(1.0, math.log1p(max(0, comment.like_count)) / math.log(11))
    request_signal = 0.75 * confidence_signal + 0.25 * engagement_signal
    combined = 0.75 * topic_score + 0.15 * recent_score + 0.10 * request_signal
    value = max(1, min(10, round(1 + 9 * combined)))
    if strong_evidence:
        confidence = "High" if len(comparable) >= 5 else "Medium"
        evidence = f"Based on {len(comparable)} comparable '{classification.topic}' videos"
    else:
        confidence = "Low"
        evidence = f"Only {len(comparable)} comparable '{classification.topic}' videos; used overall channel baseline"
    rationale = f"{evidence}. Historical performance drives 90% of the estimate; request strength and likes contribute 10%."
    return Score(value, confidence, rationale)

