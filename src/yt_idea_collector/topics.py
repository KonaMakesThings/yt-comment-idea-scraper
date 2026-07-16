from __future__ import annotations

import re
import unicodedata


def normalize_topic(topic: str) -> str:
    """Collapse common model spelling variants into stable scoring buckets."""
    value = " ".join(topic.strip().split())
    if not value:
        return "Other"
    key = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    key = re.sub(r"[^a-z0-9]+", " ", key).strip()

    if ("team fortress 2 classified" in key
            or re.search(r"\btf2\s+classified\b", key)
            or re.search(r"\btf2c\b", key)):
        return "Team Fortress 2 Classified"
    if ("team fortress 2" in key
            or re.search(r"\btf\s*2\b", key)
            or re.search(r"\btf2\b", key)
            or re.search(r"\btfc\b", key)):
        return "Team Fortress 2"
    if "garden warfare 2" in key or re.search(r"\bgw\s*2\b", key):
        return "Plants vs. Zombies: Garden Warfare 2"
    if ("garden warfare 1" in key or re.search(r"\bgw\s*1\b", key)
            or "garden warfare" in key):
        return "Plants vs. Zombies: Garden Warfare"
    if "plants vs zombies" in key or re.search(r"\bpvz\b", key):
        return "Plants vs. Zombies"
    if "splatoon" in key:
        return "Splatoon"
    if "pokemon" in key:
        return "Pokémon"
    return value
