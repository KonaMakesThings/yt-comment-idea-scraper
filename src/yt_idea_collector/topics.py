from __future__ import annotations

import unicodedata


def normalize_topic(topic: str) -> str:
    """Clean a model-provided topic without applying channel-specific aliases."""
    value = " ".join(unicodedata.normalize("NFKC", topic).strip().split())
    return value or "Other"
