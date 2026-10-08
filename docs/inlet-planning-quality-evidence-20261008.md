# Planning Quality Evidence — Reconciled 2026-10-08

Evidence cutoff: reviewed root `8125953`, including actual Meta import-to-plan
acceptance. This docs-only reconciliation branches from `133993d`; its newly frozen
progress interface and subsequent progress implementation are deliberately not credited.
This supersedes the earlier pending-service/reader entries, not the unchanged frozen
[Q01–Q16 inputs and six evaluation criteria](design/comprehensive-planning-quality-cases.md).
All provider evidence below uses synthetic data and offline MockHTTP. Browser evidence
uses real local HTTPS/Chromium. No case is promoted to complete acceptance, human expert
approval, live-provider qualification, or launch readiness. Cohorts overlap; do not sum
them into a unique acceptance count. This reconciliation ran no tests or application code.
Target selection, alternatives and Meta presence evidence below are now credited at
their reviewed integrated heads. No frozen input or expert gate has changed.

## Reviewed Evidence Index

| Ref | Reviewed implementation and exact existing evidence |
|---|---|
| E1 Composer | `a765f88` integrated at `d951399`; `tests/test_planning_composer.py` covers positive versus unqualified zero conversions, each platform alone, customer alternatives/fixed allocations, exclusions, zero ceiling and constraint deferral. Integrated composer/contracts/ports/binding/capability cohort **108 passed, 0.98s**. [Composer ledger](inlet-planning-composer-integration-20261008.md). Descriptive output remains `not_expert_qualified`. |
| E2 Reader authority | `e389d49` integrated at `b557ab0`; actual SQL/identity/native callback ordering plus persisted identity changes, original session and final five-second authority checks. Author combined cohort **137 passed, 1 expected SQLite lock-test skip**; integrated reader/adapter/response/view cohort **101 passed, 104.57s**. [Reader ledger](inlet-planning-reader-authority-20261008.md). The planning reader's identity I/O under locks is fixed, not outstanding. |
| E3 Retained source proof | Reviewed `a431fc8`, integrated at `c8b8d77`; `tests/test_planning_retained_sources.py` reconstructs reporting absence/mismatch/current manifests, native mappings and Shopify source/ledger state. Complete ordinary+witness dependencies, changed sources, privacy, expiry and viewer reads without provider I/O are covered. Author **44 passed** plus final scoped-query **6 passed**; integrated **52 passed, 61.356s**. [Proof ledger](inlet-retained-source-proof-20261008.md). Local integrity is not a fresh live-provider observation. |
| E4 Core service | `768634b` plus reviewed repair `9682753`, integrated at `5ffd552`; `tests/test_planning_document_repository.py`, `test_planning_assertion_intent.py`, `test_planning_document_responses.py`: **31 passed, 3 expected SQLite concurrency skips, 44.42s**. PostgreSQL independent-session create/revise/generate/withdrawal races, exact replay, stale binding, viewer/foreign denial and revoked-during-read rollback run. `test_planning_service_error_boundaries.py`: **12 passed, 14.80s**, including disconnected-commerce stale history and controlled invalid input. [Core ledger](inlet-planning-core-service-20261008.md). |
| E5 Customer HTTP | Reviewed `bfd95ba`; `tests/test_planning_documents_api.py` uses actual service/storage and all-three-provider readers: create/generate/read/replay, decisions/reports, artifact export, edit/version comparison, foreign/CSRF/viewer denial and released authentication transaction. Root combined API/error/contract/Chromium display cohort **35 passed, 48.742s**. [API ledger](inlet-planning-customer-api-20261008.md). |
| E6 Account-level browser | `6c812e8` plus independently closed repair `44163af`; unchanged app/tests integrated at `6452954`, closure recorded at `1eb56c0`. `tests/test_planning_documents_browser.py`: final **2 passed, 13.93s**, SQLite/PostgreSQL, actual HTTPS Google journey. One plan/two versions, separate decision/report/retraction, comparison/export, malicious customer text, late commit/receipt404/explicit same-key recovery, same-owner session replacement, exact timestamp/null-capacity edit; zero execution attempts. [Browser ledger](inlet-planning-browser-20261008.md). Not an all-platform target-picker browser result. |
| E7 Native catalog | Reviewed V2 names/entity/parent bindings across three providers, including Google ad groups; assembled V2/native API/denial cohort **283 passed, 201.22s**. [Catalog ledger](inlet-planning-catalog-v2-integration-20261008.md). Exact identity and scope remain distinct from coverage, units and budget ownership. |
| E8 Receipt storage/archive | Models/schema `e512a10`/`c7ce328`, helpers `7fe1453`/`a1cfd96`, final archive `9dc52c7`; all boundaries independently closed, integrated at `8e4ec90`. Actual0088 scoped constraints/immutability/downgrade/privacy, complete retained selection/input sets (including zero missing links), exact1MiB/+1 bounds and history after original-session removal. Integrated storage/archive/account-level browser **10 passed, 1 existing Alembic warning, 30.03s**. [Storage ledger](inlet-catalog-receipt-storage-20261008.md). |
| E9 Receipt runtime | `f0b1295`, reviewed merge `5c0252e`; `tests/test_catalog_receipt_runtime.py`: original V2 selection survives later observation through create/generate/replay for allocation/exclusion × three providers × both databases (**12 passed, 53.18s**); identity/native I/O ordering **2 passed**; mixed retained Google/fresh Meta **2 passed**; concurrent PostgreSQL same-key create **1 passed, 1 expected SQLite skip**. Existing API/reader compatibility **206 passed, 230.33s**. [Runtime ledger](inlet-catalog-receipt-runtime-20261008.md). Exact original session/source/deadline remains required; no silent remap. |
| E10 Target browser | Reviewed `1f2a19e`, integrated `d2d08bd`; actual HTTPS Google/Meta/TikTok target selection on both databases plus account-level journeys and picker DOM: **9 passed, 0 skips, 53.489s**. Explicit allocation/exclusion reselection, original edit-head CAS, scope invalidation, client-clock expiry and same-owner session replacement; zero execution attempts. [Target browser ledger](inlet-planning-target-browser-20261008.md). Not disappeared/same-name replacement acceptance or server latency proof. |
| E11 Receipt adverse boundaries | Reviewed `1ff98e9`, integrated `1d3179a`; actual owned V2 HTTP/SQL expiry at native, identity, insertion and final boundaries; authority age, separately committed bounded cleanup surviving later read/quota failure, linked-history preservation. **16 passed, 30.83s**; final cleanup refinement **4 passed, 12 deselected, 17.85s**. [Adverse ledger](inlet-receipt-runtime-adverse-20261008.md). Deterministic clocks, not operating-performance qualification. |
| E12 Alternatives editor/API | Reviewed editor `e28f345` integrated `9ae91bf`: DOM **2 passed, 4.718s**; integrated HTTPS/DOM **12 passed, 90.305s**; final excluded-target scenario subset **2 passed, 14.599s**. Google-only scenario browser, existing all-three target flows. Reviewed API `2dd75dc` integrated `f4089e7`: **2 passed, 0 skips, 16.726s**, actual three-provider receipts and customer-confirmed USD 1,000 goal; independent 400/300/200/100 and 300/400/200/100 hypotheses, invalid total/negative/fixed mismatch rejected with no plan graph. Social reporting is absent, not fabricated. [Editor](inlet-planning-scenario-editor-20261008.md), [API](inlet-planning-customer-alternatives-20261008.md). |
| E13 Presence contracts/parser/summary | Reviewed contracts `3901fc1` integrated `e5d9dae`: **61 passed, 0.17s**. Meta parser `dc82de2` integrated `a99aaed`: parser+contracts **125 passed, 0.37s**. Summary `7df0857` integrated `a4a395c`: final **14 passed, 0 skips, 0.101s**, including repaired explicit Decimal context. Exact selected count/value presence, whole-set native/scope binding and complete-day zero gates; pure evidence only. [Contracts](inlet-reporting-presence-contracts-20261008.md), [parser](inlet-meta-presence-parser-20261008.md), [summary](inlet-reporting-presence-summary-20261008.md). |
| E14 Presence storage | Reviewed `53d9118`, integrated `db4325a`: actual 0089 immutable scoped graph/archive/privacy/downgrade; final affected cohort **98 passed, 2 deselected, 1 warning, 67.83s**. The deselected old 0074 fixture failure was independently reproduced, then separately repaired at `79e9a25`/`93a93f7`: named case **2 passed, 3.084s**, whole module **22 passed, 0 skips, 18.381s**. Do not retroactively describe the storage cohort as having no exclusions. [Storage](inlet-reporting-presence-storage-20261008.md), [fixture repair](inlet-performance-migration-fixture-20261008.md). |
| E15 Original Meta producer | Reviewed `34dd4fb`, integrated `d4f7c90`: actual 0090/new-window raw presence, no legacy adoption, partial retry/conflict, exact fixed/rolling atomic publication, original-source/terminal privacy and erasure. Affected cohort **105 passed, 1 expected SQLite skip, 7 existing warnings, 113.99s**; PostgreSQL-specific skipped counterpart passed. Results are terminal evidence recorded in the [ledger](inlet-meta-presence-publication-20261008.md), not a saved raw log/JUnit. No provider-live or planner qualification from this package alone. |
| E16 V3 consumer/policy | Reviewed `03ad1e4`, integrated `a21f034`: actual SQL sidecar readers and customer API/composer, policy v2, presence/absence source pins and retained `local_reporting_v2` witnesses, legacy v1 preserved. Affected cohort **179 passed, 0 skips, 290.84s** before final cache assertions; final changed module **20 passed, 0 skips, 46.16s**, 16 deliberate unsafe-copy serialization warnings. Those consumer fixtures create sidecars directly, not imports. [Consumer ledger](inlet-qualified-reporting-consumer-20261008.md). |
| E17 Actual Meta import-to-plan | Reviewed `f4ea768`, integrated `8125953`: actual read-only Meta rolling import over 56 closed UTC days, owned customer create/generate/current/history/export and real policy v2 composer. Positive 100/10/USD 100, full explicit zero, missing selected day, sparse calendar; actual zero→missing correction stales V1, preserves original artifact/export and generates V2 withdrawing zero. Combined cohort **30 passed, 0 skips, 40.19s** (8 new both-database cases +22 existing performance cases). [Ledger and raw log/JUnit links](inlet-meta-import-plan-presence-20261008.md). This is Meta-only, not frozen Google Q01/Q02 or all frozen common-basis data. |

## Case Status: Partial Evidence, Not Full Acceptance

| Case | What is now implemented and demonstrated | Still required for the frozen case |
|---|---|---|
| Q01 Positive conversions | B01 behavior is preserved. E17 demonstrates actual Meta import→customer plan for 100 clicks/10 selected/USD 100 without a no-conversions claim; E5/E9/E10 provide Google owned target/API/browser infrastructure. | Run the exact frozen selected-event/basis fixture through customer API generation. Current legacy Google aggregate defaults do not establish that qualification merely because the count is positive. Assess useful advice, not only absence of the defect. |
| Q02 Zero versus unavailable | E13–E17 implement and demonstrate trusted Meta raw presence through API generation: full explicit zero permits investigation; omitted selected cells and missing calendar days do not qualify full-window zero. Counts and values remain independent. | Frozen Q02 reuses the Google Q01 selected-event/common-basis fixture; that producer and exact two-variant API case remain open. Meta 56-day UTC acceptance is real but does not replace the frozen September/New_York/comparison basis or expert usefulness evaluation. |
| Q03 Meta-only | E1 single-platform concepts/unit-owner gaps; E5/E9/E10 actual Meta-only owned generation, receipt selection/exclusion and browser paths; E17 adds raw selected-metric provenance. No Google/TikTok/CRM prerequisite. | Exact image/product/partial-scope fixture, useful nonbudget campaign changes and feasible substantive image brief through API and expert evaluation. |
| Q04 TikTok-only | E1 locatable regular-family plan/concept and missing-video limitations; E5/E9/E10 actual TikTok-only service/HTTP/target browser. Selected-event reporting remains unqualified. | Exact no-video fixture with actionable production/storyboard detail and placement prerequisites; useful campaign changes without invented assets/authorization/native amounts. |
| Q05 Alternatives | E12 demonstrates the exact A/B allocation amounts and independent USD 1,000 reconciliation through actual three-provider receipts, customer goal confirmation, API/composer/SQL; Google scenario browser saves/rebuilds alternatives and preserves history. | Full frozen common-basis performance/product/window fixture, all-three-platform scenario browser/readable export labels and meaningful alternative rationale/expert evaluation. E12 social reporting is absent; arithmetic acceptance alone is not full Q05. |
| Q06 Shared budget | Owned native references and conflicting-proposal contract checks exist; unsupported native amounts stay unavailable. | Qualified affected-owner coverage and useful single-owner proposal/manual verification, incomplete-coverage recovery and exact frozen shared-owner case. Receipt identity does not qualify budget ownership or units. |
| Q07 Ceiling/arithmetic | E12 proves actual three-provider over-ceiling, negative and fixed-mismatch requests return 422 with no new plan graph; exact micro arithmetic, independent sums and excluded-target browser rejection also pass. E9 binds fixed targets to retained proof. | Remaining frozen mixed-currency/aggressiveness and higher-ceiling/newly-confirmed-goal variants through API; full common-basis and expert coherence. Existing exact negative/over-ceiling cases are credited, not rerun as a substitute for missing variants. |
| Q08 Zero/sparse | E1 zero-ceiling behavior, account-level fallback and explicit missing evidence; E4–E6 usable no-target generation foundation. | Exact empty-history/$0/product-image API case and useful preparation/measurement/learning plan rather than generic diagnostic text. |
| Q09 Comparability | E13–E17 preserve raw selected-event/presence, requested/actual window, currency and coverage through Meta imports and policy v2; attribution stays explicitly unknown. No causal or unique-customer aggregation. | Comparable-window analysis and concrete alignment steps for the exact purchase/lead/different-attribution fixture. No unsupported numeric ranking or transfer policy. |
| Q10 Constraints/facts | E1 exclusions, exact fixed allocation and creative capacity; unresolved prose remains visible and defers creative. E9 actual exclusion/fixed target input and generation. | Exact combined excluded A/fixed B/no-discount/one-image/no-video/one-asset case; useful proposals satisfying constraints rather than blanket deferral. Substantive fact-supported creative remains open. |
| Q11 Correction/reconnect | E3 detects local corrections, source generation/mapping changes and stale proofs. E4–E6 implement immutable successors, source checks, comparisons, retained decisions and history. E10 adds explicit replacement/reselection. E17 demonstrates actual conversion-presence correction→stale V1→V2, preserving V1 document/export. | Full frozen corrected-conversion/refund/reconnect journey with field-level explanation and original decision history; actual disappeared-target/same-name reconciliation. Meta presence correction alone does not prove refund/reconnect variants. |
| Q12 CAS/replay | E4 actual PostgreSQL concurrent head/request races, final cross-plan replay guard, stale action binding and rollback; E5 HTTP replay; E6 actual lost-response recovery; E9 targeted same-key create race. | The complete frozen concurrent-version/decision fixture at customer HTTP boundary, including obsolete action acceptance attempts and explicit no execution/financial obligations. Existing service race coverage is real, not merely DTO/schema coverage. |
| Q13 Reported/observed | E4–E6 append-only decisions, reports and exact-chain withdrawal with current event CAS; historical withdrawal survives expiry/new version under current ownership. Browser labels customer reports unverified. | A trusted read-observed comparator/service/UI for exact/partial/conflict/unavailable proposed-field matches. Typed observation contracts alone do not implement provider verification, attribution or change-time proof. |
| Q14 Missing/ambiguous targets | E7 exact native IDs/hierarchy and duplicate/cross-binding rejection; E9 saved original selections survive rereads, session replacement blocks new use, expiry never silently remaps. E10 adds actual explicit fresh reselection and expiry/session invalidation. | Exact disappeared/unknown-parent/duplicate-name/new-same-name cases through saved plan and customer reselection UI; unsupported manual verification stays unavailable. |
| Q15 Access/text | E2–E8 scope/session/export foundations remain. E10/E12 add literal target/scenario labels, scope/expiry/session clearing; E11 tests actual server final-expiry/identity/persistence/cleanup failure boundaries on both DBs. | Assemble exact malicious native-name/note/foreign-selection/expiry cases through target UI and readable export. Existing literal render/API evidence is partial; CSV is not implemented and no formula-safe CSV claim is made. |
| Q16 Privacy/progress | E3 fresh owned Shopify ledger/watermark/correction checks; E4 immutable history; E8 actual0087/0088 erasure, archive and delivery privacy fences. E6 exposes version/event history; E14/E15 add finalized-presence erasure/archive and terminal semantic-erasure non-resurrection. | Saved-plan customer progress presentation and exact later closed-day sales/correction journey distinct from task reports; assembled post-erasure history/export/refresh non-resurrection case. Source freshness is not a completed progress experience. |

## Six Quality Gates Remain Separate

No human expert assessment has been recorded for any provider-alone case or Q05.
Automated/agent evidence must remain separate from that assessment.

| Frozen criterion | Present evidence | Open quality requirement |
|---|---|---|
| 1 Correct scope, facts, metric semantics | Owned catalog/receipt/source guards plus actual Meta selected-presence producer/consumer (E1–E17). | Google/TikTok selected-event producers, comparable attribution/window qualification and exact frozen case evaluation; no inference from legacy defaults. |
| 2 Campaign-specific usefulness | Exact locatable targets and manual diagnostic steps. | Useful typed current/proposed campaign changes and concrete prerequisites, evaluated per case. |
| 3 Coherent budgets/alternatives | Exact ceiling arithmetic and actual E12 three-platform A/B customer hypotheses; Google alternatives browser. | Useful supported alternatives/maintain rationale; qualified shared-owner/unit handling, no invented forecast. |
| 4 Traceable rationale/uncertainty | Versioned inputs/policy/evidence, limitations, stale history. | Case-specific reasoning and defensible alternatives beyond descriptive generic text. |
| 5 Feasible creative | Customer context provenance, bounded concepts, capacity and constraint deferral. | Product-specific copy/storyboards/assets/placement steps satisfying exact facts and capacity. |
| 6 Honest decisions/application/outcomes | Separate reviewed decision/report/retraction history and labels. | Trusted read-observed field comparisons and integrated corrected-sales progress without causal claims. |

## Remaining Implementation Packages In Dependency Order

1. **Finish remaining target/alternative edge acceptance.** Reviewed E10–E12 now
   cover actual target UI, explicit reselection, Google scenario UI and three-platform
   API alternatives. Remaining work is disappeared/ambiguous/same-name targets,
   exact frozen export/browser labeling and comparison-window editing, not rebuilding
   the receipt/picker architecture or redoing already credited exact sums.
2. **Qualify the missing evidence semantics needed by recommendations.** Build on reviewed
   Meta E13–E17. Implement selected Google/TikTok event producers and qualify
   comparable windows/attribution/scope; add supported native units/shared-owner affected-set proofs where available.
   Unsupported facts must remain explicit gaps. Define these evidence interfaces before
   dependent composer or observation work; no guessed thresholds/elasticities.
3. **Develop substantive deterministic planning and exact-case API evaluation.** Use
   the unchanged Q01–Q10 inputs to implement useful campaign-specific changes,
   coherent customer alternatives, constraint-respecting product creative and sparse/
   zero-budget tasks. Preserve exact ceiling/authority semantics. Input/browser/export
   support for alternatives and comparison windows must match the supported API.
   Existing service/version/CAS foundations are reused, not reimplemented.
4. **Implement read-observed manual-application verification.** Use reviewed exact
   action/proposed-field contracts plus owned fresh reads from package2; retain the
   independent customer report/correction chain. Cover exact/partial/conflict/unknown,
   disappearance and ambiguity with no write or name-based fallback.
5. **Complete plan progress and correction/reselection journeys.** No progress
   implementation after cutoff `8125953` is credited here; a frozen later interface
   alone is not working progress. Connect retained source staleness and existing Shopify progress to versioned planning UI, distinguish
   task reports from observed net sales, and qualify assembled Q11–Q16 including
   privacy erasure and no resurrection. This can proceed alongside package3 once
   shared evidence/response interfaces are frozen; it need not wait for creative prose.
6. **Resolve historical compatibility and evaluate the assembled product.** The
   execution/optimization/session API partitions are reviewed; 0074 fixture repair
   is separately qualified. The retained pre-0086 initial-review bridge is still
   incompatible: current preview reads require a draft planning mandate while its
   old execution bridge requires the same mandate active. The case remains intact,
   with no skip/xfail or guard bypass. A separately reviewed archived historical
   harness is a proposal, not implemented evidence
   ([blocker ledger](inlet-initial-review-default-20261008.md)).
   Other retired execution UI/initial fixtures still need classification. Exactly
   one aggregate remains pending; no Full result is claimed from these packages.
   **Evaluate the assembled planning product:** Record exact frozen-case
   API/browser results and six pass/fail criteria for each provider alone and Q05;
   obtain separate human expert review. Resolve remaining test-partition/full-suite
   qualification and authorized release/operational gates before launch claims.
   An authorized live pilot is a later explicit gate, never implied by local tests.


## Regression Preparation Is Not Aggregate Qualification

Reviewed execution API partition: **53 passed, 29.352s**, including 14 both-database API
cases and default boundaries ([ledger](inlet-execution-api-partition-20261008.md)).
Optimization API partition: **71 passed, 49.267s**, including 32 both-database API cases
and the same default boundary suites ([ledger](inlet-optimization-api-partition-20261008.md)).
Session API partition: **4 passed, 16.982s** plus separate default boundaries
**39 passed, 0.709s** ([ledger](inlet-session-api-partition-20261008.md)).
Initial-review default repair: **2 passed, 7.181s** plus boundaries **39 passed,
1.131s**; explicitly not a whole-module pass. These overlapping cohorts preserve
historical/current-policy boundaries; they are not quality-case completion counts.
The historical bridge blocker above and remaining UI/fixture classification remain
open. No new tests were run for this reconciliation; only document/link and diff
checks. New progress work after the stated cutoff is excluded.

The owner-approved product scope remains comprehensive planning with zero advertising
writes. Descriptive functionality and a working local customer journey are substantial
implemented foundations; they do not establish a purchasable or launch-ready SaaS.
