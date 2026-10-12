"""One separately authorized observation; never acceptance or reliability closure."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from app.settings import Settings
from sqlalchemy import Engine

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owner_runtime_composition import test_configured_owner_browser as configured_browser
from tests.test_shopify_sales import configuration as configuration


class ExpiryCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []
        self.discarded = False

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if len(self.events) >= 16 or type(record.msg) is not str or len(record.msg) > 1024:
                self.discarded = True
                return
            event = json.loads(record.msg)
            if type(event) is not dict or set(event) != {
                "event",
                "schema_version",
                "route",
                "phase",
                "cause",
                "session_predicate",
                "status",
            }:
                self.discarded = True
                return
            if (
                event["event"] != "planning_authority_expired"
                or type(event["schema_version"]) is not int
                or event["schema_version"] != 1
                or type(event["status"]) is not int
                or event["status"] != 409
                or event["route"]
                not in {"generate", "current", "history", "version", "unspecified"}
                or event["phase"] not in {"lock", "replay", "pre_cas", "post_flush", "unspecified"}
                or (event["cause"], event["session_predicate"])
                not in {
                    ("fact_age_outside_window", "not_evaluated"),
                    ("session_expired", "expired"),
                }
            ):
                self.discarded = True
                return
            self.events.append(event)
        except Exception:
            self.discarded = True  # Diagnostic failures never replace the original outcome.


def test_once_configured_v6_expiry_observation(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    capture = ExpiryCapture()
    logger = logging.getLogger("inlet.planning.authority")
    logger.addHandler(capture)
    try:
        configured_browser(
            customer_engine, request, configuration, replicas, monkeypatch, tmp_path, "positive"
        )
    finally:
        logger.removeHandler(capture)
        capture.close()
        try:
            (tmp_path / "fixed-expiry-observation.json").write_text(
                json.dumps(
                    {
                        "classification": "diagnostic_only_not_acceptance",
                        "events": capture.events,
                        "discarded": capture.discarded,
                        "logger_restored": capture not in logger.handlers,
                    },
                    indent=2,
                )
            )
        except OSError:
            request.node.user_properties.append(("fixed_expiry_artifact_write", "failed"))
