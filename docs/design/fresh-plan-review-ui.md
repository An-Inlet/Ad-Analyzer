# Fresh Customer Plan Review — Existing API Consumer

Concrete blocker at dc3c0d5: Campaign Review's create form requires an approved simulation mandate, but no visible customer control creates/approves it. This proposal only exposes the existing simulation APIs; it does not create production spending authority or provider execution.

## Minimal Page And Data

New standalone `/app/plan-review`, heading **Plan Review**, dedicated `plan-review.html/.mjs`; no edits to publication/total-budget consumer files. Add portal route and navigation link. Existing APIs:
- GET `/api/customer/v1/workspaces`, GET `/workspaces/{wid}/goals` (confirmed revisions only), GET `/workspaces/{wid}/google/connections` (verify exact existing route before implementation), and GET `/workspaces/{wid}/mandates`.
- First bounded UI offers currently connected Google accounts from the actual scoped connection response, whose `account_id` and `connection_id` supply existing `AccountScope`. No pasted IDs or browser-invented ownership. Meta/TikTok selection can follow independently; no unsupported claim.
- Existing MandateDefinition POST `/workspaces/{wid}/mandates`; then GET `/{id}` and explicit POST `/{id}/approve` with `{expected_revision}`.
- Responses are existing `id,revision,state,paused,definition,observed_simulated_micros,reserved_simulated_micros,positive_changes_used,actions_used,live_execution_enabled:false,past_spend_reversible:false`. Require simulation mode and false live flag before displaying approve.

## Controls / Exact Request

Choose workspace, confirmed goal and connected account. Show goal currency/store timezone and its current total budget/period. Planning Budget and Per-Plan Limit are explicit editable currency amounts converted exactly to micros. Start/end inputs are explicit dates in the confirmed store timezone; don't silently convert through browser timezone. Require the chosen interval to stay within the confirmed goal budget interval, and total planning budget <= confirmed goal total. No hidden increase.

For the narrow new-campaign planning purpose, request `mode:'simulation'`, selected goal ID/revision, currency/timezone from confirmed goal, exact selected account scope, explicit starts_at/ends_at, explicit total_cap_micros/per_action_cap_micros. Render all remaining existing numeric/action fields before submission: positive_change_cap_micros=0 (no existing-budget increase), allowed_actions=['new_campaign'] only, action_limit=1 (one new campaign plan), cooldown_seconds=0 (no recurring optimization), freshness_seconds=60 (planning review freshness). These are a fixed narrow planning profile, visibly explained, not production defaults/aggressiveness policy. If root prefers all numeric inputs editable, implement that instead; no 5/10/20% policy validation implied.

Save Proposed Plan makes one actual POST, no approval. Render exact returned definition and revision, explain: **This approves a planning simulation only. It does not authorize live advertising, increase your overall spending limit, or approve new campaign content.** Explicit checkbox and **Approve Planning Budget** calls existing expected_revision approval. Success links to Campaign Review; the separate draft/content approval remains mandatory.

## State / Recovery

Workspace/goal/account/session changes clear proposed definition, review and checkbox; abort/discard stale responses using the existing epoch/session/CSRF pattern. No automatic retry of POST after unknown response. Recover via actual bounded current list and explicit selection/read, never remint silently. An approval race or stale revision clears review and requires reread/reconfirmation. Current foreign workspace/role/session denial clears private state. GET and exact API POST responses remain authoritative; paid status never implies simulation approval. Log out and reload preserve only server-owned current rows.

## Tests / Ownership

Actual HTTPS browser from fresh signup/paid workspace/Google/Shopify/confirmed goal creates and approves this planning budget, then separately creates and reviews supplied Google draft, without DB seeding. UI unit/browser stale-response and no-default-authority coverage. Scope requires parent contract review before edits. Parent/customer_portal coordinate route/navigation ownership; scheduler owns fresh journey harness only unless assigned UI implementation explicitly.

## Implemented Refinements

The reviewed implementation uses the existing owned `/execution/optimization/accounts`
read projection for current Google account names. It never derives or accepts provider
IDs. New CSRF POST `/mandates/planning-context` accepts only goal ID/exact revision and
owned account ID. Server-side ZoneInfo resolves the confirmed goal's complete budget
period to UTC, rejecting ambiguous/nonexistent local midnight boundaries and periods
outside the existing simulation schema. The UI displays the fixed local period and
links to Edit Goal; it never converts through the browser timezone.

Only the approved one-new-campaign Google planning profile is offered/reviewed here:
one plan, no existing-budget increase, no recurring optimization, zero cooldown and
60-second planning freshness. All are displayed. Total and per-plan amounts are
explicitly editable and client-bounded by the confirmed goal budget; this is a
simulation UI, not a change to production mandate validation or a native spending cap.
A second explicit owner checkbox approves the exact saved revision. The existing
campaign-content review remains independent.

Original-session cookie changes, identity changes and stale selections clear the
review. Unknown writes are not automatically retried; actual saved-list/read permits
recovery. The fresh browser regression includes an actual concurrent planning revision
and rejects stale approval before reread and renewed consent.
