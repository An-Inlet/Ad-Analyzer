# Additive Google Optimization Ports

The real Google optimization HTTP transport is missing; the older GoogleActions
fixture remains a simulation-only path and is not a production-consent bridge.
This extension freezes its typed port for a separate actual adapter implementation.

`GoogleBudgetOwnerRef` identifies the exact native campaign budget resource and complete
owning campaign topology. The bounded first profile requires one campaign, a native
reference count of one and explicitly_shared=false. A budget key is the full scoped
`customers/{advertiser}/campaignBudgets/{budget}` identity, not a child campaign ID.
`GoogleCurrentState` carries that identity, exact budget settings, complete ownership,
Search/bidding/network/date settings and the generic account/currency/period/current
state lineage. Unsupported profiles still require adapter qualification; data models
alone do not authorize a mutation or turn daily budget into a total exposure cap.

`GoogleBudgetSetV1` sets one exact amount; `GoogleStatusSetV1` permits PAUSED only.
No resume, creative, targeting, negative keyword or shared-budget update is included.
The existing `OptimizationTransport` read/validate/apply/readback/reconcile interface
is unchanged. Optional Google developer-token/login-customer context is excluded from
serialization. Provider CAS remains unavailable, and unknown state is never proof of
no effect or permission for a replacement fence.

Existing social request JSON/digests remain unchanged: captured all eight Meta/TikTok
budget/pause × campaign/child variants before the extension and compared afterward;
regressions retain the original digest values. Focused contracts + actual social HTTP
checks: 47 passed. Whole mypy: 387 source files passed. No live calls, workflow dispatch,
Full run, mutation authority, migration, merge or deployment is introduced here.
