"""One closed authentic two-brand prefix, ending before any closure/privacy request."""

import ast
import hashlib
import inspect as python_inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from tests import test_two_brand_pilot as pilot
from tests.test_shopify_sales import configuration
from tests.test_tiktok_sources import configured

PIN = "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
PREFIX = "4620f1d0188c16d748a9daa0c0a20bc2bdee66e8e05cc0b04a9d729889bc65e1"


def main() -> None:
    target, output = sys.argv[1:]
    destination = Path(output)
    assert destination.name == "ids.json" and not destination.exists()
    assert destination.is_absolute() and destination.parent.resolve() == destination.parent
    assert all(not p.is_symlink() for p in destination.parents)
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == PIN
    source = Path(os.environ["PYTHONPATH"]).resolve()
    assert Path(app.__file__).resolve().is_relative_to(source)
    assert Path(pilot.__file__).resolve().is_relative_to(source)
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert url.drivername == "sqlite" and not url.query and url.database
        path = Path(url.database)
        assert path == destination.parent.parent / "current.sqlite"
        assert path.is_file() and path.resolve() == path and not path.is_symlink()
        assert all(not p.is_symlink() for p in path.parents)
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert (
            url.drivername == "postgresql+psycopg"
            and url.host in {"localhost", "127.0.0.1", "::1"}
            and not url.query
        )
        assert url.database and re.fullmatch(r"inlet_[a-z0-9_]+_ci", url.database)
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
        with engine.connect() as db:
            assert db.scalar(text("SELECT current_schema()")) == target
    try:
        names = inspect(engine).get_table_names()
        with engine.connect() as db:
            for name in names:
                if name != "alembic_version":
                    quote = db.dialect.identifier_preparer.quote(name)
                    assert db.scalar(text(f"SELECT count(*) FROM {quote}")) == 0
        function = next(
            n
            for n in ast.parse(
                python_inspect.getsource(
                    vars(pilot)["test_two_brands_api_review_execution_and_closure_isolation"]
                )
            ).body
            if isinstance(n, ast.FunctionDef)
        )
        prefix = function.body[:25]
        assert (
            hashlib.sha256(
                ast.dump(
                    ast.Module(body=prefix, type_ignores=[]), include_attributes=False
                ).encode()
            ).hexdigest()
            == PREFIX
        )
        function.body = [
            *prefix,
            ast.Return(
                value=ast.Call(func=ast.Name(id="locals", ctx=ast.Load()), args=[], keywords=[])
            ),
        ]
        function.decorator_list = []
        namespace = dict(vars(pilot))
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                str(Path(pilot.__file__)),
                "exec",
            ),
            namespace,
        )
        media = destination.parent / "media"
        media.mkdir()
        with pytest.MonkeyPatch.context() as monkeypatch:
            cast(Any, configured).__wrapped__(monkeypatch)
            values = namespace[function.name](
                engine, cast(Any, configuration).__wrapped__(), None, monkeypatch, media
            )
        with engine.connect() as db:
            metadata = MetaData()

            def rows(name: str, **filters: Any) -> list[Any]:
                table = Table(name, metadata, autoload_with=db, resolve_fks=False)
                return list(
                    db.execute(
                        select(table).where(*(table.c[k] == v for k, v in filters.items()))
                    ).mappings()
                )

            def one(name: str, **filters: Any) -> Any:
                result = rows(name, **filters)
                assert len(result) == 1, (name, len(result))
                return result[0]

            brands = []
            for value in values["brands"]:
                wid = value["wid"]
                account = one("advertising_accounts", id=value["scope"].account_id)
                store = one("commerce_stores", workspace_id=wid)
                shopify = one(
                    "shopify_connections", workspace_id=wid, commerce_store_id=store["id"]
                )
                assert shopify["workspace_integration_id"] == store["connection_id"]
                crm = one("customer_source_connections", workspace_id=wid, provider=value["crm"])
                draft = one("customer_campaign_revisions", draft_id=value["draft"], revision=1)
                native = one(
                    "google_customer_connections"
                    if value["scope"].platform == "google_ads"
                    else "meta_connections",
                    workspace_id=wid,
                )
                mandate = one("spending_mandates", workspace_id=wid)
                brands.append(
                    dict(
                        workspace_id=wid,
                        actor_id=value["actor"],
                        account_id=account["id"],
                        advertising_integration_id=account["connection_id"],
                        store_id=store["id"],
                        shopify_connection_id=shopify["id"],
                        shopify_integration_id=store["connection_id"],
                        crm_connection_id=crm["id"],
                        crm_integration_id=crm["integration_id"],
                        goal_id=value["goal"],
                        goal_revision=1,
                        simulation_mandate_id=mandate["id"],
                        draft_id=value["draft"],
                        draft_revision=1,
                        draft_digest=draft["digest"],
                        platform=value["scope"].platform,
                        crm=value["crm"],
                        native_connection_id=native["id"],
                    )
                )
            attempt = one("provider_execution_attempts", id=values["attempt_id"])
            run = one("provider_execution_runs", id=attempt["run_id"])
            parent = one("provider_execution_runs", id=run["parent_run_id"])
            review = one("provider_execution_reviews", id=run["review_id"])
            original = one("provider_execution_reviews", id=parent["review_id"])
            binding = values["binding"]
            receipts = rows("provider_execution_receipts", attempt_id=attempt["id"])
            assert len(receipts) == 1
            receipt = receipts[0]
            execution = dict(
                provider_mandate_id=binding.mandate_id,
                provider_mandate_revision=binding.revision,
                provider_policy_digest=binding.policy_digest,
                provider_consent_id=binding.consent_id,
                ledger_id=binding.ledger_id,
                reservation_id=run["reservation_id"],
                creation_review_id=original["id"],
                creation_review_digest=original["digest"],
                creation_plan_digest=original["plan_digest"],
                creation_run_id=parent["id"],
                activation_review_id=review["id"],
                activation_review_digest=review["digest"],
                activation_plan_digest=review["plan_digest"],
                activation_run_id=run["id"],
                owned_attempt_id=attempt["id"],
                owned_request_digest=attempt["request_digest"],
                owned_receipt_id=receipt["id"],
                owned_receipt_digest=receipt["digest"],
            )
            ca = rows("provider_execution_attempts", run_id=parent["id"])
            aa = rows("provider_execution_attempts", run_id=run["id"])
            counts = dict(
                creation_attempts=len(ca),
                creation_receipts=sum(
                    len(rows("provider_execution_receipts", attempt_id=a["id"])) for a in ca
                ),
                activation_attempts=len(aa),
                activation_receipts=sum(
                    len(rows("provider_execution_receipts", attempt_id=a["id"])) for a in aa
                ),
                held_reservations=len(
                    rows(
                        "provider_exposure_reservations",
                        workspace_id=brands[0]["workspace_id"],
                        state="held",
                    )
                ),
                creation_provider_posts=values["server"].posts,
                activation_provider_posts=values["server"].activations,
            )
        payload = json.dumps(
            dict(
                schema_version="inlet.test.two-brand-receipt-source.v1",
                source_commit=PIN,
                brand_a=brands[0],
                brand_b=brands[1],
                execution=execution,
                counts=counts,
            )
        )
        assert len(payload.encode()) <= 16384
        destination.write_text(payload)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
