import pytest

from yt_idea_collector.topics import normalize_topic


@pytest.mark.parametrize(("raw", "expected"), [
    ("TF2", "Team Fortress 2"),
    ("Team Fortress 2", "Team Fortress 2"),
    ("TF2 Classified", "Team Fortress 2 Classified"),
    ("Team Fortress 2 Classified", "Team Fortress 2 Classified"),
    ("PvZ Garden Warfare", "Plants vs. Zombies: Garden Warfare"),
    ("Plants vs Zombies: Garden Warfare", "Plants vs. Zombies: Garden Warfare"),
    ("GW2", "Plants vs. Zombies: Garden Warfare 2"),
])
def test_common_topic_variants_have_canonical_labels(raw, expected):
    assert normalize_topic(raw) == expected
