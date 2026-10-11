# Provider disconnect/reconsent copy: confirmed findings

Read-only source inspection at `502f3edec63a1f838321752792909e1ace7e5166`.
No code, tests, network calls or policy changes. Google is already corrected.

All erasure claims below follow the actual customer route into its writer and then
`lifecycle/privacy.bump_workspace_export_revision` →
`planning_documents/invalidation.erase_workspace_plans`, which deletes the complete
workspace plan/input/version/dependency/request/decision graph and catalog receipts.
The same privacy operation also removes selected reporting/derived measurement
evidence. It does not mean every raw imported fact or protected audit record is
deleted. Workspace scope is real, even when only one connection is changed.

| Provider / actual route path | Actual destructive behavior | Exact copy mismatch and smallest correction |
| --- | --- | --- |
| Meta DELETE `customer_meta.disconnect` → `meta/service.ConnectionService.disconnect` | Unconditional workspace semantic bump, local Meta connection deletion, integration revocation, staging and pending OAuth/grant removal. Imported advertising account/campaign/metric records are not explicitly deleted by this route. | `index.html#meta-disconnect-review` lists historical reports/campaigns/metrics/goals remaining, omitting all workspace plans/decisions/selected evidence erased. `portal.mjs` says “Historical data remains.” Add the same explicit derived-plan distinction as Google to review, existing acknowledgment and result; retain unchanged ads/provider data statements. |
| Meta fresh selection → `ConnectionService.select_account` | Existing same-advertiser connection triggers workspace semantic bump and generation increment. A different advertiser is refused with `meta_disconnect_existing_first`, not silently substituted. First connection has no bump in this branch. | `meta-callback.html` explains read-only reporting/conversion choice but not erasure. Add a conditional warning for reauthorizing the account already connected/currently stored in this workspace before existing selection. Meta disconnect deletes the connection row, so a later fresh connection does not necessarily trigger this branch; do not describe every previously connected account as destructive again. Do not claim first-time selection necessarily erases plans or that a different advertiser can replace it without disconnect. |
| TikTok DELETE `customer_sources.disconnect` → `sources/service.disconnect` | Owned SourceConnection is retained as disconnected, with revoked integration, erased grant/staging/cursor, generation increment, scoped pending analysis/checkpoint deletion **and workspace semantic bump**. No advertising raw-table purge is performed by this writer. | `index.html#tiktok-disconnect-review` says historical campaigns/metrics/reports/goals remain; `portal.mjs` says “Historical data remains.” Add workspace plans/decisions/selected-evidence erasure to review, existing acknowledgment and result while preserving raw-report/goal distinction and unchanged campaigns. |
| TikTok existing-account reconsent → `sources/service.select_account` | Existing `(workspace, provider, external_id)` branch performs workspace semantic bump and generation reset. A new advertiser creates another connection; it is not replacement of a different one. | `tiktok-callback.html` has read-only/unqualified-conversion notice but no erasure warning. Add conditional existing-account warning before the existing select control. Keep conversion semantics unqualified. |
| Klaviyo, HubSpot, Omnisend customer DELETE and reconsent | These customer routes use the same `customer_sources` → `sources/service` paths, not the separate legacy CRM service. Disconnect bumps workspace privacy and removes local grant/staging plus CRMCheckpoint for that connection. Existing-account reconsent also bumps workspace privacy; a first new account does not in that branch. | All three `index.html` disconnect reviews mention retained financial reports/goals/audit and no provider deletion but omit workspace planning/decision/selected-evidence erasure. Shared `portal.mjs` result says financial reports/goals remain unchanged, also omitting that consequence. Add the derived-plan distinction to these existing reviews/acks/results. `crm-callback.html` needs the same conditional existing-account warning before selecting; do not assert all CRM history is deleted or imply targeting consent. |
| Shopify DELETE `customer_shopify.disconnect` → `shopify/service.ConnectionService.disconnect` | Unconditional workspace semantic bump, `commerce/privacy.remove_store`, local Shopify connection deletion cascading imported facts/authorization, pending OAuth removal, privacy identity/audit preservation. **Unlike the ad/CRM routes, imported Shopify data is removed.** | Existing review already correctly says imported Shopify data/measurement snapshots are removed and saved goals/revision history remain with baselines unavailable. It does not explicitly disclose saved workspace plans and their recorded decisions/selected reporting evidence erased. Add that scope to review, existing acknowledgment and result; do not replace it with Google's “imported reporting remains” wording. Preserve goal reconfirmation instructions. |
| Shopify connection completion → `ConnectionService.finish`/binding path | Existing different shop is refused (`disconnect_existing_store_first`). When verified store binding runs (`shopify_measurement_enabled` OR provider details contain shop ID), `commerce/ledger.bind_store` calls `commerce/evidence.invalidate(..., rebind=True)`; that calls workspace semantic bump and removes measurement publications. This happens for new as well as existing verified store binding. `bind_shopify(..., reconnect=True)` alone merely reactivates an integration and is not the erasure proof. | Initial Shopify setup text says review permissions and no ad-spend authorization, with no derived-plan erasure warning. Warn before the existing Shopify authorization control that binding verified Shopify reporting clears saved workspace plans/decisions/selected evidence and requires fresh reporting/reselection/planning; retain raw-data disconnect distinction. Do not copy a “previously connected only” condition here, since the inspected verified first-bind path also invalidates. No selection-page warning can replace preauthorization disclosure because Shopify completes connection on callback. |

## Exact source references

- `app/api/customer_meta.py::disconnect` and select route;
  `app/meta/service.py::select_account` (existing account guard and privacy bump),
  `disconnect` (workspace bump before local deletion).
- `app/api/customer_sources.py::{select_account,disconnect}` (actual shared customer routes);
  `app/sources/service.py::{select_account,disconnect,discard_context_checkpoint}`.
  Reconsent lookup is exact workspace/provider/external ID; no blanket provider
  replacement inference. An exact already-consumed authorization replay takes the
  existing replay branch, not a new destructive transition.
- `app/api/customer_shopify.py::{callback,disconnect}`;
  `app/shopify/service.py` connection completion and `disconnect`;
  `app/imports/native.py::bind_shopify`;
  `app/commerce/ledger.py::bind_store`;
  `app/commerce/evidence.py::invalidate`.
- Current displayed text: `app/portal/static/index.html`,
  `portal.mjs` disconnect handlers/results, and `meta-callback.html`,
  `tiktok-callback.html`, `crm-callback.html`.

## Boundaries for a future repair

These are confirmed missing explanations, not requests to change erasure policy.
Use provider-specific copy only at existing controls; no new checkbox, API,
authorization behavior or architecture is necessary. Avoid false “all history
remains,” false “all imported data is deleted,” and false account-only plan scope.
Retained financial reports/goals are distinct from saved planning documents.
Explicit advertising non-mutation statements stay intact; reconnect is not a
claim that erased plans or decisions will return.

The separate Q11 preserved-history reconnect conflict remains open. Copy repair
cannot qualify historical preservation, and this source inspection does not claim
actual accepted-plan disconnect/reconsent tests for these providers. The Shopify
verified first-bind effect is worth making visible in acceptance planning; it is
not grounds to silently weaken its existing invalidation.

## Independent Review Boundary

The source findings were independently reviewed. Meta deletes its connection row
on disconnect, so its reauthorization warning must distinguish an account still
connected from an account disconnected earlier. Google/shared sources retain their
disconnected connection rows. Shopify verified first binding is independently
confirmed to invalidate workspace-derived plans. A copy-only repair may amend
existing explanations/acknowledgments/results and callback notices; no new
checkbox, authorization request or backend behavior is part of this repair.
Actual provider-specific retained-plan lifecycle acceptance remains separate.
