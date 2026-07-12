from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone

from .gemini import GeminiClassifier
from .models import Baseline, Comment
from .policy import CLASSIFIER_VERSION
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
        print("Fetching channel comments...", flush=True)
        comments = self.youtube.list_comments()
        cutoff = datetime.combine(self.backfill_start, time.min, tzinfo=timezone.utc)
        eligible = []
        for comment in comments:
            state = processed.get(comment.id, (None, "", "", ""))
            changed = state[0] != comment.updated_at.isoformat()
            needs_current_policy = self.reprocess and state[3] != CLASSIFIER_VERSION
            if (comment.published_at >= cutoff and comment.author_channel_id != self.channel_id
                    and (changed or needs_current_policy)):
                eligible.append(comment)
        print(f"Fetched {len(comments)} comments; {len(eligible)} need classification.", flush=True)
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
        try:
            baselines = self._baselines()
        except Exception as exc:
            baselines = []
            errors += 1
            error_messages.append(f"Baseline refresh failed; scoring used fallback: {type(exc).__name__}: {exc}")
            print(f"Baseline refresh failed; continuing with low-confidence fallback scores: {exc}", flush=True)
        ideas = 0
        total_batches = (len(eligible) + self.batch_size - 1) // self.batch_size
        for batch_number, start in enumerate(range(0, len(eligible), self.batch_size), start=1):
            batch = [c for c in eligible[start:start + self.batch_size] if c.video_id in videos]
            if not batch:
                continue
            print(f"Classifying batch {batch_number}/{total_batches} ({len(batch)} comments)...", flush=True)
            try:
                results = self.classifier.classify(batch, {key: value.title for key, value in videos.items()})
                for comment, result in zip(batch, results, strict=True):
                    score = score_idea(result, comment, baselines) if result.is_idea else None
                    ideas += int(result.is_idea)
                    if not self.dry_run:
                        existing = (self.store.ideas().get(comment.id) if self.reprocess
                                    else existing_ideas.get(comment.id))
                        self.store.write_result(comment, result, score, videos[comment.video_id], existing,
                                                CLASSIFIER_VERSION)
                print(f"Completed batch {batch_number}/{total_batches}.", flush=True)
            except Exception as exc:
                errors += len(batch)
                error_messages.append(f"Batch starting {batch[0].id}: {type(exc).__name__}: {exc}")
                print(f"Batch {batch_number}/{total_batches} failed and will be retried next run: {exc}", flush=True)
        summary = RunSummary(len(comments), len(eligible), ideas, errors)
        if not self.dry_run:
            self.store.log_run("success" if errors == 0 else "partial", summary.fetched,
                               summary.eligible, summary.ideas, summary.errors, False,
                               " | ".join(error_messages))
        return summary

    def _baselines(self) -> list[Baseline]:
        cached = self.store.baselines(max_age_days=7)
        if cached:
            print(f"Using cached seven-day video baseline ({len(cached)} videos).", flush=True)
            return cached
        print("Refreshing the seven-day video performance baseline...", flush=True)
        videos = self.youtube.recent_uploads(months=24)
        topics: dict[str, str] = {}
        for start in range(0, len(videos), self.batch_size):
            topics.update(self.classifier.topics(videos[start:start + self.batch_size]))
        rows = [self.youtube.analytics_baseline(video, topics[video.id]) for video in videos]
        if not self.dry_run:
            self.store.write_baselines(rows)
        return rows
