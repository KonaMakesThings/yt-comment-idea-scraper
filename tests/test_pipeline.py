from datetime import date, datetime, timezone

from yt_idea_collector.models import Classification, Comment, Video
from yt_idea_collector.pipeline import Pipeline
from yt_idea_collector.policy import CLASSIFIER_VERSION


NOW = datetime(2026, 1, 2, tzinfo=timezone.utc)


class YouTube:
    def __init__(self, comments):
        self._comments = comments

    def list_comments(self):
        return self._comments

    def videos(self, ids):
        return {id_: Video(id_, "Title", "", NOW, 600, "none") for id_ in ids}

    def recent_uploads(self, months):
        return []


class Classifier:
    def __init__(self):
        self.seen = []

    def classify(self, comments, titles):
        self.seen.extend(comments)
        return [Classification(c.id, True, "High", "recommendation", "Make it", "TF2", "Why") for c in comments]

    def topics(self, videos):
        return {}


class Store:
    def __init__(self, processed=None):
        self.state = processed or {}
        self.ensure_calls = 0
        self.writes = 0
        self.result_writes = 0

    def ensure_layout(self):
        self.ensure_calls += 1

    def processed(self):
        return self.state

    def ideas(self):
        return {}

    def baselines(self, max_age_days):
        return []

    def write_result(self, *args):
        self.writes += 1
        self.result_writes += 1

    def write_baselines(self, rows):
        self.writes += 1

    def log_run(self, *args):
        self.writes += 1


def comment(id_, published=NOW, updated=NOW, author="viewer"):
    return Comment(id_, "v1", None, "Viewer", author, "Idea", published, updated, 0)


def pipeline(comments, store, dry_run=False):
    return Pipeline(YouTube(comments), Classifier(), store, channel_id="owner", batch_size=20,
                    backfill_start=date(2025, 12, 1), dry_run=dry_run)


def test_filters_creator_old_and_unchanged_comments():
    old = datetime(2025, 11, 30, tzinfo=timezone.utc)
    unchanged = comment("same")
    store = Store({"same": (unchanged.updated_at.isoformat(), "idea", "2")})
    result = pipeline([comment("good"), comment("owner", author="owner"), comment("old", published=old), unchanged], store).run()
    assert result.eligible == 1
    assert result.ideas == 1


def test_dry_run_performs_no_sheet_writes_or_initialization():
    store = Store()
    result = pipeline([comment("good")], store, dry_run=True).run()
    assert result.ideas == 1
    assert store.ensure_calls == 0
    assert store.writes == 0


def test_failed_batch_is_not_processed():
    class BrokenClassifier(Classifier):
        def classify(self, comments, titles):
            raise RuntimeError("rate limited")

    store = Store()
    job = Pipeline(YouTube([comment("retry")]), BrokenClassifier(), store, channel_id="owner",
                   batch_size=20, backfill_start=date(2025, 12, 1))
    result = job.run()
    assert result.errors == 1
    assert store.result_writes == 0  # failed comments remain eligible for the next run


def test_cleanup_only_reprocesses_rows_from_an_older_policy_version():
    old = comment("old-policy")
    current = comment("current-policy")
    store = Store({
        old.id: (old.updated_at.isoformat(), "idea", "2", "older-policy"),
        current.id: (current.updated_at.isoformat(), "idea", "3", CLASSIFIER_VERSION),
    })
    classifier = Classifier()
    job = Pipeline(YouTube([old, current]), classifier, store, channel_id="owner",
                   batch_size=20, backfill_start=date(2025, 12, 1), reprocess=True)

    result = job.run()

    assert result.eligible == 1
    assert [item.id for item in classifier.seen] == [old.id]
