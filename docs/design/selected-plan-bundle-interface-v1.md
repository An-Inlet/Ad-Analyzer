# Pure Selected Plan Evidence Bundle V1 — Proposed Freeze

Own only new app/planning_documents/selected_plan_bundle.py, its pure tests and
package/interface docs. Base on root proof commit once frozen. No SQL, collector,
composer, route, capability registry, runtime enablement or old V3 edits.

## Exact Additive DTOs

SelectedWindowEvidenceV1(Frozen): reference: EvidenceRef; target: TargetRef;
document: SelectedPlanWindowV1. No copied aggregate traffic, fabricated V3,
optimistic coverage/qualification fields or synthetic selected conversions.

SelectedReportingGapV1(Frozen): account: AccountRef; target: TargetRef | None;
requested_window: ReportingWindow; reason: Literal[selected_capture_not_requested,
unsupported_selected_mapping,campaign_outside_captured_mapping,catalog_unavailable,no_catalog_campaigns];
reporting_pin_digest: Digest; explanation: Text (existing1..2000 characters).
Only catalog reasons have target=None; other reasons require exact campaign target.

SelectedPlanEvidenceBundleV1(NoAuthority): operation_id: Id; input_digest: Digest;
privacy_revision: strict int >=0; collected_at: aware datetime normalized UTC;
catalogs: tuple[CatalogEvidence,...] max20;
performance: tuple[SelectedWindowEvidenceV1,...] max400;
commerce: CommerceEvidence | None;
context: tuple[ContextEvidence,...] max2;
gaps: tuple[EvidenceGap,...] max400, forbidding reported_metrics/reporting_pin;
reporting_proof: SelectedRetainedProofV1 (root frozen contract);
selected_captures: tuple[SelectedPlanCaptureV1,...] max20, once per account;
window_gaps: tuple[SelectedReportingGapV1,...] max400.
Combined performance+window_gaps<=400; canonical serialized whole bundle<=32MiB.
No default fields invent a missing success, capture or proof. Reject copied invalid
nested DTOs via Frozen revalidation. Input selector None remains legacy and fails.

## Reference And Graph Binding

Window ref.kind=reported_metrics; campaign target/ref/account/source workspace and
privacy equal document.pin. Ref source_binding_digest/source_revision equal the
pin SourceFence (not generic aggregate conversions). Ref schema exactly document
schema; document_digest=fingerprint('selected-plan-window', document JSON).
Ref key='selected_window:'+fingerprint('selected-plan-window-entry', account ID,
local campaign ID, UTC-normalized window endpoints). Target native campaign ID
matches summary native_campaign_id and the full capture's exact local/native map.

Whole-bundle validation binds observation_started_at to capture.request.started_at
and observed_at to capture.completed_at (UTC instant comparisons), with expiry
strictly after observation and collection and no later than actual catalog expiry.
Reference coverage is independently conservative: partial if either count/value
has any observed requested cells, unavailable if neither has observed cells; never
upgrade complete requested-day coverage into broader provider completeness. Reasons
must be nonempty; metric_basis must identify selected provider-reported event data,
not traffic or attribution proof. Count/value completeness remains in typed summary.

Construct and revalidate SelectedPlanProjectionV1 from the exact whole captures and
all performance documents; every summary and pin must recompute exactly. No
supplied arithmetic summary stands in for full retained capture facts. Every
explicit input selector has exactly one graph and one retained proof capture_pin;
no extras, missing selector graph, latest lookup, stale selector-to-gap fallback,
or duplicate same-account captures. Each graph pin equals retained capture_pin;
each graph/source fence equals ticket source. Retained proof.assert_inputs binds
account set, selectors and privacy. Gap reporting_pin_digest is the corresponding
retained account proof.state_digest(), including explicit no-capture state.

## Pure assert_ticket And Exact Slot Product

Require ticket canonical PlanningCompositionPolicy(version=inlet.descriptive-review.v4,
generator_version=inlet.descriptive-planning.v4).digest equality directly, without
registering or calling a new active capability. Require exact operation/input
commitment/privacy, UTC collected_at>=prepared_at, full proof/ticket source equality.

Retain existing catalog, commerce, context, unique evidence-key and deadline
invariants from window_evidence without weakening V3 or wrapping data as V3.
Catalog account/native identity/units, exact source fence and primary reporting
window must agree. Each input account has exactly one catalog or catalog gap.
Required slots are account×actual catalog campaign×primary/comparison windows.
No campaigns gives one account/None/window slot; no catalog likewise. Exactly one
success OR gap per slot; no duplicates, omissions, extra accounts/windows/targets.

Catalog absence dictates catalog_unavailable; empty actual catalog dictates
no_catalog_campaigns. Otherwise an unsupported selected profile/account mapping
uses unsupported_selected_mapping; supported Google profile without a requested
capture uses selected_capture_not_requested. A supplied invalid/foreign/unavailable
capture is an error, never a gap. A valid graph without a given native catalog
campaign mapping must have campaign_outside_captured_mapping for that exact slot only.
A supported mapped selected capture must project successfully; absent selected
rows/cells remain a successful typed unavailable/partial summary, not a fabricated
zero and not an unrelated acquisition gap.

Comparison/primary endpoints are exact UTC instants converted by existing selected
projection to closed account-local days. September/New_York and August must be
supported by the same explicit retained Aug1–Sep30 capture and aggregate dependency.

## Tests And Remaining Boundaries

Pure tests: exact two-window coverage; omitted vs explicit zero vs positive/fractional
selected values; tampered summary/map/pin/proof/selector/reference/unit/deadline;
missing/duplicate/foreign slots; no-capture and unsupported/catalog gaps; byte cap;
strict copied-instance revalidation; UTC equivalent offsets and DST instants;
old policy rejection and unchanged capability registry. No DB/provider calls needed.

This establishes selected count/value bundle integrity only. Aggregate clicks/cost
context and the Q01 full100clicks/10selected/$100 planning diagnosis remain later
engineering. No owner decision is needed for this pure contract; changing policy
claims or upgrading provider completeness would require a separate reviewed scope.

## Frozen Concrete Profile Recognition

Use app.google_connections.selected_presence.PRODUCER and
query_profile_digest(metric_family), with metric family explicitly conversions or
all_conversions, API v24, platform google_ads, request and selection profile digest
agreement, native event owner equal account native ID, and exact resource
customers/{nativeAccount}/conversionActions/{numericAction}. Recognizing this
parser contract permits pure projection only, not live provider qualification.
Unknown producer/profile/API and TikTok use unsupported_selected_mapping; they
cannot yield successful selected evidence. Existing generic c64 fixture profiles
are deliberately unsupported unless rebuilt through the concrete parser profile.
