from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


REQUIRED = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GEMINI_API_KEY",
    "YOUTUBE_CHANNEL_ID",
    "GOOGLE_SHEET_ID",
)


@dataclass(frozen=True)
class Config:
    google_client_id: str
    google_client_secret: str
    youtube_refresh_token: str
    sheets_refresh_token: str
    gemini_api_key: str
    youtube_channel_id: str
    google_sheet_id: str
    gemini_model: str = "gemini-2.5-flash-lite"
    batch_size: int = 20
    backfill_start: date = date(2025, 12, 1)
    dry_run: bool = False

    @classmethod
    def from_env(cls, *, dry_run: bool = False) -> "Config":
        missing = [name for name in REQUIRED if not os.getenv(name)]
        legacy_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        youtube_token = os.getenv("YOUTUBE_REFRESH_TOKEN") or legacy_token
        sheets_token = os.getenv("SHEETS_REFRESH_TOKEN") or legacy_token
        if not youtube_token:
            missing.append("YOUTUBE_REFRESH_TOKEN (or GOOGLE_REFRESH_TOKEN)")
        if not sheets_token:
            missing.append("SHEETS_REFRESH_TOKEN (or GOOGLE_REFRESH_TOKEN)")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        try:
            batch_size = int(os.getenv("GEMINI_BATCH_SIZE", "20"))
        except ValueError as exc:
            raise ValueError("GEMINI_BATCH_SIZE must be an integer") from exc
        if not 1 <= batch_size <= 50:
            raise ValueError("GEMINI_BATCH_SIZE must be between 1 and 50")
        cutoff = date.fromisoformat(os.getenv("BACKFILL_START", "2025-12-01"))
        return cls(
            google_client_id=os.environ["GOOGLE_CLIENT_ID"],
            google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            youtube_refresh_token=youtube_token,
            sheets_refresh_token=sheets_token,
            gemini_api_key=os.environ["GEMINI_API_KEY"],
            youtube_channel_id=os.environ["YOUTUBE_CHANNEL_ID"],
            google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            batch_size=batch_size,
            backfill_start=cutoff,
            dry_run=dry_run,
        )
