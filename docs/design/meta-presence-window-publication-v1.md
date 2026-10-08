# Meta Presence Window Capture And Atomic Publication

Predecessors reviewed: pureparsera99aaed, contracts e5d9dae, finalized0089 storage
atdb4325a. Implement this as one coherent producer lane; root owns downstream V3/
planner consumption separately. No new provider requests, write capability, legacy
Completion columns/manifests, event selection or attribution defaults.

Reserve migration0090 for one ephemeral `meta_presence_stage_contexts` table and
paired nullable fields on MetaStagedMetric. Follow the storage-review proposal with
these exact interfaces. Module `app/meta/presence_staging.py`; model module
`app/meta/presence_models.py`; freeze dialect triggers separately as existing patterns.

`MetaPresenceWindowV1` immutabletyped context document schema
`inlet.meta-presence-window.v1`: window_token32hex, nativeconnection_id positiveint,
workspace_id/account_id/integration_id, native_advertiser_id, generation,
privacy_revision, starts_on/ends_on inclusive, currency/time_zone, selected_event
(SelectedEventV1), attribution (AttributionBasisV1), producer_contract/query_descriptor,
captured_at awareinstant. Numeric/date/ID bounds reuse reviewedpurecontracts;
canonicalcontext≤8KiB. Producer/query/attribution constants come from pureMeta parser.
Source's null conversion_action_type means unavailableevent, never guessedpurchase.

`MetaPresenceStageContext`: PKconnection_id, unique(connection_id,window_token),
workspace/account/integration/nativeadvertiser/generation/privacy/dates/capturetime
scalars plus canonical_json/payload_digest/payload_bytes. CompositeownedFKs to
MetaConnection and AdvertisingAccount scopes. ImmutableUPDATE. Insert guard exact
currentnativeconnection/account/generation/event/window/privacy; no credentialdata.

MetaStagedMetric adds presence_context_token nullable32 and presence_json nullable
boundedJSON (canonicalcells≤4KiB). Bothnull orbothpresent, compositeFK(connection_id,
contexttoken) withRESTRICT; inserts/updates verify campaignownership/platform/day
againstcontext. Preserve all existing numeric columns/normalization and rowidentity.
Delete stagedrows beforecontext; ordinary detail-checkpoint cleanup must not clear
campaignpresencecontext. Legacy rows remainbothnull; no defaults/backfill/adoption.

Shared helper entrypoints, caller-owned transaction/locks, no commits or network:

- `begin_presence(db, source, account, now)`: ONLY in actual newwindow branch after
  source.window_start/end assigned, before first token/pageIO. Clear old campaign
  staging/context in safeorder, capture originalmetadata. Never call merelybecause
  phase is campaigns, stageempty, featurechanged, or an oldcontextisabsent.
- `stage_presence(db, source, account, staged_metric, raw_source)`: if originalcontext
  exists, verify unchangedsource/event/window/money/privacy, parse ORIGINALrow with
  pureparser and bind local/nativecampaign/day and token. No context means legacy
  bothnull; orphan/partialcontextmetadata errors. Duplicate conflictingstagefacts
  cannot silentlygain qualifiedprovenance. Preserve legitimate exactpageretry behavior.
- `capture_presence(db, source, account) -> PreparedMetaPresence | None`: before
  staged deletion, read/validate completeboundedstage/context graph, currentoriginal
  sourcebindings and everyexactnumericcell. Frozen preparedobject retains context+
  bounded (localcampaignID, MetaPresenceCellsV1) tuples. A no-contextlegacywindow
  returnsNone only with no presence-bearing stagedrows.
- `publish_presence(db, prepared, completion)`: build exact ReportingSemanticsV1 and
  finalfacts bound to actualnewcompletion, then call reviewedstore_presence. Original
  context selectedevent/metadata preserved; completion provides actualterminaltime/
  legacydigest/currentpointer. Everyreturnedrow represented, absentcalendarrowsunknown.
- `clear_presence_context(db, native_connection_id)`: onlyafter stagedrows removed or
  pairednullablefields coherentlycleared; used terminal, abort/reconnect and erasure.

Change private `campaign_performance.service.publish_meta` returnannotation to
PerformanceCompletion and return actualcreateditem aftercurrentpointerflush. Existing
callers ignoringreturn remain compatible. In both rolling and fixed terminal paths,
capture before deletingstaging; publishlegacy→publishpresence using SAMEreturneditem
and SAMEtransaction; preserve reportedfeedbackcapture and final existingauthority/
lease checks. No unlocked lookup or secondtransaction can attach provenance later.
Newqualifiedwindow invalid/partialcontext must fail atomically with no newcurrent
snapshot; old no-contextwindows finishlegacy. Report any recovery-path ambiguity
before inventing a fallback that promotes or silentlydrops provenance.

Lifecycle/reconnect/failurepaths: semantic privacybump clears presence stages/context
under sameownedlocks andFK order; ordinary archive-revisionadvance alone must preserve
originalcontext unless existingimportsemantics requires restart. Connectionreset and
campaignstagingreset explicitly clearcontext; retainedwindowdates afterreset never
adopt a newcontext. Transient errors preserve valid stagedprefix/context. No export
of ephemeral context/payloads; registertable+newcolumns/classification appropriately.
Populateddowngrade refusesincludingnon-nullstagedpayload; actualemptydowngrade only.

Acceptance: actualMeta importservice+MockHTTP fromnewwindow throughterminal onbothDB,
positive100click/10selected/$100, present0 vsabsent/empty/nonselected action entries,
count/valueindependent, partialpageresume, latefailure rollback/currentpointerunchanged,
reconnect/config/privacy/window drift, legacyinprogress noadoption, retainedwindowreset
noadoption, exactretry/conflictingduplicate, emptyreturnedrowsunknown, ordinaryhistory
vssemanticerase, actual0090DDL/FKs/bounds/downgrade. Fixedterminal compatibility too.
CustomerplanningAPI qualification is downstream and must not be claimed from imports.

## Reviewed Terminal Privacy Fence

Capture validates the immutable original context against current privacy under the
caller's unchanged workspace/source locks. `publish_meta` then invalidates existing
calibrations; their deletion triggers may advance the ordinary export revision.
The final reporting header therefore uses the actual returned completion's privacy
revision, while the ephemeral context retains its original captured revision.
This exception applies only after successful capture, inside the same terminal
transaction. It does not relax context validation on resumed pages or before capture.
The original context must still exist and exactly match at attachment; semantic
privacy erasure removes it and prevents publication of an already prepared graph.
