# Versioned TikTok Linked-Identity Publication Proposal

Design only, based on dd21b8b; October 7, 2026. No application contracts, provider calls, account links or admission gates changed. The parent-verified [rendered discovery response contract](tiktok-rendered-response-contract-20261007.md) resolves the earlier owner-export documentation request. It does not qualify publication.

## Actual Current Boundary

`publication/social_catalog.py::TikTokCatalogOption` and `social_contracts.py::TikTokVideoPublicationFields` accept only CUSTOMIZED_USER. `social_customer_producer.py` constructs that exact configuration and binds separately reviewed private video and cover. `social_compiler.py` uses compiler `tiktok_video_v13_v1`; `executors/tiktok_publication.py` uploads advertiser library media, creates disabled campaign/adgroup/ad, and reads exact fields back. Its ad body has identity_id/type, video_id, image_ids, text, destination, CTA, pixel and DISABLE; it has no identity_authorized_bc_id or dark_post_status. Its upload sets auto_fix_enabled=false and auto_bind_enabled=false. Uploading a library asset is not proof of identity permission or a TikTok post.

`production_runtime/tiktok_contracts.py::admit_tiktok_source` denies all live manifests. The decoded catalog can only come from an explicit contract scenario. Default source registration remains absent. Existing actual API/browser coverage proves those offline contracts, not a currently eligible linked-profile launch. Changing the identity enum alone would misrepresent both the reviewed creative and provider semantics.

## Confirmed Primary Evidence

- TikTok's January 2026 [transition announcement](https://ads.tiktok.com/business/en/blog/custom-identity-transition?redirected=1) says Custom Identity is being phased out and links new campaign creation to verified profiles. It also describes continued use of uploaded/library videos. This is product guidance, not an API field-combination specification.
- [Identity Info](https://business-api.tiktok.com/portal/docs/get-info-about-an-identity/v1.3) documents BC_AUTH_TT requiring its authorized BC ID, linked identity availability and permission flags. GPPPA accounts cannot create Spark Ads; BC ads_only_mode forbids dark_post_status=OFF. List presence and missing flags are not affirmative permission. The info endpoint uses profile_image_url; the already verified list uses profile_image. Do not mix decoders.
- Official [Show Through Ads Only help](https://ads.tiktok.com/resources/help/article/how-to-turn-on-dont-show-on-tiktok-profile-option-in-tiktok-ads-manager?lang=es-419) distinguishes Spark Push from existing-post Pull/video-code methods. Uploaded/library videos with a linked identity can use Push; this visibility setting is not an interchangeable toggle on every creative route. UI defaults are not API defaults.
- The official [AdcreateCreatives SDK model](https://github.com/tiktok/tiktok-business-api-sdk/blob/main/js_sdk/docs/AdcreateCreatives.md) contains identity_authorized_bc_id, dark_post_status, tiktok_item_id and video_id. It models them as optional strings and does not establish conditional requirements or valid combinations. Its ENABLE default must never enter Inlet's disabled-create serializer.
- The authoritative [Create An Ad page](https://business-api.tiktok.com/portal/docs/create-an-ad/v1.3) and [stable document ID](https://business-api.tiktok.com/portal/docs?id=1739953377508354) resolved in public browsing but returned no extracted field-table text in this bounded research. No response fields or permission semantics are inferred from generic SDK InlineResponse200.

These sources support recommending a separately modeled **linked single-video Spark Push, ads-only** slice as the closest continuation of the existing private-video workflow. They do not yet prove its complete v1.3 wire contract. Existing organic-post Pull and AUTH_CODE require a different creative ownership/authorization model and are outside this minimal slice, not removed from future scope.

## Minimal Proposed Interfaces

Names below are proposals to freeze after review, not existing callable APIs. The discovery worker owns the new versioned pure parser; consume its committed normalized identity/pixel observations directly, without converting them into the old SocialCatalog.

1. `LinkedIdentityRefV1`: discriminated TT_USER(identity_id) or BC_AUTH_TT(identity_id, identity_authorized_bc_id required). No CUSTOMIZED_USER/AUTH_CODE, no inferred BC. References remain account/generation scoped by their enclosing request.
2. `LinkedIdentityObservationV1`: exact owned ExecutionAccount plus request/discovery digest, typed identity reference, observed_at/expires_at, availability and optional permission facts retaining absence. Required eligibility facts are explicitly AVAILABLE, can_push_video=true, is_gpppa=false; these are necessary checks, not sufficient launch qualification. `ads_only_mode` preserves applicability; no missing=false conversion.
3. `TikTokLinkedPushSelectionV1`: opaque option ID binding discovery request/digest, identity reference, exact returned pixel optimization_event, server profile digest and account generation. Customer chooses named options, not raw permission proof, provider JSON or arbitrary event names. Only the existing bounded SHOPPING event is initially eligible; PAGE_VIEW/null and other events remain unavailable rather than coerced.
4. `TikTokLinkedPushReviewV1`: new schema/variant committing the approved private video and separate cover bindings, identity selection, exact reviewed ads-only behavior, copy/destination/CTA and existing explicit budget/schedule/targeting configuration. This is a new hash domain; do not add optional fields to historical v1 documents or silently reinterpret CUSTOMIZED_USER plans. Fresh identity permission discovery must be rechecked before approval and every emission.
5. `TikTokLinkedPushAdmissionReader(request, observation, reviewed_selection, now) -> bound eligibility evidence OR fixed blockers`: server-code reader with concrete native facts and explicit field-combination qualification; cannot be satisfied by source-ID matching alone. Existing configuration qualification and creation/activation financial exposure ports remain separate. No customer-supplied evidence document.
6. New compiler identifier `tiktok_linked_push_v13_v1`, with explicit operations only once ad/create and readback tables establish the exact route. Reuse library upload/private media validation primitives where semantics match, but do not reuse a v1 ad operation that cannot represent BC/visibility. New kind must enter coordinator and activation version dispatch deliberately. No migration proposed until the actual immutable-document/version union and privacy registration are reviewed.

The reviewed visibility intent is ads-only. The exact wire literal and any additional creative_type/authorization flags remain unset until confirmed. No implicit organic publication is allowed. Review UI must explain linked-profile use even if the ad is hidden from the organic profile. A paused ad does not by itself prove that underlying post creation has no organic side effect.

## Exact Remaining Evidence Before Serializer Freeze

| Required evidence | Why it matters |
| --- | --- |
| ad/create creatives conditional table for TT_USER and BC_AUTH_TT, and corresponding permission/scope requirements | Establish whether uploaded video_id + explicit identity is Spark Push; whether creative_type/creative_authorized or another field is mandatory; whether BC ID is required in each operation. |
| Exact dark_post_status enum, applicability and creation behavior with DISABLE | Explicit ads-only review cannot depend on Ads Manager defaults; must know whether post creation occurs before activation and how it is hidden. |
| video_id versus tiktok_item_id rules; cover image_ids and ad_text behavior for Push | Do not accidentally select Pull, override an immutable post, discard reviewed cover/copy or create an extra unreviewed post. |
| ad/create response resource IDs and ad/get response/readable fields for linked Push | Need exact identity/BC/visibility/media/post binding and retained IDs for readback and unknown reconciliation. SDK generic return type is insufficient. |
| Permission revocation and identity/info/list authoritative currentness; business-profile verification representation if required beyond AVAILABLE | Do not treat permission flags/list membership as a complete advertiser launch qualification. Missing proof remains a blocker. |
| Upload-to-Push media constraints and existing attribution/budget/schedule field-combination support | Existing v1 engineering assumptions are not requalified by the identity transition; retain their independent blockers. |

Obtaining a publicly rendered conditional table is engineering research, not a renewed request for an owner schema export. Actual nonproduction account behavior and production qualification, when eventually authorized, are separate evidence gates; no credentials or live-account actions are requested by this proposal.

## Independent Offline Work And Acceptance

The discovery parser can finish now with strict envelopes, applicability-aware fields, bounded pagination, duplicate/cycle checks and source ownership. Next, a pure linked eligibility assessment can report precise missing/negative facts and versioned selection hashes while remaining unable to publish. Preserve old v1 fixtures and exact hashes in both packages.

After the remaining conditional table is verified and interfaces approved: add explicit serializer/readback fixtures for both TT_USER and BC_AUTH_TT; missing permission/BC/status and GPPPA cases; ads-only behavior and reviewed-cover binding; unknown one-write/no replay; permission/generation/session change during IO and after claim; separate activation using the original held reservation. Finally ordinary configured API and TLS journeys must use the owned private context and actual HTTP mock, with no runtime-getter override or seeded execution state. Default real transport must reject contract_test before construction; no default source or live admission is added. Google/Meta behavior and hashes remain unchanged.

No DB tests or Full run were needed for this design-only package. Application/runtime/contract implementation awaits interface approval and the exact publication field evidence above.
