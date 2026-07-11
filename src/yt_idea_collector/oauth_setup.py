from __future__ import annotations

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

from .auth import SCOPES, validate_access_token_scopes


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the offline Google OAuth refresh token")
    parser.add_argument("client_secrets", help="Path to the downloaded Desktop OAuth client JSON")
    args = parser.parse_args()
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    validate_access_token_scopes(creds.token)
    print("\nAdd these values as GitHub repository secrets:")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
