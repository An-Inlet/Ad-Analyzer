# Strict Catalog Substitution Fixture Repair

The original Acceptance09 negative changed the complete Google witness catalog while
retaining the saved intent's original observation digest. Its strict PlanVersion
construction correctly failed before save; six earlier cases passed and21 were unrun.
The pre-kernel resolver already enforced this digest. Original failure evidence remains
in `google-owner-v6-runtime/acceptance-09/07-sqlite.*`; no production defect is inferred.

Reviewed proposalec81fc1 repairs only the existing negative function. It acquires an
actual linked Meta catalog before saving the input; the Google intent/proof remains
original. The adversarial candidate changes exactly one Meta campaign spend_cap_native
leaf, validates CatalogEvidence and PlanVersion, and proves full original document
restoration after reverting that leaf. All inputs, ticket, actual bundle, other catalogs
and Google proof remain byte-identical. An original-once boundary spy verifies entry
into actual owner-bundle binding before its exact409, with unchanged planning/financial
state. The value is untrusted candidate data, not claimed authentic provider observation.

Evidence: `/workspace/inlet-evidence/20261011/owner-catalog-negative-repair/`.
Initial mypy01 test alias reexport issue was fixed by importing its defining function;
whole Ruff02/mypy02 passed1479 files. Initial nodes01 collection named a nonexistent
lifecycle file and executed no tests. nodes02 collects the exact22 old manifest nodes
from index6 onward; original6 passed IDs are excluded. gate-manifest.json records the
reviewed WIPdiff/source hashes, unchanged productionf4e3b72, resource floors and one
corrected SQLite gate. No production/shared fixture change or clean-runner bypass.

The independently reviewed gate manifest dfb40f2d was retained unchanged; separate
authorization records the root-approved one-case execution. Explicit unique basetemp,
cache, log, XML and result paths were absent including symlinks; inherited PYTEST_*,
OBSERVER and PYTHONPATH overrides were removed before the declared environment.

The repaired SQLite case passed once (exit0, one pass, zero skips; XML case9.604s,
process14.070s). It reached the intended exact catalog comparison after strict candidate
construction. Final whole Ruff and configured no-path mypy passed (1479 files), and
diff checking passed. Only this one repaired case is newly qualified; original six
successes remain separate and the remaining21 have not run. Their clean-source
manifest requires separate review and authorization. This fixture repair does not
close R01/R02/R03 or establish deadline reliability/performance improvements.
