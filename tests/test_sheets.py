from datetime import datetime, timezone

from yt_idea_collector.models import Classification, Comment, Score, Video
from yt_idea_collector.sheets import IDEA_HEADERS, SheetStore


class MemorySheet(SheetStore):
    def __init__(self):
        super().__init__(None, "sheet")
        self.idea_rows = []
        self.processed_rows = []

    def _values(self, range_):
        if range_ == "'Ideas'!A2:R":
            return [row[:] for row in self.idea_rows]
        if range_ == "'_Processed'!A2:D":
            return [row[:] for row in self.processed_rows]
        if range_ == "'_Processed'!A2:A":
            return [[row[0]] for row in self.processed_rows]
        raise AssertionError(range_)

    def _append(self, range_, values):
        if range_ == "'Ideas'!A:R":
            self.idea_rows.extend([row[:] for row in values])
        elif range_ == "'_Processed'!A:D":
            self.processed_rows.extend([row[:] for row in values])
        else:
            raise AssertionError(range_)

    def _update(self, range_, values):
        if range_.startswith("'Ideas'!A"):
            index = int(range_.split("A")[-1]) - 2
            self.idea_rows[index] = values[0][:]
        elif range_.startswith("'_Processed'!A"):
            index = int(range_.split("A")[-1]) - 2
            self.processed_rows[index] = values[0][:]
        else:
            raise AssertionError(range_)

    def _delete_row(self, title, row_number):
        assert title == "Ideas"
        del self.idea_rows[row_number - 2]


def objects(text="Try Overwatch"):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    comment = Comment("c1", "v1", None, "Viewer", "viewer", text, now, now, 4)
    result = Classification("c1", True, "High", "recommendation", "Play Overwatch", "Overwatch", "Actionable")
    score = Score(8, "Low", "Overall baseline")
    video = Video("v1", "TF2 video", "", now, 600, "none")
    return comment, result, score, video


def test_new_then_edited_comment_updates_without_duplicate():
    store = MemorySheet()
    comment, result, score, video = objects()
    store.write_result(comment, result, score, video, None)
    assert len(store.idea_rows) == 1
    assert len(store.processed_rows) == 1
    assert store.idea_rows[0][IDEA_HEADERS.index("Raw Comment")] == "Try Overwatch"

    edited, result, score, video = objects("Please play Overwatch 2")
    existing = store.ideas()["c1"]
    store.write_result(edited, result, score, video, existing)
    assert len(store.idea_rows) == 1
    assert len(store.processed_rows) == 1
    assert store.idea_rows[0][IDEA_HEADERS.index("Raw Comment")] == "Please play Overwatch 2"


def test_comment_that_no_longer_qualifies_is_removed_but_deduped():
    store = MemorySheet()
    comment, result, score, video = objects()
    store.write_result(comment, result, score, video, None)
    no_idea = Classification("c1", False, "High", "not_an_idea", "", "", "Not actionable")
    store.write_result(comment, no_idea, None, video, store.ideas()["c1"])
    assert len(store.idea_rows) == 0
    assert len(store.processed_rows) == 1
    assert store.processed_rows[0][2] == "not_idea"
