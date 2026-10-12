# Retained Selected Observation Provenance v1

Baseline: local `0b9962a`. First dependency is a typed retained metadata path for
already qualified captures; social producers are a separate dependent package.

## Contract And Compatibility

Add optional `observation_provenance` to the existing selected capture pin. Absent
means the historical document did not retain typed metadata. Omit the absent key
when serializing, preserving historical document/state digests and export bytes.
Do not migrate, backfill or re-sign historical documents; no document version bump.
This is an additive retained schema shape: new readers accept old documents, but old
extra-forbid readers reject enriched documents. Downgrade compatibility is not promised.

The bounded immutable value retains original event namespace/owner/native ID, metric
family, API version/query profile, producer contract, attribution basis, exact requested
local capture interval, start/completion time and capability. It carries no observation
counts, current provider defaults, customer identifier, credentials or new authority.
The enclosing pin binds full account/source/privacy/generation, selection/capture/request
and aggregate digests, currency/time zone. Validate platform event/family/owner grammar,
producer attribution agreement, date containment and timestamp ordering at construction.
Every historical integrity path (current read, export and exact replay) additionally reprojects metadata from the exact immutable capture and
requires equality. Present metadata cannot be stripped from a saved document without
breaking its stored digest/dependency equality. Absent legacy metadata stays absent.

New graph projections retain metadata automatically. Legacy pin consumers remain valid;
old historical exports keep existing digest validation. A previously generated document
may be conservatively stale for currentness after enrichment; never rewrite it or silently
make it current. Historical access still validates original capture integrity and current
viewer/privacy authority. Test this compatibility explicitly.

Null attribution windows are unavailable, not zero. A retained zero-day window is literal
provider metadata, never comparability approval. Unknown provider-default provenance must
have null windows and unknown report-time basis. Supported capability does not establish
business event equivalence or complete coverage. No generic aggregate becomes selected
proof. Requested capture dates are not evidence of complete day observations; requested
plan windows remain the existing separately scoped evidence intervals.

## Smallest Complete Path

Implement typed projection → new pin → existing saved PlanVersion/current/export/replay
→ strict historical reprojection, without new persistence tables/API routes/policy versions.
The customer review may display typed saved fields but must keep unknowns and all existing
coverage/comparability warnings. No current-settings substitution or numeric combination.

Focused acceptance: strict typed shape, malformed scope/event/date/producer/capability;
original metadata equality and tamper rejection; absent-key serialization/digest stability;
actual new capture generation/read/export/replay on SQLite then PostgreSQL; one genuinely
pre-change saved document roundtrip with exact payload/digest; known/unknown attribution
and zero window semantics; legacy renderer remains honest. Full Ruff/configured mypy and
bounded focused pytest with exact original exit/XML/source evidence. Stop first failure.

Before any genuine Meta/TikTok selected producer, verify official source semantics and
existing adapter ownership/read-only contracts. Fixtures/injected clients only. No live
verification is inferred. No push/hosted/deploy/credentials/provider calls/spend; retention,
sharing and human quality holds unchanged.

## Adapter Investigation / Official Semantics Status

The existing Google selected request explicitly uses provider_default_unknown attribution
(null click/view windows, unknown time basis); retain that fact, do not infer defaults.
Meta `presence_staging.py` retains a chosen action type with unknown attribution, while
`client.py`/`normalize.py` use legacy reporting. TikTok `presence.py` deliberately keeps
generic conversion separate from unsupported selected observations. Neither is sufficient
by itself for the selected capture/proof path. No social producer implemented here.

Official documentation retrieval on 2026-10-12: Meta Insights
https://developers.facebook.com/docs/marketing-api/insights/ returned HTTP429; parameters
page inaccessible. TikTok https://business-api.tiktok.com/portal/docs?id=1738864835805186
returned no readable documentation. Official Meta SDK fields were readable at
https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/main/facebook_business/adobjects/adsinsights.py
and identify action/attribution fields, but field presence does not verify request/version
semantics or default windows. No conclusions drawn from third-party search results.
Obtain version-specific authoritative semantics before social implementation; this is
a documentation/contract verification gap, separate from future live verification.

Compatibility acceptance distinguishes the genuine pre-change exported JSON fixture
(pure full-payload/document/state-digest equality) from actual database legacy cases
newly generated with an explicit old omit-metadata projection. The latter require
source_changed currentness after enrichment while current/export/replay document payloads
remain equal. They are not represented as original pre-change persisted database rows.
