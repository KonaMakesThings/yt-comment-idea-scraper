import pytest

from yt_idea_collector.topics import normalize_topic


@pytest.mark.parametrize(("raw", "expected"), [
    ("  Street   Photography  ", "Street Photography"),
    ("Cafe\u0301 Reviews", "Café Reviews"),
    ("", "Other"),
])
def test_topics_are_cleaned_without_channel_specific_aliases(raw, expected):
    assert normalize_topic(raw) == expected
