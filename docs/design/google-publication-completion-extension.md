# Google Original Operation Completion: Creation And Activation

Status: source-reviewed implementation with offline contract/API evidence; no live qualification. Source baseline `ac26a67d158faaccad0c8f112f2f834b0b7af34a`; candidate assembly `9580eb98c6adf348ffda3622f1beb44328c9c9ad` was reviewed separately and changes no completion semantics.

## Concrete Gap And Scope

`GooglePublicationHTTP.apply_once` and `GoogleActivationHTTP.apply_once` already issue one synchronous resource-service mutation with `validateOnly=false` and service-specific partial-failure support, validate one returned resource, and return an acknowledgment. They discard the original response evidence. The existing `GoogleSynchronousCapture`/`GoogleCompletionDocument` and `google_completion.read_owned` support optimization requests only.

Extend original-operation evidence to these existing operations; do not add provider mutations. A successful synchronous original response can establish completion of its exact configuration operation. It does not establish final advertising effects, delivery time, cost completeness, a financial bound, settlement, or absence of later external changes. Unknown original responses remain unknown even if readback later matches. No retry or replacement fence is introduced.

## Exact Source Qualification Before Implementation

Individually verify official pinned Google v25 request/response service schemas for campaign_budget_service, campaign_service, conversion_goal_campaign_config_service, campaign_criterion_service, ad_group_service, ad_group_criterion_service and ad_group_ad_service. Record the authoritative revision and supported operation/result mapping; the earlier optimization-only synchronous inference does not automatically qualify every collection.

Creation serializer currently emits campaignBudgets(create daily or total), campaigns(create paused), conversionGoalCampaignConfigs(update), campaignCriteria(create), adGroups(create paused), adGroupCriteria(create paused exact keyword), and adGroupAds(create paused responsive search ad). Activation uses only the exact existing activatable target collections and a status update. A collection with unverified synchronous semantics receives no capture. Existing execution behavior and serializers remain unchanged.

## Frozen Proposed Types And Callables

Add `GoogleExecutionCaptureV2`, profile-discriminated by creation versus activation, and `GoogleExecutionCompletionV2` with schema `inlet.google-original-completion.v2`. Preserve existing v1 model, bytes, parser and optimization profile. V2 captures bind purpose, owned account/environment, original request digest, original attempt/fence, exact endpoint and compiled operation digest, returned resource and normalized single-result digest. The persisted document additionally binds run/step lineage resolved from the owned original attempt and recorded UTC time. No raw operation contents, credentials, creative text or raw provider response is stored.

Capture creation result must be a valid exact-customer resource of the serializer's collection; composite criterion/ad resource names must bind the parent in the compiled request. Deterministic update resource names must equal the request exactly. Activation result must equal the exact approved target. Both require exactly one successful result, no partial-failure error, non-validation execution, and the fixed endpoint. Strict malformed/ambiguous responses never produce evidence.

In-process `GoogleCapturedCreationResponse(ProviderResponse)` and `GoogleCapturedActivationResponse(ActivationResponse)` carry `capture` excluded from serialization. Therefore historical response JSON, normalized receipts, request/plan/review digests and existing adapter protocols stay byte-compatible.

`capture_execution_response(db, original_request, captured_response, now)` runs under the existing purpose-specific evidence locks inside `coordinator.record_response` / `activation.record_response`, before their existing commit. It inserts into the existing `google_original_completions` table in the same transaction as the response. Repeated identical evidence is idempotent; conflicting evidence fails closed. No new table is planned; validate existing immutable triggers, composite FK, retention and export parser support for the new discriminator.

`read_execution_completion(db, workspace_id, attempt_id, actor, *, authorize, clock)` resolves persisted run purpose and dispatches to the existing creation/activation/optimization evidence lock; it validates the document against the reconstructed original request and actual original response record. Mandatory caller-bound authorization is checked under canonical workspace-first ordering and immediately before delivery. No IO or commits. The v1 optimization read contract remains unchanged.

## Actual Consumer

The existing GET `/api/customer/v1/workspaces/{workspace_id}/execution/attempts/{attempt_id}/receipt` gains a strict sibling `original_operation_completion` projection; existing `receipt`, `state` and `causal_effect_time` values remain unchanged. Projection fields:

- `status`: `completed` or `unavailable`.
- `purpose`: owned creation/activation/optimization purpose, or null when unavailable.
- `profile`: exact supported source profile, or null.
- `commitment`: canonical stored completion digest, or null.
- `assertion`: always `original_configuration_operation_only`.
- `financial_finality`: always `unavailable`.

No native resource identifiers or original request bodies enter this projection. Availability does not depend on an active new provider connection or new execution grant; historical read ownership remains mandatory. A current conflicting receipt is not silently overridden: expose unavailable unless current lineage is coherent. No new settlement endpoint, unused closure batch helper, or conversion to `ClosedOriginalRequest` is included. A future financial consumer must separately qualify any such inference.

## Acceptance And Boundaries

Use ordinary configured Google API fixtures and lower MockHTTP: creation graph then separate activation, original response persistence and owned receipt GET on SQLite/PostgreSQL. Verify all supported service mappings, exact original lineage, resource parent mismatch, foreign scope, wrong fence/request/endpoint, partial-error/multiple-result/malformed responses, missing or legacy capture, lost response, crash/rollback before capture, duplicate/conflicting capture, original session revocation and role loss. Record/receipt/capture failure must be atomic. Existing v1 bytes and response digests remain exact. Assert unknown reconciliation never manufactures completion, repeats no mutation, and completion never releases or reduces the original reservation. Include strict export/retention compatibility and composite-FK tests.

This closes a genuine evidence production and consumption gap. Financial production remains blocked on independently substantiated accounting basis, whole obligation-domain coverage, external-writer/control boundary and future-liability proof. Existing native inventories and total-budget compiler/UI are already implemented; neither should be duplicated or relabeled as a qualified U/F/P source. No live configuration or factory is enabled.

## Verified Service Matrix And Wire Repair (2026-10-07)

All seven official service protos were read at pinned googleapis revision `7c0638cf893464ba844aeb04683026406eb3f8ca`. Each mutate RPC returns its specific response directly; its result resource is documented as belonging to successful operations. This supports only the original configuration-operation assertion, not effect finality.

| Service | Fixed collection | Supported operation | Partial failure | Successful result |
|---|---|---|---|---|
| [campaign_budget](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/campaign_budget_service.proto) | `campaignBudgets` | create | false | `MutateCampaignBudgetResult.resource_name` |
| [campaign](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/campaign_service.proto) | `campaigns` | create/status update | false | `MutateCampaignResult.resource_name` |
| [conversion_goal_campaign_config](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/conversion_goal_campaign_config_service.proto) | `conversionGoalCampaignConfigs` | update only | unsupported; omit | `MutateConversionGoalCampaignConfigResult.resource_name` |
| [campaign_criterion](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/campaign_criterion_service.proto) | `campaignCriteria` | create | false | `MutateCampaignCriterionResult.resource_name` |
| [ad_group](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/ad_group_service.proto) | `adGroups` | create/status update | false | `MutateAdGroupResult.resource_name` |
| [ad_group_criterion](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/ad_group_criterion_service.proto) | `adGroupCriteria` | create/status update | false | `MutateAdGroupCriterionResult.resource_name` |
| [ad_group_ad](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/ad_group_ad_service.proto) | `adGroupAds` | create/status update | false | `MutateAdGroupAdResult.resource_name` |

Every service has `validate_only`; only the six non-conversion-goal services declare `partial_failure`. The existing adapter incorrectly sent `partialFailure:false` to conversionGoalCampaignConfigs for both validation and execution. A strict whole-DAG request-schema regression reproduced failure before the narrow endpoint-specific omission (1 failed, `/tmp/inlet-google-goal-wire-before.log`). Both daily/total DAGs now reject unknown request fields and pass. Other six endpoint bodies remain unchanged. Focused publication/total-budget tests: 41 passed; whole Ruff and app mypy passed. This is a wire correction, not live API verification. No typed operation or persisted review/request hash changes.

## Implemented Binding And Consumer

Pure contracts are frozen in `24ffb68`; the preceding endpoint-only wire fix is `3318338`. `GoogleExecutionCaptureV2` contains only transport-available account/purpose/request/fence and exact operation/result commitments. Existing request types intentionally contain no original attempt ID (creation also has no execution environment). `GoogleExecutionCompletionV2` enriches those facts with attempt/run/step/environment under the existing DB evidence lock; it also binds the unchanged normalized-response digest. The capture field is excluded from response serialization. The additive strict export union handles both immutable document versions in the existing protected table.

`read_execution_completion` consumes the capture and the persisted response alongside the latest validated original-attempt receipt. A latest unknown/conflicting receipt leaves the projection unavailable even when historical capture survives. This conservative projection rule is not a claim that original execution was undone. The receipt route invokes the existing dedicated lifecycle owner/session guard before locks and at delivery; current owners may read a closing workspace without an active former spending grant or native connection. Expired/revoked sessions and lost roles cannot read the result.

No `ClosedOriginalRequest` mapping, settlement reader, monetary bound, new table, migration, live factory, or UI claim was added. Completion never reduces a reservation. The original v1 optimization reader and document remain intact; its new sibling projection additionally verifies the original normalized response. Historical fixture support stubs only the new append when the pre0066 schema explicitly proves that the entire capture table does not exist; there is no production missing-table fallback.

Adverse evidence retained: the first new strict parent checks exposed six synthetic fixture failures because ad-group child IDs incorrectly used the campaign ID. Fixtures now derive the actual compiled parent; wrong-parent rejection stays tested. One new rollback test initially failed because its test import was absent, then was corrected. Native restore initially skipped twice because client tools were absent from PATH; rerunning through the already-running local PostgreSQL container exercised the real tools and passed both versions. These invocation/fixture corrections are not live-provider evidence.
