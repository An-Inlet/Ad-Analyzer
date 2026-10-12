"""Failure recorder retains only fixed categories and preserves original failures."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.test_prepared_generation_runtime import _persist_expiry_outcome


def test_fixed_refusal_and_delay_recorded(tmp_path: Path) -> None:
    event = dict(
        event="planning_authority_expired",
        schema_version=1,
        route="generate",
        phase="pre_cas",
        cause="fact_age_outside_window",
        session_predicate="not_evaluated",
        status=409,
    )
    record = logging.LogRecord(
        "inlet.planning.authority", 30, "unused", 1, json.dumps(event), (), None
    )
    destination = tmp_path / "outcome.json"
    _persist_expiry_outcome(
        destination,
        httpx.Response(409, json={"detail": "planning_authority_expired"}),
        [],
        [record],
        failed=True,
    )
    value = json.loads(destination.read_text())
    assert value["status"] == 409 and value["category"] == "planning_authority_expired"
    assert value["delay_reached"] is False and value["authority_events"] == [event]
    assert value["malformed_events"] == 0 and value["assertion_or_request_failed"] is True


def test_unknown_payload_and_malformed_log_not_retained(tmp_path: Path) -> None:
    destination = tmp_path / "outcome.json"
    record = logging.LogRecord(
        "inlet.planning.authority", 30, "unused", 1, "DO_NOT_RETAIN", (), None
    )
    _persist_expiry_outcome(
        destination,
        httpx.Response(409, json={"detail": "DO_NOT_RETAIN"}),
        [True],
        [record],
        failed=False,
    )
    text = destination.read_text()
    assert "DO_NOT_RETAIN" not in text
    value = json.loads(text)
    assert value["category"] == "other_response" and value["malformed_events"] == 1
    assert value["delay_reached"] is True


def test_writer_failure_preserves_original_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = AssertionError("original assertion")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("write failure")

    class BrokenStderr:
        def write(self, text: str) -> int:
            raise OSError("stderr failure")

    monkeypatch.setattr(Path, "open", fail)
    monkeypatch.setattr(sys, "stderr", BrokenStderr())
    with pytest.raises(AssertionError) as result:
        try:
            raise original
        finally:
            _persist_expiry_outcome(tmp_path / "outcome.json", None, [], [], failed=True)
    assert result.value is original
    with pytest.raises(OSError):
        _persist_expiry_outcome(tmp_path / "outcome.json", None, [], [], failed=False)


def test_non_json_response_still_records_status_and_delay(tmp_path: Path) -> None:
    destination = tmp_path / "outcome.json"
    _persist_expiry_outcome(
        destination, httpx.Response(409, text="DO_NOT_RETAIN"), [], [], failed=True
    )
    text = destination.read_text()
    assert "DO_NOT_RETAIN" not in text
    value = json.loads(text)
    assert value["status"] == 409 and value["category"] == "other_response"
    assert value["malformed_response"] is True and value["delay_reached"] is False
    assert value["assertion_or_request_failed"] is True
