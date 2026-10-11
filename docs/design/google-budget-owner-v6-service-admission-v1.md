# V6 original-receipt service admission

Design only, based on integrated pure slice `e8c7600`, the reviewed V6 design,
and retained-port interface `0ea8854`. No code, capability activation or tests in
this commit. Isolated source-only implementation may proceed against the reviewed
ports. Integration, qualification and capability exposure wait for the retained
author's frozen implementation and independent closure. This completes the existing private V6 path, not a new version.

## Ownership and exact configured capability

The integration lane owns `service.py`, `repository.py` only at save-generation
binding/dispatch, `policy_capabilities.py`, the input policy gate in
`google_budget_generation_guard.py`, a new `owner_review_generation.py`, minimal
`capabilities_view.py` and `api/customer_planning_documents.py` mode handling,
and the existing discovery policy gate in `google_budget_owner_discovery.py`.
`generation_ports.py` keeps its exact existing union: genuine
CreativePairedEvidenceV1 is already sufficient. A comment may document the new
consumer; no duplicate bundle type is needed. Tests use new fixture/API files.

The retained lane owns `google_budget_owner_retained.py`, `retained_sources.py`,
`selected_plan_history.py`, and reviewed creative witness/currentness extractions.
This lane does not edit those files or `catalog_receipts.py`.

Register only exact `inlet.descriptive-review.v6` / `inlet.descriptive-planning.v6`
with mode `owner_review_creative_selected_requested_window` and existing
`local_reporting_v3`. Ticket recognition also compares the canonical policy digest.
The existing service constructor continues to default to V3. Explicit private
constructor injection of canonical V6 requires an explicit media store, just as V5.
No environment switch, latest-policy selection or new default factory is added.

The existing capabilities response shape remains unchanged. Its exact V6 pair
reports selected_reporting_available=true, derived from the same configured
service instance. The separately reviewed UI contract derives creative/ownerReview
support from that exact pair; no new unreviewed Boolean is necessary. Default V3
capability behavior stays unchanged.

Receipt-backed owner discovery admits exact canonical V5 (existing input-only
behavior) and V6, using the existing original-session configured service and all
source/paid/expiry gates. Discovery still performs no provider read or mutation.

## Input and generation dispatch

V6 input create/edit requires an explicit owner tuple, including empty when the
customer declines owner hypotheses, plus explicit selected_reporting and creative
inputs. Extend only the supported input-policy pair set to include V6. V5 continues
to accept stored owner hypotheses but refuses their generation; V1–V4 behavior and
all old pure composer/document refusals remain unchanged. No field omission is
silently converted to empty or interpreted as opting into V6.

Keep existing create/edit capability checks before the original request replay
lookup; do not move legacy gates. Keep generation completed-request replay in its
existing position before new-generation input checks. That replay still invokes
`repository.version` and therefore the complete retained history validator.
A new V6 generation requires explicit owner input; every old policy still calls
`reject_google_budget_generation`, including nonnull-empty. Check current heads,
input digest, goal, full sources and original actor/session as already implemented.

V6 collects through actual OwnedCreativePairedReader, which already uses pure exact
selected-policy recognition, saved input catalogs, and the genuine original ticket.
No alternate reader/getter or proof callback is introduced. Required identity
refreshes remain outside SQL. Every collection and finalization keeps current
selected/image/selected rechecks, exact observation timestamps, source privacy,
original deadlines and the five-second authority fact. New scope failures do not
renew the fact or fall back to old composition.

Dispatch only the new mode to OwnerReviewPlanComposer. V5 keeps CreativePlanComposer;
V4 keeps SelectedPlanComposer. Do not pass fake policy versions or strip owner
fields. Expected-bundle checks in service and repository accept
CreativePairedEvidenceV1 for both explicit creative modes.

## Final original/actual binding ports

New internal pure port:

```
assert_owner_review_generation_bundle(
    *, ticket: GenerationTicket, candidate: PlanVersion,
    bundle: CreativePairedEvidenceV1,
) -> None
```

Revalidate exact V6 canonical ticket/policy semantics, candidate and bundle; compare
candidate input/version/actor/policy through the existing repository checks. Derive
the complete relevant tuple with `linked_owner_input_catalogs(ticket.inputs,
bundle.reporting.selected.catalogs)`. Compare canonical full catalog bytes exactly
to candidate.google_budget_input_catalogs. Invoke the active owner review validator
with those actual linked catalogs and the complete original ticket source tuple.
Keep all ordinary catalog references, full targets and selected/traffic/creative
proof comparisons; stable owner facts alone are insufficient.

Call this port in `repository.save_generation` after its existing completed replay
return and actual target/allocation comparisons, before any write and before
retained source capture. Normalize only expected validation failures to the fixed
409 `owner review differs from actual collected evidence`. Do not catch callback,
clock, SQL or provider exceptions as ordinary proof absence.

New current SQL port:

```
recheck_owner_review_input_receipts(
    db: Session, *, principal: CustomerPrincipal, ticket: GenerationTicket,
    candidate: PlanVersion, catalogs: tuple[CatalogEvidence, ...], now: datetime,
) -> None
```

Use the existing `resolve_saved_input_catalogs` exactly once in this port. It checks
actual immutable input/link rows, original actor/session/scalar opaque commitment,
current original source/paid/privacy/report window and receipt expiry. Compare its
complete ordered original catalog bytes to both the candidate tuple and the linked
subset derived from the actual collected catalogs. Require all supplied actual
catalogs to be owned and unique through existing pure bundle validation. No synthetic
SourceFence, fake principal, current-session replacement, stable-facts substitution,
or refreshed receipt observation is accepted.

In V6's service final_sources branch, this replaces the single existing
`recheck_saved_input_receipts` call after the selected/image/selected sequence;
it does not remove or duplicate that sequence. V5 keeps its existing call unchanged.
The repository's subsequent retained capture may independently reread receipts,
as the reviewed complete witness contract requires; no unchecked cache is added.
This callback has local SQL only, before plan writes, under existing original
transaction/authority locks. Final repository authority/time checks remain after
retained capture and after writes; no after-commit reauthentication is added.

## Complete current/history/export prerequisite

The retained author's three ports and exact dispatch must be integrated before
registration or API qualification. `repository.version` continues using the shared
selected-history dispatcher; this lane does not add a second recursive history
path. V6 history requires every existing selected/traffic/commerce/creative
witness plus exact original input links/catalogs and opaque scalar commitments.
No new dependency kind, table, retention rule or paid/TTL check for history.
Current status uses original retained/source checks and does not claim a fresh
provider inventory read. Missing or erased links deny current/history/export through
those reviewed boundaries, including completed generation and input replay.

## Bounded actual API qualification after dependency freeze

Use `google_budget_input_fixture.ready_inputs` / acquired_owner_catalog as the
actual original-session catalog and discovery basis. Configure only the existing
API service constructor to canonical V6 with the real fixture-owned LocalMediaStore;
perform uploads, source acquisition, option discovery, input save and generation
through real endpoints. No seeded positive PlanVersion, proof, execution record,
runtime getter replacement or clock extension. Existing V5 helpers/defaults remain
unchanged. Share a new helper with the retained author if their tests need the
actual saved input, but no circular fixture import or shared-file race.

Run disjoint SQLite cases first, then their PostgreSQL counterparts, with normal
clocks and -x; do not repeat passed SQLite cases unless a source repair requires it:

- Nonempty owner hypothesis and explicit empty tuple: actual create, generate,
  current read, versions, export and exact completed replay. Assert full original
  linked catalogs, one investigation per account/owner, full membership, no native
  proposal/Apply authority, zero execution/approval/reservation effects. Replay and
  history/export perform no extra native acquisition.
- Genuine zero confirmed ceiling plus zero daily hypothesis remains investigation
  only; partial membership/ineligible ownership is unavailable at discovery/admission.
- Mixed-platform scenario/exclusion and unrelated included account retain the exact
  linked subset alongside full source proof. Bound this to one actual mixed case
  if the unchanged pure matrix already proves both providers' structural variants.
- Same-owner new session, changed original source/receipt, expired generation
  receipt, changed goal/head/input CAS and media/privacy failure: fixed denials,
  unchanged generation head/version/dependency/request rows. Do not manufacture
  a fresh receipt or permission to get a positive path.
- Strict-valid altered candidate owner catalog/proof versus unchanged real bundle
  fails the new repository hook; preserve whole original input/candidate validation
  so the hook is actually reached. Missing/tampered original links refuse the final
  SQL path. A late post-flush fault proves transaction rollback with real rows.
- Retained current/history/export dispatch is exercised through actual endpoints;
  predecessor snapshots remain unchanged after a legitimate input edit/successor.
  Erasure and original actor/session/authentication scalar faults use retained-lane
  tests where exact compatibility permits, with one API smoke rather than duplication.
- Default V3, ordinary V4/V5/Q08 and V5 owner-generation refusals stay intact. Exact
  capability digest mismatch and missing V6 owner tuple are rejected before source IO.

Freeze exact selected node IDs/counts after the dependency fixture is available;
this is not authorization for a broad aggregate. Preserve all first failures. Any
normal five-second authority failure is retained and diagnosed; no retry-to-green,
clock shift, increased limit or R01/R02-resolution inference. Observational timing,
if needed, is a separately reviewed measurement, not acceptance instrumentation.
The customer UI remains dependent on this complete API freeze and its own reviewed
contract; no frontend/default activation occurs in this package.
