# P02 Catalog Usability Follow-Up — Proposal Only

This is a shared-interface proposal, not implementation authorization or completed coverage. It follows the catalog contract at166048b and implementation06b2ac5. Do not change existing GoogleNativeInventory/MetaNativeInventory/TikTokNativeInventory fields, defaults, validators, serialization or digest domains to add names or child rows. Existing persisted source/calibration evidence must continue to deserialize and hash identically.

## New Observation Sidecar

Introduce `PlanningEntityMetadataObservationV1` as a new frozen, extra-forbidden type and digest domain `inlet.planning-entity-metadata-observation.v1`. Fields: schema_version; exact workspace/account/connection/platform/connection_version; source_binding_digest; reporting starts/ends; observation_started_at, observed_at, expires_at; per-kind coverage with count/scope/reasons; bounded entities. No default TTL. Expiry is bounded by the actual existing read context/observation lifetimes; composite expiry is their minimum. No unbounded JSON metadata or credential fields.

Each `PlanningEntityMetadataV1` carries kind, native_entity_id, native_parent_campaign_id nullable, native_name nullable, and name_status observed/unavailable. IDs use existing provider grammars: Google customer10digits/entitynumeric resource segments; Meta/TikTok numeric1..32; explicit source/account binding is mandatory. Name bounds need a checked provider contract; over-bound data must fail that metadata observation or report an explicit field unavailable, never silently claim exact truncated native text. Entity cap200 per kind and page/time/byte limits match the existing collectors. No guessed management URLs. Customer names are plain text, rendered with textContent/escaping; never HTML.

New `PlanningCatalogObservationV1` wraps the *unchanged* native inventory plus the new metadata sidecar, their individual digests and a new composite digest domain. It must validate identical source ownership/generation and reporting period; duplicate IDs, foreign children or incompatible parent sets fail. Independent native reads are not atomic: record both time intervals and `atomic_snapshot:false`. A final fresh source/session/entitlement/read-control check follows both reads. No observation may outlive its earliest expiry. Do not persist it in existing inventory/evidence columns under an old discriminator.

## Provider Reads

Google: new fixed bounded semantic read of campaign.id/resource_name/name plus a separate bounded ad_group query selecting resource_name/id/name/status/type/campaign. Validate every Google resource customer against the owned customer and each child against an observed campaign. Preserve missing-parent/topology-change as explicit unavailable/retry, not silently remove children. New adgroup settings projection is versioned, never shoehorned into campaign budget fields. Existing Google native inventory reads/digests remain unchanged; sidecar supplies names and child inventory. Shared campaignBudget linkage remains visible.

Meta: new bounded owned campaign/adset metadata reads include id/account_id/campaign_id/name with the same effective-status scope as native inventory. Keep known-status limitation even when all pages complete. TikTok: bounded campaign/adgroup metadata reads include advertiser_id/campaign_id/adgroup_id/name fields confirmed against the supported provider contract, and retain regular-family limitation. These are exact fixed endpoints/fields, no user-supplied queries or URLs. All three adapters use refreshed owned read contexts around every IO boundary and existing private HTTP read guards. No credential or raw response logging.

Do not overload the old NativeDiagnosticService response with defaults. Add a separate planning catalog service/composition or a new explicitly versioned read method, reusing its current ownership/session/vault checks; a tiny shared private read-context binder can be proposed separately if necessary. It must preserve post-IO rebinding and API transaction release. No execution runtime, budget mandate, financial qualification or mutation sink is needed.

## Customer Projection V2

Introduce `TargetCatalogV2` / `TargetV2` with explicit schema version. Keep V1 endpoint response available or create a versioned route; no existing consumer silently changes response meaning. New fields:

- `canonical_entity_key`: deterministic domain-separated key over workspace, owned account identity, platform, kind and native entity ID; stable across successive observations and reconnect generations of the same account. This is a lookup identifier, not authority.
- `selection_key`: ephemeral selection identifier bound to canonical key plus exact source generation, native inventory digest and metadata digest. Do not describe the V1 source-only selection hash as snapshot-bound; its existing semantics remain unchanged.
- `provider_reference`: strict structured platform, advertiser/customer ID, entity ID and parent campaign ID when applicable. Customers can see their own IDs; no secrets or arbitrary external URL strings.
- `name`, `name_source`, and observation provenance from the sidecar; null plus explicit reason when unavailable.

A future plan consumer receives canonical entity key and expected snapshot selection identifier, freshly resolves the owned current source, and requires a new observation if generation/inventory/metadata changes. It never treats a hash, display name, provider reference or browser-provided native ID as authorization. Social budget-owner keys remain null until a separate versioned hierarchy classifier can establish ownership; native amount presence is insufficient.

## Migration And Acceptance Impact

No SQL migration required for an ephemeral new read endpoint. Old observation models/digests stay byte-for-byte stable; add golden old payload/hash tests before introducing the sidecar. If later persisted, use a new document discriminator/table schema migration explicitly; do not reinterpret existing protected evidence.

Required acceptance before UI: all three actual MockHTTP readers; bounded pagination/capacity and foreign-parent denial; absent/malformed/overlong names; HTML-like names rendered as text; Google adgroups and shared budgets preserved; missing names explicitly unavailable; original-session/source generation/revocation/expiry during either read denied; exact unchanged legacy observation hashes; canonical keys stable across refresh while snapshot keys change; references never authorize foreign targets. Distinct read intervals and partial scope stay visible. No live-provider claim until separately authorized and verified.
