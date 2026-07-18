from __future__ import annotations

import re

from .topics import normalize_topic


def duplicate_group(summary: str, topic: str) -> str:
    """Return a generic, deterministic fingerprint for manual duplicate review."""
    stop_words = {
        "about", "again", "could", "create", "for", "make", "more", "please", "request", "should",
        "that", "the", "this", "try", "video", "with", "would", "your",
    }
    topic_label = normalize_topic(topic)
    topic_words = set(re.findall(r"[a-z0-9]+", topic_label.casefold()))
    words = re.findall(r"[a-z0-9]+", summary.casefold())
    keywords = sorted({word for word in words if len(word) > 2 and word not in stop_words
                       and word not in topic_words})
    return f"{topic_label}: {'-'.join(keywords[:5])}" if keywords else ""
