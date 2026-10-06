# Existing Campaign Optimization Customer Contract

Status: design only, inspected at `5dd0d7a` (migration 0058). No endpoints,
configuration, provider access or additional spending authority are enabled here.
This is separate from creation, social configuration and action-outcome maturity.

## Existing Evidence And Missing Customer Boundary

`app/publication/optimization.py` prepares exact budget/pause reviews from server
qualification, current provider state and exposure evidence. It supports approval,
reservation, one original attempt, independent readback and fenced reconciliation.
`replacement.py` adds separately reviewed repeat optimization with full predecessor
exposure lineage. Both review schemas have purpose `existing_campaign_optimize`;
the repeat schema, not a new purpose string, identifies replacement semantics.

`app/api/customer_execution.py` currently handles approval, run admission, advance
and reconciliation through activation-versus-creation branches. Those branches must
become exhaustive before optimization reviews can use them. An unknown purpose or
schema must reject, never fall through to creation. Customer authority binding
currently covers creation and activation; optimization needs the same fresh original
session binding, including reauthorization after provider I/O and before emission.

`get_optimization_runtime()` returns `None`. Replacement additionally requires a
server `replacement_reader`. No native source currently qualifies original-request
finality and the complete transition bound for repeat optimization. A contract-test
source or successful target-state readback does not remove that live blocker.
See [repeat accounting](../inlet-repeat-optimization-accounting.md).

## Proposed Versioned Customer Interface

All paths below are relative to
`/api/customer/v1/workspaces/{workspace_id}/execution/optimization`.
These are proposed names, not implemented routes.

| Method And Path | Input / Result |
| --- | --- |
| GET `/capabilities` | Owner-only, per-provider catalog/initial/repeat availability and fixed blocker codes; explicit environment. |
| POST `/target-options` | Owned mandate and exact consent references, owned advertising-account reference, optional opaque page cursor. Returns bounded named target choices. |
| POST `/initial-reviews` | Mandate/consent references, choice reference and version, exact budget or pause intent, bounded customer rationale. Returns owned review reference and exact safe review projection. |
| POST `/repeat-reviews` | Same inputs plus an owned predecessor reservation reference. Requires complete server replacement proof; returns a separately approved repeat review. |

POST reads use the existing mutation principal and CSRF convention. Every route
requires a current owner session, active workspace and explicit account ownership.
Responses are `no-store`. A role downgrade, revoked session, closing workspace,
changed source generation or changed mandate/consent blocks preparation. Catalog
read, provider qualification and preparation must reauthorize after I/O; supplied
workspace/account references never substitute for ownership checks.

Use existing common review/approval/run/recovery routes only after adding exhaustive
purpose **and schema** dispatch and safe optimization-specific read projections.
Initial and repeat preparation stay separate; there is no automatic fallback from
repeat to initial, or from a blocked initial request to repeat. Approval acknowledges
the exact server review digest; it does not submit an executable plan. Reuse existing
idempotent run admission, original attempt/fence and local cancellation semantics.

## Named Owned Target Catalog

Propose `inlet.customer-optimization-target-options.v1` and a separate optional
server catalog factory whose default is `None`. The catalog resolves an opaque
choice reference under the owned workspace/account and current source generation;
the browser cannot supply native IDs, target topology, money metadata, qualification,
exposure, closure evidence, provider payloads or runtime/environment selectors.

Each choice includes a bounded plain-text display name, platform, target level,
parent display name where needed, budget-owner mode, affected-target count, current
budget/status, currency, budget period kind, observation/expiry timestamps, allowed
intent kinds and fixed eligibility/blocker codes. The review exposes a bounded,
escaped named affected-target list when sharing matters. Do not silently truncate a
complete topology: reject unsupported/oversized topology. Names are presentation
only and never participate in authorization. Do not log provider names or raw data.

The choice reference binds the server-resolved native target, native budget owner,
complete affected-target topology, source generation, current-state digest, current
policy/consent revision and catalog version. Resolve it through a bounded server
source on every preparation; no browser snapshot is authoritative. Prefer a
reconstructible source-owned opaque reference with exact version checking, avoiding
new persistence unless the actual source requires it. A digest without an owned
server lookup is insufficient. Cursor pagination must be scoped and bounded, with
explicit expiry/restart behavior; catalog expiration requires refresh, not replay.

Browsing an observed target is not dispatch eligibility. Report missing qualification
and exposure producers separately from catalog availability. Unsupported shared
budgets remain unavailable: current Google contract is independent only; Meta/TikTok
require the exact supported native budget owner and complete affected-target set.

## Exact Intent And Spending Semantics

Browser intent is a discriminated absolute budget amount or pause request, not a
percentage delta or generic patch. Use the existing exact bounded integer micros
contract with strict integer validation and explicit currency/period display. Server
mapping chooses the provider operation and existing budget field/mode; the browser
cannot change daily/lifetime mode, currency, target identity or native budget owner.
Pause maps to Google/Meta `PAUSED` or TikTok `DISABLE`. Resume, creative edits and new
campaigns are outside this interface.

The review must show before/after budget or status, affected targets, observation
freshness, overall mandate ceiling, separately reserved exposure, positive-change
charge, aggressiveness check and unavailable provider compare-and-swap. Show an
explicit initial/repeat label, and repeat predecessor/transition summary. Preserve
exact evidence privately in the existing strict review document; return only a
validated customer projection, never raw provider requests or source evidence.

Draft 5%/10%/20% aggressiveness values are policy inputs, not permission to raise the
overall spending limit. Existing per-change and cumulative positive-change bounds,
recorded spend, held exposure, current portfolio and account-set/period/currency
constraints all remain independent gates. A budget decrease, pause, local cancel,
new consent or new mandate revision does not refund a hold or reset usage. Existing
unknown/over-cap conditions also block pause: this is not emergency containment.
Changes to the overall mandate need the existing explicit mandate/consent flow.

Initial optimization cannot bypass a held native-owner reservation. Repeat requires
the current owned predecessor and complete server-qualified closure/current portfolio/
transition proof. Preserve migration 0058 chain bounds and all ancestor receipt
checks; changed approved evidence requires a new review. Target-state observation
alone cannot prove closure or release exposure. The UI must not offer a retry that
creates another original attempt after an uncertain response.

## Portal Coordination And Implementation Order

The portal owner confirmed no namespace conflict with `/execution/social/options`,
`/reviews/{id}/confirmation` or `/app/social-configuration`. No shared UI file is
changed by this document. Later add a distinct Existing Campaigns entry to the
execution workspace, then target selection, exact intent, review and common owned
run recovery. Keep creation/activation and optimization labels distinct. Show
contract-test status throughout; live eligibility remains false without qualified
native producers. Do not imply delivery time, maturity, causal lift or finality.

1. Freeze strict customer request/response schemas and optional catalog/runtime
   interfaces. Add exhaustive dispatcher and original-session authority binding.
2. Implement owned catalog resolution and initial preparation/read projections.
   Add repeat preparation only with explicit unavailable behavior and fixture proof.
3. Add portal controls against the stable API; reuse existing exact approval and
   one-step recovery, keeping stale-response/session/role guards.
4. Qualify native sources separately before any live enablement. No schema change
   is proposed here; any persistence need requires separate migration coordination.

## Required Offline Acceptance

- Real owner login/session and CSRF through assembled APIs on SQLite/PostgreSQL;
  unrelated workspace/account, viewer, revoked session and missing CSRF denied.
- Catalog spoofing, unknown choice/version, foreign predecessor, stale source,
  changed owner topology and changed policy reject before mutation. Session/role/
  closure changes during catalog or qualification I/O cannot yield usable authority.
- Initial exact budget/pause review to approval, run, actual adapter MockTransport,
  readback and owned receipt. All common dispatch sites reject unsupported schemas.
- Repeat fixture closure proof to exact approval and atomic successor transfer;
  stale ancestor receipt/proof, concurrent admission, cancellation, reconnect and
  delayed/no-effect outcomes preserve existing lineage and hold guarantees.
- Aggressiveness and cumulative change cannot exceed the mandate cap; decreases,
  pause, cancellation and consent changes do not reset spend or release exposure.
- Browser uses only named owned choices; no raw provider/proof entry. Late success
  or failure after session/workspace change clears or leaves cleared customer data.
  Unknown response uses owned recovery, never blind resubmission.
- Default factories `None` expose honest unavailable states and cause no provider
  calls. Contract-test fixtures never make a live source qualified.

Existing coordinator/replacement tests remain evidence for their service contracts;
they do not establish this absent customer API/browser journey. No new owner decision
is needed to design the offline facade. Live source qualification, deployment and
unresolved business policies remain separate gates; this document grants none.
