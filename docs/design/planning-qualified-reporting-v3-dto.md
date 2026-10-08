# Qualified Reporting V3 Concrete Consumer DTO

Base `014db57`; implements the separately approved consumer seam. Meta import and
0090 publication are not implemented or modified here. Legacy V1/V2 types, routes,
manifest bytes, and PlanVersion serialization fields remain unchanged.

`CampaignPerformanceV3` has schema `inlet.owned-campaign-performance.v3` and fields:

- `legacy`: exact unchanged CampaignPerformanceV1 or V2, retaining its numeric
  interpretation separately; nested unsafe copies are reparsed with explicit
  primitive-coercion rejection in the V3 boundary.
- `presence`: full ReportingSemanticsV1 header, including the original whole-set
  count/digest and exact source/completion/manifest/window/money/event metadata.
- `native_campaign_id`: exact numeric native identifier.
- `campaign_facts`: at most 400 ReportedMetricPresenceV1 facts, only for this exact
  campaign/native pair. Duplicate days, foreign bindings and excess subset count
  reject. No missing day is inserted.
- `summary`: typed CampaignSummaryV1, recomputed and equality-checked against those
  campaign facts. It contains requested_days, returned_days, missing_calendar_days,
  the five metric summaries, and selected_zero_for_requested_window. Each metric
  has value, present_days, missing_days, unsupported_days, legacy_unknown_days and
  coverage. Decimal conversion sums are normalized plain strings; integer counts
  and money remain integers; unavailable values are null.
- `causal_attribution=unavailable`, `spending_authorized=false`.

The DTO proves its own campaign projection consistency, not that a client holds
all completion facts. The derived subset commitment used solely by the pure
summary validator never replaces the full header commitment. Only the SQL reader
validates the actual complete stored graph using read_presence. The copied legacy
report stays separate from observed-field summary; no V3 CPA/ROAS is fabricated.

`read_current_with_presence` has the legacy read_current positional parameters and
an optional private `context=PresenceReadContext(db)`. It calls the actual owned
legacy reader, validates stored whole graph and exact native mapping, binds the
campaign projection, and preserves the final original-session authorize callback.
Actual sidecar absence returns unchanged V1/V2; corrupt/incomplete sidecars raise
controlled unavailable. No commit or external IO is added.

The context is explicit, operation/transaction-local, and rejects transaction
rollover. It caches at most one complete graph and builds campaign/native indexes
once, so campaign projection does not rescan the full presence set or reload it per
campaign. Legacy reader manifest behavior remains unchanged. A fresh context is
created for final checks. Limits: 2 MiB per V3 document and 32 MiB for the new-policy
collected reporting documents, plus the existing 400 evidence and reviewed graph
limits. These are operational capacities, not reporting completeness or policy
thresholds. Capacity failure aborts instead of truncating evidence.

## Planning Version And Proof Boundary

Default policy/generator are now `inlet.descriptive-review.v2` and
`inlet.descriptive-planning.v2`. Explicit v1 policy/generator remain supported and
never consume V3. Existing v1 plan documents/digests and local_reporting_v1 witness
algorithm are preserved. The old pure composer fixtures explicitly select their
original policy versions; their assertions are retained.

Only v2 collection invokes the new reader. Private EvidenceBundle.reporting_pins
contains exactly one ReportingPresencePin(account, document_digest) per selected
account, captured from actual local state before provider reads. It commits to the
existing complete legacy reporting state plus the validated canonical presence
header/facts or explicit absence, using the new local-reporting-state.v2 domain.
Pins are not added to persisted PlanVersion or public legacy reports. Both
assert_ticket and the composer reject incomplete/duplicate account pin sets or
new-schema evidence under a legacy policy. Collection and final recheck both
validate actual state; appearance, disappearance, corruption or changed current
completion cannot silently save advice composed from an earlier state.

Retained dependencies retain the same `local:reporting:{account_id}` keys. New
policy writes `local_reporting_v2`; historical v1 documents recompute v1. Exact
ordinary-plus-local dependency count/key binding remains unchanged. Viewers use
DB-only current-auth checks; no native or identity provider call is introduced
inside source locks.

## Advice Semantics

Observed traffic/spend remains visible with its metric coverage. Positive selected
count is described as an observed provider-reported sum and never as no-conversion
advice. True requested-window zero requires the reviewed summary conditions:
explicit event, returned row for every requested day, all selected count cells
present, completed pagination, full requested actual interval and closed period.
Only then does advice suggest a locatable tracking/landing-page investigation.
Missing or partial zero explicitly remains unavailable/partial; no whole-window
zero, campaign pause, budget transfer, forecast or spending authority follows.
Attribution remains unqualified; the initial supported provenance has unknown
provider defaults. No cross-platform conversion totals are combined.
