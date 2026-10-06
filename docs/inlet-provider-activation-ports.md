# Separate Exact Activation Ports

`app/publication/activation_contracts.py` freezes server-compiled activation targets
and the actual adapter protocol. Targets carry the original immutable creation
request, same-scope verified receipt reference/digest, exact resource identity,
reviewed paused readback digest, and explicit provider status transition. The bounded
activation plan activates the campaign last. Budget/media/creative/targeting operations
are not activation targets. Separate exact customer approval and current production
mandate/qualification/reservation checks belong to the durable coordinator, not adapters.

`ActivationTransport.read_exact(request, context, expected, now)` verifies **all**
reviewed source fields with only the intended status changed. Its digest must match
the reviewed paused digest before `apply_once`. `read_back` and `reconcile` return
`verified_target_state`, unknown or conflict; no status observation implies treatment
time, delivery, causation, no-effect, or a provider compare-and-swap guarantee. A
paused read after an uncertain update stays unknown because the original may finish
later. There is no internal retry or replacement fence.

`GoogleActivationHTTP` implements fixed v25 status-only updates with the original
full-field serializer/readback expectations, bounded HTTP, immutable exact resource
identity, and no replay. Meta/TikTok adapters are dependent work. Runtime factory is
None. Durable activation review/claim/reservation integration and settlement remain
implementation work; no live admission or completed B15/B16 claim.

Primary contract references checked2026-10-06:

- [Google v25 campaign status](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignStatusEnum.CampaignStatus)
  defines PAUSED/ENABLED; only the status field is submitted in the update mask.
- [Meta first-party AdSet SDK](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adset.py)
  exposes configured PAUSED/ACTIVE separately from effective status.
- [TikTok first-party status-update model](https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/business_api_client/models/campaign_status_update_body.py)
  and [Adgroup API](https://github.com/tiktok/tiktok-business-api-sdk/blob/main/js_sdk/docs/AdgroupApi.md)
  describe separate status-update operations; SDK schema alone is not live qualification.
