# Google Optimization HTTP Adapter — Offline Implementation And Bounds

Implemented in `app/executors/google_optimization.py` on isolated branch
`codex/inlet-google-optimization-http` from frozen shared-port head
`c7a9713566bcf0962310e8421cdeaf031fcef7d9`. Existing GoogleActions remains simulation.
The adapter consumes separate production execution contracts and never promotes
B07 simulation approval. No runtime registration or live calls in this package.

## Verified Primary References

- https://developers.google.com/google-ads/api/fields/v25/campaign_budget
  reference_count is campaigns actively using a budget; explicitly_shared is
  independently selectable; budget period includes DAILY and CUSTOM_PERIOD.
- https://developers.google.com/google-ads/api/docs/campaigns/budgets/share-budgets
  explicitly_shared=false restricts budget sharing; it does not replace a complete
  owner topology snapshot and matching reference count.
- https://developers.google.com/google-ads/api/docs/mutating/service-mutates
  single-resource service updates use update plus update_mask; REST uses operations,
  partialFailure and validateOnly. One bounded update per original attempt.
- https://developers.google.com/google-ads/api/samples/update-campaign
  campaign status PAUSED is an ordinary masked update.
- https://developers.google.com/google-ads/api/docs/reporting/paging
  v19+ Search has fixed page size 10,000; never emit page_size. Follow bounded opaque
  page tokens with unchanged GAQL; repeated/missing/incomplete pages fail closed.

## Implemented Runtime Boundary

Pin v25 as existing GooglePublicationHTTP does. Fixed googleads.googleapis.com
endpoint, customerId from typed scope, optional configured legacy developer-token
and login-customer-id only. Bearer secret never appears in a model dump, log or
exception. Bounded streamed identity-encoded response, fixed timeouts, no redirects,
no environment proxies, no automatic mutation retries.

Read customer identity/currency/timezone/status; selected campaign and native
campaignBudget settings; all campaigns using that budget across bounded pages.
Require exact resource/customer ownership, Search/manual CPC, independent DAILY
STANDARD budget, one active owner matching target, no unqualified automation/shared
budget topology. Preserve distinct native budget key and campaign target.
Missing or unsupported fields must not become qualified defaults by accident;
protobuf JSON omission handling needs explicit selected-field semantics/tests.

validate_only emits the same masked single update with validateOnly=true only if
local preflight/exposure/authority bindings support the exact request. apply_once
re-reads current state immediately, rejects drift, then submits one original masked
budget amount or PAUSED status operation. Timeout/malformed/partial failure remains
unknown. Readback verifies target plus unaffected settings/topology, not merely
budget/status; read-only reconcile never resubmits. Old state cannot prove no effect
or release a reservation, and configured PAUSED is not an authoritative treatment
interval. Provider CAS is unavailable. No resume, negative keywords, shared budgets,
campaign creation, spend-limit changes or live qualification.

## Mocked Verification

Exact v25 request/query/body/header serialization; owner/account mismatches; hidden
second campaign on later page; duplicate/cyclic/overflow pagination; changed native
budget; unsupported strategy/shared flags; customer currency/timezone/status changes;
strict amount precision; validate-only never mutates; timeout before/after simulated
apply; delayed acknowledgement/readback; altered unaffected settings; repeated
reconcile no writes; compressed/oversized/error bodies and sanitized logging.

## Exact Supported Subset

Read the v25 `start_date_time`/`end_date_time` fields. Finite schedules must use
customer-local daily boundaries; a cleared native end produces explicit null
`campaign_end_date` and `ends_at`, with no sentinel date or invented spend horizon.
Google Search/manual CPC, independent DAILY/STANDARD/ENABLED budget and one complete
owning campaign are required. Display expansion, partner-only networks, YouTube/TV,
AI Max, dynamic Search and enabled automatic recommendation subscriptions fail
closed. This conservative profile does not claim complete Google product coverage.

Source facts: [v25 campaign fields](https://developers.google.com/google-ads/api/fields/v25/campaign),
[recommendation subscriptions](https://developers.google.com/google-ads/api/fields/v25/recommendation_subscription),
and [FieldMask JSON encoding](https://protobuf.dev/reference/protobuf/google.protobuf/#field-mask).
The masked budget REST update uses `amountMicros`; pause uses `status`.

Optional selected protobuf scalar defaults are interpreted as false/UNSPECIFIED;
identity, account context, money, reference count and required schedule values
are never synthesized. Entire remaining selected settings, topology and subscription
snapshot bind readback. Provider CAS is unavailable. A matching configured target
is not proof of causal attribution, effective treatment time or settlement.

## Validation And Remaining Engineering

Actual Google HTTP MockTransport, shared Google contracts, unchanged frozen social
JSON/digests/adapters and Google publication regression: **92 passed, zero skipped**.
Whole-tree Ruff, mypy app/tests (**389 source files**) and diff check passed.
No database schema changes or Full run. Tests cover masked budget/pause operations,
provider validation-only, hidden later-page owners, duplicate/cyclic pagination,
foreign identity, changed settings, incomplete ownership, unsupported strategies,
context expiry, precision, partial/invalid acknowledgements, compressed/oversized
responses, private error/log handling, timeout-before-effect and late observed effect.
Reconciliation repeats only reads and retains the original attempt/fence.

Durable optimization coordinator integration is a separate package. Live portfolio
exposure bounds, account-specific provider qualification, consent/activation gates,
external-writer operational controls and authoritative effect/settlement evidence
remain unqualified or unimplemented. The existing factory still returns None and
the adapter refuses live-environment exposure. These are not credential-only gaps.
No shared budgets, resume, negative keywords, campaign creation, provider calls,
spend authority, merge or deployment were introduced.
