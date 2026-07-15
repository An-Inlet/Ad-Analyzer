"""Generate a Google Ads OAuth refresh token from a Desktop OAuth JSON file.

The helper opens a browser-based consent flow with only the Google Ads API
scope. It writes the resulting refresh token to a local file so token material is
not printed to terminal output or application logs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.token_files import secure_write_refresh_token_file
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path.home() / ".google_ads_refresh_token.local"


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_repo_local(path: Path) -> bool:
    return _resolved(path).is_relative_to(REPOSITORY_ROOT)


def _validated_desktop_oauth_json(path: Path) -> Path:
    resolved_path = _resolved(path)
    if _is_repo_local(resolved_path):
        raise SystemExit(
            "Desktop OAuth client JSON must be stored outside this Git repository."
        )
    return resolved_path


def _validated_output_path(path: Path) -> Path:
    resolved_path = _resolved(path)
    if _is_repo_local(resolved_path):
        raise SystemExit(
            "Refresh-token output file must be stored outside this Git repository."
        )
    return resolved_path


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
        help="Local output file for GOOGLE_ADS_REFRESH_TOKEN; defaults to a home file.",
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
    desktop_oauth_json = _validated_desktop_oauth_json(args.desktop_oauth_json)
    output_path = _validated_output_path(args.output)
    flow = InstalledAppFlow.from_client_secrets_file(
        str(desktop_oauth_json),
        scopes=[GOOGLE_ADS_SCOPE],
    )
    credentials = flow.run_local_server(
        port=args.port,
        access_type="offline",
        prompt="consent",
    )
    if not credentials.refresh_token:
        raise SystemExit("Google did not return a refresh token; retry with a new consent flow.")

    secure_write_refresh_token_file(
        output_path,
        f"GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}\n",
    )
    print(f"Refresh token environment variable written to {output_path}.")
    print("Copy it into your local .env file and do not commit either file.")


if __name__ == "__main__":
    main()
