# Pure Original Google Owner Intent Input Binding

Design-only next slice on `689f56d`, dependent on reviewed standalone types and
`google-budget-owner-consumer-port-v1.md`. No existing consumer fields/API changes.

New `app/planning_documents/google_budget_input_bindings.py` exports exactly:

```
validate_google_daily_budget_input_bindings(
    *, inputs: PlanInputRevision,
    intents: tuple[ResolvedGoogleDailyBudgetIntentV1, ...],
    catalogs: tuple[CatalogEvidence, ...], sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> tuple[GoogleDailyBudgetOwnerWitnessV1, ...]
```

Returns witnesses in intent order. No clock/callback/SQL argument, original-session
authentication, selector lookup, TTL renewal, current-provider observation or
claim of economic compatibility. Missing/malformed/mismatched bindings raise
ValueError; recognized owner-profile unavailability retains the standalone typed
GoogleBudgetOwnerUnavailable failure. No error becomes an empty witness tuple.
An explicit empty intent tuple returns empty only after validating supplied graph
shape/account/source/privacy/time context; it does not signal generation support.

## Exact Admission Time (Requires Review Before Coding)

Use `inputs.created_at` as the immutable original admission instant. This is valid
for this port because each intent requires a supplied scenario allocation that
selects an already-acquired original catalog receipt; no owner-only fresh catalog
fallback is allowed. Require original reference/native/metadata observed instants
<= inputs.created_at < original minimum expiry, with reporting closed by original
observation. Compare UTC instants, reject numeric/bool copied timestamps, do not
restamp or compare with now. Input reporting windows must equal catalog windows
in UTC. Runtime still invokes existing receipt `_load` and final expiry checks;
historical callers reconstruct original receipts and original input admission time.
If runtime's saved created_at does not express this order, stop and freeze an
explicit original_admitted_at argument; never reinterpret generation time as input
admission. This helper is not a later-current-witness comparator.

## Graph And Owner Binding

Strictly revalidate input/intents/catalogs/sources including copied instances;
require tuple containers and bounded max20 intents, max20 input accounts/catalogs/
sources. privacy_revision is a strict nonnegative integer. Require unique exact
full input accounts, exactly one source per input account and no foreign/duplicate
catalog accounts; at least the exact catalog for every intent account. The source
account equals the input account, source_revision equals account.connection_version,
and privacy equals the argument. Catalog reference/account/source_binding/source
revision/privacy, native and metadata identity must equal that source. Strict
owner derivation handles UTC cross-node windows/min expiry and original values.

For every intent derive its full original witness only from that exact account
catalog and owner key. Rebind primitive intent through the standalone resolver:
original observation digest and stable owner facts digest, account/currency/current
amount/source_binding/representative must all match. Compare the complete resolved
primitive object, not only the request subset. Requested amount cannot exceed
observed current. Both catalog currency and intent currency equal the confirmed
goal/budget-period currency; no FX conversion. One `(full AccountRef, owner_key)`
across all intents even if amounts/scenarios agree; multiple distinct owners in one
account are allowed. No global freeform constraints accepted. Zero ceiling forbids
positive requested amount; zero remains an economically/provider-unqualified
hypothesis. Existing PlanInputRevision preserves exact goal and scenario sums.

## Scenario, Exclusions And Children

Resolve exactly one customer-supplied scenario by intent.scenario_key. Require
exactly one allocation in that scenario to a campaign belonging to this owner,
using full canonical catalog target equality and advertiser/native identity, not
just matching budget_owner_key. The allocated campaign may be any eligible affected
member; representative remains server-derived. The entire scenario remains its own
alternative; never add budgets across alternatives or convert period allocation
into daily settings. Fixed allocations remain preserved by existing input validation.

Rebuild the complete catalog target map using all observed entities, not just the
scenario selection. Every allocation or excluded target used in owner checks must
resolve exactly in its account catalog. Reject any exclusion of an active affected
campaign or observed child whose full advertiser/native parent is an owner campaign.
Retained REMOVED owner campaign rows also participate in parent identification;
never relabel their child as an independent pool. Unknown/ambiguous parent identity
fails the new intent. No name-based linkage.

Within the named scenario reject an extra allocation to an affected child even if
its Google budget_owner_key is None; absence of native child settings is not proof
of an independent budget. Ordinary unrelated independent-owner allocations remain
valid. Existing duplicate-owner scenario validation remains unchanged. Cross-account
IDs and aliases cannot evade these joins. Global graph validity and exact source
binding precede all membership checks.

## Ownership And Tests

This lane owns only the new helper, new focused pure tests and ledger. Root owns
future input fields/admission/generation refusal/history consumers; discovery lane
owns database original-session receipt lookup. No shared edits or migrations.

Pure tests: exact original witness returns; two independent owners same account;
conflicting/duplicate owner intents across alternatives; scenario missing/no owner/
wrong account/member; child allocation with owner None; excluded campaign/child;
removed-parent handling; cross-advertiser/alias/copied corruption; source/privacy/
generation/window/currency mismatch; positive under zero ceiling; freeform constraint;
changed resolved fields; original admission before observation/at expiry; offset/DST
chronology; empty tuple still checks context. Historical time accepted even if wall
clock later, because no clock is consulted. Legacy input bytes untouched.

No tests run until the discovery lane releases the sole pytest slot. Independent
review of this time/source contract must precede implementation.
