# Durable Planning Feedback Regression — Stage 2

Branch `codex/inlet-reported-planning-durable`, base `9b90e0c` (reviewed relative
source and exact owned SQLite boundary). New default-collected tests only. No
production edits, shared helper changes, dated probe changes or original28 consumer
adaptations in this package.

`test_reported_feedback_planning_consent.py` runs five modes on both databases:
actual initial V2 preview/PlanningConsent to valid reported feedback46m→47m;
revoked session401; stale configured planning policy409; real prepared cap rejects
47m; native quantum rejects unrepresentable1microunit adjustment. Failures leave
zero feedback slot/current pointer. This is lasting regression for `cc02905`'s
existing checked_planning_limits substitution; no execution consent on new reference.

`test_reported_feedback_planning_api.py` runs three modes on both databases:
ordinary actual login with unchanged TTL; actual comparison POST, initial V2 POST,
committing comparison GET and feedback POST; successful46m→47m/no-store plus401
revocation and409stale planning policy with zero slots. The relative authentic
original makes the real request already due. No issue_at, date assertion, API/customer
access namespace replacement or global clock mutation is present. Actual identity,
DB freshness floor and authority checks remain. Runtime injection supplies configured
server-owned runtime only, as in the reviewed dated HTTP seam; this does not claim
configured-runtime factory coverage from test_planning_runtime_assembly.

The existing acquisition fixture's explicit1+61+1-second repeat cadence remains.
Thus this is durable ordinary-login HTTP contract evidence with synthetic offline
acquisition clocks/data, not a live-provider/browser or completely wall-clock-paced
workflow. Strict outer graph checks preserve the original same-period ledger, caps,
one50m→45m MockHTTP effect/receipt/40mhold, and only the exact approved current
planning draft/confirmation. Current native traffic is GET only. Existing dated
October probes and all original failure assertions remain unchanged.

## Checks

Evidence: `/workspace/inlet-evidence/20261009/reported-planning-durable/`.
Collection: `pytest --collect-only -q tests/test_reported_feedback_planning_consent.py tests/test_reported_feedback_planning_api.py`
=>10service+6HTTP nodes (`collection.log`).

With disposable localhost PostgreSQL URL/flag and isolated schemas:
`pytest -q tests/test_reported_feedback_planning_consent.py tests/test_reported_feedback_planning_api.py --basetemp=/workspace/inlet-evidence/20261009/reported-planning-durable/qualified-artifacts --junitxml=/workspace/inlet-evidence/20261009/reported-planning-durable/qualified.xml`
=> **16passed,0failures,0skips,189.649s**, first invocation (`qualified.log/xml`).
All producer IDs, logs and SourceLifetime manifests remain; extraction copies were
removed by the reviewed bounded lifecycle, not arbitrary deletion.

Whole `ruff check .` and bare `mypy` passed (1,188files), `ruff.log`/`mypy.log`;
`git diff --check` passed. No source edits after those checks except this ledger.

To preserve disk capacity, only ignored/untracked regenerable mypy caches from
completed API/relative worktrees were inventoried and removed; inventory
`completed-mypy-cache-inventory.json`,84,767,168logical bytes. All source, active
cache, logs/XML/IDs/databases were retained.

This closes the missing durable regression evidence for the narrow planning-consent
fix, subject to review. It contributes no original failed-node recovery credit and
is not a full-suite result. Next: exact28-node consumer fixture proposal and explicit
defer/include mapping for separate configured-runtime10; no silent scope expansion.
