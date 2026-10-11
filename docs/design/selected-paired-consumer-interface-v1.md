# Selected Paired Evidence And Consumer — Proposal

This is the next dependent private interface after the raw traffic producer/pure
DTO and selected collector reviews. No capability registration until actual
collector, composer, persistence, currentness, archive and erasure checks pass.

## Saved Proof

Add optional traffic_pin: SelectedTrafficPinV1 | None = None to
SelectedRetainedAccountProofV1, with omission when None in Python/JSON serialization
and digests. Pin lives in dependency-light selected_traffic_contracts.py to avoid
ports/documents/proof cycles. Existing legacy and already-frozen absent-traffic v4
canonical bytes remain unchanged. A non-null traffic pin requires chosen capture,
identical SourceFence, AggregateDependencyV1 and campaign_map_digest. No independent
selected/generic conversion merging or inferred traffic proof.

## Current And Historical Ports

Add internal selected_traffic_reader.load_raw_range_traffic(db, *,account,
expected_source, selected_pin) -> RawRangeTrafficGraphV1 | KnownTrafficGap.
Exact current selected aggregate verified before absent-receipt/absent-profile gaps;
no newest lookup, no stale capture→gap. Resolve at most2 exact owned completion
receipts; unknown/corrupt/multiple present receipts abort. Owned current manifest,
full campaign map, current source/privacy and strict sidecar correspondence required.
Read receipt/currentness and sidecar fully; profile mismatch is explicit unsupported
only for intact recognized legacy provenance, never corruption. No identity/network.
Caller uses original-session contexts before/after and final checks after all reads.
Current capture_selected_reporting_pin builds optional traffic pin from this result
and repeats it with existing whole reporting proof. Semantic absence is already
bound through qualified legacy_reporting_digest, so a new valid sidecar changes proof.

Historical traffic validator uses immutable receipt/header/facts and saved pin,
not current DailyMetric/current pointers/live session/TTL/full current map. Match
exact header/fact digests, receipt digest, aggregate dependency/source scope and
retained campaign ownership integrity. Saved old full-map hash remains opaque.
Any missing chosen traffic receipt or sidecar fails historical integrity. Existing
semantic erasure removes both graphs and revokes prepared export authorization.

## Paired Bundle

SelectedPairedEvidenceV1(NoAuthority): selected:SelectedPlanEvidenceBundleV1;
traffic_graphs tuple[RawRangeTrafficGraphV1,...] <=20;
traffic tuple[TrafficWindowEvidenceV1,...] <=400;
traffic_gaps tuple[TrafficWindowGapV1,...] <=400.
Combined private canonical bytes<=32MiB; combined traffic slots<=400.
TrafficWindowEvidenceV1.reference kind=reported_metrics, independent traffic_window
key and full typed document digest, source fence exact, observation interval from
receipt request/acquisition/publication, expiry no later than catalog deadline.
Each traffic window's account/campaign/UTC-local window/native units/aggregate/map
exactly pairs with a selected successful window; it cannot accompany an unsupported
or absent selected slot. Full raw graph recomputes every projection, one graph per
account, graph pin equals saved proof. Selected.assert_ticket always required.
Every successful selected performance slot has exactly one traffic result or typed
provenance/unsupported gap; no unrequested extra slots. No absent selected slot gets
invented traffic. Gaps bind full retained account state_digest. For mapped selected
performance, campaign_outside_mapping is impossible if complete maps must match;
mapping mismatch aborts, not downgrade. Intact absence never implies observedzero.

OwnedSelectedPairedReader initially calls reviewed selected collector (which now
retains traffic pins), then loads exact traffic graphs in new original-session
contexts and creates pure window projections. Final recheck reconstructs both
selected proof and full traffic graph after all provider/commerce/context waits.
No direct provider traffic calls from planner: deliberate range API must acquire it.

## Composer

SelectedPlanComposer.compose(ticket, evidence:SelectedPairedEvidenceV1, policy,
generated_at) -> PlanVersion. Require exact reserved v4 pair/digest and actual
server ticket, complete context/goal/native settings, exact source set and deadline.
Output embeds selected.reporting_proof and all actual selected+traffic references.
Preserve current planner's bounded manual action/scenario/creative scaffolding,
fixed allocations, exclusions, ceilings and no-execution authority. Do not pass
fabricated selected data to V3 contracts or relabel V3 documents as v4. Prefer an
additive composer to avoid changing old policy semantics and canonical bytes.

Every primary/comparison window is described separately. Render selected event
resource and conversions vs all_conversions family explicitly; exact Decimal
counts and integer-micros traffic, metric presence and missingcalendar days.
Positive selected count can never produce a no-conversions finding. Only complete
requested-day selected cells with exact sumzero permit the statement of observed
zero; spend wording additionally needs actual positive traffic observation. Partial
zero/missing selected cells say unavailable/partial, never no conversions. Missing
traffic provenance is explicit, not $0/0clicks. Positive count may retain the existing
descriptive retain action, subject to customer constraints/zero ceiling; it confers
no spend authority. No causal attribution, relative ROI, forecast, automatic budget
change or cross-platform normalized recommendation is introduced.

Tests: actual Aug1–Sep30 range publisher+selected API→owned pairedreader→composer
with September100clicks/10selected/$100 and a separately sliced August; explicit
zero vs omitted cells/rows; both conversion families; incomplete traffic/capture;
source/head/receipt/graph/privacy/session changes; all legacy goldenbytes unchanged.
Then service/registry/repository dispatch, historicalread/export/semanticerasure,
and real TLS browser→persistedselectedinput→v4plan before any user-facingactivation.

## Review Clarifications

Traffic reference observation times use actual retained receipt/header timestamps,
never collection-time restamping. Final expiry and authority sampling follow all
paired reads. Revalidate copied nested graphs/proofs and recompute both projections
before composer acceptance. Qualified state commits sidecar state but does not
itself authenticate receipts; the owned loader checks receipt presence/absence and
the current explicit selected aggregate on every use. Partial positive spend must
be described as an observed subtotal. No-conversions wording requires complete,
explicit selected zero. Contracts alone do not close Q01 or activate the runtime.
