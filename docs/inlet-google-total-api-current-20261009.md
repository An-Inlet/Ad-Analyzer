# Current Google Total-Envelope API Regression

Approved staged interfaces: `ef5cf24` / `71adde9`; independently reviewed source
stage `45b8140`. The original20 total-envelope cases remain current tests, with
all ten parameter values unchanged. No historical20 batch is added and no
existing361 historical cases are rerun. No production/API/financial-source or
capability implementation changed.

The original `created` helper remains AST-identical but runs only inside the
verified original source child. Current tests rebind ordinary replica database
dependencies to that owned source, use actual normal same-actor login and prove
a new session plus unchanged issuer/subject. The current customer diagnostic
router uses only explicit offline OAuth settings, its genuine stored encrypted
grant and the original native MockHTTP callbacks; no execution runtime is supplied.
Every actual MockHTTP request must be OAuth token POST or Google search POST.

The post-setup original body is factored into `current_envelope_body`. All original
session/generation/late-expiry callbacks, expected statuses, no-read assertions,
matching/drift/unavailable output, exact totals, null financial upper bound,
no-spending-authority, observation expiry and hold comparisons remain current.
AST evidence preserves12 of13 original assertions exactly, plus the untouched
parameterization/helper. The one replaced assertion is `server.posts == writes`:
the parent does not have or fabricate an original server. Instead it verifies
the measured source count2, forbids mutation HTTP at the actual current transport,
and compares the entire financial/provider graph across the current HTTP read.

## Exact Intentional Unknown Receipt

Only `expected_unknown=True` with mode `total_created` may permit a delta in the
source context. It verifies exactly one new receipt on the original **budget**
attempt, next sequence, original supersedes pointer, exact unknown(request,
dispatched_at) body/fingerprint/observed time and current normalized projection.
Only the original run.state and budget step.state become `unknown`. Every prior
receipt, other step, response, attempt, completion, hold and all other captured
financial/provider fields remain exact. Physical schema remains exact too.

The consumer snapshots again after this intentional original test adversary;
the subsequent envelope read changes no financial row. No privacy/candidate
invalidation exception or completion deletion was necessary. Four new pure
argument guards reject nonboolean options and an unknown allowance in either
daily mode before any I/O.

## Evidence

Raw evidence: `/workspace/inlet-evidence/20261009/google-total-api20/`.
All pytest basetemps are unique explicit `/tmp/inlet-google-total-*` roots;
logs/XML/proof JSON remain outside them. No default pytest temp rotation.

- Source qualification is separately recorded in
  `docs/inlet-google-total-source-20261009.md`:82 passed, including actual bothDB
  total source and existing daily compatibility.
- Actual current `None` and `unknown` cases on SQLite/PostgreSQL:
  **4 passed, 37.34s**, `api-probe.log/xml`, basetemp
  `/tmp/inlet-google-total-api-probe-01`. Original process exit0 and XML confirmed
  after the environment callback; no interruption or duplicate run occurred.
- Initial full mypy reported one test-helper import-export error:
  `coordinator.utc` is not explicitly exported. Changed to the direct existing
  `app.shopify.security.utc` import; behavior and allowance unchanged. Original
  `api-initial-mypy.log` retained. No pytest failure or contract mismatch so far.

The stronger `assertion-proof.py/json` additionally normalizes only the enumerated
source resource/count assignments and newly added boundary assertions, then
compares the **entire** original post-setup body AST. It matches. The historical
server counter is not presented as a mutable current-provider observation.

Final qualification: **148 passed, 222.18s, zero skips/failures/errors**,
`api-qualified.log/xml`, `/tmp/inlet-google-total-api-qualified-01`:

- Entire current total-envelope module20 (all ten cases × SQLite/PostgreSQL).
- Unchanged unpatched execution35 + transport51 boundaries =86.
- Source path/closed-allowance guards38.
- Existing daily completed/unknown current API compatibility4 (bothDB).

Command: `pytest -o addopts= -q tests/test_google_total_envelope_api.py
 tests/test_planning_execution_boundary.py tests/test_planning_provider_transport_boundary.py
 tests/test_google_created_source_guards.py` plus exact closing/unknown nodes of
`test_current_completion_privacy_and_unknown_hold` for SQLite and PostgreSQL.
The disposable PostgreSQL fixture environment remains the established loopback
configuration; no aggregate DB was accessed.

Whole `ruff check .` passed (`api-ruff.log`); bare mypy using `/tmp` cache passed
**1222 source files** (`api-mypy.log`), separately captured exits. Final diff check
passed. No additional pytest run was needed after terminal: only this ledger was
completed. Unique temp roots preserve actual source IDs, child logs, SQLite and
SourceLifetime provenance; no cleanup of failed evidence or another lane's files.

This qualifies the bounded current regression package, not live Google operation,
financial authority, aggregate health or comprehensive product quality. No Full,
hosted, live-provider or historical-suite rerun occurred.
