"""Pure scalar-file guard only; fabricated values do not confer source authority."""

import json
from pathlib import Path

import pytest

from tests.campaign_review_ui_retained_fixture import CampaignReviewUiIds, read_ids


def scalar_values() -> dict[str, object]:
    return {
        key: ("a" * 64 if key == "mandate_policy_digest" else "a" * 32)
        if key in {"actor_id", "mandate_id", "google_source_id", "tiktok_source_id",
                   "mandate_policy_digest"} else (0 if key == "provider_posts" else 1)
        for key in CampaignReviewUiIds.__dataclass_fields__
    }


def test_campaign_ui_regular_bounded_scalar_file(tmp_path: Path) -> None:
    path = tmp_path / "ids.json"
    values = scalar_values()
    path.write_text(json.dumps(values))
    assert vars(read_ids(path)) == values


@pytest.mark.parametrize("kind", ["symlink", "directory", "missing", "oversize", "list",
                                 "bool", "extra"])
def test_campaign_ui_ids_reject_invalid_path_or_copy(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "ids.json"
    values = scalar_values()
    if kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text(json.dumps(values))
        path.symlink_to(target)
    elif kind == "directory":
        path.mkdir()
    elif kind == "oversize":
        path.write_bytes(b" " * 8193)
    elif kind == "list":
        path.write_text("[]")
    elif kind != "missing":
        if kind == "bool":
            values["workspace_id"] = True
        else:
            values["unrecognized"] = 1
        path.write_text(json.dumps(values))
    with pytest.raises((AssertionError, FileNotFoundError)):
        read_ids(path)
