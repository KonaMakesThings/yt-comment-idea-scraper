from __future__ import annotations

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

from .auth import SCOPES, SHEETS_SCOPES, YOUTUBE_SCOPES, validate_access_token_scopes


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the offline Google OAuth refresh token")
    parser.add_argument("client_secrets", help="Path to the downloaded Desktop OAuth client JSON")
    parser.add_argument(
        "--account", choices=("all", "youtube", "sheets"), default="all",
        help="Authorize one account for everything, or create an account-specific refresh token",
    )
    args = parser.parse_args()
    scopes = {"all": SCOPES, "youtube": YOUTUBE_SCOPES, "sheets": SHEETS_SCOPES}[args.account]
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, scopes)
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent select_account",
    )
    validate_access_token_scopes(creds.token, scopes)
    print("\nAdd these values as GitHub repository secrets:")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    secret_name = {
        "all": "GOOGLE_REFRESH_TOKEN",
        "youtube": "YOUTUBE_REFRESH_TOKEN",
        "sheets": "SHEETS_REFRESH_TOKEN",
    }[args.account]
    print(f"{secret_name}={creds.refresh_token}")


if __name__ == "__main__":
    main()
