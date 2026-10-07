# First Customer Budget Mandate Interface

Design proposal only, inspected at `02377c8`. No runtime, financial qualification,
provider execution, schema, or legacy preview behavior changes are proposed here.

## Observed Reachability

1. `app/api/customer_goals.py` exposes draft/edit/preview/confirm independently of
   provider execution. `GoalDefinition` already records budget, budget dates,
   currency/time zone, and named aggressiveness. Confirmation requires actual
   commerce measurement and current customer access; these are real prerequisites.
2. `app/api/customer_initial_planning.py` uses the configured read-only planning
   bundle. Capture/calibration and native options do not require a write runtime.
   Actual owned campaign reports, current calibration, paid access, enabled reads,
   profile and credentials remain necessary. A brand need not have a prior Inlet
   optimization attempt to use initial planning; reported feedback separately does.
3. Native options list existing active `ProviderExecutionMandate` rows.
   `preview_v2_service.amount` requires exact consent, goal/revision, current
   account/generation, currency/time zone and complete budget-owner target digest.
4. There is no ordinary configured way to create that first mandate:
   `/execution/mandates` calls `bound`, but `get_customer_execution_runtime()` returns
   None. `/optimization/mandates` calls `bind`, but its runtime getter also returns
   None. Existing optimization consent requires the qualified target catalog too.
   `/execution/mandates/{id}/consent` delegates optimization policies to that path.
   Both fail before local mandate preparation/consent can succeed.
5. B07 `/mandates` records simulated authority and cannot substitute for separately
   consented production policy. The configured journey fixture directly invokes
   `execution_mandates.revise`/`consent`; it proves preview assembly, not ordinary
   first-customer mandate onboarding.

This is a missing application interface, not evidence that provider write
qualification is required to *record* a customer's bounded conditional mandate.
An active local mandate still cannot bypass runtime, exposure, exact action review,
reservation, source or execution gates. It is not proof of available headroom.

## Proposed Additive Ports

Reuse `InitialPlanningRuntime` and its per-request `native_budget` factory. Do not
construct `CustomerOptimizationRuntime`, `OptimizationState`, qualification IDs,
financial evidence, or synthetic accounting periods. Keep all old getters unchanged.

New strict request models in `app/initial_planning/budget_mandate_contracts.py`:

- `BudgetMandateSelectionV1`: calibration_id, observation_id, native_option_id.
  The server derives objective, confirmed goal/revision, profile/environment,
  owned account/generation and complete native budget owner from existing readers.
- `BudgetMandateLimitsV1`: explicit total_cap_micros, per_plan_cap_micros,
  positive_change_cap_micros, action_limit, cooldown_seconds, freshness_seconds,
  aggressiveness_percent. No numeric defaults. Preserve current 5/10/20 model as
  declared inputs, not empirically validated policy or permission to raise a cap.
- `PrepareBudgetMandateV1`: selection, limits, optional mandate_id and
  expected_revision together for edit. Dates derive from the confirmed goal's
  budget_start/budget_end using its named zone and explicit exclusive-end semantics.
  Total cap must not exceed that confirmed goal budget. A higher cap requires a
  separate goal edit/reconfirmation and a new exact mandate consent.
- `ConsentBudgetMandateV1`: selection, expected_revision, policy_digest.
  The selection is a locator for fresh server reads, never trusted native proof.
- Response: existing policy_view plus native option label/affected-target count,
  explicit `execution_available=false`, `exposure_qualified=false`, and separate
  review/activation requirements. Do not relabel consent as launch readiness.

New service `app/initial_planning/budget_mandates.py`:

```
prepare_budget_mandate(db, principal, provider, body, runtime) -> policy view
consent_budget_mandate(db, principal, provider, mandate_id, body, runtime) -> binding
```

Both resolve existing calibration/observation through original-session owned
readers, invoke the actual GET-only catalog, rederive current inputs after HTTP,
then reauthorize the original principal under workspace/user/session/membership
locks. Native currency must be supported USD with exponent2; daily budget only for
this existing v2 amount path. Lifetime and unsupported topology fail explicitly.

Create the canonical existing ProviderMandatePolicy with one actual account,
`existing_campaign_optimize`, exact native target-set digest, current goal revision,
server environment/currency/time zone, supplied explicit bounded limits, and
existing exact-review/separate-activation policies. Preserve overlapping-period,
fixed accounting account-set and mixed-currency hold checks. Never create a new
ledger to evade prior reservations or spend. Multiple-account expansion remains a
separate implementation requirement; existing overlapping-ledger conflicts must be
shown honestly rather than narrowing an already consented portfolio.

Consent re-reads native topology and current goal, verifies the stored policy's
entire scope and current bounds, and compares exact expected revision/digest before
calling existing consent. The draft's policy is the durable authority document;
no claim that a catalog observation or profile digest is persisted inside it.
Changed native option/profile requires customer refresh/review, never substitution.

Existing revise/consent commit internally. The final original-session guard must
remain held into that commit; no intermediate commit or identity-refresh gap may
be introduced after the last recheck. No new persistence or migration is needed
for this minimal policy/consent slice. Existing mandate revisions and consent actor
records are reused; reads must not upgrade simulation or grant provider authority.

New routes under `/initial-planning/budget-mandates`:

- POST creates/revises an exact draft using PrepareBudgetMandateV1.
- POST `/{id}/consent` records exact local consent using ConsentBudgetMandateV1.

Both use MutationPrincipal/CSRF, original Provider, actual DB-bound runtime and
no-store responses. Existing execution mandate listing/revocation remain usable.
UI presents the confirmed goal budget/period, exact native owner scope, required
limits and separate consent before allowing native preview. It must expose missing
mandate preparation even when execution capabilities are false, without enabling
execution controls. No changes to old preview v1 hashes, v2 row representation,
0076 bridge rejection, feedback or migration0078.

## Inputs Versus Engineering Gaps

Engineering: these two services/routes, named customer review/consent UI, exact
post-HTTP fencing and ordinary application acceptance tests. No owner decision is
needed to invent credentials, exposure, or a provider runtime; none is appropriate.

Customer inputs: confirmed goal budget/period and explicit limits/consent. Keeping
all advanced numbers explicit is a safe first implementation. Translating named
aggressiveness into recommended limits, default cooldown/action count/freshness,
and validating 5/10/20 empirically need an explicit server policy; do not silently
choose values. Such configuration can be added later without blocking the explicit
form. Existing server planning/window rules must also be deliberately configured.

Operational prerequisites: real identity/session, owned store/account connection,
current measurement/calibration, billing eligibility and configured read policy.
Live mandate validation already requires `live_paid_work`; do not downgrade it to
contract-test billing. Native-read USD/Meta/daily coverage is an implementation
limit, not a change to Google/Meta/TikTok launch scope.

Still separate full-MVP work: qualified production execution assembly, exposure
and reservation evidence, supported provider profiles, exact creative/activation
review and live verification. A mandate recorded now is conditional consent and
never evidence that these requirements are satisfied.

## Acceptance Before Claiming First-Customer Reachability

Start with no ProviderExecutionMandate/Consent/Attempt/Reservation and no directly
seeded production policy. Through ordinary APIs and real configured runtime:
customer goal confirmation → real imported reports/capture/calibration → actual
MockHTTP GET native options → draft mandate → exact consent → native v2 preview.
Use real API original-session authentication and CSRF, SQLite and PostgreSQL,
plus actual TLS browser navigation. Execution runtime getters remain None, no
runtime dependency overrides, no provider writes, no fabricated exposure rows.

Assert exact ledger/policy/consent, goal cap/date binding and unchanged write
capabilities. Reject foreign scope, revoked/rotated session during HTTP, changed
goal, generation/topology/profile/selection drift, expired report, unsupported
currency/lifetime, absent numbers, changed digest/revision and overlapping period
or locked accounting-set conflict. Consent retries must reuse the original consent;
edits increment revision and invalidate prior consent. Revoke must remain available.
Test retained reservations/high-water accounting survive edits/revocation, and
prepare/consent cannot create a financial hold or execute an action. Existing v1
and injected qualified-runtime tests remain unchanged. No Full needed for proposal.
