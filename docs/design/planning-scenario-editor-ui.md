# Customer Budget Alternative Editor

This extends the reviewed customer planning form without changing server request
schemas or authority. Each named alternative is a customer hypothesis, not an
optimized recommendation, native budget command, forecast or additional ceiling.
Use the existing `ScenarioIntent` request and `CustomerScenarioIntent` stored types.

Private component module `app/portal/static/plan-scenarios.mjs`:

```javascript
clearPlanScenarios(host) // invalidate old handles and clear owned DOM
renderPlanScenarios(host, {
  currency, totalCeilingMicros, expiresAt,
  targets: [{selector: {account_id, canonical_entity_key, selection_key}, label}]
}, onChange)
// returns {readIntent(now = Date.now()) -> ScenarioIntent[]}
```

Root supplies only targets from the same currently validated retained catalogs
used by the target picker. The component snapshots them, never remaps references,
and renders all labels literally. Original earliest receipt expiry controls the
handle; clear/rerender revokes previous handles. Root clears both components on
scope/session change, expiry, cancel, save or editor replacement. No network calls.

Initially zero alternatives. Customer explicitly adds at most8 named alternatives,
each with at most100 target rows and a separately entered unallocated reserve.
Each row explicitly selects one target and an exact nonnegative amount in confirmed
goal currency. Target duplicates within an alternative fail. Each alternative
independently sums to the confirmed ceiling using BigInt integer micros; never add
alternatives together. Parse exactly up to6 decimal places without floating rounding.
Use a shared exported amount parser from the existing target-picker module (retain
its existing behavior and coverage), not a different parser. Keys are stable local
`alternative_1`... identifiers, never customer labels or array position after removal.

Root validates each alternative against current exclusions and fixed allocations
before submission, matching the server's exact invariants. Excluded targets cannot
appear; each fixed target amount must appear unchanged in each alternative. No
account currency conversion or native budget semantics inferred. These are goal-
currency planning hypotheses. Server remains authoritative for all bindings/sums.

Existing saved scenarios cannot be silently copied to new observations. Editing a
scenario-bearing input requires explicit fresh target reading, rebuilding intended
alternatives and confirmation of replacement (including removal). Comparison-window
editing remains separately blocked until its evidence behavior is implemented.

Acceptance: realDOM literal labels/exactdecimal/revocation/expiry/8and100 bounds/
duplicate/independent sums, followed by actualHTTPS create/generate/revise with two
alternatives, fixed/excluded mismatch rejection, and immutable prior version.
Do not claim Q05 complete solely from this editor or synthetic alternatives.
