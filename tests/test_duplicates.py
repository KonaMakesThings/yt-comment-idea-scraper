from yt_idea_collector.duplicates import duplicate_group


def test_duplicate_groups_cover_repeatable_requests():
    assert duplicate_group("Request for All-Star gameplay", "PvZ GW2") == (
        "Plants vs. Zombies: Garden Warfare 2: all-star"
    )
    assert duplicate_group("Create a pack opening video", "PvZ GW1") == (
        "Plants vs. Zombies: Garden Warfare: pack-opening"
    )


def test_duplicate_group_is_empty_for_unrelated_ideas():
    assert duplicate_group("Play the Meteor Shower", "TF2") == ""
