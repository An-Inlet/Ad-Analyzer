"""Private closed historical producer child; no public restore CLI options."""

import importlib
import json
import os
import sys
import types
from dataclasses import asdict
from pathlib import Path

import app
from sqlalchemy import create_engine, event, make_url


def main() -> None:
    mode, target, output = sys.argv[1:]
    current_scripts = Path(__file__).resolve().parent
    package = types.ModuleType("_inlet_current_restore")
    package.__path__ = [str(current_scripts)]
    sys.modules[package.__name__] = package
    boundary = importlib.import_module("_inlet_current_restore.inlet_restore_historical")
    boundary.require(os.environ.get("INLET_RESTORE_HISTORICAL_CHILD") == boundary.PIN)
    source = Path(os.environ["PYTHONPATH"]).resolve()
    boundary.require(Path(app.__file__).resolve().is_relative_to(source))
    from scripts import inlet_restore_drill as historical

    boundary.require(Path(historical.__file__).resolve().is_relative_to(source))
    boundary.require(mode in {"native", "fixture"})
    if target.startswith("/"):
        boundary.require(mode == "fixture")
        engine = create_engine("sqlite:///" + target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        url = make_url(boundary.validate_disposable_url())
        engine = create_engine(url.update_query_dict({"options": f"-csearch_path={target}"}))
    try:
        print("STAGE=guard", flush=True)
        before = boundary.guard(engine, mode)
        print("STAGE=producer", flush=True)
        historical.seed(engine)
        print("STAGE=bootstrap", flush=True)
        boundary.unchanged_bootstrap(engine, before)
        print("STAGE=lineage", flush=True)
        result = boundary.read_ids(engine)
        print("STAGE=output", flush=True)
        Path(output).write_text(json.dumps(asdict(result)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("synthetic historical child failed", file=sys.stderr)
        raise SystemExit(1) from None
