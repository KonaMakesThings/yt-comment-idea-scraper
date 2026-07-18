from datetime import datetime, timezone

from yt_idea_collector.models import Classification, Comment, Video
from yt_idea_collector.sheets import IDEA_HEADERS, QUEUE_SHEET, SheetStore


PREVIOUS_QUEUE_HEADERS = [
    "Review Status", "Opportunity Score", "Idea Summary", "Original Comment",
    "Inferred Game/Topic", "Source Video Title", "Comment Link", "Posted Time", "Creator Notes",
    "Duplicate Group", "Score Confidence", "Score Rationale", "Idea Type", "Video Link", "Username",
    "Comment Likes", "Classification Confidence", "Processed Time", "Comment ID",
]


class MemorySheet(SheetStore):
    def __init__(self):
        super().__init__(None, "sheet")
        self.idea_rows = []
        self.processed_rows = []

    def _values(self, range_):
        if range_ == f"'{QUEUE_SHEET}'!A2:P":
            return [row[:] for row in self.idea_rows]
        if range_ == "'_Processed'!A2:E":
            return [row[:] for row in self.processed_rows]
        raise AssertionError(range_)

    def _append(self, range_, values):
        if range_ == f"'{QUEUE_SHEET}'!A:P":
            self.idea_rows.extend([row[:] for row in values])
        elif range_ == "'_Processed'!A:E":
            self.processed_rows.extend([row[:] for row in values])
        else:
            raise AssertionError(range_)

    def _insert_queue_row(self, row):
        self.idea_rows.insert(0, row[:])

    def _update(self, range_, values):
        if range_.startswith(f"'{QUEUE_SHEET}'!A"):
            index = int(range_.split("A")[-1]) - 2
            self.idea_rows[index] = values[0][:]
        elif range_.startswith("'_Processed'!A"):
            index = int(range_.split("A")[-1]) - 2
            self.processed_rows[index] = values[0][:]
        else:
            raise AssertionError(range_)

    def _delete_row(self, title, row_number):
        assert title == QUEUE_SHEET
        del self.idea_rows[row_number - 2]


class HeaderMemorySheet(SheetStore):
    def __init__(self, current):
        super().__init__(None, "sheet")
        self.current = current
        self.updates = []
        self.clears = []

    def _values(self, range_):
        return self.current

    def _update(self, range_, values):
        self.updates.append((range_, values))

    def _clear(self, range_):
        self.clears.append(range_)


def objects(text="Create a beginner photography tutorial"):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    comment = Comment("c1", "v1", None, "Viewer", "viewer", text, now, now, 4)
    result = Classification("c1", True, "High", "recommendation", "Create a beginner tutorial", "Photography", "Actionable")
    video = Video("v1", "Camera basics", "", now, 600, "none")
    return comment, result, video


def test_new_then_edited_comment_updates_without_duplicate():
    store = MemorySheet()
    comment, result, video = objects()
    store.write_result(comment, result, video, None, "policy-v3")
    assert len(store.idea_rows) == 1
    assert len(store.processed_rows) == 1
    assert store.idea_rows[0][IDEA_HEADERS.index("Original Comment")] == "Create a beginner photography tutorial"
    assert store.processed_rows[0][4] == "policy-v3"

    edited, result, video = objects("Please create a beginner camera tutorial")
    existing = store.ideas()["c1"]
    store.write_result(edited, result, video, existing)
    assert len(store.idea_rows) == 1
    assert len(store.processed_rows) == 1
    assert store.idea_rows[0][IDEA_HEADERS.index("Original Comment")] == "Please create a beginner camera tutorial"


def test_new_ideas_are_inserted_at_the_top_of_the_queue():
    store = MemorySheet()
    first, result, video = objects("Create a lighting tutorial")
    second, result, video = objects("Compare two camera lenses")
    second = Comment("c2", second.video_id, second.parent_id, second.author_name, second.author_channel_id,
                     second.text, second.published_at, second.updated_at, second.like_count)

    store.write_result(first, result, video, None)
    store.write_result(second, result, video, None)

    assert store.idea_rows[0][IDEA_HEADERS.index("Comment ID")] == "c2"
    assert store.idea_rows[1][IDEA_HEADERS.index("Comment ID")] == "c1"


def test_comment_that_no_longer_qualifies_is_removed_but_deduped():
    store = MemorySheet()
    comment, result, video = objects()
    store.write_result(comment, result, video, None)
    no_idea = Classification("c1", False, "High", "not_an_idea", "", "", "Not actionable")
    store.write_result(comment, no_idea, video, store.ideas()["c1"])
    assert len(store.idea_rows) == 0
    assert len(store.processed_rows) == 1
    assert store.processed_rows[0][2] == "not_idea"


def test_many_terminal_outcomes_append_once_and_are_idempotent():
    store = MemorySheet()
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    comments = [Comment(f"gone-{index}", "missing", None, "Viewer", "viewer", "text",
                        now, now, 0) for index in range(3)]

    store.mark_processed_many(comments, "unavailable_video", "policy-v4")
    store.mark_processed_many(comments, "unavailable_video", "policy-v4")

    assert len(store.processed_rows) == 3
    assert {row[2] for row in store.processed_rows} == {"unavailable_video"}


def test_managed_header_row_is_repaired_without_rewriting_data_rows():
    store = HeaderMemorySheet([["Custom heading", *IDEA_HEADERS[1:]]])

    store._ensure_headers(QUEUE_SHEET, IDEA_HEADERS)

    assert store.updates == [(f"'{QUEUE_SHEET}'!A1", [IDEA_HEADERS])]


def test_matching_header_row_is_left_untouched():
    store = HeaderMemorySheet([IDEA_HEADERS.copy()])

    store._ensure_headers(QUEUE_SHEET, IDEA_HEADERS)

    assert store.updates == []


def test_scored_queue_is_migrated_without_score_columns():
    old = dict.fromkeys(PREVIOUS_QUEUE_HEADERS, "")
    old.update({
        "Review Status": "Keep", "Opportunity Score": 9, "Idea Summary": "Create a camera guide",
        "Original Comment": "Could you make a camera guide?", "Inferred Game/Topic": "Photography",
        "Creator Notes": "Good fit", "Score Rationale": "Private performance detail", "Comment ID": "c1",
    })
    store = HeaderMemorySheet([PREVIOUS_QUEUE_HEADERS, [old[name] for name in PREVIOUS_QUEUE_HEADERS]])

    store._migrate_queue_headers()

    migrated = store.updates[0][1][1]
    assert migrated[IDEA_HEADERS.index("Review Status")] == "Keep"
    assert migrated[IDEA_HEADERS.index("Creator Notes")] == "Good fit"
    assert migrated[IDEA_HEADERS.index("Inferred Topic")] == "Photography"
    assert "Private performance detail" not in migrated
    assert store.clears == [f"'{QUEUE_SHEET}'!Q:S"]
