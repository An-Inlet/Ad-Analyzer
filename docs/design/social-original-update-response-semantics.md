# Social Original Budget Update Response Semantics

2026-10-06. Bounded primary-source review on isolated `a4fcd3a` child. No account calls,
credentials, code changes, terminality mapping or runtime activation. Related:
[source matrix](production-spending-source-readiness.md) and
[prior social exposure assessment](meta-tiktok-native-exposure-assessment.md).

## Result

**Do not add a Meta or TikTok terminality reader from the evidence obtained here.**
The retrieved official SDK sources establish update request construction and generic
response handling, but do not establish that each exact supported budget-update success
response means the configuration operation has completed rather than been accepted for
processing. This is an evidence-access/semantics gap, not proof that those endpoints are
asynchronous or that a narrow source can never be qualified.

The assertion under consideration is only `original_configuration_operation_completed`,
which could support `authoritative_request_terminal` after review. It would never mean
that delivery stopped, all costs arrived, later effects are impossible, or a reservation
can be released. Google’s approved single-update response mapping is not transferable
merely because another provider also returns HTTP 200 or a success indicator.

## Exact Existing Operations

| Provider | Current adapter operation | Current evidence | Missing endpoint-specific evidence |
|---|---|---|---|
| Meta | POST `/v26.0/{campaign_id}` or `/v26.0/{adset_id}`, exactly one `daily_budget` or `lifetime_budget` field | [Adapter](../../app/executors/meta_optimization.py) treats `success is True` as acknowledgment. Original resource/field/result provenance is not durably captured. | Readable version-qualified specification that success for this direct, non-batch, non-validation update means completed configuration mutation; any async/deferred exceptions and response variants. |
| TikTok | POST `/open_api/v1.3/campaign/update/` or `/open_api/v1.3/adgroup/update/`, one advertiser and target, one budget | [Adapter](../../app/executors/tiktok_optimization.py) acknowledges the shared transport's successful response; returned update data is not checked for exact target/budget or retained as typed provenance. | Exact successful response schema and documented meaning for these regular manual endpoints, including partial/deferred/async conditions. Generic code and correlation ID alone cannot supply that meaning. |

Status, batch, Smart+, ACO, GMV Max, scheduled budget operations and campaign creation
are outside this review. No conclusion for them is inherited from a future budget-only
profile.

## Meta Evidence And Limits

Pinned official Python Business SDK commit
`efd8423a2e595ea8d4c04eb824ce113f2f1d68cd`:

- [Campaign.api_update](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/campaign.py#L544)
  builds a node POST with budget fields and supports execution options. It invokes a
  generic object parser. This confirms the request surface, not server completion timing.
- [AdSet.api_update](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adset.py#L417)
  likewise accepts budget updates and execution options. `validate_only` exists in this
  SDK, so any future capture must bind the exact request and exclude validation mode.
  This review does not assert a specific validation response body.
- [FacebookResponse.is_success](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/api.py#L83)
  is a generic SDK predicate: it handles error fields, success fields, bodies without
  an error, HTTP 304 and empty HTTP 200. Its implementation even handles a service-
  unavailable response case. An SDK success callback or this predicate therefore cannot
  itself be an endpoint-specific completed-budget-mutation assertion.

The [campaign reference](https://developers.facebook.com/docs/marketing-api/reference/ad-campaign-group/)
and [ad-set reference](https://developers.facebook.com/docs/marketing-api/reference/ad-campaign/)
returned HTTP 429 to the document retrieval tool in this review. The Graph API platform
and overview pages were inaccessible/429. No retries through authenticated access or
alternate providers were attempted. Generic update conventions or third-party examples
were not substituted for the unavailable specification.

This is not a discovered counterexample to the exact Meta budget response; it is a
concrete counterexample to treating the generic SDK success predicate as sufficient.
Whether exact `{"success":true}` on the constrained direct mutation justifies the
narrow inference remains unqualified until the endpoint semantics can be reviewed.

## TikTok Evidence And Limits

Pinned official Business SDK commit
`f809c396520df2d7b201a9ccc5378d822b728ed3`:

- [CampaignCreationApi.campaign_update](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/CampaignCreationApi.md#campaign_update)
  and [AdgroupApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/AdgroupApi.md)
  describe update methods but return the generic `InlineResponse200` model.
- [InlineResponse200](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/InlineResponse200.md)
  leaves `data` as an object and directs readers to individual endpoint documentation.
  Its request ID description is log correlation. It supplies no completed-operation,
  idempotency, cancellation or unknown-request recovery contract.
- The official [manual campaign update](https://business-api.tiktok.com/portal/docs/update-a-campaign/v1.3)
  and [manual ad-group update](https://business-api.tiktok.com/portal/docs/update-an-ad-group/v1.3)
  URLs resolve to correctly titled pages but returned empty rendered bodies. The older
  [campaign document ID](https://business-api.tiktok.com/portal/docs?id=1739320422086657)
  also yielded no readable body.

A readable first-party [TTO campaign update](https://business-api.tiktok.com/portal/docs/update-a-tto-creator-marketplace-campaign/v1.3)
reference explicitly supports per-handle failures alongside returned successful handles.
That is a different endpoint and not a budget-update failure claim. It demonstrates why
one provider-wide success envelope cannot replace endpoint-specific result validation.

A search-indexed excerpt of the official [ACO reference](https://business-api.tiktok.com/gateway/docs/index?doc_id=1739473020978177)
states that ACO create/update responses can echo request parameters while processing is
unfinished. Opening that document yielded only a JavaScript shell, so this is recorded
as indexed primary text, not a fully retrieved specification. It is a warning against
generalizing code-zero/echoed-data semantics, not evidence that regular budget updates
behave that way. No inference about regular endpoint terminality is based on it.

## Bounded Next Proposal, Conditional On Semantics

Before proposing a source implementation, obtain a readable, version-qualified provider
statement for each exact regular budget-update endpoint covering successful original
response meaning, response fields, and deferred/partial/validation exceptions. A capture
profile can then be reviewed separately for each endpoint. The proposed shape would bind:

- fixed API version/path and one native owner, exact budget field/value and operation digest;
- original owned account/generation/environment, request digest, attempt and fence;
- bounded typed original success result and coordinator capture time, without tokens or
  arbitrary raw response payloads;
- an explicit endpoint-specific assertion, with unsupported response shapes rejected.

Only after that review could append-only original capture, lifecycle/export/restore
registration, an owned durable reader and full-ancestor terminal batch be implemented.
Crash before capture, timeout after acceptance, legacy generic acknowledgment, malformed
response, and any missing ancestor remain unavailable. Later matching readback cannot
retroactively produce original-response evidence. No broad no-later-effect assertion or
financial source is proposed. Independent transition, portfolio and U/F/P guarantees remain
mandatory; terminality alone never funds a replacement or releases exposure.

Current missing engineering is real: neither social adapter records this exact protocol
provenance nor has the proposed owned reader. Implementing those types now would still
leave the semantic assertion unqualified; this review therefore does not claim that
credentials or owner permission alone unblock the source. No new owner policy decision
is needed to preserve these gates.

Validation: reviewed local adapters and pinned official SDK source; bounded public
reference retrieval, relative links and diff check. Documentation only; no tests, provider
account calls or live verification claimed.
