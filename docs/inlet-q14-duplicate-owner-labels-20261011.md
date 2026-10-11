# Q14 Duplicate Owner Labels — Three Bounded Cases Passed

Current result: one repaired renderer case and two actual authenticated TLS cases
(SQLite and PostgreSQL) passed on this isolated `bcc362a` child. This qualifies
only duplicate-name display and exact selection, not full Q14 or a live product.
Q15 `9ef5ca9` remains preserved.

## Historical Source Preparation

The initial draft below preceded baseline execution and the narrow repair.

Proposed shared formatter after baseline: ownerCampaignLabel(member) returns the
literal display name (or existing Campaign Name Unavailable fallback), followed by
` · Campaign ` and the actual provider_reference.entity_id. Native references must
match the existing NumericId contract (`^[0-9]{1,32}$`), otherwise fail closed. Reuse
in owner option/detail/included lists and saved review; textContent only. No schema,
backend, ownership, economic qualification or historical-proof changes.

The new focused component case composes a genuine pure V6 DTO after changing only
synthetic metadata names before projection/composition. Saved DTOs are not retagged.
Its first assertion requires distinct actual IDs in the saved member list and is
expected to fail on the current name-only renderer. Later assertions cover literal
text, malformed/missing reference refusal and original missing-name fallback.
A separately labeled synthetic current component response exercises option/detail/
included labels; it is not authenticated acquisition or an upgrade of the saved
historical document to current authority.

The existing actual TLS harness adds only duplicate_names, two DB nodes. The
qualified optional fixture name map supplies three simultaneously same-named native
campaigns. Browser chooses campaign2 by exact catalog identity, excludes independent
campaign3 and explicitly includes shared owner members1/2. It asserts distinct labels
and primitive exact selections, typed saved target/owner/exclusion bindings, JSON
export equality and existing session/financial/no-Apply boundaries. Defaults and
all previous variants remain unchanged. No unknown-parent or whole-Q14 claim.

Proposed selection after authorized collection:

- tests/test_owner_duplicate_name_labels.py::test_saved_owner_members_distinguish_duplicate_names
- tests/test_owner_review_planning_browser.py::test_actual_owner_review_planning_browser[sqlite-duplicate_names]
- tests/test_owner_review_planning_browser.py::test_actual_owner_review_planning_browser[postgres-duplicate_names]

Baseline phase executes only the focused renderer node and preserves its first
failure. After the narrow formatter repair and source/static review, qualify the
changed focused node and two new actual TLS cases with exact per-node manifests,
resource/source/cleanup gates and no broad old-cohort repetition. No test bodies
until explicit parent authorization.

## Baseline Evidence And Narrow Repair Draft

The authorized singleton baseline reproduced the exact first saved-label assertion:
`duplicate names must show distinct actual campaign IDs`. Pytest reported one
failure in 3.81 seconds; original subprocess exit was 1 (5.723 seconds). No TLS
case ran. Immutable source and evidence are preserved outside the checkout in
`/workspace/inlet-evidence/20261011/q14-owner-labels/baseline-freeze-01.json`
(SHA256 `07521991a24b328310b7bb5b6ff0eaa4e0922950268cd84b4f13e926df1e8a4e`).

Preparation Ruff initially found four long new test lines; formatting fixed them.
Initial mypy identified that the fixture passed a projected catalog instead of a
native inventory. The corrected fixture wraps the existing test-module projection
seam, preserving real Inventory, projection, reference construction and composition.
Final preparation Ruff, configured mypy (1,490 files), both changed JS syntax checks
and exact singleton collection passed. These checks precede the repair source.

The narrow repair draft adds one shared literal label formatter, requiring a
numeric native campaign reference of 1–32 characters and appending that exact ID.
Both owner components reuse it; two existing harness dependency-copy lists include
the new module. No DTO, identity, backend, policy or provider operation changes.
Repair checks and two new authenticated TLS cases remain pending authorization.

## Final Bounded Qualification

The first repaired cohort passed the component (3.87 seconds) then stopped at the
SQLite shared-owner option assertion (9.94 seconds); PostgreSQL was unrun. The test
incorrectly prescribed numeric campaign-ID order. Backend witnesses preserve
canonical-key order, so the corrected TLS expectation follows actual discovery
order while independently verifying the exact ID set `{1,2}`, equal names, full
account scope, catalog canonical/selection keys and provider references. The
failed run did not capture actual label strings; an observed order reversal is
not claimed. No product change was made for this test expectation correction.
The complete failure/source freeze is `repair-failure-freeze-02.json`, SHA256
`656a1fa7ec5f94d4763465807eca85dcaa80d734faca3737ec8c3add6358b352`.

Final runner03 passed SQLite in 24.04 seconds and PostgreSQL in 32.67 seconds,
with original subprocess exits zero, exact singleton XML cases/no skips, source
pre/post checks and successful browser shutdown/artifact checks. The unchanged
component pass is carried forward, not rerun. Thus the disjoint qualification is
three cases: one renderer and two authenticated mocked-provider browser journeys.
The browser checks exact duplicate-name option/detail/included/saved labels,
selection of campaign 2, full primitive exclusion of independent campaign 3,
original saved member order and exact JSON export. No advertising operation or
new financial authority is introduced.

Whole Ruff, configured mypy (1,490 files), JavaScript syntax and exact changed
selection collection passed before final execution. Earlier static findings and
both failure packets remain preserved. Evidence resides under
`/workspace/inlet-evidence/20261011/q14-owner-labels/`; manifest03 binds final
runtime/test sources and excludes the already passed component. Only this ledger
was updated after terminal execution. No broad cohort, hosted CI, provider/live
calls, merge or deployment occurred.
