# YouTube Comment Idea Collector

Turn actionable YouTube comments into a private Google Sheets review queue. The collector reads public comments from one channel, asks Gemini to identify concrete creator-directed video ideas, and preserves your review status and notes across scheduled runs.

It uses only official APIs. It does not scrape YouTube, read private analytics, estimate an idea's quality, or score ideas using channel performance.

## What it does

- Reads published top-level comments and replies with the YouTube Data API.
- Ignores the channel owner's comments, previously processed comments, and comments outside the configured window.
- Uses structured Gemini output plus deterministic guardrails to keep specific, creator-directed ideas.
- Inserts new ideas at the top of a Google Sheets queue.
- Preserves `Review Status`, `Creator Notes`, and duplicate groups when comments are reprocessed.
- Records processed comment IDs so scheduled runs are resumable and idempotent.
- Withholds API exception details from public GitHub Actions logs.

The visible `Review Queue` columns are status, idea summary, original comment, inferred topic, source video, comment link, posted time, notes, and duplicate group. Less frequently used metadata is hidden to the right. The hidden `_Processed` and `_RunLog` tabs are managed by the collector.

Upgrading from an older version is automatic: existing queue rows, statuses, notes, and original comments are migrated to the new score-free layout. Obsolete score columns and the `_VideoBaseline` tab are removed during the next normal run. The older `Ideas` tab, if present, is retained as a hidden backup.

## Requirements

- Python 3.11 or newer
- A Google Cloud project with the YouTube Data API v3 and Google Sheets API enabled
- A YouTube Data API key
- A Desktop OAuth client for Google Sheets access
- A Gemini API key
- A Google Sheet you control
- A GitHub repository if you want scheduled collection

Comment and video reads use the API key. OAuth requests only the `spreadsheets` scope and is used solely to update the destination Sheet.

## Install

```bash
git clone https://github.com/your-account/yt-comment-idea-scraper.git
cd yt-comment-idea-scraper
python -m venv .venv
```

Activate the environment, then install the package:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Google setup

1. Create or select a Google Cloud project.
2. Enable **YouTube Data API v3** and **Google Sheets API**.
3. Create a YouTube API key and restrict it to YouTube Data API v3 where possible.
4. Configure the OAuth consent screen.
5. Create an OAuth client with application type **Desktop app** and download its JSON file.
6. Create a Google Sheet and copy the ID between `/d/` and `/edit` in its URL.
7. Run the one-time OAuth helper locally:

```bash
yt-idea-oauth path/to/client_secret.json
```

Select an account that can edit the destination Sheet. The helper prints the client ID, client secret, and refresh token to save as repository secrets. Never commit the downloaded JSON or printed values.

## Configuration

Add these GitHub Actions repository secrets under **Settings > Secrets and variables > Actions**:

| Secret | Purpose |
| --- | --- |
| `GOOGLE_CLIENT_ID` | Desktop OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Desktop OAuth client secret |
| `GOOGLE_REFRESH_TOKEN` | Sheets refresh token printed by `yt-idea-oauth` |
| `YOUTUBE_API_KEY` | Restricted YouTube Data API key |
| `GEMINI_API_KEY` | Gemini API key |
| `YOUTUBE_CHANNEL_ID` | Channel ID whose public comments are read |
| `GOOGLE_SHEET_ID` | Destination spreadsheet ID |

`SHEETS_REFRESH_TOKEN` is also accepted and takes precedence over `GOOGLE_REFRESH_TOKEN`. This supports existing installations without requiring secrets to be recreated.

Optional repository variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model name |
| `GEMINI_BATCH_SIZE` | `20` | Comments per request; allowed range is 1-50 |
| `BACKFILL_START` | 30 days before each run | Fixed earliest comment date in `YYYY-MM-DD` form |
| `REPROCESS_COMMENTS` | `false` | Reapply the current classifier policy to older processed rows |

The included workflow runs daily and can also be started manually. Its `dry_run` input reads and classifies comments without initializing or updating the Sheet. Its `reprocess` input safely cleans existing rows using the current policy and can resume after interruption.

## Run locally

Set the same environment variables in your shell, then run:

```bash
yt-idea-collector --dry-run
yt-idea-collector
```

The first command is a read-only preview. The second initializes or updates the Sheet.

## Review workflow

Use `Review Status` values such as `New`, `Keep`, `Maybe`, `Reject`, `Duplicate`, or `Used`. Put private planning context in `Creator Notes`. Those two fields are preserved when a source comment is edited and classified again.

Duplicate groups are generic keyword fingerprints intended only to help manual review. They do not merge or delete ideas automatically.

## Privacy and security

The collector sends each eligible public comment and its source video title to Gemini for classification. Qualifying rows stored in your Sheet include the public author display name, comment text, and public YouTube links. Keep the Sheet private if you do not want that material redistributed, and review the data-use terms for the APIs you enable.

Secrets remain in GitHub Actions or your local environment and are never written to the Sheet. The repository ignores common local credential files. If a credential is ever committed or printed publicly, revoke and replace it; deleting the text from a later commit is not enough.

Report a vulnerability privately through the repository's **Security** tab and its private vulnerability-reporting feature rather than opening a public issue.

## License

MIT. See [LICENSE](LICENSE).
