"""Strict checkpoint scalars; no schema or historical execution bypass."""

import pytest

from tests.feedback_review_retained_fixture import FeedbackReviewIds, parse_ids


def raw(stage: str) -> dict[str, object]:
    result: dict[str, object] = {
        key: "a" * (64 if key.endswith("digest") else 32)
        for key in FeedbackReviewIds.__dataclass_fields__
    }
    result.update(
        stage=stage,
        workspace_id=1,
        reservation_amount_micros=1,
        native_budget_amount_micros=1,
        provider_posts=int(stage == "completed"),
        receipt_sequence=1,
    )
    if stage == "claimed_final_context":
        for key in (
            "response_digest",
            "receipt_id",
            "receipt_digest",
            "receipt_sequence",
            "completion_digest",
        ):
            result[key] = None
    return result


@pytest.mark.parametrize("stage", ["claimed_final_context", "completed"])
def test_closed_stage_shape(stage: str) -> None:
    assert parse_ids(raw(stage), stage).stage == stage


@pytest.mark.parametrize(
    "key,value",
    [
        ("workspace_id", True),
        ("provider_posts", True),
        ("native_budget_amount_micros", -1),
        ("receipt_sequence", 2),
        ("session_digest", "a" * 32),
        ("receipt_digest", None),
        ("extra", "unknown"),
        ("stage", "other"),
    ],
)
def test_rejects_invalid_completed_scalars(key: str, value: object) -> None:
    data = raw("completed")
    data[key] = value
    with pytest.raises(AssertionError):
        parse_ids(data, "completed")


def test_claimed_does_not_invent_completed_evidence() -> None:
    data = raw("claimed_final_context")
    data["completion_digest"] = "a" * 64
    with pytest.raises(AssertionError):
        parse_ids(data, "claimed_final_context")


@pytest.mark.parametrize("kind", ["empty", "oversize", "directory", "symlink", "valid"])
def test_checkpoint_file_boundaries(tmp_path, kind: str) -> None:  # type: ignore[no-untyped-def]
    import json

    from tests.feedback_review_retained_fixture import read_ids

    output = tmp_path / "ids.json"
    if kind == "directory":
        output.mkdir()
    elif kind == "symlink":
        source = tmp_path / "source.json"
        source.write_text(json.dumps(raw("completed")))
        output.symlink_to(source)
    else:
        output.write_text(
            {"empty": "", "oversize": " " * 8193, "valid": json.dumps(raw("completed"))}[kind]
        )
    if kind == "valid":
        assert read_ids(output, "completed").stage == "completed"
    else:
        with pytest.raises(AssertionError):
            read_ids(output, "completed")
