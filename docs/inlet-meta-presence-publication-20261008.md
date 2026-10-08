# Original Meta Window Presence — 2026-10-08

Branch `codex/inlet-meta-presence-publication`, base `9ec74d8`.

Migration0090 adds one ephemeral owned window-context table and paired nullable
presence fields on existing campaign staging. Frozen SQLite/PostgreSQL DDL matches
model guards: immutable context, owned window/source/event binding, paired fields,
scoped token FK, native campaign/day binding and bounded canonical payloads. Existing
numeric columns, row identities, query descriptors and legacy manifests are unchanged.
Populated downgrade refuses; legacy both-null staged rows survive empty-context
downgrade/re-upgrade with their numeric values intact.

Actual new-window assignment captures original metadata before the first token/page
I/O. In-progress legacy windows and resets retaining dates never adopt a context.
Original response rows feed the reviewed pure parser. Missing selected metrics stay
missing, explicit zero stays present zero, and count/value presence is independent.
Qualified partial/corrupt graphs fail; persisted both-null rows cannot gain provenance
on retry. Identical complete page retries remain supported.

Rolling and fixed terminal paths capture the complete staged graph before deletion,
then publish legacy metrics/current pointer and finalized presence against the exact
returned completion in one transaction. Caller locks, authority and rollback remain.
No helper commits or new provider requests. Fixed-window testing restores both default
advertising write-denial guards before all import pages, proving no new execution
attempts or native mutations beyond its explicit historical setup.

The reviewed terminal privacy distinction is intentional: capture checks original
privacy; actual calibration invalidation may advance the ordinary export revision.
The final header uses the returned completion revision, while the immutable context
retains its original revision and must still exist exactly at attachment. Semantic
privacy erasure deletes context/stages and prevents prepared-graph resurrection.
Detail checkpoint cleanup does not delete campaign presence. Reconnect, campaign
reset, fixed abort and semantic erasure use child-before-context cleanup.

Ephemeral context and staged presence payload/token are explicitly private archive
omissions. Existing numerical staging export policy is preserved. No new worker or
queue family is introduced. Finalized historical presence export remains0089 behavior.

## Validation

Executables `/workspace/inlet-venv/bin/`; commands in this worktree. Both-DB tests use
`AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci`
with `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`, isolated schemas only.

Final affected cohort:

```
pytest -q -o addopts='' tests/test_meta_presence_publication.py tests/test_meta_connection.py tests/test_meta_detail.py tests/test_meta_detail_scheduler.py tests/test_model_registry.py -x --tb=short
```

**105 passed, 1 expected SQLite skip, 7 existing Alembic configuration warnings,
113.99s.** No failures or deselected tests. The skipped case is PostgreSQL-specific
compound ownership/migration acceptance; its PostgreSQL parameter passed.

Additional executed checks:

- Original Meta connection suite:18 passed4.17s.
- Actual0090 DDL/scoped FK/downgrade checks:2 passed3.43s after enabling SQLite FK
  enforcement in that migration fixture (first run's disabled FK caused one failure).
- Actual terminal calibration privacy/semantic erasure:2 passed4.77s; its first
  fixture used an expired calibration, which correctly did not advance the counter.
  The corrected fixture uses real future expiry without changing runtime clocks.
- Fixed read-import wrapper:2 passed6.17s. The unadapted historical acquisition test
  stopped at the planning write guard in setup; the bounded setup-only override is
  explicitly local, restored before actual import, not a suite-wide bypass.
- Persistent-stage tightening and positive/retry checks:20 passed16.26s; final actual
  retry/integrity subset8 passed9.43s.
- Whole `ruff check .` passed; configured `mypy` passed1082 source files.
- `git diff --check` passed.

Two earlier expanded cohorts stopped after71 and98 passes at old0029/0040 downgrade
fixtures, respectively: real new imports now create presence and correctly trigger
0089/0090 populated refusal. Those two migration-specific fixtures now explicitly
model pre0090 in-progress windows and assert absence of presence. All other import
fixtures still exercise actual new windows. No production guard was weakened.

Actual tests cover constructed read-only HTTP requests through new-window terminal
publication,100click/10selected/$100, zero/missing/empty/non-selected entries, independent
count/value, partial-page resume, exact and conflicting duplicates, empty returned
rows, late-failure rollback, original generation/event/money/privacy/window drift,
reset no-adoption, fixed coverage preservation, semantic erasure, private export
classification, DDL and legacy numeric/child publication compatibility. This is
local offline producer qualification only: no Full suite, live provider validation,
new API behavior, customer planning qualification, model calls or deployment.
