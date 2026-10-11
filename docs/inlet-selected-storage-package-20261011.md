# Selected Reporting Storage — 2026-10-11

Local package based on `df93f86`, branch `codex/inlet-selected-storage` in
`/workspace/inlet-selected-storage`. Migration 0091 follows 0090. No public API,
provider call, default runtime activation, retention extension, remote push or
advertising mutation is included.

## Implemented

Four scoped tables retain immutable customer selection, explicit current head,
capture header and complete campaign/day facts. Composite ownership FKs,
canonical payload commitments and immutable triggers apply on SQLite/PostgreSQL.
Internal readers recheck actual active source/integration, generation, native
account, currency/timezone, privacy, exact current completion and whole manifest.
Missing values remain missing; observed zero remains zero.

An explicit invalidation transition marks the head, removes dependent captures and
account calibration outputs, and advances the existing privacy fence. The caller
commits before genuine aggregate refresh and explicit reconfirmation. Exact CAS
requires a new immutable selection at current privacy; raw active pointer changes
and stale A→B→A readoption fail. Repeated invalidation is idempotent.

Raw fact deletion retracts the entire capture graph and fences exports; PostgreSQL
uses a workspace NOWAIT guard. Semantic privacy erasure removes all four tables.
The lifecycle registry is explicit, export validates full historical graphs and
labels them historical, and a bounded single-capture index prevents per-fact
quadratic revalidation. Archive snapshot and delivery privacy checks remain active.
Populated downgrade is refused, rather than discarding retained customer data.

## Validation And Evidence

Durable evidence root:
`/workspace/inlet-evidence/20261011/selected-storage/`.
Every invocation has its own basetemp, run.log and results.xml. SQLite is local;
PostgreSQL uses the existing `customer_engine`/`export_engine` random-schema fixtures
on the explicitly disposable local test database. No original schema/database was
reset. Commands use `/workspace/inlet-venv/bin` and the established disposable-PG
test environment, with `--durations=20`.

- `pytest -q tests/test_selected_storage.py`: final07 **30 passed**, 33.226s,
  no skips. Includes actual Meta terminal aggregate import, strict currentness,
  replay, CAS, immutable rows, raw deletion, real-refresh reconfirmation, frozen
  migration parity/upgrade/populated downgrade refusal, export and actual PG locks.
- Compatibility command: selected later-fact rollback case plus
  `tests/test_selected_reporting_contracts.py`,
  `tests/test_reporting_presence_storage.py`, `tests/test_model_registry.py`:
  compat08 **101 passed / 4 failed**, 46.852s. Two failures were a new malformed
  two-fact test failing earlier Pydantic one-to-one validation; corrected to a
  separately identified missing second campaign, preserving partial-insert rollback.
  Two found a real missing `invalidated` export allowlist field; fixed.
- repair10: those rollback cases, platform ownership cases and existing actual
  archive completeness/privacy cases: **6 passed**, 16.235s, no skips.
- Existing campaign-platform FK already blocks mutation while metrics exist, and
  the account-platform FK independently blocks it after metrics are removed.
  Tests retain these constraints; defensive full-graph/fact platform checks remain.
- PostgreSQL NOWAIT/concurrent CAS test returns early on SQLite; that is not a
  claim of SQLite row-lock behavior. No suite skip or guard suppression was added.

Retained earlier failures: sqlite01 invalid fixture attribution; sqlite02 fixture
FK enforcement absent; bothdb03 missing test import; bothdb04 SQLite quoted boolean
default (fixed with SQL false()) and refresh fixture incorrectly expecting no old
current pointer during staging; final06/platform09 demonstrated existing platform
FK protection; archive11 omitted actual export claim in its new harness. Their
logs/XML remain intact. Early Ruff/mypy diagnostic logs are also retained.

## Remaining Obligations

These are internal ports, not customer authentication or catalog authority. Public
callers must establish and recheck the original session and owner membership and
acquire the existing workspace/account fences. No event catalog or actual selected
provider query is supplied here; synthetic selected facts are tested over a genuine
mock-HTTP aggregate import. Source selection HTTP staging, customer confirmation,
retry UX, calibrated consumers and live qualification remain separate work.
No historical selection or completion privacy is rewritten to regain currentness.

Final actual selected archive: archive13 **2 passed**, zero skips, both databases.
The test claims a real lifecycle export, builds the archive containing all four
selected tables, verifies complete supported-data metadata, then deletes a raw fact
and proves the prepared authority is invalidated. archive11 first lacked the test's
export claim; archive12 exposed global `request_digest` filtering from the SELECT.
The final fix adds only this table's validation field, preserving exact row equality.
Its exported request digest is explicitly the public canonical selected-document
commitment already present in the document, not a customer request/session token;
the global secret/internal allowlist is unchanged. Wrapper-only oversized sentinel
is removed before exact stored-row validation. Both failed runs remain preserved.

Final static commands: `/workspace/inlet-venv/bin/ruff check .`,
`/workspace/inlet-venv/bin/mypy`, and `git diff --check`. Ruff passed; mypy passed
**1,289 source files**. Final static logs are `ruff-final14.log` and
`mypy-final14.log`. No broad Full/aggregate was run.

Reproduction: use the established disposable `customer_engine`/`export_engine`
fixture environment and run `pytest -q tests/test_selected_storage.py
--durations=20 --basetemp=<new durable directory>/tmp
--junitxml=<new durable directory>/results.xml`, redirecting output to that new
directory's `run.log`. Existing evidence directories must never be reused. The
parent will run the additional assembled new-parser/summary/HTTP/export cohort.
