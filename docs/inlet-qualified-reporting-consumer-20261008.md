# Qualified Reporting Consumer And Planning Policy V2

Base `014db57`, isolated branch `codex/inlet-qualified-reporting-consumer`.
Concrete DTO and invariants: `docs/design/planning-qualified-reporting-v3-dto.md`.
No Meta, legacy campaign performance service, schema, migration or lifecycle edits.
This consumer package is separate from the original-window Meta0090 producer.

## Implemented

New owned SQL reader returns V3 only from a valid actual finalized sidecar graph.
It preserves unchanged legacy reporting separately and projects typed, bounded,
recomputed campaign presence summaries. Missing sidecars return legacy reports;
corrupt/partial sidecar graphs do not silently fall back. Explicit per-transaction
cache validates the whole graph once and indexes campaign/native mappings once.
Final checks use fresh contexts; no provider calls or commits occur inside these
reporting helpers.

Default descriptive policy/generator advance to v2. Actual evidence collection
pins complete legacy reporting plus canonical presence or explicit absence for
EVERY selected account, including unavailable/mismatched reporting. Final local
source checks require those same pins; exact persisted local_reporting_v2 witnesses
protect later advice/current reads. Old v1 witnesses and historical policy behavior
remain unchanged. PlanVersion and legacy report fields are not extended. Existing
pure composer tests now explicitly select their original v1 constants without
removing any assertions.

Positive selected counts retain useful observed clicks/spend and their coverage,
with event/window/count qualifiers. Only genuinely observed requested-window zero
produces a tracking/landing-page investigation; missing/partial zero is explicitly
unavailable/partial. No pause, transfer, forecast, causal claim or write authority
is introduced. Legacy evidence remains conservatively unqualified where appropriate.

## Actual Consumer Qualification

New tests use existing owned source/session/Shopify/native MockHTTP fixtures, then
actual `store_presence`, legacy/new SQL readers and customer create/generate/read/
artifact-export APIs. Sidecars are deliberately fixture-created, not claimed as
Meta imports. Tests cover positive100clicks/10selected/USD100, true observedzero,
missingselectedcount and partialpaginationzero on SQLite and PostgreSQL.

Additional actual API tests change evidence AFTER real collection: whole sidecar
deletion, sidecar appearance from pinned absence, corrupt incomplete graph and
original-session revocation. Each refuses generation without version, dependency
or generate-request records. Legacy v1 plan remains current when only new presence
is deleted; a viewer can read that historical document with no native HTTP calls.
Existing retained-source tests exercise current owner/viewer/session behavior under
new default policy as well.

DTO checks reject forged zero flags, summary/body mismatch, foreign/native pairs,
subset exceeding headercount and unsafe nested primitive coercions. Exact JSON
roundtrip preserves canonical count strings. Two actual campaigns share one graph
read and separate indexed projections; reused cache after rollback rejects.
Per-document capacity refusal is tested by reducing its bound, not allocating giant
fixtures. Aggregate reporting cap is enforced, not a maximum-volume performance
qualification. No synthetic generated bundle or composer/final-proof bypass is used
for the actual API acceptance.

## Checks

Commands use approved disposable PostgreSQL and isolated UUID schemas, with
`AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true` and executables in `/workspace/inlet-venv/bin`.

- Initial4-state actual consumer cohort: **8 passed,18.33s**.
- Extended new/API plus pure legacy composer/ports: **55 passed,35.97s**.
- Affected cohort:
  `pytest -q -o addopts='' tests/test_planning_qualified_reporting.py tests/test_planning_evidence_adapter.py tests/test_planning_retained_sources.py tests/test_planning_documents_api.py tests/test_planning_composer.py tests/test_planning_document_ports.py -x --junitxml=/tmp/qualified-reporting-cohort.xml`:
  **179 passed,0skips,290.84s**. This preceded final cache/strictness assertions;
  the final new-module run below covers those changes.
- Whole `ruff check .`: passed. Whole `mypy`: **1080 source files passed**.
- `git diff --check`: passed.

Initial new-test failures were fixture/assertion mistakes: outsider lacked login
(401), authenticated foreign workspace correctly returned404 rather than asserted403,
and revocation time used datetime instead of the persisted epoch integer (PostgreSQL
rejected). Corrected tests preserve actual behavior and auth rejection. Initial
static errors were variable/type/import annotations; final checks pass. No legacy
production behavior or authorization guard was weakened to satisfy tests.

Logs/JUnit retained outside git under
`/workspace/inlet-evidence/20261008/qualified-reporting-consumer/`.
No Full, remote, hosted, live provider, deployment or advertising-write operation.
Actual Meta import-to-plan proof belongs to the root combined producer/consumer
package after both are reviewed. Google selected-event and TikTok explicit-selected/
window producer qualification remain separate, unresolved protocol work. This is
not full Q01/Q02/Q09 or launch qualification.

Final changed-source/cache/DTO/API rerun:
`pytest -q -o addopts='' tests/test_planning_qualified_reporting.py -x --junitxml=/tmp/qualified-reporting-final.xml`:
**20 passed,0skips,46.16s**,16 expected Pydantic serialization warnings from deliberate
unsafe nested bytes/float copies that subsequently reject validation. Both database
variants and the new indexed two-campaign/transaction-refusal case passed. Whole
Ruff/mypy1080 and diff checks above ran after final production edits.
