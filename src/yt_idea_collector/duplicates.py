from __future__ import annotations

import re

from .topics import normalize_topic


def duplicate_group(summary: str, topic: str) -> str:
    """Return a human-readable group for obvious repeatable requests."""
    text = f"{summary} {topic}".casefold()
    patterns = (
        (r"\ball[ -]?star\b", "all-star"),
        (r"\bsplatoon\b", "splatoon"),
        (r"\bpotato(?:e)? mines?\b", "potato-mines"),
        (r"\bpack opening\b|\bbuy packs?\b", "pack-opening"),
        (r"\b(?:classic )?gardens? (?:and|&) graveyards?\b", "gardens-and-graveyards"),
        (r"\btaco bandits\b", "taco-bandits"),
        (r"\banimation\b", "animation"),
        (r"\b(?:ice|toxic) (?:variants?|next)\b", "ice-toxic-series"),
        (r"\binscryption\b", "inscryption"),
    )
    for pattern, label in patterns:
        if re.search(pattern, text):
            return f"{normalize_topic(topic)}: {label}"
    return ""
