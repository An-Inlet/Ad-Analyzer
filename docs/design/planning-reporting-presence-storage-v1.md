# Reporting Presence Storage And Meta Parser Interfaces

Exact pure contracts3901fc1 are reviewed and integrated ate5d9dae. Freeze the
following independent lanes. These extend existing architecture and authorize no
provider calls or writes. No change to legacy Completion columns/manifests/V1/V2.

## Finalized Storage Lane — Migration0089

Own new modules `campaign_performance/presence_models.py`, `presence_storage.py`,
`presence_export.py`, dialect triggers, migration0089 and necessary registry/erasure/
archive/model imports. Only TWO final tables in0089. Meta staging context/nullable
columns are deferred to a separately frozen0090 after these interfaces qualify.

`ReportingSemanticsRow` table `campaign_performance_semantics`: completion_id PK;
workspace_id/account_id/connection_id; platform/source_connection_ref/generation/
privacy_revision; requested_starts_on/requested_ends_on; legacy_manifest_digest;
canonical_json/payload_digest/payload_bytes; fact_count/fact_digest. Composite FK
completion/account/workspace to existing completion scope, and account/workspace/
connection to existing advertising account scope. Unique complete header scope for
child FK. SQL counts/bytes/dates bounds use reviewedpurelimits. Immutable UPDATE.

`MetricPresenceRow` table `campaign_performance_metric_presence`: composite PK
completion_id/campaign_id/metric_date; workspace_id/account_id/native_campaign_id;
canonical_json/payload_digest/payload_bytes. Composite header scope and campaign/
account FK. Header/completion/workspace deletion cascades owned children. Source
credential/session is historical provenance, not a lifetime live FK. Immutable UPDATE.
Insert binding guards scope/platform/nativecampaign/dates and exact scalar/header/
completion correspondence. Frozen dialectDDL; equivalent modelcreate_all triggers.
Populated downgrade refuses; empty downgrade only. Never delete data to downgrade.

Helpers (no commits or network):

```python
store_presence(db: Session, header: ReportingSemanticsV1,
               facts: Sequence[ReportedMetricPresenceV1]) -> None
read_presence(db: Session, completion: PerformanceCompletion)
    -> tuple[ReportingSemanticsV1, tuple[ReportedMetricPresenceV1, ...]] | None
```

`store_presence`: caller owns source/workspace locks/finalauthority. Revalidate pure
models; exact actual completion and current pointer, owned account money/scope,
legacy manifest and complete current campaign/day rows. Each fact corresponds to
one actual legacy row and native/local mapping; every present cell equals its
normalized legacy value. Missing cells do not pretend default0 was observed. Query
descriptor equals actual completion.query_version; requested dates/completed_at/
sourcegeneration/privacy/currency/timezone/selectedevent exactly bind completion.
No header accepted merely from client hashes. New store graph immutable; retry of
identical complete graph may return without mutation, changed/partial existinggraph
fails. Bound all lists/bytes before mutation, validate complete set, flush atomically
inside caller transaction (no helper commit). Unexpected source drift raises typed
`ReportingPresenceUnavailable` (ValueError subclass), not partial success.

`read_presence`: DB-only historicalas-observed canonical/header/scalar/completefactset
validation, including actual empty set. Check completion binding but not current
pointer, live source generation/session or currentDailyMetric values (later corrections
must not rewrite history). ReturnNone only when headerandfacts are genuinely absent.
Missing/extra/duplicate/mismatched/corrupt facts underheader raise typedunavailable.
No legacy row is backfilled or reinterpreted. Export uses the same snapshotSession
and this complete-set validator for EVERY header, including when allfacts disappeared.
Each selected exportrow must match actualvalidatedrow. Preserve archivecaps/current
customer+privacydeliveryfences; no originalsession/TTL requirement forhistoricalexport.

Lifecycle: ordinaryowned finalizeddata, no protectedexecutionlineage. Register both
new tables, scope erasure and semantic privacy-bump cleanup; ordinary archive revision
advance preserves historicalfacts. Same-table eraseorder accountsforFKs. No newworker,
queue, lease or credential. TestsactualSQLite/PostgresDDL/create_all/ownership/corrupt
whole-set/history/erasure/archive/rollback/downgrade, plus legacyV1/V2 compatibility.

## Independent Pure Meta Parser Lane

Own `app/meta/presence.py`, focusedtests+ledger only. No collector, staging, DB or
legacy-normalizer change. Expose frozen `MetaPresenceCellsV1` with native_campaign_id,
metric_date, selected_event and fivecells matching ReportedMetricPresenceV1.
Expose `parse_meta_presence(source, *, expected_advertiser, currency, starts_on,
ends_on, selected_event: str | None) -> MetaPresenceCellsV1`.
Use existing metric_values validation/profile and compare against its exact numeric
outputs. Reconstruct presence from ORIGINAL parsed source, never normalizeddefaults.
Required impressions/clicks/spend fields obey existingmalformed-response rules.
Selectedaction entry with explicit0 =>present0; absent/null actionlist, emptylist or
selectedactionabsent =>missing, not0. Count/value independent. Unselectedevent and
unsupported selected-value event =>unsupported/null. Duplicate matchingaction or
malformed metric remains controlledMetaError. Preserve exact Decimal counts; unsupported
precision fails qualification. Money uses existingmicros conversion, documented in
producercontract; no conversioncount inferred from monetaryvalue. Advertiser/date/
currency/nativecampaign checks remain exact. No guessed event/attribution window.

Export constants PRESENCE_PRODUCER_CONTRACT='meta.campaign-day.presence.v1' and
querydescriptor matching existing pinned Meta queryversion. Attribution defaults stay
explicitlyunknown. This parser is NOT persisted provenance or a functioningimport;
next0090 immutableperwindowcontext starts only in actualnewwindowbranch, beforeIO,
with pairednullable stagedtoken/payload. Oldin-progress no-contextwindows staylegacy.
Root will freeze0090 context/publisher seams after storage+parserreview; neitherlane
owns MetaSyncService or changes publish_meta yet. No dependent lane invents schema.
