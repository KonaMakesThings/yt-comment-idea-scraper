from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta


REQUIRED = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "YOUTUBE_API_KEY",
    "GEMINI_API_KEY",
    "YOUTUBE_CHANNEL_ID",
    "GOOGLE_SHEET_ID",
)
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
RETIRED_GEMINI_MODELS = {
    "gemini-2.5-flash-lite": DEFAULT_GEMINI_MODEL,
    "gemini-2.5-flash-lite-preview-09-2025": DEFAULT_GEMINI_MODEL,
    "gemini-3.1-flash-lite-preview": DEFAULT_GEMINI_MODEL,
}


@dataclass(frozen=True)
class Config:
    google_client_id: str
    google_client_secret: str
    sheets_refresh_token: str
    youtube_api_key: str
    gemini_api_key: str
    youtube_channel_id: str
    google_sheet_id: str
    gemini_model: str = DEFAULT_GEMINI_MODEL
    batch_size: int = 20
    backfill_start: date = field(default_factory=lambda: date.today() - timedelta(days=30))
    dry_run: bool = False
    reprocess: bool = False

    @classmethod
    def from_env(cls, *, dry_run: bool = False) -> "Config":
        missing = [name for name in REQUIRED if not os.getenv(name)]
        sheets_token = os.getenv("SHEETS_REFRESH_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN")
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
        backfill_value = os.getenv("BACKFILL_START")
        cutoff = date.fromisoformat(backfill_value) if backfill_value else date.today() - timedelta(days=30)
        requested_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        model = RETIRED_GEMINI_MODELS.get(requested_model, requested_model)
        return cls(
            google_client_id=os.environ["GOOGLE_CLIENT_ID"],
            google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            sheets_refresh_token=sheets_token,
            youtube_api_key=os.environ["YOUTUBE_API_KEY"],
            gemini_api_key=os.environ["GEMINI_API_KEY"],
            youtube_channel_id=os.environ["YOUTUBE_CHANNEL_ID"],
            google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
            gemini_model=model,
            batch_size=batch_size,
            backfill_start=cutoff,
            dry_run=dry_run,
            reprocess=os.getenv("REPROCESS_COMMENTS", "false").strip().lower() in {"1", "true", "yes", "on"},
        )
