from datetime import datetime, timezone

from yt_idea_collector.models import Baseline, Classification, Comment, Video
from yt_idea_collector.scoring import performance_indices, score_idea


def video(number, topic="TF2"):
    return Baseline(
        Video(str(number), f"Video {number}", "", datetime(2026, 1, number, tzinfo=timezone.utc), 600, "none"),
        topic, number * 100, number * 50, 30 + number, number * 5, number, number, number,
    )


def comment(likes=0):
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    return Comment("c1", "v1", None, "Viewer", "viewer", "Try this", now, now, likes)


def classification(topic="TF2", confidence="High"):
    return Classification("c1", True, confidence, "recommendation", "Try a loadout", topic, "Actionable")


def test_performance_index_orders_videos():
    rows = [video(1), video(2), video(3)]
    indices = performance_indices(rows)
    assert indices["1"] < indices["2"] < indices["3"]


def test_topic_with_three_comparables_has_non_low_confidence():
    result = score_idea(classification(), comment(5), [video(1), video(2), video(3)])
    assert 1 <= result.value <= 10
    assert result.confidence == "Medium"
    assert "3 comparable" in result.rationale


def test_missing_topic_uses_low_confidence_fallback():
    result = score_idea(classification("Overwatch"), comment(), [video(1), video(2), video(3)])
    assert result.confidence == "Low"
    assert "overall channel baseline" in result.rationale


def test_topic_aliases_share_one_scoring_bucket():
    rows = [video(1, "TF2"), video(2, "TF2 Classified"), video(3, "Team Fortress 2")]
    result = score_idea(classification("Team Fortress 2"), comment(), rows)
    assert result.confidence == "Medium"
    assert "3 comparable" in result.rationale


def test_score_works_without_baseline():
    result = score_idea(classification("Unknown"), comment(), [])
    assert 1 <= result.value <= 10
    assert result.confidence == "Low"
