"""Fixed original emission; record-only capture of its actual mock server."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests import test_google_completion_evidence as original
from tests.test_google_optimization_http import Server
from tests.test_shopify_sales import configuration


def main() -> None:
    target, output = sys.argv[1:]
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    path = Path(output).resolve().parent
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert (
            not url.query
            and url.database
            and Path(url.database).resolve() == path / "current.sqlite"
        )
        assert Path(url.database).is_file()
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == target
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        captured: list[Any] = []
        ready = cast(Any, original).ready

        def record(*args: Any, **kwargs: Any) -> Any:
            result = ready(*args, **kwargs)
            captured.append(result)
            return result

        with pytest.MonkeyPatch.context() as patch, Session(engine) as db:
            patch.setattr(original, "ready", record)
            wid, actor, attempt_id = original.emitted(
                db, cast(Any, configuration).__wrapped__(), path
            )
            assert len(captured) == 1 and isinstance(captured[0][-1], Server)
            server = captured[0][-1]
            assert len(server.writes) == 1
            attempt = db.scalars(select(ProviderExecutionAttempt)).one()
            response = db.scalars(select(ProviderExecutionResponse)).one()
            receipt = db.scalars(select(ProviderExecutionReceipt)).one()
            completion = db.scalars(select(GoogleOriginalCompletion)).one()
            run = db.get(ProviderExecutionRun, attempt.run_id)
            assert run and run.reservation_id
            hold = db.scalars(select(ProviderExposureReservation)).one()
            assert hold.id == run.reservation_id and hold.state == "held"
            assert attempt.id == attempt_id == response.attempt_id == receipt.attempt_id
            assert (
                completion.attempt_id == attempt_id
                and receipt.receipt["outcome"] == "verified_target_state"
            )
            data = dict(
                workspace_id=wid,
                actor_id=actor,
                attempt_id=attempt_id,
                fence=attempt.fence,
                request_digest=attempt.request_digest,
                completion_digest=completion.digest,
                response_digest=response.digest,
                receipt_id=receipt.id,
                receipt_sequence=receipt.sequence,
                receipt_digest=receipt.digest,
                reservation_id=hold.id,
                reservation_amount_micros=hold.amount_micros,
                provider_posts=len(server.writes),
            )
            db.commit()
        Path(output).write_text(json.dumps(data))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
