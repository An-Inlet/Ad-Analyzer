# Plan Sales Progress UI V1 — Frozen Interface

Root8125953. Depends on the frozen plan-bound backend contract in
[planning-plan-bound-sales-progress-v1.md](planning-plan-bound-sales-progress-v1.md).
This document defines work ownership, not implemented behavior or acceptance.

Add a pure `app/portal/static/plan-progress.mjs` component:

```
clearPlanSalesProgress(host)
renderPlanSalesProgress(host, response, {workspaceId, planId, version, documentDigest, goal})
```

Clear prior output before validation. Require exact response schema, false/no
advertising authority, unknown attribution/manual application, exact workspace,
plan/version/document digest and saved goal reference (ID/revision/definition digest/
confirmation plus original definition fields). The expected goal comes from the
DISPLAYED immutable document.inputs.goal, never current edited inputs. Validate
matched/unavailable binding and null consistency. Use literal textContent only.
No component fetch, timer, storage, imports, reports or event writes.

Display current observed Shopify merchandise net sales, original target and goal
window, measured closed-day prefix/partial or full extent, as-of and source watermark,
currency/time zone, current measurement status/reasons. Binding unavailable preserves
original goal context and explicit changed/unavailable reason; show no replacement
amount. Explain refunds/corrections can change later reads without asserting which
cause occurred. No plan-impact, achieved milestone, forecast, progress percentage or
customer-action completion claim. Manual reports remain their existing separate UI.

Amounts: use only server-computed `net_sales_micros_exact`, canonical signed integer
string, BigInt arithmetic and exact six fractional digits. Reject missing/malformed/
negative-zero strings when matched sales carry an amount; never fall back to rounded
nested JSON numeric net_sales_micros. The legacy nested integer can exceed JS safe
range. Validate safe original target integer (<=1e15), format exactly. Preserve zero
and negative net sales. For a safe nested amount, verify exact string agreement;
for an unsafe number, do not infer its original digits from JSON.parse. Never write
these display values back to the API. Backend validates the computed correspondence.

Controller/template changes belong to the UI lane: add an explicit Read Sales Progress
button (`planning-progress-read`) and separate hidden output host (`planning-progress`).
Make the button available only with an actually displayed generated document. No
polling/automatic import; existing plan load does not need a progress fetch. The button
uses existing guarded original-session operation and same-origin/no-store API helper,
GET selected()/progress?version=<displayed version>, then session recheck.

Capture the displayed read object, goal, version, document digest, workspace/plan and
operation epoch before I/O. Clear prior progress on request, clearDocument/clearPlan,
version/workspace navigation, errors and logout/session invalidation. Reject late
callbacks unless all captured values still match and the plan document remains
visible. Existing stale-plan notices and manual decision eligibility remain untouched;
expired/historical plans can independently show matched current sales. Do not update
plan freshness, event sequence, document digest, saved inputs or original artifact.
Use existing guarded error/session handling, keep failure output empty, and require
an explicit new read after invalidation. No report/decision mutation is added.

Acceptance: pure DOM literal text/negativezero/zero/negative/unsafe-number exactness,
wrong binding/null/status rejection and clearing. Actual local HTTPS journey on both
DBs after backend integration: generated plan -> explicit progress -> real ledger
correction -> explicit read; immutable plan/export unchanged, customer manual report
remains labeled unverified. Historical version/changed goal unavailable, session and
late response navigation fences. Do not claim these API/browser tests before running
the integrated backend. No live provider, advertising writes or website changes.

UI lane owns component, planning.mjs, relevant portal template and its focused DOM/
HTTPS tests. Backend lane owns service/route/DTO. Start pure component/controller work
from8125953; combine reviewed backend before actual HTTP/browser qualification. Define
any browser fixture helper shared with backend before parallel modifications.
