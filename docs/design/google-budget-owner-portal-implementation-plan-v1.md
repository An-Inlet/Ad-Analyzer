# Private V6 Portal Implementation And Qualification Plan

Source-only inspection from a6fb552, following the approved
[portal contract](google-budget-owner-portal-interface-v1.md). No UI implementation,
imports, tests or API changes in this package. Service implementation is currently
being qualified separately; its exact frozen hash and interface are prerequisites.

## Concrete Production Ownership

The portal lane owns `app/portal/static/planning.html`, `planning.mjs`,
`plan-capability.mjs`, `plan-document.mjs`, and two new modules
`plan-google-owner-inputs.mjs` / `plan-google-owner-review.mjs`. Its component tests
use a new `tests/javascript/plan_google_owner_inputs_dom.mjs` and corresponding
bounded Python harness. No service, receipt, schema or policy registry ownership.

The browser qualification lane owns new `tests/test_owner_review_planning_browser.py`
and `tests/javascript/planning_owner_review_browser.mjs`, with reuse of existing
local TLS startup, middleware/CSP, authenticated same-origin session and completion
reporting. It may extend the fixed observer and its pure tests as described below;
coordinate those two files before edits. The existing creative browser module and
its qualified cases remain unchanged unless a separately reviewed extraction is
actually necessary. The parent assigns lanes before implementation.

## Exact Existing Wiring And Minimal Delta

`planningCapability()` currently accepts exact pairs1–5 and returns only selected
and creative flags. Add exact pair6 and its server-frozen response checks, with
creative true and ownerReview true only for6. Preserve the *exact returned objects*
for1–5; do not add false fields to legacy output or change the default configuration.
Mixed/unknown pairs still refuse. No browser-provided policy selection.

`planning.mjs.editor()` obtains capabilities before rendering creative inputs;
retain the same verified capability for the owner component. `clearEditor()`,
`clearTargets()`, `enable()` and session invalidation must clear/disable owner state
as well. Account/window/goal changes invalidate discovered groups synchronously.
The `targets-read` handler already holds each account's full returned catalog in
`targetPickers`; use that exact receipt digest and period for guarded owner discovery.
`renderPlanScenarios()` exposes `readIntent()` and `onChange`; owner selection reads
that exact snapshot, without adding a second scenario model. When a scenario is
incomplete, owner binding stays unavailable instead of fabricating a reserve/key.
Changes notify the owner component and require explicit valid reselection.

Stable scoped DOM contract before dependent tests: host `#google-owner-inputs`;
controls inside it use data-role `owner-discover`, `owner-option`, `owner-scenario`,
`owner-requested`, `owner-include`, `owner-remove`, `owner-status`, `owner-members`.
Rows additionally carry local ordinal data-index, never secret/session values.
Accessible names follow the approved contract: “Observed Daily Setting”,
“Requested Daily Hypothesis”, “Customer Alternative”, “Include This Review”,
“Remove This Review”. Options/member labels are literal text, not identities.
The immutable rendered proof host is `#google-owner-review`; current/version/export
share the existing document path. No Apply button or native-mutation endpoint.

Component result remains `readIntents()` (ordered max20), `setBusy(bool)`, `clear()`.
Only verifiedV6 emits `google_daily_budget_intents`, including explicit `[]`.
Preserve untouched primitive fields and saved order; a new inclusion appends once.
Unique owner identity is full account plus the server-bound owner option, not a
campaign name. Existing scenario selectors provide the representative selection;
server admission remains authoritative for native parentage/exclusions.

`parsePlanningMicros` is the existing exact micros parser to inspect/reuse; do not
reuse the document's two-decimal `money()` for native observations/hypotheses.
Render up to six fractional digits, no rounding. Submitted amounts never derive
from period allocations. Requested amount must be nonnegative/no more than observed;
zero confirmed ceiling permits only zero request, without promising provider validity.

`inputs()` joins the owner primitive list with the already parsed scenario list.
`mutate()` retains its stable request key and exact body on unknown outcome.
An owner error cannot silently strip intents, mint a replacement request key, or
turn explicitV6[] into an absentV5 field. Saved out-of-list choices remain visible
as historical; replacing an expired receipt requires explicit target read,
rediscovery and reselection. Add renderer immediately beside `appendCreativeBasis()`
using only saved `google_budget_owner_review`/`google_budget_input_catalogs`, with
complete affected members, per-day units, observations, hypothesis and investigate-only
recovery copy. The existing period ceiling/scenario renderer remains separate.

## API Freeze Dependencies And Authentic Fixture

Consume unchanged existing target-catalog-v2 and google-budget-owners routes, then
ordinary create/revise/generate/current/versions/version/export/request-receipt routes.
Service freeze must include exact V6 capability recognition, discovery admission,
explicit-empty handling, original receipt/current collection save binding and
retained current/history dispatch. No alternative response schema or mode.
The current service WIP's fixed refusal is
`owner review differs from actual collected evidence`; verify the literal at freeze.

Reuse frozen `tests/owner_review_runtime_fixture.py::configured_owner_review` only
after its actual API qualification closes. It returns `(fixture, body, calls,
catalog)` and builds real upload/aggregate/selected/catalog/discovery evidence before
saving any input. Do not send its prepared create body behind the browser: the
browser must choose its own target alternative and owner hypothesis, perform actual
discovery and submit real inputs. Reuse the provider MockHTTP wiring for the
browser's explicit fresh target acquisition, not copied frontend responses or seeded
PlanVersion/proof rows. Configure the private V6 factory with the same owned store;
retain original principal/session and actual HTML response/CSP.

Positive topology is actual paginated A/B shared and C independent. Partial topology
requires the existing acquisition fixture's `partial=True` path (reference count3
but only2 observed members), never editing downstream receipts/proofs. If the frozen
runtime fixture does not expose that option, define a narrow additive test-only
acquisition parameter *before* use; do not change production or shared helper silently.

## Bounded Qualification Sequence For Review

Component tests first: legacy returned flags/request omission byte checks; exactV6[];
ordered max20 and duplicate-owner rejection; six-digit amounts; saved out-of-list
values; affected-member literal rendering; scenario change/exclusion/expiry/session
invalidations; unknown request recovery; proof rendering with no Apply.

Proposed actual TLS nodes, each parametrized by existing customer_engine SQLite/PG:
`test_actual_owner_review_planning_browser[sqlite-positive]` and
`[sqlite-partial]` first; corresponding PostgreSQL nodes once if clean, not another
full repeated SQLite matrix. Positive journey: actual discovery → alternative A
allocation100/reserve900 under ceiling1000 → requested daily hypothesis5 → save →
generate → current → versions → export, exact receipt replay and unchanged provider
call count during receipt discovery/save/generation. Explicit browser target reads
may add documented read calls. Review edit to explicit owner removal separately
under revision CAS and assert a V6[] saved input; it is not an automatic fallback.
Partial journey: display unavailable/full-membership recovery, refuse owner inclusion,
then explicit zero-owner V6 save/generation if customer chooses ordinary planning.
Never infer missing membership from complete metadata.

A separate bounded safety component case covers session replacement/expired discovery;
actual API suite owns already-qualified foreign access, immutable history and atomic
save faults. Add a TLS safety node only if source inspection identifies a browser-only
race not covered by these controls; obtain exact scope review first, not blanket reruns.
Store actual document and export artifacts with hashes locally, never upload/share.
Assert no advertising effects and no spending authority, not just successful HTTP.

## Minimal Fixed Route Diagnostics

Existing `tests/creative_browser_observer.py` observes only POSTgenerate, GETcurrent
and GETversions; it cannot identify owner discovery/save/export failures. Preserve
those classes and add closed regex/method matches for `owner_discovery` (POST
planning/google-budget-owners), `create` (POSTplanning/plans), `revise` (POST
plans/{id}/inputs), `version` (GETplans/{id}/versions/{positive}), `export` (GET
plans/{id}/export), and `request_receipt` using the exact frozen existing route after
source confirmation. Do not classify arbitrary paths or log captured IDs/query strings.
Add only the exact frozen owner refusal literal to fixed_detail; unlisted strings,
structured422 payloads and arbitrary exception texts remain `unlisted_server_detail`.
Pure tests cover precise methods, malformed IDs/paths and safe fallback.

Reuse bounded original-once ASGI observation: status, fixed route/detail, ordinal,
monotonic elapsed only; bounded error-body buffer never persisted, no headers,
request/response documents, identity facts or credentials in diagnostics. Preserve
exceptions and terminal pytest result if artifact persistence fails. Record any
observer truncation/shutdown failure explicitly. Export and plan artifacts belong
to separate owned synthetic test evidence, not the diagnostic log.

This route observer makes each new journey failure attributable to its endpoint;
it does not explain original R01 (route unobserved) or R02 (known POST409, predicate
unobserved). Successful new tests do not close either incident. The independently
reviewed helper census is a separate external observer, still requires a parent-
authorized exact new milestone/source/observer manifest and sole test slot; no
execution or optimization is authorized by this plan. Preserve normal clocks,
five-second facts, all fresh passes and failed outcomes without pass-chasing.
