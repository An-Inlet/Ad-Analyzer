# Proposed Q14 Browser Disappearance And Exact Reselection Acceptance

Read-only design from `3b39199`; root review must freeze this interface before implementation. No tests, provider calls, production edits or aggregate activity ran in this investigation. Heavy browser/database qualification waits for the original aggregate to finish or explicit root go-ahead, and uses only isolated disposable fixture schemas.

## Existing Evidence And Scope

Frozen Q14 also requires unknown-parent topology, simultaneous duplicate names and unsupported manual verification. This package addresses only disappearance and a same-name/new-native-ID replacement through the customer browser. It must not mark Q14 or comprehensive quality complete.

Reviewed `126a30e` / `tests/test_planning_target_disappearance.py` already proves the actual API scenario for all three providers on both databases. A newly empty inventory does **not** retroactively revoke a still-valid original as-of receipt. Exact original generation is legitimate until its actual expiry/source/session fence says otherwise. The test must preserve that behavior, never reinterpret a fresh catalog as independent revocation or live truth.

Current non-dated `tests/test_planning_documents_browser.py` provides localhost HTTPS, actual portal/controller/API/service, owned setup, real Chromium, no-network flags and result collection. `planning_targets_browser.mjs` already tests ordinary explicit reselection, expiry and same-owner session replacement. It lacks mutable native inventory. Reuse this harness rather than the dated Q16 fixture.

## Proposed Private Test Interfaces And Ownership

Add `tests/planning_target_inventory_fixture.py` only, with:

```python
InventoryPhase = Literal["original", "absent", "replacement"]
install_inventory_scenario(platform: str, patch: pytest.MonkeyPatch) -> InventoryScenario
InventoryScenario.advance(phase: Literal["absent", "replacement"]) -> None
```

Install immediately after existing `setup_evidence`. It wraps the already installed native MockHTTP transport; it does not construct catalogs, receipts, goals, plans or source facts. It admits only ordered `original -> absent -> replacement` transitions and rejects unknown/reset phases. Capture the current phase once per request; drive phase changes only after prior browser operations settle. Preserve OAuth, account metadata, source generation, original scopes and actual deadlines.

Port the response transformations already qualified in the API test: empty campaign/child inventories when absent; replacement native campaign ID `9` with the exact original name, and child parent IDs updated consistently wherever those children exist. Google original campaign ID is `1`; Meta/TikTok original is `5`. Do not claim Google child coverage if its existing fixture returns none. Observe actual V2 responses and assert these native IDs/names instead of trusting the fixture transform. No new collector, report presence, attribution or selected-event producer.

Extend the existing browser harness with journey `target_disappearance` for Google/Meta/TikTok. Add only two closed test-control POST paths (`/__fixture__/inventory/absent` and `/__fixture__/inventory/replacement`) for this journey. They change MockHTTP phase only and return current phase plus `len(calls)`. No request-supplied SQL, payload, import path, callable, arbitrary mode, authorization bypass or production endpoint. The usual driver/result endpoint remains unchanged. Production routes, DTOs, controller and component stay untouched unless a concrete reproducible defect is separately reviewed.

New driver: `tests/javascript/planning_target_disappearance_browser.mjs`. Inject the same existing `__INPUTS__` document as other drivers; derive owned account/native targets from actual responses. Use existing fieldset `data-target-key`, `[data-role=target-choice]`, `[data-role=target-amount]`, and actual UI controls. Record request bodies only for assertions; do not synthesize mutation requests in place of user selection.

## Exact Browser Sequence

1. Actual sign-in, owned workspace/goal/account selection, current report window, explicit target read. Find the actual campaign by kind and native ID, not array position or name. Record its owned account, advertiser/native ID, canonical key, selection key and receipt expiry. Select a fixed one-micro planning allocation using the exact decimal UI and save revision1. Capture actual create body and persisted input.
2. Advance fixture to `absent`. Open Edit and explicitly read fresh targets. Assert actual V2 `targets=[]`, the real empty-coverage message, no old target control and no same-name fallback. Attempt Save without replacement confirmation: no save request/graph mutation. Cancel the draft through the actual Cancel control.
3. Generate V1 from the original saved inputs while its original receipt is still valid. Assert no new native reads between the empty observation and generation; persisted exact original native ID/canonical/selection survive. This is retained as-of evidence, not a claim the target still exists. Capture immutable V1 and original artifact digest through read-only customer API requests from the browser.
4. Advance to `replacement`. Edit and explicitly reread. Assert replacement native ID9, same original name, distinct canonical and selection keys; no target retaining the old campaign ID. Where child rows exist their parent is ID9. UI legend includes the exact native ID, original saved fixed choice is not prefilled onto the replacement, and replacement confirmation is unchecked. Attempt Save without explicit confirmation: no input mutation.
5. Select the replacement campaign explicitly, enter the same one-micro allocation, confirm replacement, Save revision2, Generate V2. Capture the actual UI-generated selector in the mutation body; it must equal the exact fresh owned response, never name-derived. Generation adds no native rereads. Persisted V2 identifies ID9; history V1 and its artifact digest remain exact. Read-only API checks verify history/export; this is not a separate export-button/download-interaction claim.
6. Python postconditions: one plan, two immutable input revisions, two versions, two input receipt links, no planning events and zero execution attempts. Browser captures catalog/native-call checkpoints and exact selector/version assertions. Preserve native request logs only as synthetic bounded evidence; no full response credential logs.

Do not manufacture expiry, freeze time, increase TTL or retry a failed expired observation invisibly. If the unchanged fixture lifetime is insufficient, report the stage/actual age and an explicit expiry outcome; any revised sequence or fixture timing needs review. Existing session/expiry browser tests remain separate compatibility evidence rather than being silently credited here.

## Qualification Plan

After interface approval implement tests only, then wait for root's load window. Run the six new actual HTTPS cases (three providers × SQLite/PostgreSQL) and the six existing target-browser cases affected by shared harness edits; run original six API disappearance cases only if the transport extraction modifies their source (preferred: leave their reviewed test untouched). Required whole Ruff, bare mypy, Node syntax and diffcheck. Record precise commands, terminal results, skips/failures and raw log/XML plus sanitized original/replacement selectors, V1/V2 digests and browser stage results. Do not sum overlapping runs or claim whole-suite acceptance.

Remaining Q14 packages after this bounded result: unknown-parent and simultaneous duplicate-name saved-plan/UI behavior, plus unsupported manual-verification presentation under exact provider evidence. No source or policy expansion is implied by this proposal.
