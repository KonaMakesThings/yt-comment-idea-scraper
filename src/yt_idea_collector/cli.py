from __future__ import annotations

import argparse
import json
import sys

from google import genai
from googleapiclient.discovery import build

from .auth import SHEETS_SCOPES, credentials, refresh_and_validate_scopes
from .config import Config
from .gemini import GeminiClassifier
from .pipeline import Pipeline
from .sheets import SheetStore
from .youtube import YouTubeClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect video ideas from YouTube comments")
    parser.add_argument("--dry-run", action="store_true", help="Read and classify without writing to Sheets")
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        # GitHub Actions logs are public for a public repository. API exception
        # messages can contain request URLs with private resource identifiers.
        print(f"Collector failed ({type(exc).__name__}); details were withheld from public logs.", file=sys.stderr)
        return 1


def run(args: argparse.Namespace) -> int:
    config = Config.from_env(dry_run=args.dry_run)
    sheets_creds = credentials(config.google_client_id, config.google_client_secret,
                               config.sheets_refresh_token, SHEETS_SCOPES)
    refresh_and_validate_scopes(sheets_creds, SHEETS_SCOPES)
    # Comment and video reads are public. Using an API key here avoids YouTube's
    # disproportionately broad youtube.force-ssl OAuth scope for comment listing.
    data_api = build("youtube", "v3", developerKey=config.youtube_api_key, cache_discovery=False)
    sheets_api = build("sheets", "v4", credentials=sheets_creds, cache_discovery=False)
    pipeline = Pipeline(
        YouTubeClient(data_api, config.youtube_channel_id),
        GeminiClassifier(genai.Client(api_key=config.gemini_api_key), config.gemini_model),
        SheetStore(sheets_api, config.google_sheet_id),
        channel_id=config.youtube_channel_id, batch_size=config.batch_size,
        backfill_start=config.backfill_start, dry_run=config.dry_run, reprocess=config.reprocess,
    )
    summary = pipeline.run()
    print(json.dumps(summary.__dict__, indent=2))
    # GitHub Actions should alert on a partial run. Failed Gemini batches remain
    # unprocessed and are intentionally retried on the next scheduled run.
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
