# Next Creative Quality Packages — Q06 / Q08 / Q09 / Q10

Read-only assessment against root `d0514a6`, after qualified Q05 and the approved Q07
design. Frozen [case inputs](comprehensive-planning-quality-cases.md) remain unchanged.
No implementation/tests, external sharing, live calls or new policy authority here.
Q07 arithmetic/goal-reconfirmation work belongs to the existing implementation lane.

## Existing Evidence Versus Missing Actual Joins

| Case | Concrete existing evidence | Missing engineering / actual v5 API join |
| --- | --- | --- |
| Q06 Shared budget | `test_planning_metadata_api.py` and `test_planning_target_catalog_api.py` assert observed Google shared-budget fields. `test_planning_document_contracts.py::test_shared_owner_cannot_be_allocated_twice` and `::test_shared_owner_contradictory_native_budgets_rejected` reject duplicate/conflicting synthetic proposals. Google native inventory reconciles campaign-budget reference counts; catalog projects owner keys and native units. | No actual three-campaign Common Basis input→generation→export case emitting one owned budget group with both affected campaigns, plus independent third owner. Current selected composer deliberately returns native budget proposals unavailable; conflict rejection is not positive owner-group planning. Need an exact affected-owner coverage/proposal/manual-verification contract before implementing this positive branch, plus incomplete-coverage recovery. Diagnostic daily-budget facts do not become a total-spend cap or financial qualification. |
| Q08 Zero/sparse | `test_planning_composer.py::test_zero_budget_never_creates_positive_allocation` / `::test_zero_ceiling_does_not_instruct_maintaining_positive_native_spend`; `test_selected_paired_composer.py::test_positive_selected_counts_do_not_override_zero_ceiling`; genuine v5 zero-image and missing-product API/composer coverage. | Those are not the frozen $0 confirmed goal + empty advertising history + typed mug facts/owned image case. Current selected composer can provide an account-level investigation, but `creative_composition.py` explicitly defers when no included campaign exists. Thus a useful non-campaign preparation/measurement/learning plan is an actual composition gap, not a credential gate. First capture the real sparse API result, then design a bounded owned-account preparation task target; never fabricate a campaign or failing performance. |
| Q09 Comparability | Q05 actual three-platform API preserves Google selected purchase observations and social unsupported gaps; pure selected/traffic tests distinguish windows, sparse rows and generic versus selected counts. Meta raw-presence tests cover chosen actions and unknown default attribution; nonpurchase value remains unsupported. | Q05 explicitly does **not** supply the frozen Meta leads + TikTok purchase with different known attribution window. The current recognized selected profile is Google; social selected mapping remains unsupported. Need real provider/profile-specific event and attribution evidence ports and owned acquisition/publication before claiming exact v5 Q09. No retagging generic TikTok conversion as purchase, no assumed attribution windows, no fabricated capsule. A negative API test that preserves unknowns is useful partial evidence only. |
| Q10 Constraints/facts | Pure `test_selected_paired_composer.py::test_manual_constraints_scenarios_ceiling_and_exclusions`, creative global-capacity/constraint tests, legacy actual exclusion/fixed target APIs, and Q05 actual v5 alternatives with one global creative asset. Actual Common Basis currently asserts exclusions/fixed allocations/constraints all empty. | Missing one real v5 join: campaign A excluded, B fixed at $200 exactly once, explicit no-discount product restriction, one image/no supplied video, global capacity1; persisted/current/export outputs must all preserve this. Global freeform constraints currently defer all creative; that behavior must not be hidden by deleting or moving an existing customer constraint. Separate typed product restrictions already flow verbatim into substantive image production, making a bounded current-contract positive path plausible. |

These tests were inspected, not rerun. Pure synthetic documents establish contract
validation, not the missing actual owned API journey, provider qualification or expert
usefulness. Q05's retained actual artifact is the three-platform precedent; no broad
acceptance claim follows from its ten-case cohort.

## Recommended Next Package: Q10 Exact Customer Input Join

Smallest dependency order after Q07: **Q10 first**, then Q08 sparse preparation;
Q06 owner-group contract/source qualification and Q09 social selected/attribution
producer contracts are separately larger dependencies. Q10 can begin as a test-only
real-API package using the existing Meta-only two-campaign Common Basis fixture.
The frozen Q10 does not require all three platforms; do not unnecessarily import Q05's
three-platform setup. No new storage, policy, provider connector or authority needed.

Freeze the following fixture/input interpretation before writing tests:

- Preserve the unchanged Common Basis owner, paid store/goal, September/August reporting,
  November USD1,000 ceiling, mug/$25/image and ordinary original session.
- Use actual observed Meta campaign A/B and their issued target-catalog receipts.
  Submit exact A exclusion and B fixed allocation200,000,000 micros through customer
  input APIs, not constructed TargetRefs or seeded input/proof rows.
- Explicit customer product restriction "No discount claims" belongs in the existing
  typed `creative.product.restrictions` field for this new case. Preserve no-approved-
  health-claims/testimonials restrictions too. This is a declared fixture input, not
  silently migrating an existing global constraint to bypass deferral.
- One owned PNG/JPEG through actual media upload; no video observation/asset ID. Confirm
  global maximum_creative_assets=1. A Meta image brief is production work, not an
  already approved/published advertising asset and not a visual/rights finding.
- Generate via real v5 service; retain canonical document and exact export. Assert A
  does not reappear in actions/briefs/alternatives, B fixed amount occurs once per
  independent scenario, no duplicated owner pools, no native numeric budget edit,
  and at most one production proposal. Verify no invented discount/testimonial/health
  claim/forecast language; exact restrictions and review prerequisites are present.
- Include a distinct explicit global-constraint variant (same prohibition placed in
  `inputs.constraints`) to record the current truthful deferral, without claiming it
  meets the frozen useful-proposal expectation. If that variant is required as the
  positive product path, stop for a typed constraint interpretation/composition design
  rather than weakening the expected output or hiding the original text.

Use SQLite first and bounded both-database cases only after review/slot authorization.
Replay/current/version/export must preserve exact observations and native-call counts;
execution/approval/reservation rows stay unchanged. Start with actual fixture output,
then assess useful advice and human-review quality separately. If a structural gap
appears, preserve the failure and propose its narrow contract before production edits.

## Follow-On Boundaries

Q08 needs a definition of useful work without any campaign/history: truthful setup,
measurement prerequisites, inspect/prepare the customer image, and an explicit future
learning question. An empty history is neither zero selected conversions nor a failed
campaign. Clarify whether the fixture has an owned empty catalog versus no advertising
connection; the current input schema requires accounts, so an entirely unconnected
brand is a distinct product/interface question, not something a fixture may simulate
with a fake account. No paid allocation at a zero ceiling.

Q06 should separate observed shared-setting explanation/one-owner grouping from a new
native numeric proposal. The existing no-budget-change descriptive policy cannot be
silently relabeled as providing the frozen positive native edit. Freeze exact affected
campaign closure/units and manual verification evidence; keep unavailable/incomplete
recovery honest and all execution gates unchanged.

Q09's missing social event/attribution producers are engineering/specification gaps.
Approved access or credentials alone would not fill them. Known event/window differences
must be presented prominently without cross-platform CPA rankings or transfers; unknown
semantics stay unknown. Any genuine missing provider guarantee should be recorded after
specific source-contract investigation, not invented from default reports.

No owner decision is currently needed for the proposed Q10 join. Potential later owner
choices are explicitly limited to no-connected-account Q08 product scope or a changed
native-proposal policy; neither is requested or presumed by this note.
