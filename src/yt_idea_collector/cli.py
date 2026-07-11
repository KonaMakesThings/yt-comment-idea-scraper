from __future__ import annotations

import argparse
import json

from google import genai
from googleapiclient.discovery import build

from .auth import SHEETS_SCOPES, YOUTUBE_SCOPES, credentials, refresh_and_validate_scopes
from .config import Config
from .gemini import GeminiClassifier
from .pipeline import Pipeline
from .sheets import SheetStore
from .youtube import YouTubeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect video ideas from YouTube comments")
    parser.add_argument("--dry-run", action="store_true", help="Read and classify without writing to Sheets")
    args = parser.parse_args()
    config = Config.from_env(dry_run=args.dry_run)
    youtube_creds = credentials(config.google_client_id, config.google_client_secret,
                                config.youtube_refresh_token, YOUTUBE_SCOPES)
    sheets_creds = credentials(config.google_client_id, config.google_client_secret,
                               config.sheets_refresh_token, SHEETS_SCOPES)
    refresh_and_validate_scopes(youtube_creds, YOUTUBE_SCOPES)
    refresh_and_validate_scopes(sheets_creds, SHEETS_SCOPES)
    # Comment and video reads are public. Using an API key here avoids YouTube's
    # disproportionately broad youtube.force-ssl OAuth scope for comment listing.
    data_api = build("youtube", "v3", developerKey=config.youtube_api_key, cache_discovery=False)
    analytics_api = build("youtubeAnalytics", "v2", credentials=youtube_creds, cache_discovery=False)
    sheets_api = build("sheets", "v4", credentials=sheets_creds, cache_discovery=False)
    pipeline = Pipeline(
        YouTubeClient(data_api, analytics_api, config.youtube_channel_id),
        GeminiClassifier(genai.Client(api_key=config.gemini_api_key), config.gemini_model),
        SheetStore(sheets_api, config.google_sheet_id),
        channel_id=config.youtube_channel_id, batch_size=config.batch_size,
        backfill_start=config.backfill_start, dry_run=config.dry_run,
    )
    print(json.dumps(pipeline.run().__dict__, indent=2))


if __name__ == "__main__":
    main()
