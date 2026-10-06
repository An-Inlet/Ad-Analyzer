# Meta And TikTok Publication Contract Extension

Additive module `app/publication/social_contracts.py`, based on PR108. Google and
fixture documents are unchanged. The API/compiler pairs are Meta v26.0 /
`meta_image_v26_v1` and TikTok v1.3 / `tiktok_video_v13_v1`.

Frozen dependent-adapter names:

- `ProviderMediaBinding`, `ProviderMediaReader.read_verified(workspace_id, binding)`.
- `MetaImagePublicationFields`, `TikTokVideoPublicationFields`, `SocialPublicationReview`.
- Ten typed operation classes (`MetaUploadImage`, `MetaCreatePausedCampaign`,
  `MetaCreatePausedAdSet`, `MetaCreateImageCreative`, `MetaCreatePausedAd`,
  `TikTokUploadVideo`, `TikTokUploadCover`, `TikTokCreateDisabledCampaign`,
  `TikTokCreateDisabledAdGroup`, `TikTokCreateDisabledVideoAd`).
- `SocialResourceRef(step_id, kind, output='resource_name')`, `SocialPublishStep`,
  `SocialPublishPlan`, `SocialBoundRequest`, `SocialProviderResponse`,
  `SocialProviderReceipt`, `SocialProviderContext`, `SocialValidationEvidence`,
  `SocialPublicationTransport` and disabled `get_social_publication_transport()`.
- `OUTPUT_KINDS`, `social_refs(operation)`, `social_resource(scope, name, kind)`.

Transport methods match Google port sequencing: validate_only, apply_once,
read_back, reconcile; all take exact typed request, transient context and current
time. Reconcile takes immutable original-attempt response history. Context secrets
are excluded from serialization. `SocialValidationEvidence.kind` distinguishes
local_schema, provider_validate_only and unsupported. None authorizes publication.

Meta's first profile is a manual Facebook-feed image ad; TikTok's is a manual,
non-Spark video with explicitly reviewed cover, adult age groups and TikTok-only
placement. All entity operations explicitly PAUSED or DISABLE. Media bindings
include owned ID, SHA256, byte size, dimensions and validation version/digest;
video additionally requires duration. Provider IDs remain internal scoped names,
not URLs. Opaque media IDs are bounded; parent kinds are checked, not merely prefixes.

Required qualification blockers remain on social reviews: primary SDK shapes do
not establish eligibility for exact budget, attribution, identity, tracking,
placement or schedule combinations. Later qualification needs server-persisted
current evidence and a separately reviewed schema extension. No live eligibility
is inferred from compilation. Current factory is unavailable. Compilers, HTTP
adapters, qualification, coordinator integration and UI remain dependent work.

Primary shape references supplied by the provider research package:

- [Meta official SDK v26.0](https://github.com/facebook/facebook-python-business-sdk/tree/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd)
- [TikTok official SDK v1.3](https://github.com/tiktok/tiktok-business-api-sdk/tree/f809c396520df2d7b201a9ccc5378d822b728ed3)
- [TikTok web pixel events](https://business-api.tiktok.com/portal/docs?id=1739361474981889)
- [TikTok video information](https://business-api.tiktok.com/portal/docs?id=1740050161973250)

No credentials, provider connections, uploads, advertising changes or spend used.
