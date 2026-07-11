from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone

from .gemini import GeminiClassifier
from .models import Baseline, Comment
from .scoring import score_idea
from .sheets import SheetStore
from .youtube import YouTubeClient


@dataclass(frozen=True)
class RunSummary:
    fetched: int
    eligible: int
    ideas: int
    errors: int


class Pipeline:
    def __init__(self, youtube: YouTubeClient, classifier: GeminiClassifier, store: SheetStore,
                 *, channel_id: str, batch_size: int, backfill_start, dry_run: bool = False,
                 reprocess: bool = False):
        self.youtube = youtube
        self.classifier = classifier
        self.store = store
        self.channel_id = channel_id
        self.batch_size = batch_size
        self.backfill_start = backfill_start
        self.dry_run = dry_run
        self.reprocess = reprocess

    def run(self) -> RunSummary:
        # A dry run is deliberately read-only. It therefore expects a sheet that has
        # already been initialized by at least one normal run.
        if not self.dry_run:
            self.store.ensure_layout()
        processed = self.store.processed()
        existing_ideas = self.store.ideas()
        comments = self.youtube.list_comments()
        cutoff = datetime.combine(self.backfill_start, time.min, tzinfo=timezone.utc)
        eligible = [c for c in comments if c.published_at >= cutoff and
                    c.author_channel_id != self.channel_id and
                    (self.reprocess or processed.get(c.id, (None,))[0] != c.updated_at.isoformat())]
        video_ids = sorted({c.video_id for c in eligible if c.video_id})
        videos = self.youtube.videos(video_ids)
        missing_video_ids = {c.video_id for c in eligible if not c.video_id or c.video_id not in videos}
        errors = sum(1 for c in eligible if c.video_id in missing_video_ids)
        error_messages = ([f"Missing/unavailable video metadata: {', '.join(sorted(missing_video_ids))}"]
                          if missing_video_ids else [])
        if not eligible:
            summary = RunSummary(len(comments), 0, 0, 0)
            if not self.dry_run:
                self.store.log_run("success", summary.fetched, 0, 0, 0, False, "No new or edited comments")
            return summary
        baselines = self._baselines()
        ideas = 0
        for start in range(0, len(eligible), self.batch_size):
            batch = [c for c in eligible[start:start + self.batch_size] if c.video_id in videos]
            if not batch:
                continue
            try:
                results = self.classifier.classify(batch, {key: value.title for key, value in videos.items()})
                for comment, result in zip(batch, results, strict=True):
                    score = score_idea(result, comment, baselines) if result.is_idea else None
                    ideas += int(result.is_idea)
                    if not self.dry_run:
                        existing = (self.store.ideas().get(comment.id) if self.reprocess
                                    else existing_ideas.get(comment.id))
                        self.store.write_result(comment, result, score, videos[comment.video_id], existing)
            except Exception as exc:
                errors += len(batch)
                error_messages.append(f"Batch starting {batch[0].id}: {type(exc).__name__}: {exc}")
        summary = RunSummary(len(comments), len(eligible), ideas, errors)
        if not self.dry_run:
            self.store.log_run("success" if errors == 0 else "partial", summary.fetched,
                               summary.eligible, summary.ideas, summary.errors, False,
                               " | ".join(error_messages))
        return summary

    def _baselines(self) -> list[Baseline]:
        videos = self.youtube.recent_uploads(months=24)
        topics: dict[str, str] = {}
        for start in range(0, len(videos), self.batch_size):
            topics.update(self.classifier.topics(videos[start:start + self.batch_size]))
        rows = [self.youtube.analytics_baseline(video, topics[video.id]) for video in videos]
        if not self.dry_run:
            self.store.write_baselines(rows)
        return rows
