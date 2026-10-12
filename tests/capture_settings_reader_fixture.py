"""Prior strict plan DTO probe, not a complete old-image rollback drill."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from app.planning_documents.documents import PlanVersion


def assert_prior_plan_reader(document: PlanVersion, path: Path) -> None:
    source = Path("tests/fixtures/selected_provenance/pre-settings-documents.py.txt")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "f9bf09947a7f6957eac204debe1cc8928bc0709f7f6097342109b9f1f7ea997a"
    )
    payload = path / "new-plan.json"
    payload.write_text(document.model_dump_json())
    script = path / "prior_plan_reader.py"
    script.write_text("""
import json,sys,types
from pathlib import Path
root=Path(sys.argv[1]); fixtures=root/'tests/fixtures/selected_provenance'
name='app.planning_documents.documents'
module=types.ModuleType(name);sys.modules[name]=module
source=fixtures/'pre-settings-documents.py.txt'
exec(compile(source.read_text(),str(source),'exec'),module.__dict__)
legacy=json.loads((fixtures/'pre-settings-plan-v2.json').read_text())
assert module.PlanVersion.model_validate(legacy).model_dump(mode='json')==legacy
new=json.loads(Path(sys.argv[2]).read_text())
try:module.PlanVersion.model_validate(new)
except ValueError:pass
else:raise AssertionError('old plan reader admitted new format')
print('PASS prior plan2 exact; actual new plan3 refused')
""")
    result = subprocess.run(
        [sys.executable, str(script), str(Path.cwd()), str(payload)],
        env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS prior plan2 exact; actual new plan3 refused"
