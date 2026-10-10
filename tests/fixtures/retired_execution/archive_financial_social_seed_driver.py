"""Exact unchanged original two-brand prefix, stopping before all customer HTTP."""

import ast
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, cast

import app
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, create_engine, event, select, text
from sqlalchemy.engine import make_url
from tests import test_archive_closure_financial_social as original
from tests.test_shopify_sales import configuration

PIN = "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
FILE = "15049bf103f6f9178c41622cad79c2c3d2ef75ef574191daa07c801eec2ed4b3"
FUNCTION = "36ba3f74cb7f08b5e9db750ee83d270b73d9b1ef5cbb8fed53911779a8f60199"
PREFIX = "f58209c8b6a20b1fffbe0fa202feec8fe466e0889f5475426aadc893e7e07cf2"


def main() -> None:
    target, output = sys.argv[1:]
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == PIN
    source = Path(os.environ["PYTHONPATH"]).resolve()
    assert Path(app.__file__).resolve().is_relative_to(source)
    path = Path(output).parent
    assert path.is_absolute() and path.resolve() == path
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert url.drivername == "sqlite" and not url.query
        assert not any((url.username, url.password, url.host, url.port))
        database = path / "current.sqlite"
        assert url.database == str(database) and not database.is_symlink()
        assert all(not p.is_symlink() for p in database.parents)
        assert stat.S_ISREG(database.lstat().st_mode)
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    try:
        metadata = MetaData()
        metadata.reflect(engine)
        assert "alembic_version" not in metadata.tables
        with engine.connect() as db:
            if engine.dialect.name == "postgresql":
                assert db.scalar(text("SELECT current_schema()")) == target
            for table in metadata.sorted_tables:
                assert db.execute(select(table).limit(1)).first() is None
        content = Path(original.__file__).read_bytes()
        assert hashlib.sha256(content).hexdigest() == FILE
        function = next(
            n
            for n in ast.parse(content).body
            if isinstance(n, ast.FunctionDef)
            and n.name == "test_owned_archive_then_closure_retains_replacement_and_social_evidence"
        )
        assert hashlib.sha256(ast.dump(function).encode()).hexdigest() == FUNCTION
        prefix = ast.Module(body=function.body[:2], type_ignores=[])
        assert hashlib.sha256(ast.dump(prefix).encode()).hexdigest() == PREFIX
        scope = dict(
            vars(original),
            export_engine=engine,
            configuration=cast(Any, configuration).__wrapped__(),
            tmp_path=path / "media",
        )
        exec(compile(prefix, str(original.__file__), "exec"), scope)
        with engine.connect() as db:
            rows = {
                t.name: [dict(r) for r in db.execute(select(t)).mappings()]
                for t in metadata.sorted_tables
            }

        def one(table: str, **values: Any) -> dict[str, Any]:
            found = [r for r in rows[table] if all(r[k] == v for k, v in values.items())]
            assert len(found) == 1, table
            return found[0]

        def source_revision(row: dict[str, Any]) -> dict[str, Any]:
            return dict(draft_id=row["draft_id"], revision=row["revision"], digest=row["digest"])

        brands = []
        for entry, provider in zip(scope["brands"], ("meta_ads", "google_ads"), strict=True):
            wid, actor, successor_id, claim, _runtime, server, social_id = entry
            effects = server.posts if provider == "meta_ads" else server.writes
            assert claim is None and len(effects) == 1
            mandate = one("provider_execution_mandates", workspace_id=wid)
            consent = one("provider_execution_consents", workspace_id=wid)
            attempt = one("provider_execution_attempts", workspace_id=wid)
            response = one("provider_execution_responses", attempt_id=attempt["id"])
            receipt = one("provider_execution_receipts", attempt_id=attempt["id"])
            old = one("provider_execution_runs", id=attempt["run_id"])
            repeat = one("provider_execution_runs", id=successor_id)
            review = one("provider_execution_reviews", id=repeat["review_id"])
            replacement = one("provider_reservation_replacements", workspace_id=wid)
            google = one("google_customer_connections", workspace_id=wid)
            meta = one("meta_connections", workspace_id=wid) if provider == "meta_ads" else None
            shop = one("shopify_connections", workspace_id=wid)
            crm = one("crm_connections", workspace_id=wid)
            revisions = [r for r in rows["customer_campaign_revisions"] if r["workspace_id"] == wid]
            google_revision = next(
                r
                for r in revisions
                if r["artifact"]["definition"]["content"]["kind"] == "google_search_v1"
            )
            social = None
            if social_id:
                sr = one("customer_social_configuration_reviews", id=social_id)
                approval = one("customer_social_configuration_approvals", review_id=social_id)
                media = one("customer_media_objects", workspace_id=wid)
                social = dict(
                    source=source_revision(
                        one("customer_campaign_revisions", draft_id=sr["draft_id"])
                    ),
                    media_id=media["id"],
                    media_sha256=media["sha256"],
                    review_id=sr["id"],
                    review_digest=sr["digest"],
                    approval_digest=approval["digest"],
                )
            brands.append(
                dict(
                    provider=provider,
                    workspace_id=wid,
                    actor_id=actor,
                    goal_id=one("customer_goals", workspace_id=wid)["id"],
                    simulation_mandate_id=one("spending_mandates", workspace_id=wid)["id"],
                    google_connection_id=google["id"],
                    google_account_id=google["account_id"],
                    google_integration_id=google["integration_id"],
                    meta_connection_id=meta["id"] if meta else None,
                    meta_account_id=meta["account_id"] if meta else None,
                    meta_integration_id=meta["workspace_integration_id"] if meta else None,
                    shopify_connection_id=shop["id"],
                    shopify_integration_id=shop["workspace_integration_id"],
                    crm_connection_id=crm["id"],
                    crm_integration_id=crm["workspace_integration_id"],
                    commerce_store_id=shop["commerce_store_id"],
                    provider_mandate_id=mandate["id"],
                    consent_id=consent["id"],
                    ledger_id=mandate["ledger_id"],
                    provider_mandate_revision=mandate["revision"],
                    original_review_id=old["review_id"],
                    original_run_id=old["id"],
                    original_attempt_id=attempt["id"],
                    original_fence=attempt["fence"],
                    original_request_digest=attempt["request_digest"],
                    original_response_digest=response["digest"],
                    original_receipt_digest=receipt["digest"],
                    original_receipt_id=receipt["id"],
                    predecessor_reservation_id=old["reservation_id"],
                    repeat_review_id=repeat["review_id"],
                    successor_run_id=successor_id,
                    successor_reservation_id=repeat["reservation_id"],
                    replacement_id=replacement["id"],
                    repeat_review_digest=review["digest"],
                    replacement_digest=replacement["digest"],
                    google_source=source_revision(google_revision),
                    social=social,
                    source_mutation_count=len(effects),
                )
            )
        data = dict(
            schema_version="inlet.test.archive-financial-social-source.v1",
            source_commit=PIN,
            source_file_sha256=FILE,
            source_function_ast_sha256=FUNCTION,
            source_prefix_ast_sha256=PREFIX,
            brand_a=brands[0],
            brand_b=brands[1],
        )
        encoded = json.dumps(data)
        assert len(encoded.encode()) <= 16384
        Path(output).write_text(encoded)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
