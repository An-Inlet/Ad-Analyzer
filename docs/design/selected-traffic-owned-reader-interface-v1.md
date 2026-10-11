# Owned Raw Traffic Reader — Exact Ports

Proposed implementation files: app/planning_documents/selected_traffic_reader.py,
new focused tests, package ledger. No proof/history/bundle/runtime edits.

## Current SQL Port

load_raw_range_traffic(db: Session, *, account: AccountRef,
                      expected_source: SourceFence,
                      selected_pin: SelectedPlanPinV1)
    -> RawRangeTrafficGraphV1 | KnownTrafficGap

Caller owns a clean active non-nested transaction, original-session authorization
and workspace-first locks before/after this call. No commits, network, clock/token
reads or standalone authority. Revalidate every copied DTO. Resolve the actual local
account/source binding using the same customer_intents.account and source fingerprint
formula as resolve_source_fences (no principal/network substitute); compare exact
expected source, connection version and current privacy.

Before ANY gap: load_selected_plan_graph for the exact selected_pin.capture_id,
which checks actual current selected capture/selection/aggregate/full manifest;
require its recomputed pin == selected_pin and its full current owned campaign map.
Never downgrade mismatched map/source/privacy or unrelated completion into absence.

Resolve RangeReceiptRow only by exact workspace/account/completion, bounded LIMIT2;
multiple rows abort. Zero rows yields range_traffic_provenance_unavailable ONLY after
selected-pin validation. Non-Google current selected account yields unsupported_traffic_profile.
For one receipt use read_range_receipt(require_current=True), require its aggregate
exactly matches selected_pin.aggregate. Read exact completion presence. Absent header
AND facts yields provenance gap; corrupt partial graph always aborts.
A present unknown or different producer is not silently accepted. Known structurally
valid alternative profile can yield unsupported_traffic_profile; an unrecognized or
metadata-incompatible header aborts. Initial implementation recognizes only the new
raw traffic profile for Google success; no legacy query-version inference.

Build RawRangeTrafficGraphV1 with the complete selected graph campaign map and the
actual receipt/header/facts. Recompute full manifest and require every retained traffic
cell matches its DailyMetric value and vice versa; generic conversions remain manifest
integrity inputs only. Require resulting aggregate/fence/map commitments equal selected
pin. Return only after full validation. Failure raises existing changed() generic409,
not raw provider/SQL content. Caller final authorization remains mandatory.

## Exact Gap DTO

KnownTrafficGap(Frozen):
- schema_version Literal['inlet.selected-traffic-gap.v1'] default same
- account: AccountRef
- selected_pin: SelectedPlanPinV1
- reason Literal['range_traffic_provenance_unavailable','unsupported_traffic_profile']
- explanation: fixed server text selected by reason, not arbitrary caller prose

Require account == selected_pin.account. The selected pin commits the validated scope,
aggregate/capture and full mapping. reporting_pin_digest at paired bundle level is derived from the complete
SelectedRetainedAccountProofV1.state_digest, not merely the selected pin. No campaign_outside_captured_mapping
at this account reader: the map MUST match the selected capture; a per-target adapter
may use that existing reason only when its own exact target genuinely lies outside
an otherwise valid map, never for map disagreement.

## Historical SQL Port

validate_historical_raw_range_traffic(db: Session, *,
                                     expected_pin: SelectedTrafficPinV1) -> None

Clean caller-owned transaction; caller retains normal historical read/privacy authority.
PlanVersion retains only the pin, not the entire traffic graph. Resolve the EXACT
owned receipt by pin.range_request_id and require receipt digest/aggregate equality.
Read exact immutable completion/header/facts and compare the complete profile, scope,
metadata, header/fact digests. Validate retained facts' current campaign ownership and
native identity. The original complete-map digest is an opaque saved commitment: it
cannot be reconstructed from a changed current map and is not claimed independently
verified by this historical port. No current DailyMetric manifest, current pointer,
source grant, TTL or privacy-counter comparison. Semantic erasure removes retained
receipt/presence and rejects history. No refreshed proof/restamping.

Tests: actual raw range + selected acquisition/confirmation/capture on both DBs;
exact-current graph success; no receipt/old receipt missing profile gaps after exact
selected validation; raw fact loss/foreign scope/map/current aggregate changes abort;
manifest/cell tampering abort; duplicate completion receipts abort; later import retains
saved history while semantic erasure denies it. No manufactured aggregate or presence
fixture substitutes for the actual successful path.
