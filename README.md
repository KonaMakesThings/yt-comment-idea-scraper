# YouTube Comment Idea Collector

This project scans published comments and viewer replies across a YouTube channel, uses Gemini 3.1 Flash-Lite to find broad video-idea signals, scores them against the channel's own long-form performance, and maintains a review queue in Google Sheets.

It uses official Google APIs—no HTML scraping. The first run considers comments posted on or after **December 1, 2025**. Subsequent runs skip unchanged comments and revisit edited ones. A scheduled GitHub Actions workflow runs every day at 13:00 UTC.

## What counts as an idea

The prompt is intentionally recall-oriented. It includes direct requests, “have you played…” questions, recommendations, detailed loadouts or strategies, suggested experiments and comparisons, and other comments with an actionable creative seed. Gemini returns a confidence and category so borderline ideas remain easy to review.

The visible `Ideas` tab contains the editable review status and notes, deterministic 1–10 opportunity score and rationale, normalized topic, source links, author and timestamp, raw comment, and classifier metadata. Hidden tabs contain processed IDs, the video performance baseline, and run history. Rejected comments are represented only by ID, update time, and outcome—raw rejected text is not archived.

## Prerequisites

- A GitHub repository (private is fine) with Actions enabled
- A Google Cloud project
- A Google Sheet you own
- A free Gemini API key from Google AI Studio
- Python 3.11+ for the one-time OAuth setup

In the Google Cloud project, enable:

1. YouTube Data API v3
2. YouTube Analytics API
3. Google Sheets API

Create an API key under **APIs & Services → Credentials** for public YouTube Data API reads. Restrict the key's API restrictions to **YouTube Data API v3**. The collector deliberately uses this key for comments and public video metadata because YouTube otherwise requires the broad `youtube.force-ssl` OAuth scope for comment listing. Private channel performance still uses read-only OAuth through the YouTube Analytics API.

Configure the OAuth consent screen, then create an OAuth client with application type **Desktop app** and download its JSON file. For a personal automation, add every Google account that will authorize the app as a test user—including a separate business/Workspace account if it will own the Sheet. Be aware that refresh tokens for an OAuth app left in Testing can expire after seven days; move the consent screen to Production for a durable scheduled job. Workspace administrators can restrict external OAuth apps, so the business account may require administrator approval.

## One-time authorization

Create a virtual environment and install the project:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
yt-idea-oauth .\client_secret.json
```

A browser opens for authorization. The command prints `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN`. Treat all three as secrets; do not commit the downloaded JSON or printed values. This default mode uses one Google account for both YouTube and Sheets.

### Separate YouTube and business Sheet accounts

Use the same Desktop OAuth client JSON for both authorizations, but run setup twice:

```powershell
yt-idea-oauth .\client_secret.json --account youtube
yt-idea-oauth .\client_secret.json --account sheets
```

The first browser flow forces the account picker: select the Google account that owns the YouTube channel. It requests only YouTube Data and Analytics read access and prints `YOUTUBE_REFRESH_TOKEN`.

The second flow forces the account picker again: select the business Google account that owns or can edit the destination Sheet. It requests only Google Sheets access and prints `SHEETS_REFRESH_TOKEN`.

Both runs print the same `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Add the two account-specific refresh tokens to GitHub and remove the legacy `GOOGLE_REFRESH_TOKEN` secret to avoid confusion. The Sheet ID must identify a Sheet accessible to the business account used in the second flow.

If GitHub reports `insufficient authentication scopes`, the stored refresh token was issued without one or more required permissions. Remove the app from [Google Account connections](https://myaccount.google.com/connections), run the OAuth command again, explicitly select every requested permission, and replace all three `GOOGLE_*` GitHub secrets with the newly printed values. The setup command verifies the actual access-token scopes before printing credentials. Changing scopes in source code cannot add permissions to an existing refresh token.

## GitHub configuration

Create these repository **Actions secrets** under Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `GOOGLE_CLIENT_ID` | Printed by `yt-idea-oauth` |
| `GOOGLE_CLIENT_SECRET` | Printed by `yt-idea-oauth` |
| `GOOGLE_REFRESH_TOKEN` | Single-account mode only; printed by the default OAuth command |
| `YOUTUBE_REFRESH_TOKEN` | Two-account mode; printed by `--account youtube` |
| `SHEETS_REFRESH_TOKEN` | Two-account mode; printed by `--account sheets` |
| `YOUTUBE_API_KEY` | Google Cloud API key restricted to YouTube Data API v3 |
| `GEMINI_API_KEY` | Gemini API key from Google AI Studio |
| `YOUTUBE_CHANNEL_ID` | The channel ID beginning with `UC` |
| `GOOGLE_SHEET_ID` | The value between `/d/` and `/edit` in the Sheet URL |

Optional Actions variables:

| Variable | Default | Purpose |
|---|---:|---|
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Stable Gemini model name |
| `GEMINI_BATCH_SIZE` | `20` | Comments/videos per model call; valid range 1–50 |
| `REPROCESS_COMMENTS` | `false` | Set `true` for one manual run to reclassify all comments since `BACKFILL_START` |

Push the repository, open Actions, select **Collect YouTube video ideas**, and use **Run workflow**. The first normal run initializes the four Sheet tabs and performs the backfill. Later runs are incremental. Manual dry runs are read-only and require the Sheet to have been initialized by a previous normal run.

### Cleaning an over-broad first pass

The classifier is intentionally conservative about what counts as a concrete video idea. If an older run put social chatter, naming questions, or requests to play together into `Ideas`, create the Actions variable `REPROCESS_COMMENTS=true`, run the workflow once normally (not dry-run), then remove the variable or set it back to `false`. The run reclassifies the existing comment history and deletes rows that no longer qualify while retaining their IDs in `_Processed` so they do not return on the next daily run. Direct topic questions such as “have you played X?” and concrete weapon/loadout recommendations remain eligible.

## Local execution

Set the same required environment variables, using either `GOOGLE_REFRESH_TOKEN` for single-account mode or both account-specific refresh tokens for two-account mode, then run:

```powershell
yt-idea-collector
yt-idea-collector --dry-run
```

`BACKFILL_START` can override the default `2025-12-01`. A dry run retrieves data, rebuilds the in-memory baseline, and calls Gemini, but does not initialize or write to the Sheet.

## How scoring works

The collector looks at non-live uploads from the past 24 months, excludes videos three minutes or shorter as a conservative public-API Shorts heuristic (the YouTube Data API has no explicit Shorts flag), and waits until a video is at least 30 days old. For each included video, the read-only Analytics API supplies its complete first 30 days of views, watch time, average viewed percentage, likes, comments, shares, and subscriber gains.

Each historical video gets a percentile-based performance index. An idea's score is:

- 75% average performance of videos with the same normalized topic
- 15% the ten most recent long-form videos
- 10% classifier confidence and comment likes

At least three topic matches are required. Otherwise the system uses the overall long-form baseline, marks confidence `Low`, and explains the fallback. Gemini writes the topic and idea summary, but it does not choose the numeric score.

The score is directional, not a promise of future views. After the queue has been useful for a while, competitor benchmarking can be added as a separate calibrated signal.

## Reliability and privacy notes

- YouTube list operations used here normally cost one quota unit per page; the collector scans all thread pages so it can notice replies added to old threads.
- Public YouTube comments and video metadata use `YOUTUBE_API_KEY`; OAuth is reserved for read-only owner Analytics.
- Complete replies are fetched when the thread's reported reply count exceeds its embedded reply sample.
- API rate limits and transient server errors use exponential backoff. A failed Gemini batch is not written to `_Processed`, so the next run retries it.
- The Sheet header shape is validated before writes. Unexpected columns stop the run instead of risking data loss. Add personal columns only after the existing columns, or use `Creator Notes`.
- Gemini's free tier may use submitted content to improve Google products. This project submits public comment text and source-video titles.

## Development

```powershell
pip install -e ".[dev]"
pytest
```
