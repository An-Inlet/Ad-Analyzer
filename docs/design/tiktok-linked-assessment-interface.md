# Pure Linked-Identity Assessment Interface Proposal

Base: frozen discovery parser1b5cee8459e7de27c4dcdb23221dfb50877195ec. No implementation or schema changes in this checkpoint. This consumes discovery facts; it is not a publication qualification reader.

Proposed new module: `app/publication/tiktok_linked_assessment.py`.

```
assess_linked_identity(
    request: TikTokLinkedAssessmentRequestV1,
    identity_page: TikTokIdentityPageV1,
    pixel_page: TikTokPixelPageV1,
) -> TikTokLinkedAssessmentV1
```

Request is frozen/strict and contains schema_version, actual `ExecutionAccount` scope, identity_page_digest, pixel_page_digest, selected identity_id, pixel_index and optional event_index. Pixel/event indexes select exact observations under committed page digests; they are not converted into opaque provider IDs or made into customer catalog options. This avoids normalizing unverified string/integer native IDs into fictional equality. Indexes are bounded by the existing20 pixels/endpoint-bounded events and must address an actual item. A missing event_index yields event_not_selected, not an inferred event.

Page digests use separate canonical domains `inlet.tiktok-identity-page-evidence.v1` and `inlet.tiktok-pixel-page-evidence.v1` over complete typed page documents. The function revalidates nested models, including unchecked model_copy inputs, before use. Scope must be tiktok_ads and both page advertiser IDs must equal the scope external advertiser ID. Identity ID must occur exactly once, identity type must match the request type and BC scope must match exactly when applicable. Mismatched commitments, indexes, ownership or duplicate selected identity raise a fixed `TikTokLinkedAssessmentInputError` with no payload logging; they never produce a plausible positive result.

Result is frozen/strict/versioned, with request and exact selected identity/pixel/event observations, both page digests, fixed ordered deduplicated blockers, and constant fields:

- publication_eligibility = not_assessed
- spending_authority = none
- tracking_readiness = unknown
- scalar_shape_qualification = unverified
- collection_completeness = page_only
- freshness_assessment = not_assessed

No eligible/ready boolean, no fallback event, no qualification ID, no TTL invented from timeless page data. Unrelated permission facts remain in the selected observation but can_pull_video/can_manage_message/can_use_live_ads are not required for this proposed uploaded-video assessment. Facts alone do not establish a complete Spark Push contract.

## Fixed Reason Vocabulary And Decisions

Always include `publication_contract_not_assessed`, `pixel_scalar_shape_unverified`, `page_coverage_only` and `observation_freshness_not_assessed`. These prevent an all-present necessary-facts case from being mistaken for approval.

Identity route:

- CUSTOMIZED_USER: `custom_identity_phaseout`; no AVAILABLE requirement because that field is inapplicable.
- AUTH_CODE: `identity_route_unsupported`; no invented push permission.
- TT_USER/BC_AUTH_TT: available_status absent/null/unrecognized gives `identity_status_unknown`; recognized non-AVAILABLE gives `identity_unavailable` while preserving the exact status fact. Missing/null/inapplicable can_push_video gives `push_permission_unknown`; false gives `push_permission_denied`. Missing/null is_gpppa gives `gpppa_status_unknown`; true gives `gpppa_disallowed`.
- BC_AUTH_TT requires exact BC ID as input binding; missing returned BC proof gives `identity_bc_binding_missing`, contradictory returned BC is input failure. Missing/null ads_only_mode gives `ads_only_mode_unknown`. True/false is retained, never interpreted as authorization for organic publication. For TT_USER the inapplicable ads_only_mode is retained without inventing a requirement.

Pixel:

- Absent/null ownership gives `pixel_ownership_unknown`. Recognized UNBOUND gives `pixel_unbound`; unrecognized or inconsistent relation/ownership combinations give `pixel_ownership_unknown`. SHARED/false is retained as shared ownership, not rejected merely because not owned. TRANSFERRED/true and documented null relation/true are internally consistent; do not promote them to advertising permission. No extra requirement that pixel owner BC equal identity BC.
- Absent/null/empty events gives `pixel_events_unobserved` (not tracking absent). Optional event selection is required to assess event facts; none gives `event_not_selected`.
- Selected deprecated=true gives `event_deprecated`; missing/null deprecated gives `event_deprecation_unknown`.
- Returned event_type PAGE_VIEW or null optimization_event gives `event_not_optimizable`; absent/unrecognized optimization_event gives `optimization_event_unknown`. Returned SHOPPING is the only bounded existing configuration event considered; another present event gives `optimization_event_outside_current_profile` without claiming it is invalid on TikTok. Never derive optimization_event from name/event_code/event_id/event_type.

Unknown enum recognition and applicability come from the frozen parser. Contradictory typed fields cannot silently satisfy a necessary fact; assessment checks applicability/presence/recognition together.

## Focused Acceptance After Approval

Use actual pure parser fixtures, not fabricated eligible catalog objects. Cases: all necessary TT/BC facts present still not_assessed; CustomIdentity no missing-status false alarm; AUTH_CODE unsupported; each absent/null/false permission; GPPPA; wrong BC/account/digest/duplicate identity; UNBOUND versus SHARED and null/TRANSFERRED ownership; empty delayed events; deprecated/null PAGE_VIEW/unknown/non-SHOPPING; strict integer-versus-string IDs retained; model_copy tampering rejected; deterministic digest/reasons; no IO or mutation. Preserve all historical social configuration/compiler hashes. Run focused pure tests, Ruff/mypy/diff only; no DB, Full, remote or live calls.

## Implemented Checkpoint

`app/publication/tiktok_linked_assessment.py` implements the proposed pure callable
and strict request/result. `ownership_assessment="scope_consistency_only"` explicitly
labels the supplied account comparison; it is not database ownership or freshness
proof. SHOPPING is compared as the exact returned current-profile necessary fact,
accepting the parser's deliberate `not_evaluated` enum recognition without treating
that as unsupported. No source registration, catalog conversion, ad wire or TTL.

Actual parser-backed tests cover complete TT/BC facts without eligibility, other
routes, negative/null permissions, BC binding, shared/unbound/transferred ownership,
deprecated/PAGE_VIEW/other events, delayed empty events, exact string/integer IDs,
and malicious model_copy plus recomputed digest.93 assessment/parser tests passed;
the deliberately wrong-type model_copy case emits the expected Pydantic serializer
warning before strict revalidation rejects it. Whole Ruff/mypy832 passed.
