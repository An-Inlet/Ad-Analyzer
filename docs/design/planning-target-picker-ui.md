# Planning Target Picker Interface

Private browser component module `app/portal/static/plan-target-picker.mjs`:

```javascript
clearPlanTargetPicker(host) // clears all owned DOM and invalidates old handles
renderPlanTargetPicker(host, catalog, {
  workspaceId, account, period, currency, totalCeilingMicros
}, onChange, now = Date.now())
// returns {expiresAt, readIntent(now = Date.now())}
// readIntent returns {exclusions: TargetSelector[], fixed_allocations: AllocationIntent[]}
```

`account` is the existing owned `{id,name,platform}` choice; `period` is the exact V2
`{starts_at,ends_at}` request; currency/ceiling are from the selected confirmed goal.
TargetSelector is exactly `{account_id,canonical_entity_key,selection_key}`; allocation
is `{target:TargetSelector,amount_micros}`. Never include client-composed TargetRefs or
catalog documents in customer mutation bodies. Existing V2 response schema is unchanged.

Reuse `renderNativeTargets` for validation and original coverage/source/expiry display.
Native names, advertiser/entity/parent IDs remain literal text. Per target offer: include
without fixed allocation (default), exclude, or fix a planning allocation in goal currency.
Allocation is a customer budget hypothesis, explicitly not a native budget setting or
permission to spend. Parse exact nonnegative decimal amounts with at most6fractional
places into bounded safe integer micros; never use floating multiplication/rounding.
Exclusions and fixed choices are mutually exclusive. Each list is at most100, aggregate
fixed amount in one picker <=confirmed ceiling; root also validates sums across accounts.
No forecasts, provider writes, implicit budget increase or silent selected-target remap.

The component owns a revocable handle: clear/re-render invalidates earlier readIntent;
readIntent checks current actual expiry and returns freshly copied exact selectors.
Malformed/foreign/expired render clears previous DOM before rejecting. Customer interaction
calls onChange but never performs network IO or retries. Root owns actual V2 POST, original
session/cookie/epoch fence, receipt lifetime timer, selected-account/reporting-window/goal
changes, cross-account sums, create/edit payloads and explicit reselection after expiration.
Existing target-bearing inputs must not be silently reconstructed from a fresh catalog.

Component owner: initial_start, isolated branch from the root containing this freeze.
Own only module, focused real DOM tests and component ledger; no main controller edits.
Root owns planning.html/planning.mjs/controller and real authenticated receipt journey.
Independent runtime negative/race tests remain separate from this display contract.
