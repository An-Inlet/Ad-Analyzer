# Owned Requested Window Reader

Branch `codex/inlet-owned-window-reader`, worktree
`/workspace/inlet-owned-window-reader`, frozen reader contract base `c560717`.
Reviewed private contracts `1d373af` merged as `0859728` before qualification.

## Implementation

New `app/planning_documents/window_reader.py` prepares an owned, account-specific,
transaction-bound read context. Actual DB-only authority, source fence and catalog
binding checks precede completion queries. A supplied clock and database clock
bound catalog freshness; the caller supplies already resolved server-owned catalog
or receipt provenance and external identity freshness outside SQL. Exact TargetRef
membership includes native identity and snapshot selector; no name remapping.

Each cache use checks transaction state, current authority, catalog/source/privacy,
current pointer, a detached tuple of every completion scalar, and the full local
reporting pin. Loaded/supplied scalar mutations are checked before refresh. The
optional private pin-helper context shares the validated/indexed presence graph
with real read_current_with_presence and cached campaign originals. Legacy
manifest reads remain. Original V3/header bytes are preserved; only the frozen pure
projector derives a requested window. Typed known-data gaps remain distinct from
authority, scope and integrity failures. No broad exception-to-gap conversion.

The context is a context manager with idempotent close and observer cleanup on
preparation/entry failure. Root transaction changes, any nested transaction lifecycle
(including completed rollback/release), dirty/new/deleted ORM state and flush
attempts reject reuse. Close removes listeners, including on errors. Separate
transactions and accounts never share a context. The existing default
PresenceReadContext and all old pin-helper callers retain their None/default path.
No adapters, composers, policies, routes, settings, migrations or fixtures changed.

Raw SQL mutation or provider I/O during a slice remains prohibited caller behavior,
not a sandbox guarantee against arbitrary Python sharing the connection. The
reader owns no commit/rollback and must close before persistence or external I/O.
The caller retains final authority-age and original expiry checks. The new module
is not wired into customer generation; runtime v3 remains rejected.

## Qualification

The new tests use actual owned source/goal fixtures, real MockHTTP native collection,
real persisted reporting/sidecar storage and real legacy/V3 readers. The positive
fixture's sidecar is installed by the existing qualified-reporting SQL helper;
this is **not** a new raw provider-import qualification or a customer comparison
API claim. No constructed ready evidence bundle, bypassed authority, or invented
SQL table is used. Existing source generation/manifest/immutability guards remain.

The initial 54 SQLite/PostgreSQL cases cover positive selected counts, real three-platform
legacy absence, one presence parse across the pin and repeated original/projection
reads, equality with the uncached pin, transaction/nested/flush invalidation and
cleanup, loaded completion mutations, source/mapping/privacy/session changes,
corrupt presence, absent current state, exact selector/expiry/callback checks, and
a SQL ordering assertion that failed authority never queries completion tables.
Loaded scalar tests use set_committed_value in memory, not disabled immutable
triggers. Persisted source/race tests occur before a fresh context; they do not
claim same-connection raw SQL writes are safely supported during cache reuse.

Initial new module: **54 passed in 89.36 seconds**, no skips. Initial whole Ruff
passed. Initial mypy found two test-only explicit-export references; imports and
monkeypatch target were corrected. No production change was needed for those
static errors. Final whole Ruff passed; bare mypy passed **1,097 source files**;
git diff --check passed. Final compatibility cohort: **118 passed, 0 skipped,
16 expected adversarial unsafe-copy serializer warnings in 171.34 seconds**.
A supplementary actual foreign-workspace/source-binding test was added after the
cohort collected: **2 passed, 54 deselected in 4.61 seconds**, both databases.
The final static checks were repeated after that addition and passed. No new
production changes occurred during qualification.
The preliminary and final cohorts overlap and must not be summed.

Commands (approved disposable PostgreSQL URL/flag supplied; isolated fixture schemas):

```text
pytest -o addopts='' -q tests/test_owned_window_reader.py --maxfail=1 --junitxml=.../initial.xml
pytest -o addopts='' -q tests/test_owned_window_reader.py tests/test_planning_retained_sources.py tests/test_planning_qualified_reporting.py --junitxml=.../final.xml
pytest -o addopts='' -q tests/test_owned_window_reader.py -k actual_foreign_workspace --junitxml=.../foreign.xml
ruff check .
mypy
git diff --check
```

Raw initial/final/supplementary (`foreign`) log and JUnit files live in
`/workspace/inlet-evidence/20261008/owned-window-reader/`.

## Remaining Work

Independent review and parent integration are required. This package does not
activate v3 or provide customer requested-window/comparison support. Adapter/final
recheck/composer integration, actual import→requested-window API acceptance,
public comparison output and UI remain separate. The current reader tests use a
single-day positive persisted graph and an outside-window known gap; multi-day
projection/DST semantics belong to the already separate pure projector qualification,
not an implied new 56-day import acceptance here. No latency benchmark, Full suite,
remote/hosted run, live provider request, ad mutation or deployment ran.
