# Q11 reconnect lifecycle: acceptance decision proposal

Read-only at root `7906bc09ea86c6e00ac594c1bd9c586a534ba354`. No code, tests,
network access, new retention or weakened erasure is proposed here.

## Decision recommended now

Keep the implemented semantic privacy boundary. Qualify correction/ordinary
refresh with historical V1 and its decision preserved; qualify explicit Google
reconsent/disconnect with the existing derived-data erasure and unavailable old
plan. Do not call the latter a passing preserved-history reconnect case. Record
the frozen Q11 reconnect clause as unreconciled with the current lifecycle policy,
and fix the customer-facing explanation separately without changing retention.

This is an acceptance split, not permission to silently rewrite the frozen Q11
criterion. If the owner actually wants same-account reauthorization to preserve
plan history, that is a separate retention/privacy design decision requiring a
reviewed transition and proof boundaries. It is not necessary to implement the
narrow acceptance and truthful-copy package recommended here.

## Source-backed distinctions

| Operation | Actual current behavior | Q11 interpretation |
| --- | --- | --- |
| Normal access-token refresh using an existing grant | `google_connections/http.py::access_context` refreshes access internally; it does not itself invoke semantic privacy erasure or select a new connection generation. Existing owned rechecks still apply. | Do not call every token refresh a reconnect. Ordinary refreshed reports/corrections can support immutable successors/history subject to original evidence validity. |
| New consent and selection of the same advertiser | `service.py::choose` finds by workspace + external advertiser ID. Existing connection branch calls `bump_workspace_export_revision`, drops pending analysis, increments generation, resets staged import state and replaces encrypted grant. No distinction is made between still-connected and previously-disconnected same-account reconsent. | Even same-account reauthorization is currently a semantic invalidation, not historical-plan-preserving rotation. Stable native identity alone does not restore erased proof. |
| Replay of the exact already-consumed selection authorization | Early `state == selected` branch returns the same owned connection when advertiser matches; different advertiser rejects. | This idempotent replay is not a second reauthorization/generation change and must not be used as a fake reconnect-positive test. |
| Choose a different advertiser through new consent | No existing row for that advertiser means a new owned connection/integration/account; the inspected choose path does not replace or delete a different advertiser's connection. | Account addition is not automatic account replacement. Source IDs and targets must remain isolated; explicitly disconnecting the old account is a separate operation. |
| Explicit local disconnect | `service.py::disconnect` obtains the owned scope, bumps semantic privacy, revokes the local integration, clears grant/staging/scheduling and increments generation. It does not revoke the broader remote OAuth grant or mutate ads. | Old derived planning history is erased, not merely marked stale; neither accepted decisions nor prepared exports can be resurrected on reconnect. |
| Terminal `invalid_grant`/Ads authorization failure | `tick` calls semantic privacy bump, clears grant/staging, increments generation and persists `reconnect_required`; old queued work is fenced. Transient read failure only sets retry/error state. | This loss-of-authority transition also differs from a harmless refresh. It is not a fresh-consent or preserved-history positive. |

`lifecycle/privacy.py::bump_workspace_export_revision` explicitly describes
semantic erasure. It removes workspace range receipts, selected/presence data,
plans, candidates and initial observations, then advances the export fence.
`planning_documents/invalidation.py::erase_workspace_plans` deletes requests,
decision/assertion events, input receipt links, dependencies, versions, inputs,
heads and catalog receipts. **The planning effect is workspace-wide**, not just
plans referencing the disconnected advertiser. It does not imply deletion of all
raw imported metrics, goals or protected financial/audit records. Counter-only
`advance_workspace_export_revision` exists for corrections preserving history,
but substituting it into reconnect is a behavior/policy change, not a test repair.

The existing design already names this boundary:
`docs/design/planning-google-selected-event-proposal-v1.md` describes
reauthorization/disconnect privacy and generation invalidation, fresh selection
and semantic graph erasure. `docs/inlet-initial-planning-lifecycle.md` separately
distinguishes real privacy/native reconnect loss from expiry-only cleanup.
Older grant lifecycle prose saying previously published data remains must be read
as its retained import/report scope, not a promise that later-derived plans survive.

## Concrete customer-facing discrepancy

- `portal/static/index.html` Google disconnect review lists retained campaigns,
  metrics, reports, goal history and audit records, but does not explain deletion
  of derived plans, their decisions, selected reporting and workspace-wide effects.
- `portal/static/portal.mjs` reports: “Google Ads disconnected. Historical data
  remains; imports have stopped.” This unqualified message can be understood as
  preserving plan history although the server deletes it.
- `google-callback.html` and `.mjs` offer “Connect Selected Account” after explaining
  read-only imports and no spending authority. They do not warn that selecting an
  already-connected advertiser replaces consent and erases workspace-derived
  planning data. The callback account DTO is provider account discovery, not a
  verified affected-plan inventory; do not invent exact plan counts in UI copy.

A narrow follow-up can correct these warnings and acknowledgments before the
destructive selection/disconnect and use bounded, accurate result text afterward.
Suggested content: retained raw reports/goals are distinct from derived plans;
reconnecting an existing account clears saved workspace plans and their recorded
decisions/selected reporting, and new import/selection/planning is required. State
that running ads and provider data are unchanged. Wording must name the actual
workspace-wide effect rather than promise account-only deletion. No server
erasure change or broad provider revocation is needed to make this truthful.

## Existing tests and smallest acceptance follow-up

Inspected source, not executed:

- `test_google_customer_connections.py::test_two_customers_partial_import_reconnect_and_revocation`
  proves same connection identity/new generation after disconnect/reconnect and
  rejection of old queued generations, but contains no accepted plan history.
- `test_google_lifecycle.py` covers terminal authorization failure, transient
  retry, stale-session disconnect, scoped pending-analysis discard and obsolete
  generation fencing. Scoped pending-analysis assertions do not prove plan erasure
  is account-scoped; it is not.
- `test_selected_runtime_lifecycle.py` and `test_creative_runtime_lifecycle.py`
  exercise semantic bump against actual derived graphs; these do not by themselves
  prove the complete Google customer reconsent route + accepted-decision journey.
- Frozen Q11 in `comprehensive-planning-quality-cases.md` explicitly requires V1
  and its decision historical after correction **or reconnect with a new
  generation**. Current same-advertiser consent selection does not meet that
  reconnect clause. Existing correction evidence is not its replacement.

Recommend a separately reviewed, bounded actual API acceptance package that starts
with a genuine private-V6 V1 and accepted manual-review decision, then performs
same-advertiser fresh-consent selection through actual local OAuth MockHTTP/API.
Assert the existing privacy transition, complete planning graph/decision removal,
prepared-export invalidation, old request/version/read unavailability, increased
generation and rejected old source work, other workspace unchanged, no provider
mutation and protected financial/goal records unchanged. Regenerating after fresh
import is a **new plan**, not an invented V2 of erased history. Test explicit
disconnect separately only if the same consumer path is not already qualified.

Keep the historical-preserving correction branch and its accepted-decision/no-
carryover evidence separate. Neither test changes policy or closes the contrary
reconnect expectation. Before adding a preservation reconnect path, an owner
decision would have to define exactly which original grant/provenance/authorization
changes are safe to retain, how workspace-wide dependencies are fenced and which
revocation/privacy transitions still erase. No such guarantee is established by
same account ID alone, and this proposal does not ask the owner to weaken erasure.

## Reviewed Copy Repair Boundary

Independent source review confirmed the customer-facing discrepancy. The narrow
repair changes existing Google disconnect explanation, acknowledgment label and
result text, plus a conditional warning before the existing callback selection.
It must disclose workspace-wide saved-plan/decision/selected-evidence erasure,
distinguish retained imported reporting and goals, and explain the need for new
import/selection/planning. No new checkbox, request, API, authorization mechanism,
backend behavior or inferred affected-plan count is introduced. Other providers
and the owner-managed public webpage are outside this repair. Existing focused
portal checks may verify the copy; actual reconnect API qualification is separate.
The frozen Q11 history-preserving reconnect conflict remains explicitly open.
