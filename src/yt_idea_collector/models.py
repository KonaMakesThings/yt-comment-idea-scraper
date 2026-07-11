from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Comment:
    id: str
    video_id: str
    parent_id: str | None
    author_name: str
    author_channel_id: str | None
    text: str
    published_at: datetime
    updated_at: datetime
    like_count: int


@dataclass(frozen=True)
class Video:
    id: str
    title: str
    description: str
    published_at: datetime
    duration_seconds: int
    live_broadcast_content: str


@dataclass(frozen=True)
class Classification:
    comment_id: str
    is_idea: bool
    confidence: str
    idea_type: str
    summary: str
    topic: str
    rationale: str


@dataclass(frozen=True)
class Baseline:
    video: Video
    topic: str
    views: float
    watch_minutes: float
    average_view_percentage: float
    likes: float
    comments: float
    shares: float
    subscribers_gained: float


@dataclass(frozen=True)
class Score:
    value: int
    confidence: str
    rationale: str

