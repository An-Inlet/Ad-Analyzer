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
- `BudgetMandateCustomerIntentV1`: selection, total_cap_micros, and named
  aggressiveness (`conservative`, `balanced`, `assertive`). No client-supplied
  action count, cooldown, freshness, percentage or derived caps. Aggressiveness
  must equal the confirmed goal; changing it uses goal edit/reconfirmation first.
- `PrepareBudgetMandateV1`: customer intent, optional mandate_id and
  expected_revision together for edit. Dates derive from the confirmed goal's
  budget_start/budget_end using its named zone and explicit exclusive-end semantics.
  Total cap must not exceed that confirmed goal budget. A higher cap requires a
  separate goal edit/reconfirmation and a new exact mandate consent. An edit never
  silently increases the previously consented overall cap or changes ledger period.
- `ConsentBudgetMandateV1`: selection, expected_revision, policy_digest,
  preparation_digest. The selection locates fresh server reads, never trusted
  native proof. The preparation digest identifies the persisted exact policy origin.
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
server environment/currency/time zone, explicitly configured derived limits, and
existing exact-review/separate-activation policies. Preserve overlapping-period,
fixed accounting account-set and mixed-currency hold checks. Never create a new
ledger to evade prior reservations or spend. Multiple-account expansion remains a
separate implementation requirement; existing overlapping-ledger conflicts must be
shown honestly rather than narrowing an already consented portfolio.

Consent re-reads native topology and current goal, verifies the stored policy's
entire scope and bounds, and compares exact expected revision, policy digest and
preparation digest before calling existing consent. It reloads the currently pinned
server policy and planning profile, requiring exact matches to the durable
preparation provenance. Any change requires a new draft/review; it does not silently
recompile or upgrade consent. The canonical ProviderMandatePolicy remains unchanged.

### Separate Explicit Server Policy

New immutable `BudgetMandateOperatingPolicyV1`, loaded from a bounded nonsecret
server file with a separately configured expected digest. Proposed settings:
`AD_ANALYZER_BUDGET_MANDATE_POLICY_PATH` and
`AD_ANALYZER_BUDGET_MANDATE_POLICY_DIGEST`. Both absent disables only this consent
slice with `budget_mandate_policy_unavailable`; partial/invalid configuration fails
closed. Constructors perform no provider calls. No existing planning profile field,
profile digest, ProviderMandatePolicy schema, or preview v1 hash is modified.

Required fields: schema/version, policy_id, revision, environment,
planning_reporting_profile_digest, currency=`USD`, currency_exponent=2, and exactly
three named aggression rules. Each rule explicitly supplies:

- aggressiveness_percent (supported legacy 5/10/20 enum, explicitly mapped to its
  name; no assumed conservative→5/balanced→10/assertive→20 mapping);
- per_plan_cap_micros and positive_change_cap_micros (absolute USD-micros maxima);
- action_limit, cooldown_seconds, freshness_seconds (existing model bounds).

The selected rule derives `per_plan_cap = min(customer_total, rule.per_plan_cap)`
and `positive_change_cap = min(customer_total, per_plan_cap,
rule.positive_change_cap)`. Currency quantum is enforced on every amount. These
are explicit nominal request caps, not daily-to-period spend estimates. No fraction
of total, inferred residual exposure, duration multiplier or automatic cap increase
is introduced. Customer review explains the resulting maximum configured budget
and maximum increase in plain money amounts; technical timings stay out of the
required customer form. The preview's separate configured step must fit these caps
and the declared percentage or it honestly produces no usable proposal.

This initial absolute-cap policy is deliberately small. It cannot claim validated
aggression effectiveness. Any later relative-cap algorithm requires an explicit
new server policy version, not a silent interpretation change.

### Durable Preparation Binding — Schema Delta For Review

To preserve exact server-policy provenance across draft/consent and later config
changes, propose one immutable sidecar keyed by (workspace_id, mandate_id,
mandate_revision), with a compound FK to the owned execution revision. Store the
canonical preparation document plus digest: schema version, policy digest, complete
operating-policy snapshot/digest, planning-profile digest, goal definition digest,
customer intent, native option identity and exact scope/target-set digest. No
credentials, native HTTP payload, or original-session secret is stored. Existing
revision actor/time supply audit identity; consent still binds its actual actor.

Classify this as mandate authority provenance consistently with protected execution
revisions, not a new financial balance or erasable read queue. Exact export and
retention classification must be implemented with the schema; it does not preserve
raw customer performance reports. No migration number is allocated here: this is
an explicit proposed schema delta requiring root review before implementation.

`execution_mandates.revise` currently commits internally. Add backward-compatible
keyword `commit: bool = True` so this new service can call it with False, flush the
sidecar atomically, recheck the bound original-session authority and commit once.
Existing callers retain their transaction behavior. Consent loads/fences the
sidecar and current policy/profile, recomputes the whole ProviderMandatePolicy and
requires exact equality before its existing commit. Original workspace/user/session/
membership locks remain held through both final commits. No provider HTTP spans
these transactions. A missing sidecar cannot enter this new consent path; legacy
qualified-runtime consent remains unchanged and cannot be silently upgraded.

New routes under `/initial-planning/budget-mandates`:

- POST creates/revises an exact draft using PrepareBudgetMandateV1.
- POST `/{id}/consent` records exact local consent using ConsentBudgetMandateV1.

Both use MutationPrincipal/CSRF, original Provider, actual DB-bound runtime and
no-store responses. Existing execution mandate listing/revocation remain usable.
UI presents the confirmed goal budget/period, exact native owner scope, named
aggressiveness, derived money limits and separate consent before allowing native preview. It must expose missing
mandate preparation even when execution capabilities are false, without enabling
execution controls. No changes to old preview v1 hashes, v2 row representation,
0076 bridge rejection, feedback or migration0078.

## Inputs Versus Engineering Gaps

Engineering: these two services/routes, named customer review/consent UI, exact
post-HTTP fencing and ordinary application acceptance tests. No owner decision is
needed to invent credentials, exposure, or a provider runtime; none is appropriate.

Customer inputs: confirmed goal budget/period, named aggressiveness, selected
scope and exact consent. Operating timings, action limits and cap mappings are
required validated SERVER policy, never a customer onboarding burden. Real policy
values and empirical validation remain owner/operator inputs; fixture values can
exercise all offline acceptance without pretending they are production-qualified.
Missing policy disables this slice honestly. Existing planning/window rules also
remain deliberately configured, with no default values introduced.

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
currency/lifetime, absent or partial server policy, client technical fields, changed
operating-policy/profile/preparation digest or revision and overlapping period
or locked accounting-set conflict. Consent retries must reuse the original consent;
edits increment revision and invalidate prior consent. Revoke must remain available.
Test retained reservations/high-water accounting survive edits/revocation, and
prepare/consent cannot create a financial hold or execute an action. Existing v1
and injected qualified-runtime tests remain unchanged. No Full needed for proposal.

Additional acceptance: preserve byte-for-byte existing profile/v1 hashes; missing
new configuration does not disable existing read previews or legacy injected
qualified flows. Tampered/missing/foreign preparation, config replacement between
draft and consent (including same compiled amounts), mismatched profile/environment,
non-quantized caps and unmapped names must deny. Rollback must leave neither an
orphan draft nor sidecar. Verify customer UI never asks for technical operating
knobs and no consent route accepts them. Fixture server policies explicitly supply
every number. No execution enablement follows from installing this policy.

## Implementation Freeze 1

Actual strict models and bounded loader are in
`app/initial_planning/budget_mandate_contracts.py` and
`app/initial_planning/budget_mandate_configuration.py`.
`BudgetMandatePreparedV1` is the customer response; preparation and consent return
this projection, with consent state active. No technical inputs are added to UI.

Concrete service signatures (implementation follows; no callable stubs):

```
prepare_budget_mandate(db: Session, workspace_id: int,
    principal: CustomerPrincipal, provider: IdentityProvider,
    body: PrepareBudgetMandateV1, runtime: InitialPlanningRuntime,
    operating_policy: BudgetMandateOperatingPolicyV1 | None
) -> BudgetMandatePreparedV1
consent_budget_mandate(db: Session, workspace_id: int,
    principal: CustomerPrincipal, provider: IdentityProvider, mandate_id: str,
    body: ConsentBudgetMandateV1, runtime: InitialPlanningRuntime,
    operating_policy: BudgetMandateOperatingPolicyV1 | None
) -> BudgetMandatePreparedV1
```

The operating policy is supplied by a separate server dependency using the actual
request engine's planning runtime. Never accept it from a request. API paths are
POST `/api/customer/v1/workspaces/{workspace_id}/initial-planning/budget-mandates`
and POST the same prefix `/{mandate_id}/consent`. Projection money caps and named
aggressiveness suffice for the review; period is shown from the existing confirmed
goal and must be rechecked against that exact revision before consent.

Reserved migration `20261007_0079`, down `20261007_0078`: table
`initial_budget_mandate_preparations`, columns workspace_id(Integer),
mandate_id(String32), mandate_revision(Integer), policy_digest(String64),
digest(String64), document(JSON). Primary key (mandate_id, mandate_revision),
compound owned FK (mandate_id, mandate_revision, workspace_id) to
provider_execution_revisions(mandate_id, revision, workspace_id), RESTRICT.
Every scalar binds the strict versioned document; service additionally binds
policy_digest to the actual referenced immutable revision. Reject UPDATE and
DELETE of preparation rows with DB triggers; existing authority retention applies.
Downgrade refuses any nonempty table, preserving prior records without synthesis.
Registry classifies it as protected workspace authority; export uses bounded strict
parsing and scalar/digest/revision binding, never a generic JSON pass-through.

Pinning is per process configuration identity, not distributed revocation. Deploy
new policy file/digest and profile coherently across workers; stale processes must
be drained/restarted by deployment operations. No global hot reload or revocation
claim follows from a settings change. Native-write qualification remains separate.
