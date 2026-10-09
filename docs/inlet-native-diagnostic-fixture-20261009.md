# Native Diagnostic Historical Fixture Repair

Base `868a740`; reviewed proposal `7072524`. Implementation branch
`codex/native-diagnostic-historical-repair`, worktree
`/workspace/inlet-native-diagnostic-investigation`.

## Behavior

The existing mandate-bound native diagnostics tests could not reach read assertions:
`test_mandates.seed` called current `mandates.approve`, correctly denied by the
planning-only capability boundary. One exact SQLite case reproduced that failure;
raw log/XML/exit are retained in the evidence directory below.

The new closed `native_diagnostic` historical producer mode uses the unchanged local
pin `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`. It calls pinned `ready` only to
create authentic approved mandates/consent and owned provider sources. It never
prepares or executes optimization. It asserts zero provider writes, attempts,
responses, receipts and reservations, returning immutable scalar identities only.
No runtime, authorization callback, credential or provider payload crosses the seam.

Current code checks returned fields against scoped persisted mandate, consent,
ledger, policy, actor and account; reconstructs the binding and runs CURRENT
`execution_mandates.checked`. All native collectors, original mandate-negative,
foreign-selection, currency, expiry, vault, source/session/role and post-HTTP
assertions remain current. Tests consistently use the returned engine, including
SQLite's separate current-schema file. The current advertising write boundary
is asserted before setup, after setup, and after reads; effects tables remain empty.

Existing review and initial-rule producer dispatch is unchanged. The exact pin,
local-tree verification, schema allowlists and subprocess bounds remain intact.
No capability monkeypatch, blanket retained-execution marker, production source
change, aggregate DB access, frozen W1 edit, live request or deployment occurred.
Google OAuth and search POSTs in current read tests remain semantic reads to local
MockHTTP; the historical producer makes zero provider writes/POSTs.

## Qualification

Evidence directory:
`/workspace/inlet-evidence/20261009/native-diagnostic-investigation/`.
The original failing single case is in `sqlite.log/xml/exit`. The repaired single
case is in `repaired-one.log/xml/exit`: 1 passed, zero skips/errors/failures,
JUnit 7.901 seconds, exit 0. Shared-dispatch compatibility is in
`compatibility.log/xml/exit`: 4 passed, zero skips, 82.01 seconds, exit 0.
The complete existing diagnostic module ran once on both databases:
`module.log/xml/exit`: **78 passed, zero failures/errors/skips, 499.84 seconds, exit 0**.
The single repaired case overlaps the full module and is not an additional unique test.

Disposable PostgreSQL uses only task-owned
`inlet_w1_20261008_gates_09a55cf2_ci` on loopback55432, with separate fixture schemas.
The exact two shared-dispatch compatibility functions are
`test_genuine_archived_producer_rows_use_current_lifecycle` and
`test_current_populated_0085_refuses_downgrade`, each SQLite/PostgreSQL.

Initial whole Ruff found inherited B009 in `tests/q16_clock_feasibility_probe.py:97`.
Its original `ruff.log/exit` is preserved. Parent-verified `fa2f1d3` was cherry-picked
as `9eab2d8`; final whole Ruff passes. Parent probe tests were not rerun here.
Bare mypy passes all 1118 source files, including after that unrelated correction.
Source/test changes stayed fixed throughout their active qualification runs.


Exact terminal commands (local venv PATH; disposable PostgreSQL variables as above):

```sh
python -m pytest tests/test_native_diagnostic_assembly.py --tb=short --junitxml=/workspace/inlet-evidence/20261009/native-diagnostic-investigation/module.xml
python -m pytest tests/test_retired_producer_current_lifecycle.py::test_genuine_archived_producer_rows_use_current_lifecycle tests/test_retained_initial_rule_lifecycle.py::test_current_populated_0085_refuses_downgrade --tb=short --junitxml=/workspace/inlet-evidence/20261009/native-diagnostic-investigation/compatibility.xml
ruff check .
mypy
git diff --check
```

After terminal qualification, changed only the diagnostic module docstring to
clarify genuine retained mandates plus current vault/HTTP readers. No tests were
repeated for that wording-only change. Final static checks and diff check passed.
This qualifies this existing read-compatibility module and the two selected
producer modes only; it does not make the frozen aggregate pass, enable writes,
qualify a live environment, or fix other historical fixture dependencies.
