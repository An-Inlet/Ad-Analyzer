# A30 Producer Source Lifetime Followup

Base `41899ff`, branch `codex/inlet-a30-source-lifetime`. Adds only two closed
registry entries and extraction/runner wrappers: `tiktok_draft` and
`optimization_source`. Both use literal `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`,
fixed existing drivers, `source` leaf and `historical-source.tar`. The reviewed
SourceLifetime algorithm is unchanged. DTOs, genuine producers, current ownership,
source/media checks, no-effects assertions and teardown remain unchanged.

Qualification: **22 passed, zero failures/errors/skips, 83.502 seconds**: six
actual current read prerequisites (TikTok controlled/linked and Google optimization,
each SQLite/PostgreSQL) plus all sixteen source-lifetime boundary cases. Whole
Ruff passed; bare mypy passed, 1175 files; diff check passed. No intermediate
failure or retry occurred in this followup. Command:

```
pytest -q tests/test_tiktok_current_read_prerequisites.py tests/test_optimization_current_read_prerequisites.py tests/test_producer_source_lifetime.py --basetemp=/workspace/inlet-evidence/20261009/a30-source-lifetime/artifacts --junitxml=/workspace/inlet-evidence/20261009/a30-source-lifetime/qualified.xml
```

The existing disposable loopback PostgreSQL environment was used. Evidence lives
in `/workspace/inlet-evidence/20261009/a30-source-lifetime/`: raw log/XML, Ruff,
mypy, `source-scope.json` and `provenance-validation.json`. AST comparison verifies
the utility unchanged except registry and both helpers identical after stripping
only the lifetime import/wrapper/transitions/source-path assignment. Six actual
provenance records verify source removal, driver hash agreement and retained
sibling file hashes (IDs, logs, media, video input and SQLite where applicable).
Their inventories total 102,756,152 logical source bytes removed, not free-space
measurement. Current read assertions execute after source removal.

No generic runner/extractor/historical harness changes, retrospective cleanup,
aggregate rerun, provider calls or advertising writes. This closes the two known
A30 call-site omissions; it does not qualify whole-suite storage capacity.
