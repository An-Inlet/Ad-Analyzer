# Reported Rule Customer Controls — 2026-10-07

Isolated branch `codex/inlet-operational-customer-ui`, based on dispatcher
`3cf2d8f` and frozen customer interface `94a103f` (local cherry-pick `689a580`).
This is an interface consumer checkpoint, not a configured automatic runtime or
live advertising qualification. The root integration and frozen Full checkout
remain unchanged.

- Candidate reads accept a separate operational reported-efficiency result and
  require its current server basis projection. Display inclusive account-local
  windows, exact reported spend/conversions/CPA without floating-point rounding,
  four-or-more report completions versus one original attempt, correction status,
  noncausal interpretation, nominal proposal and all supplied rule parameters.
- Explicit operational Start displays decision basis, parameters, cadence and
  lifetime, and posts its exact selected policy digest and existing mandate.
  Legacy Start bytes remain unchanged. No production policy is registered and
  the UI cannot make an unavailable backend available.
- Confirming a nominal adjustment never increases the overall spending limit.
  New campaigns and creative retain separate reviews. Unknown responses are not
  replayed. Original-session scope, Stop and owned history remain separate.
- A focused regression reproduced a same-user sign-in between actions sending
  a request using prior choices (one unexpected POST). The optimization page now
  remembers its initial session CSRF binding, rejects rotation before requests,
  and clears selections. Explicit Refresh establishes a new clean session.

Checks actually run on this checkpoint:

- `python -m pytest -ra tests/test_reported_rule_ui.py tests/test_candidate_read_ui.py tests/test_reported_rule_customer_contracts.py`:
  **7 passed in 1.71s**, zero skips.
- `python -m pytest -ra tests/test_session_automation_ui.py` with disposable
  PostgreSQL URL `inlet_oct07_next_integration_ci`: **2 passed in 16.28s**,
  SQLite and PostgreSQL actual TLS browser journeys. These validate legacy
  automatic compatibility; the new reported-rule route awaits backend assembly.
- Whole-repository `ruff check .`: passed; prescribed `mypy`: passed, 900 files.
- Node syntax checks and `git diff --check`: passed.

Next: independent review, configured reported-rule backend, then actual HTTPS
customer-to-worker paths including stale session, retraction and uncertain
responses. Do not relabel the DOM contract tests as actual backend or live proof.
