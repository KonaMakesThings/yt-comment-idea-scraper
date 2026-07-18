from yt_idea_collector.duplicates import duplicate_group


def test_duplicate_groups_cover_repeatable_requests():
    assert duplicate_group("Create a beginner camera tutorial", "Photography") == (
        "Photography: beginner-camera-tutorial"
    )
    assert duplicate_group("Make a camera tutorial for beginners", "Photography") == (
        "Photography: beginners-camera-tutorial"
    )


def test_duplicate_group_is_empty_for_unrelated_ideas():
    assert duplicate_group("Make a video about Photography", "Photography") == ""
