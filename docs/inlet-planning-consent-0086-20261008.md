# Planning Consent Integration And Early Route Denial

Frozen interface: `326ffc4`, `docs/design/planning-consent-0086.md`.
Worktree `/workspace/inlet-planning-consent-integrated`, branch
`codex/inlet-planning-consent-integrated`. Ancestry is root `beb761d`, customer
package `fec7286` (cherry-pick of preserved `fea1cf6`), interface `326ffc4`, and
annotation-only root correction `a5c466d` (cherry-pick of `b93661d`; root status
document retained in a modify/delete conflict). Root execution-consent, admission
and worker guards are present in this actual test base. Sink followups remain for
root assembly; no live operations, credentials, hosted tests or deployment.

## Closed Integration Defects

1. Customer blocked routes now declare authenticated/scoped decorator dependencies
   before function Runtime/Store dependencies. Mutating intents validate session,
   origin/CSRF and owner; GET execution options validate session and owner. Both
   dependency and direct-call body guards use the unconditional shared boundary.
   Actual HTTP tests inject forbidden runtime/media factories and prove zero calls
   across all guarded routes, including unauthenticated-role/CSRF denials. Existing
   history, local Stop/revoke and read-only reconciliation are not globally gated.
2. Initial planning budget confirmation no longer invokes execution consent.
   Migration0086 adds an independent workspace-scoped confirmation with exact
   preparation/revision FK, policy/preparation digests, confirmer, time and its
   own commitment. INSERT binds the owned protected preparation/revision; UPDATE
   is denied and DELETE is allowed. Populated downgrade refuses data loss.
   Confirmation creates no ProviderExecutionConsent and leaves the mandate draft.
   API/UI use `confirmed`, `planning_only=true`, `spending_authority=none`.

The new planning checker returns policy as limits data, never an execution binding.
It rechecks current authenticated ownership, active original confirmer, exact
current draft revision, preparation commitments, pinned profile/operating-policy
identity, goal definition/revision/assessment, owned account/source generation,
existing billing gates and the current period. It has no execution consent fallback
or financial admission/exposure/accounting gates. A later legitimate login may use
planning limits. Preview original-session fences remain as before. A departed
confirmer invalidates that confirmation with409 so unrelated valid native options
are not denied as if the current caller lost access.

Native options enumerate current draft revisions with planning confirmations.
Both preview amount paths and final preview read use the new checker. Historical
execution review/Start bridges remain blocked, never converted to planning
permission. Legacy execution-backed preview fixtures must be adapted explicitly;
the draft/current-revision/no-fallback checks were not weakened to accommodate them.

Lifecycle classifies the new row as workspace-owned scalar export and deletable,
not financial retention or queued work. Tests cover actual authenticated archive
inclusion and scoped registry deletion plus SQL immutability/ownership constraints.
This is not a completed end-to-end workspace-erasure workflow claim.

## Exact Checks And Results

All commands run from this worktree, using `/workspace/inlet-venv/bin/python`.
Both-DB commands set the approved existing disposable localhost PostgreSQL URL
for `inlet_oct07_next_integration_ci` and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`;
fixtures create isolated schemas, never reset the database. Capability guards are
unpatched in these planning tests. No suite-wide or new historical bypass added.

- Early dependency-order cohort:
  `python -m pytest tests/test_planning_customer_boundary.py -k 'not filters' --durations=3`
  **6 passed, 2 deselected, 8.38s** (both databases).
- First integrated consent API/TLS proof:
  `python -m pytest tests/test_budget_mandate_api.py::test_first_customer_mandate_and_preview tests/test_initial_budget_mandate_browser.py -k sqlite --durations=3`
  **3 passed, 3 deselected, 11.16s**.
- Main focused both-DB cohort:
  `python -m pytest tests/test_planning_consents.py tests/test_planning_consent_migration.py tests/test_budget_mandate_api.py tests/test_initial_budget_mandate_browser.py tests/test_planning_customer_boundary.py tests/test_customer_exports.py::test_supported_schema_has_explicit_field_dispositions --durations=8`
  **45 passed, 2 failed, 1 warning, 99.87s**. The two failures used the unsupported
  synthetic Meta state `disconnected`; SQL correctly rejected it. Test fixture
  corrected to the real `reconnect_required` state. Raw log:
  `/tmp/inlet-planning-consent-checks.log`.
- Narrow final both-DB followup after that fixture correction and stronger
  assertions (distinct current owner versus suspended original confirmer,
  exact-repeat actor/time/digest invariance, real authenticated archive,
  preview reread and refreshed planning-native options):
  `python -m pytest tests/test_planning_consents.py tests/test_planning_consent_migration.py tests/test_budget_mandate_api.py::test_first_customer_mandate_and_preview -k 'source or confirmer or real_0086 or first_customer' --durations=6`
  **8 passed, 12 deselected, 1 warning, 27.22s**. Raw log:
  `/tmp/inlet-planning-consent-followup.log`.
  All **47 distinct focused cases** passed across these runs. The warning is
  Alembic's existing `path_separator` deprecation.
- Final `ruff check .`: passed. Final `mypy`: passed, **992 source files**.
- `node --check app/portal/static/initial-planning.mjs` and browser driver:
  passed. `git diff --check`: passed.

Actual HTTPS Chromium/API tests preserve report capture, calibration, native
GET-only reads, explicit unchecked planning confirmation, non-authorizing preview,
changed-input/session invalidation and unavailable-policy messaging. They assert
no execution controls/requests, no provider mutation POSTs, no execution consent,
attempt or hold; stored execution mandate stays draft in API acceptance.
Migration0086 descends from0085; previous0085 tests/DDL remain unchanged. Existing
schema-head assertions are dynamic and not pinned backward.

## Remaining Qualification

Independent implementation review and root assembly with final provider sinks are
required. No Full suite pass claimed. Existing execution-heavy initial-preview/API/
browser fixtures now need deliberate historical test partition/adaptation; only
root's existing explicit six-module historical engine opt-in is inherited. General
Google/Meta/TikTok native planning catalog remains separate P02 work. Existing
preparation still uses draft execution-policy storage/zero-use ledger scaffolding;
this package removes authority creation without claiming that storage has already
been fully separated from the historical execution schema.
