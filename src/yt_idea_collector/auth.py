from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

YOUTUBE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)
SHEETS_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
)
SCOPES = YOUTUBE_SCOPES + SHEETS_SCOPES


def credentials(client_id: str, client_secret: str, refresh_token: str,
                scopes: tuple[str, ...] = SCOPES) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )


def access_token_scopes(access_token: str) -> set[str]:
    """Ask Google's token endpoint which scopes the access token actually has."""
    request = UrlRequest(
        "https://oauth2.googleapis.com/tokeninfo",
        data=urlencode({"access_token": access_token}).encode("utf-8"),
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return set(payload.get("scope", "").split())


def validate_access_token_scopes(access_token: str, required_scopes: tuple[str, ...] = SCOPES) -> None:
    granted = access_token_scopes(access_token)
    missing = set(required_scopes) - granted
    if missing:
        formatted = "\n  - ".join(sorted(missing))
        raise RuntimeError(
            "Google issued an access token without every required permission. Revoke the app "
            "at https://myaccount.google.com/connections, run `yt-idea-oauth "
            "client_secret.json` again, and explicitly approve every requested permission. "
            f"Missing scopes:\n  - {formatted}"
        )


def refresh_and_validate_scopes(creds: Credentials,
                                required_scopes: tuple[str, ...] = SCOPES) -> None:
    """Refresh once and turn incomplete OAuth consent into an actionable error."""
    creds.refresh(Request())
    validate_access_token_scopes(creds.token, required_scopes)
