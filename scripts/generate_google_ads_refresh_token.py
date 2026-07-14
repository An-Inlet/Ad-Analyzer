"""Generate a Google Ads OAuth refresh token from a Desktop OAuth JSON file.

The helper opens a browser-based consent flow with only the Google Ads API
scope. It writes the resulting refresh token to a local file so token material is
not printed to terminal output or application logs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
DEFAULT_OUTPUT_PATH = Path(".google_ads_refresh_token.local")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Google Ads OAuth refresh token for read-only collectors."
    )
    parser.add_argument(
        "desktop_oauth_json",
        type=Path,
        help="Path to the downloaded Google Cloud Desktop OAuth client JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Local output file for GOOGLE_ADS_REFRESH_TOKEN; defaults to a gitignored file.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local callback port for the OAuth browser flow; defaults to a random port.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.desktop_oauth_json),
        scopes=[GOOGLE_ADS_SCOPE],
    )
    credentials = flow.run_local_server(
        port=args.port,
        access_type="offline",
        prompt="consent",
    )
    if not credentials.refresh_token:
        raise SystemExit("Google did not return a refresh token; retry with a new consent flow.")

    args.output.write_text(
        f"GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}\n",
        encoding="utf-8",
    )
    args.output.chmod(0o600)
    print(f"Refresh token environment variable written to {args.output}.")
    print("Copy it into your local .env file and do not commit either file.")


if __name__ == "__main__":
    main()
