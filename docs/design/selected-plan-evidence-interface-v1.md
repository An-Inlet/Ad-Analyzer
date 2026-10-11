# Selected Reporting Plan Evidence Interface V1

This freezes additive offline engineering ports after the reviewed selected
capture and requested-range foundations. It does not activate a policy, permit
provider writes, qualify a live query, or close a human usefulness gate.

## Persisted Customer Selection

Add `SelectedCaptureSelectorV1(account_id: Positive, capture_id: Id)` and optional
`selected_reporting: tuple[SelectedCaptureSelectorV1, ...] | None = None` to
CustomerInputs and PlanInputRevision. The tuple has at most 20 unique account IDs,
all among the input's accounts. None means legacy input; an explicit empty tuple
means the customer deliberately supplies no selected captures. Capture IDs are
untrusted selectors, never evidence or authority. Input prepare/resolve and the
existing immutable input-revision/receipt path retain the exact tuple. Changing a
selector requires a new input revision. Do not add a transient GeneratePlan field,
a side table, latest-capture lookup, or stitched captures.

Use a dedicated wrap serializer on both input models to omit only this field when
None, in both Python and JSON modes including nested serialization. Preserve every
old canonical document, receipt fingerprint and plan digest byte. Explicit empty
and nonempty tuples remain serialized. Unsafe copied instances must be revalidated.
Golden old input and full plan fixtures are a prerequisite; if byte preservation
fails, stop this approach and use an explicit new input schema instead. All legacy
policy/generator pairs reject non-None selectors. Reserve the exact pair
`inlet.descriptive-review.v4` / `inlet.descriptive-planning.v4`; register it only
with its actual owned consumer, retained proof and privacy tests.

## Private Selected Evidence

`SelectedPlanPinV1` binds the owned AccountRef, exact SourceFence, complete
AggregateDependencyV1, selection ID/digest, explicit capture ID, request digest,
full capture digest, and digest of the complete sorted local/native campaign map.
All references must agree with the account/source/privacy and capture request.
The owned reader loads the full capture via read_selected_capture, never trusts a
client pin, and compares the entire graph before slicing. One chosen capture must
cover primary and comparison windows; an explicit invalid, foreign, stale or
corrupt selector aborts the operation. It must not become a missing-data gap.

`SelectedWindowEvidenceV1` binds reference, exact catalog campaign TargetRef, pin,
requested ReportingWindow, and typed SelectedCampaignSummary values. Convert UTC
window endpoints to exact closed local midnights using the account timezone;
compare instants in UTC (including DST folds). Preserve calendar-day completeness,
independent conversion/value presence and exact decimal totals. Use the existing
whole-graph summarize_selected_capture result, not a fabricated V3 document.
Only fully observed explicit zero counts yield a zero observation. Positive partial
observations stay visibly partial; omitted days or cells never become zero.

The private bundle enforces exactly one evidence or typed gap for each owned
account × catalog campaign × requested window, unique per-account pins, bounded
bytes and unchanged catalog/commerce/customer-context provenance. Accounts without
a supplied capture have an exact `selected_capture_not_requested` gap. Unsupported
platforms have a distinct unsupported mapping gap; TikTok remains unsupported.
Unauthorized source failures and integrity failures abort, not generic gaps.
Aggregate traffic remains separate provider-aggregate context; its generic
conversion count is never relabeled as the selected event or added across platforms.

## Retained Proof And Currentness

Add `local_reporting_v3` only alongside the working v4 consumer. Its digest wraps
the existing complete owned reporting-state commitment, exact persisted selector
(or explicit absence), the selected pin and native/local mapping. Collection,
final locked persistence, later decision/currentness and archive checks reconstruct
the same witness from persisted inputs. Do not change local_reporting_v1/v2 bytes.
A selection replacement/invalidation, ordinary aggregate sync, source change,
capture loss/corruption, privacy change or mapping change invalidates the witness.
Retain old immutable plan bytes as stale history; existing planning-graph semantic
erasure removes the new witnesses with their parent. No new table is required if
existing PlanDependencyRow/registry/export bounds support the new closed kind.

## Implementation Order And Acceptance

1. Input selector DTO, byte-preserving serializers and immutable input plumbing;
   reserve policy identifiers without making v4 usable yet.
2. Pure pin/window evidence and summary comparison with exact provenance tests.
3. Original-session owned full-graph reader; collector and final recheck.
4. New retained witness/currentness/export/erasure, then v4 composer and registration.
5. Actual local API/browser range → explicit selection → capture → persisted input
   → generated plan → history/decision freshness, using injected provider HTTP.

September and August use one genuinely acquired Aug 1–Sep 30 completion and one
covering selected capture, with exact local windows. Positive 10 conversions must
not produce a no-conversions diagnosis. Test explicit daily zeros, omitted rows,
independent missing values, fractions, mapping races, final-session expiry and
privacy erasure on SQLite and PostgreSQL. Preserve baseline qualification and old
policy golden bytes. Fixtures do not establish live provider support, paid product
readiness, causal lift, cross-platform attribution or spending authority.

## Review Clarifications

The private bundle carries each full validated selected capture exactly once,
indexed by its explicit account/capture selector. Bundle validation recomputes each
window summary from that complete graph and compares every typed value plus pin.
A digest alone cannot qualify arithmetic or make an arbitrary copied summary true.
Do not duplicate the full capture per campaign/window; count its bytes once within
the bundle cap. The owned reader still supplies actual authority and currentness.

Historical archive validation checks retained immutable graph/row integrity and
preserves old plan bytes even after an ordinary sync. It does not require current
live source equality. Current decisions, final persistence and currentness checks
remain strict; history can correctly be stale without becoming unexportable.
