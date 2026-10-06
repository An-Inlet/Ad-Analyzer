# Meta And TikTok Exact Activation Adapters

This package implements concrete Meta v26.0 and TikTok v1.3 activation transports
against central activation ports 126f887. That shared successor repairs a discovered
singular/plural namespace mismatch: activation now retains the original creation
receipt's campaigns/adsets/adgroups/ads resource identity without remapping it.

The adapters accept only the fixed reviewed activation target. They reuse the
original immutable creation serializer to reconstruct every expected field, override
only status, read the exact same resource and require the reviewed paused readback
digest immediately before emission. Meta sends one POST to the fixed object ID with
status=ACTIVE. TikTok sends one campaign/adgroup/ad status-update POST with the exact
advertiser and a single original resource ID, operation_status=ENABLE, and explicit
allow_partial_success=false for ad groups. No budget, targeting, creative, identity,
media, schedule, creation or delete fields are submitted.

Context scope, provider, token expiry and dispatch time are rechecked. Changed
budget, parent, name or any other original expected field prevents emission. Missing
readback is unknown; differing complete readback conflicts. Paused/disabled readback
after an uncertain activation is unknown because the original may still finish.
Reconciliation reads the original identity only and never retries a mutation or
replaces its fence. Target-state verification carries no delivery/effective-time,
causation, authoritative-no-effect or provider-CAS claim.

Creation serializers bind ad creative/media references. Separate durable activation
preparation must additionally recheck non-activatable creation graph resources
(including creative content and uploaded media), as well as parent graph identity,
current native generation, owner/entitlement, qualified exposure, distinct exact
activation approval and the original shared reservation. This transport package
cannot replace those coordinator checks. The shared owner is implementing that
integration; no full activation customer journey is claimed here.

Constructors open no sockets, HTTP transports remain injectable, all default runtime
factories remain disabled, and no credential/provider factory is added. Existing
bounded HTTP, secret-log suppression and no-redirect/no-retry behavior are reused.
No live provider calls, account changes, advertising spend, merge or deployment.

Primary evidence checked on 2026-10-06:

- Meta official SDK commit efd8423a2e595ea8d4c04eb824ce113f2f1d68cd defines ACTIVE/PAUSED
  status and POST node updates in [Ad](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/ad.py),
  [AdSet](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adset.py),
  and [Campaign](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/campaign.py).
- TikTok official SDK commit f809c396520df2d7b201a9ccc5378d822b728ed3 defines distinct
  status-update endpoints and payload fields in [AdApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/AdApi.md),
  [AdStatusUpdateBody](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/AdStatusUpdateBody.md),
  [AdgroupStatusUpdateBody](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/AdgroupStatusUpdateBody.md)
  and [CampaignStatusUpdateBody](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/CampaignStatusUpdateBody.md).
  The official [ad status portal](https://business-api.tiktok.com/portal/docs?id=1739953422970882)
  returned an empty document body. SDK string fields do not independently qualify
  every current enum/account combination; native/live profile qualification remains
  a separate gate, not inferred from mocked success.

Focused checks: 34 tests across social and Google activation passed, including six
concrete status-update targets, original receipt digest parity, timeout before visible
effect/after effect without retry, missing readback, changed budget/parent/digest,
foreign scope and expired context. Whole Ruff, configured mypy (384 files) and diff
check pass. Full and hosted CI are not yet verified for this candidate.
Broader social/Google publication, execution and optimization contract/HTTP coverage:
134 tests passed in 2.21 seconds on the final implementation candidate.
