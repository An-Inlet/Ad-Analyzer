# Planning MVP Provider Transport Boundary

Base1c7e30d; isolated branch `codex/inlet-planning-transport-boundary`.

All11 concrete publication/activation/optimization `apply_once` implementations call the immutable shared `app.advertising_capabilities.require_advertising_write` before context checks, reads, credential resolution or HTTP. Five final HTTP sinks independently allow only explicit semantic reads; Google lazy publication override applies the same classification before runtime resolution. Google mutation validation requests are denied even with validateOnly. There is no production setting, mock-transport exemption or global test bypass.

Read classification preserves Google POST googleAds:search/searchStream (existing lower transport restrictions still apply), Meta v26 object/adset/image GETs, and TikTok v1.3 campaign/adgroup/ad/advertiser/file-info GETs. Unknown endpoints/methods, query/header method overrides and GET bodies/forms/files are denied. Google publication rejects customer identifiers that could change URL routing. OAuth/connection/import transports are not globally intercepted. Existing context/path/privacy checks remain.

The coordinator/worker policy is a separate root-owned integration. These transport guards do not supersede tenant, session, billing, ownership, provenance or financial guards, and do not release retained obligations. Historical execution suites now need explicit local test-only capability patches if exercised; this package adds none. Denial is outside adapter uncertainty catches.

Validation actually run:

- `python -m pytest tests/test_planning_provider_transport_boundary.py tests/test_google_catalog_http.py tests/test_google_native_inventory.py`: **113 passed in0.89s** (49 new default-policy cases,64 retained read regressions).
- `ruff check .`: passed.
- `mypy` without narrowed arguments: passed,984 source files.
- `git diff --check`: passed.

Mock HTTP only; no live/provider calls, deployment or Full. Raw final logs retained at `/workspace/inlet-evidence/20261008/planning-transports/`. An initial test collection failure from a mistaken linked class name and initial test-only type errors were repaired before this final cohort. No claim is made that these focused passes qualify the complete planning deployment.
