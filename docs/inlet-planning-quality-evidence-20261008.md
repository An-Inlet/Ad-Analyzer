# Planning Quality Evidence — Reconciled 2026-10-08

Evidence cutoff: root `95a9ec1`, including reviewed receipt runtime merge `5c0252e`.
This supersedes the earlier pending-service/reader entries, not the unchanged frozen
[Q01–Q16 inputs and six evaluation criteria](design/comprehensive-planning-quality-cases.md).
All provider evidence below uses synthetic data and offline MockHTTP. Browser evidence
uses real local HTTPS/Chromium. No case is promoted to complete acceptance, human expert
approval, live-provider qualification, or launch readiness. Cohorts overlap; do not sum
them into a unique acceptance count. This reconciliation ran no tests or application code.
Target-picker/controller/browser work after this cutoff, including `62c8436` and WIP,
is deliberately not credited.

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

## Case Status: Partial Evidence, Not Full Acceptance

| Case | What is now implemented and demonstrated | Still required for the frozen case |
|---|---|---|
| Q01 Positive conversions | B01 behavior is preserved; E1's exact 100-click/10-conversion/$100 regression cannot produce a no-conversions claim. E5/E9 provide actual Google service/HTTP infrastructure and locatable owned targets. | Run the exact frozen selected-event/basis fixture through customer API generation. Current legacy Google aggregate defaults do not establish that qualification merely because the count is positive. Assess useful advice, not only absence of the defect. |
| Q02 Zero versus unavailable | E1 preserves unknown/zero qualification limits and investigation instead of asserting unsupported zero. | Trusted event-presence provenance distinguishing a present selected zero from an omitted/defaulted zero; exact two-variant API case and campaign-specific investigation. Do not weaken B01's valid true-zero behavior. |
| Q03 Meta-only | E1 single-platform concepts and explicit unit/owner gaps; E5/E9 actual Meta-only owned generation, fixed selection and exclusion paths. No Google/TikTok/CRM prerequisite. | Exact image/product/partial-scope fixture, useful nonbudget campaign changes and feasible substantive image brief through API and expert evaluation. |
| Q04 TikTok-only | E1 locatable regular-family plan/concept and missing-video limitations; E5/E9 actual TikTok-only service/HTTP and target receipt flow. | Exact no-video fixture with actionable production/storyboard detail and placement prerequisites; useful campaign changes without invented assets/authorization/native amounts. |
| Q05 Alternatives | E1 preserves typed independent customer alternatives; exact arithmetic and fixed allocations are implemented. E9 also exercises mixed retained/fresh accounts. | Exact three-platform A/B allocations/reserve through one customer input/version and readable export/browser. Mixed two-account acquisition is not this scenario. Meaningful alternative rationale remains unqualified. |
| Q06 Shared budget | Owned native references and conflicting-proposal contract checks exist; unsupported native amounts stay unavailable. | Qualified affected-owner coverage and useful single-owner proposal/manual verification, incomplete-coverage recovery and exact frozen shared-owner case. Receipt identity does not qualify budget ownership or units. |
| Q07 Ceiling/arithmetic | Exact integer contracts, independent scenario totals, bound errors and confirmed goal linkage; E4/E5 reject invalid customer inputs atomically. E9 resolves fixed allocation targets from retained proof. | Frozen three-platform over-ceiling/negative/mixed-currency/aggressiveness variants through API; prove a higher ceiling requires newly confirmed goal/input. Do not equate generic validation with the whole case. |
| Q08 Zero/sparse | E1 zero-ceiling behavior, account-level fallback and explicit missing evidence; E4–E6 usable no-target generation foundation. | Exact empty-history/$0/product-image API case and useful preparation/measurement/learning plan rather than generic diagnostic text. |
| Q09 Comparability | Evidence ports preserve event/window/currency/coverage; E1 avoids causal or unique-customer aggregation. | Comparable-window analysis and concrete alignment steps for the exact purchase/lead/different-attribution fixture. No unsupported numeric ranking or transfer policy. |
| Q10 Constraints/facts | E1 exclusions, exact fixed allocation and creative capacity; unresolved prose remains visible and defers creative. E9 actual exclusion/fixed target input and generation. | Exact combined excluded A/fixed B/no-discount/one-image/no-video/one-asset case; useful proposals satisfying constraints rather than blanket deferral. Substantive fact-supported creative remains open. |
| Q11 Correction/reconnect | E3 detects local corrections, source generation/mapping changes and stale proofs. E4–E6 implement immutable successors, source checks, exact-parent field comparisons, independent retained decisions and browser version history. | Exact corrected-conversion/refund/reconnect → stale V1 → refreshed V2 journey with field-level explanation and original decision history in one assembled test. Target disappearance/reselection browser flow is not yet credited. |
| Q12 CAS/replay | E4 actual PostgreSQL concurrent head/request races, final cross-plan replay guard, stale action binding and rollback; E5 HTTP replay; E6 actual lost-response recovery; E9 targeted same-key create race. | The complete frozen concurrent-version/decision fixture at customer HTTP boundary, including obsolete action acceptance attempts and explicit no execution/financial obligations. Existing service race coverage is real, not merely DTO/schema coverage. |
| Q13 Reported/observed | E4–E6 append-only decisions, reports and exact-chain withdrawal with current event CAS; historical withdrawal survives expiry/new version under current ownership. Browser labels customer reports unverified. | A trusted read-observed comparator/service/UI for exact/partial/conflict/unavailable proposed-field matches. Typed observation contracts alone do not implement provider verification, attribution or change-time proof. |
| Q14 Missing/ambiguous targets | E7 exact native IDs/hierarchy and duplicate/cross-binding rejection; E9 saved original selections survive rereads, session replacement blocks new use, expiry never silently remaps. | Exact disappeared/unknown-parent/duplicate-name/new-same-name cases through saved plan and customer reselection UI; unsupported manual verification stays unavailable. Post-cutoff target-browser WIP is excluded. |
| Q15 Access/text | E2 fixed I/O ordering and current principal/final-age checks; E3–E5 scoped reads/exports, revoked-during-IO rollback and foreign/viewer denial; E6 actual hostile text and session fences; E8 archive integrity/privacy checks. | Assemble exact malicious native-name/note/foreign-selection/expiry cases through target UI and readable export. Existing literal render/API evidence is partial; CSV is not implemented and no formula-safe CSV claim is made. |
| Q16 Privacy/progress | E3 fresh owned Shopify ledger/watermark/correction checks; E4 immutable history; E8 actual0087/0088 erasure, archive and delivery privacy fences. E6 exposes version/event history. | Saved-plan customer progress presentation and exact later closed-day sales/correction journey distinct from task reports; assembled post-erasure history/export/refresh non-resurrection case. Source freshness is not a completed progress experience. |

## Six Quality Gates Remain Separate

No human expert assessment has been recorded for any provider-alone case or Q05.
Automated/agent evidence must remain separate from that assessment.

| Frozen criterion | Present evidence | Open quality requirement |
|---|---|---|
| 1 Correct scope, facts, metric semantics | Owned catalog/receipt/source guards and conservative qualification (E1–E9). | Qualified selected-zero/event presence and exact case evaluation; no inference from legacy defaults. |
| 2 Campaign-specific usefulness | Exact locatable targets and manual diagnostic steps. | Useful typed current/proposed campaign changes and concrete prerequisites, evaluated per case. |
| 3 Coherent budgets/alternatives | Exact ceiling arithmetic and labeled customer hypotheses. | Useful supported alternatives/maintain rationale; qualified shared-owner/unit handling, no invented forecast. |
| 4 Traceable rationale/uncertainty | Versioned inputs/policy/evidence, limitations, stale history. | Case-specific reasoning and defensible alternatives beyond descriptive generic text. |
| 5 Feasible creative | Customer context provenance, bounded concepts, capacity and constraint deferral. | Product-specific copy/storyboards/assets/placement steps satisfying exact facts and capacity. |
| 6 Honest decisions/application/outcomes | Separate reviewed decision/report/retraction history and labels. | Trusted read-observed field comparisons and integrated corrected-sales progress without causal claims. |

## Remaining Implementation Packages In Dependency Order

1. **Finish target-selection customer integration and negative acceptance.** Build on
   reviewed E8/E9, not another receipt architecture. Finish authenticated picker/edit/
   expiry/reselection/session flow and cross-account sum checks, then review/record
   its actual results. Work after this cutoff remains uncredited.
2. **Qualify the missing evidence semantics needed by recommendations.** Preserve
   actual selected-event presence, zero versus unavailable, comparable windows and
   scope; add supported native units/shared-owner affected-set proofs where available.
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
5. **Complete plan progress and correction/reselection journeys.** Connect retained
   source staleness and existing Shopify progress to versioned planning UI, distinguish
   task reports from observed net sales, and qualify assembled Q11–Q16 including
   privacy erasure and no resurrection. This can proceed alongside package3 once
   shared evidence/response interfaces are frozen; it need not wait for creative prose.
6. **Evaluate and qualify the assembled planning product.** Record exact frozen-case
   API/browser results and six pass/fail criteria for each provider alone and Q05;
   obtain separate human expert review. Resolve remaining test-partition/full-suite
   qualification and authorized release/operational gates before launch claims.
   An authorized live pilot is a later explicit gate, never implied by local tests.

The owner-approved product scope remains comprehensive planning with zero advertising
writes. Descriptive functionality and a working local customer journey are substantial
implemented foundations; they do not establish a purchasable or launch-ready SaaS.
