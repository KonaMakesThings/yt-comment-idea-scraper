from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
)


def credentials(client_id: str, client_secret: str, refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def refresh_and_validate_scopes(creds: Credentials) -> None:
    """Refresh once and turn incomplete OAuth consent into an actionable error."""
    creds.refresh(Request())
    granted = set(creds.granted_scopes or ())
    if not granted:
        return
    missing = set(SCOPES) - granted
    if missing:
        formatted = "\n  - ".join(sorted(missing))
        raise RuntimeError(
            "The saved GOOGLE_REFRESH_TOKEN is missing required permissions. "
            "Run `yt-idea-oauth client_secret.json` again, approve every requested "
            f"permission, and replace the GitHub secret. Missing scopes:\n  - {formatted}"
        )
