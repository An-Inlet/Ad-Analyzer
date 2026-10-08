# Planning Document Contracts — 2026-10-08

Branch: `codex/inlet-plan-document-contracts`, isolated from proposal `49484c4`.
Concrete design: `docs/design/comprehensive-planning-contracts-v1.md`.

Implemented pure immutable/revalidated document, exact goal/input, evidence, target,
action, alternative scenario, creative brief, decision, manual assertion and typed
read-comparison contracts. Added fixed allocation and account-level empty-inventory
cases after root's early interface review. Explicit native decimal-major-unit proposals
and bidding values are unavailable; no coercion, guessed conversion or forecast.
No persistence/API/provider consumer/migration changes, no execution authority.

Checks actually run at final source state:

- `/workspace/inlet-venv/bin/pytest tests/test_planning_document_contracts.py`:
  **33 passed in 0.16s**.
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: passed, **1009 source files**.
- `/workspace/inlet-venv/bin/ruff format app/planning_documents tests/test_planning_document_contracts.py`:
  formatting applied; final checks passed.
- `git diff --check`: passed.

Earlier 24/28-case slices passed; intermediate Ruff long-line/style and mypy local
variable/test-dict typing errors were corrected before the final run. No broad pytest,
DB, browser, live-provider, recommendation-quality or production qualification claim.

Next gate: independent concrete interface review, including supported field coverage,
read-observation binding and exact input provenance. Persistence/API require reviewed
schema plus source resolver/current session/ownership/CAS/erasure interfaces. Root's
fixed synthetic quality cases at 25eb733 are composer acceptance inputs, not passed by
these structural tests. Catalog V2 5535021 was announced during final checks and remains
unimported pending its independent final review; references are conceptual bindings.

## Concrete Review Repairs

Successor: `codex/inlet-plan-contract-repair` at
`/workspace/inlet-plan-contract-repair`, from reviewed root `382895e`, with only
contract commit `e049a37` cherry-picked as `35aff00`. Predecessor remains unchanged.

Root target-location/contradiction findings and independent event-validation/native
fact-provenance P2s repaired: actual ProviderReferenceV1 reused; platform/parent/identity
congruence; same-setting/shared-owner contradictory proposals rejected; mandatory
concrete-event revalidation; exact available catalog binding for typed native facts;
read observation source/account/target/time structure and binding checks.

Final successor checks:
- `/workspace/inlet-venv/bin/pytest tests/test_planning_document_contracts.py`:
  **47 passed in 0.21s** (provider/export, contradictory fields/shared owners, aliases,
  event/nested-copy bypass, both typed fact families × three invalid evidence kinds,
  observation target/expiry, plus original contracts).
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: passed, **1019 source files**.
- `git diff --check`: passed.

Still pure schema work. No API/persistence, DB/browser/live test or quality claim.
Independent repair closure remains required before implementation dependencies.
