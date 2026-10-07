# Meta And TikTok Existing-Campaign Optimization Adapters

Based on frozen ports17aefff. Provider modules are additive and the default
`get_optimization_transport()` remains `None`. No customer route, scheduler dispatch,
credential or live account is connected by this package. Shared schemas/migrations
are unchanged. Separate production consent and the central period ledger remain
required; constructing a request model is not authority.

The concrete transports fetch current account currency/timezone/status, campaign,
target and bounded complete child topology over injected HTTP. Meta uses v26.0;
TikTok uses v1.3 and explicit STATUS_ALL filters. Collection requests are bounded
at ten pages and199 children; malformed/changing/cycling pagination fails closed.
Sparse updates support campaign/adset Meta daily or lifetime budget and PAUSED,
and campaign/adgroup TikTok unchanged-mode budget and DISABLE. No resume, creative,
new campaign, targeting, schedule or account spending-limit update is serialized.
Campaign ownership includes its complete child target set. Independent child
budgets require explicit compatible parent settings; unknown flags block.

Every mutation validates the exact request, context, preflight and exposure binding,
then freshly reads the resource and compares its state digest before one POST.
The adapter does not calculate or mint exposure. Live requests remain unsupported
because native profile/exposure qualification is absent. Contract-test exposure is
explicitly separate and must enter through the durable coordinator, not customer
JSON or a fixture authority implementation. Qualified state/exposure alone does not
replace coordinator owner/consent/entitlement/cancellation/reservation checks.

Meta currency minor units and TikTok decimal amounts must be exactly representable.
Account currency/timezone must match the reviewed MoneyContext. Currency exponent,
UTC TikTok scheduling and regular-campaign daypart/ownership interpretation remain
qualification inputs, not inferred live guarantees. The supported contract scenario
uses explicit all-hours TikTok daypart bits and non-optimized regular campaigns.
Unknown/smart/sharing/scheduled profiles do not silently gain eligibility.

Readback re-fetches the full observed state. Same-owner exact desired state yields
`verified_target_state`, not causal attribution or delivery time. Changed state
conflicts; missing/foreign evidence remains unknown. An unchanged old value after
a timeout is unknown, never proof of no effect. Reconcile emits only GET requests
against the original target and retains the original attempt/fence. It never retries
a mutation. External manual edits can race preflight because no provider CAS is
qualified; the state explicitly records `provider_cas=unavailable`.

HTTP uses12-second phase timeouts, two-megabyte responses, identity compression and
no redirects/retries. Context secrets and raw responses are not persisted. HTTPX
request logs are suppressed during requests; errors are constant codes. Constructors
open no sockets. Missing native flags/fields do not become assumed-safe zero values.

Primary endpoint/schema evidence and qualification gaps are documented in the
approved `/workspace/inlet-design/META-TIKTOK-OPTIMIZATION-PORTS-PROPOSAL.md`, based on
official Meta SDK efd8423a2e595ea8d4c04eb824ce113f2f1d68cd and TikTok SDK
f809c396520df2d7b201a9ccc5378d822b728ed3. Portal Meta fetch returned429 and relevant
TikTok portal bodies were unavailable; SDK fields do not qualify native exposure,
CAS, budget minimums, all update combinations or omitted-field semantics.

Validation: 100 focused optimization/shared-contract/social-and-Google HTTP tests
passed; whole-tree Ruff, configured mypy (316 files) and diff check passed. No Full
or hosted CI result is claimed for this candidate. Actual durable
coordinator journey coverage is pending the central owner's callable implementation;
pure injected-HTTP tests do not establish complete B16 acceptance or live behavior.
