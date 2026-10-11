# Injected Google Reporting Catalog — 2026-10-11

Local branch codex/inlet-selected-catalog, base6f47ce5; interface7abce7f.
Implementation: app/google_connections/selected_catalog.py; tests:
tests/test_google_reporting_catalog.py. No progress.md change.

Provides strict original-session/scoped catalog contracts and actual injectable
v24 HTTP search parsing. Reads account identity/units and complete bounded ENABLED
action pages, preserving all observed types/categories. Two explicit metric options
per action; opaque IDs bind scope/actor/session/label/family/profile. No default
choice, publication custom-goal inference or cross-account action ownership.
Complete-result256KiB bound can reject fewer than1000 actions; never truncates.
No SQL schema, storage, route, default factory, customer resolver or live access.

Checks actually run on final source:
- pytest tests/test_google_reporting_catalog.py tests/test_google_selected_http.py:
  43 passed, no skips. Actual MockTransport only; wrong owner/units/status, repeated
  rows/cursors, HTTP failures, result/body bounds, copied DTOs, exact option identity,
  blocking authorization expiry, finalization and trickling-stream closure covered.
- Ruff check of implementation/test: pass; Ruff formatting applied.
- mypy of implementation/test (scratch cache): success, 2 source files.
- git diff --check: pass.
No broad baseline, DB tests, provider/network calls, hosted checks or push.

Durable XML/logs: /workspace/inlet-evidence/20261011/google-selected-catalog/.
Preflight workspace1532MiB/scratch5915MiB/memory13507MiB available; after focused
work workspace1522MiB/scratch5890MiB; requested reserves maintained. Caches in /tmp.

Remaining: actual v24 query/API compatibility and live qualification remain
unverified; required developer-token constraint preserved. Scope provenance still
requires server original-session/vault resolver; DTOs do not prove authorization.
Separate customer confirmation/invalidation+0091CAS and full aggregate-range
acquisition/selected capture finalization/consumer work remain. No Q01/Q02 acceptance
or provider snapshot atomicity is claimed. Root's separate explicit invalidation
contract supersedes earlier same-request privacy transition proposal.

## Review Repairs

Parent found the private session digest still serialized and same-ZoneInfo wall-time
comparisons were unsafe across DST folds. Both are repaired: excluded serialization
with explicit private domain commitment, strict aware instants normalized to UTC,
and UTC-normalized injected clock. Normal JSON cannot reconstruct private DTOs without
independently authenticated session data. Reviewer also found native resource/owner
strings accepted copied bytes; both now strict and regression-covered.

Latest focused run: 52 passed, no skips (catalog+existing selected HTTP); scoped
Ruff/mypy (2 files) and diff check pass. Evidence review-freeze.xml/.log,
review-freeze-mypy.log and review-fix-ruff.log in the same durable directory.
Original f3f7f9 evidence remains intact. Intermediate review-fix.log retains one
regression-test missing-UTC-import failure, repaired before final run. No runtime
activation, external calls, customer routes or storage changes.
