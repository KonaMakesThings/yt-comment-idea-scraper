# YouTube Comment Idea Collector

This project scans published comments and viewer replies across a YouTube channel, uses Gemini 3.1 Flash-Lite to find concrete creator-directed video ideas, scores them against the channel's own long-form performance, and maintains a compact review queue in Google Sheets.

It uses official Google APIs—no HTML scraping. The first run considers comments posted on or after **December 1, 2025**. Subsequent runs skip unchanged comments and revisit edited ones. A scheduled GitHub Actions workflow runs every day at 13:00 UTC.

## What counts as an idea

An idea must direct the creator toward a specific game, weapon, loadout, challenge, experiment, comparison, video format, or substantial topic. Examples include “have you played Overwatch?”, “try the Meteor Shower on Heavy”, a custom-weapon tier list, or a request for more Splatoon content.

The collector rejects requests to play with the commenter, server/link/install help, regional-server requests, naming brainstorms, ordinary opinions, nostalgia, game-developer wishes, and viewer-invented weapons unless the viewer explicitly asks the creator to make content about them. A deterministic policy check runs after Gemini so these high-noise categories cannot slip through solely because the model wrote an enthusiastic summary.

The visible `Review Queue` tab puts the useful fields first: status, score, idea, original comment, normalized game/topic, source video, comment link, date, creator notes, and duplicate group. Technical columns remain available but hidden. New qualifying ideas are inserted immediately below the header so they appear at the top of the queue; existing rows keep their review status and notes. Common labels such as TF2/Team Fortress 2 and TF2 Classified, plus PvZ Garden Warfare spellings, are repaired to consistent canonical display names during layout maintenance. On upgrade, the old `Ideas` tab is copied into the new queue and retained as a hidden backup. Hidden implementation tabs contain processed IDs, the cached video-performance baseline, and run history. Rejected comments are represented only by ID, update time, and outcome; raw rejected text is not archived.

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
| `REPROCESS_COMMENTS` | `false` | Advanced: continuously request cleanup with the current policy version |

Push the repository, open **Actions**, select **Collect YouTube video ideas**, and choose **Run workflow**. Use the branch containing the version you want to run; after a pull request is merged, use `main`.

For normal use:

1. Leave both boxes unchecked.
2. Click **Run workflow**.
3. Watch the `Collect ideas` step. It reports the fetched count and progress as `batch 1/N`, `batch 2/N`, and so on.

The first normal run initializes the Sheet and performs the backfill. Later scheduled runs are incremental and usually process only a small number of new or edited comments. **Preview only** (dry run) calls the APIs and Gemini but never changes or cleans the Sheet.

### Cleaning an over-broad first pass

If an older run put clutter into the queue, run the workflow once with **Clean the existing queue with the newest rules** checked and **Preview only** unchecked. Cleanup is resumable: every successful batch records the classifier-policy version, so a timeout or cancellation can be restarted with the same selections without beginning again. Rows that no longer qualify are removed from `Review Queue`, while their IDs remain in `_Processed` so they do not return on the next daily run.

Direct topic questions such as “have you played X?” and concrete weapon/loadout recommendations remain eligible. Support questions, social requests, ordinary opinions, and speculative concepts are removed. You do not need to toggle the repository variable back and forth; the version marker prevents already-cleaned comments from being repeatedly reprocessed.

### Reviewing ideas without the clutter

Use the status dropdown in `Review Queue`:

- `Keep`: worth developing
- `Maybe`: revisit later
- `Reject`: not useful after human review
- `Duplicate`: same underlying request as another row; use `Duplicate Group` to keep the cluster together
- `Used`: turned into content

Add context in `Creator Notes`. The automation preserves both fields when a comment is edited and reclassified. The wide technical fields are hidden to the right; unhide them only when diagnosing a score or classification.

## Local execution

Set the same required environment variables, using either `GOOGLE_REFRESH_TOKEN` for single-account mode or both account-specific refresh tokens for two-account mode, then run:

```powershell
yt-idea-collector
yt-idea-collector --dry-run
```

`BACKFILL_START` can override the default `2025-12-01`. A dry run retrieves data, uses the cached baseline when available, and calls Gemini, but does not initialize or write to the Sheet.

## How scoring works

The collector looks at non-live uploads from the past 24 months, excludes videos three minutes or shorter as a conservative public-API Shorts heuristic (the YouTube Data API has no explicit Shorts flag), and waits until a video is at least 30 days old. For each included video, the read-only Analytics API supplies its complete first 30 days of views, watch time, average viewed percentage, likes, comments, shares, and subscriber gains.

Each historical video gets a percentile-based performance index. An idea's score is:

- 75% average performance of videos with the same normalized topic
- 15% the ten most recent long-form videos
- 10% classifier confidence and comment likes

At least three topic matches are required. Aliases for `TF2` and `Team Fortress 2` share one scoring bucket; `TF2 Classified`/`Team Fortress 2 Classified` use a separate bucket. Garden Warfare spellings are normalized similarly. Otherwise the system uses the overall long-form baseline, marks confidence `Low`, and explains the fallback. Gemini writes the topic and idea summary, but it does not choose the numeric score. The performance baseline is cached for seven days so ordinary and cleanup runs do not repeatedly call Analytics for every historical video.

The score is directional, not a promise of future views. After the queue has been useful for a while, competitor benchmarking can be added as a separate calibrated signal.

## Reliability and privacy notes

- YouTube list operations used here normally cost one quota unit per page; the collector scans all thread pages so it can notice replies added to old threads.
- Public YouTube comments and video metadata use `YOUTUBE_API_KEY`; OAuth is reserved for read-only owner Analytics.
- Complete replies are fetched when the thread's reported reply count exceeds its embedded reply sample.
- API rate limits, read timeouts, and transient connection/server errors use exponential backoff. A failed Gemini batch is not written to `_Processed`, so the next run retries it.
- Comments whose source video is deleted, private, or otherwise unavailable through the public Data API are recorded as `unavailable_video` in `_Processed` and skipped without being retried forever. Other processing errors make the GitHub Actions run fail visibly so they can be investigated.
- Collector-owned headers are repaired automatically. Keep personal review text in `Creator Notes`; the old wide `Ideas` tab is retained as a hidden migration backup rather than overwritten or deleted.
- Gemini's free tier may use submitted content to improve Google products. This project submits public comment text and source-video titles.

## Development

```powershell
pip install -e ".[dev]"
pytest
```
