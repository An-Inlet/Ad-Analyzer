# Standalone creative historical dependency — 2026-10-11

Child of reviewed `8e09b73`. Implements the frozen creative history/dependency
interface without service/retained-source dispatch, registration, migration or v5
runtime activation.

`RetainedSourceWitness` adds only `local_creative_basis_v1`, requiring exactly
`local:creative:basis` and null account/connection/store. Existing kinds retain
fields, rules and serialized representation. `creative_local_witness(document)`
requires a fully valid exact-v5 document, including original typed proof, and binds
full proof digest, ordered source-binding digest, schema, scope/privacy, generation
and expiration. Generation time labels the immutable basis commitment; original
image observation times remain inside the proof. Empty image selections still
require this complete witness.

`validate_creative_local_dependency` validates the reserved-key OR reserved-kind
subset, requiring exactly one full normalized row. `validate_selected_historical_dependencies`
recognizes only exact v4/v5 through the existing pure selected-policy contract.
V5 consumes its validated creative row before checking every ordinary evidence,
reporting and commerce dependency; v4 continues to reject creative/extra rows.
Allowed dependency cardinality grows by one only for v5. The SQL history fetch
retains the overflow sentinel: v4 MAX_EVIDENCE+MAX_ACCOUNTS+2, v5 +3.

The SQL historical path still verifies stored document digest, original selected
capture and raw traffic graphs. It performs no image metadata/storage reads,
identity-provider IO or paid entitlement check. Caller READ_ROLES/privacy authority
remains mandatory; this internal function grants none. Ordinary media deletion
leaves immutable inspection evidence readable. Semantic workspace privacy erasure
removes the plan and its version-owned dependency set. No creator/session fields
are introduced into public documents.

Test fixtures distinguish pure synthetic proof tests from actual SQL qualification.
The latter uses real mocked-HTTP range/event/selection/capture services, the actual
owned reporting collector, uploaded/inspected owned image and genuine v5 pure
composer. It directly stores the resulting immutable document/dependencies for the
standalone history validator; this is not a v5 API generation claim. Commerce
witnesses are produced from actual owned commerce state. Boundary tests lower only
engineering count constants to fixture cardinality, verifying exact allowed count
then one fetched overflow row for both versions. No fake v4 creative document.

Evidence: `/workspace/inlet-evidence/20261011/creative-history`.
Initial pure24 passed3.75s; actual SQLite media-loss/history/privacy case passed6.48s.
First static logs retain test-only FixtureRequest signature/optional-input errors;
fixed with explicit fixture argument and nonnull saved-input assertion. No product
fallbacks were introduced. Final outcomes follow below.

Final qualification:

- `both01.log/xml`: **72 passed, zero skipped, 104.79s**, including new pure and
  actual SQLite/PostgreSQL history tests plus existing selected history and real
  read/archive/erasure regressions.
- `pure02.log/xml`: **5 passed, 24 deselected, 5.14s**; additional exact witness
  scope and fresh-process standalone import checks.
- Whole `ruff check .` passed (`ruff-final.log`); configured mypy passed **1396**
  source files (`mypy-final.log`); `git diff --check` passed.
- Database command: pytest new `test_creative_history.py`,
  `test_creative_history_sql.py`, existing `test_selected_plan_history.py` and
  `test_selected_plan_history_read_export.py`, with `--durations=20`, unique
  `/tmp/inlet-creative-history-both01` basetemp and durable JUnit. Existing
  disposable PostgreSQL uses isolated per-test schemas; no reset or shared data
  mutation. No pytest failure occurred; initial/static logs are retained.
- No live traffic, Full, hosted CI, push, merge or deployment performed.
