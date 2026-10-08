# P02 Initial Target Catalog Integration

Reviewed catalog111c55c/166048b/06b2ac5 with ownership repairba51145 and proposal-only
c7bb7f2 integrated onto qualified P01c736d40. The main.py import conflict was resolved
by retaining both the owned account catalog and target catalog routers. Both routes
are registered; no execution route or guard was re-enabled.

New /planning/target-catalog uses the existing current-session, owned, paid, generation-
bound NativeDiagnosticService for Google/Meta/TikTok. Google search POSTs remain reads.
No spending mandate, financial source or execution runtime is required. Shared Google
budget resources remain visible. Meta/TikTok native amounts do not establish budget
ownership: owner keys remain null with explicit reasons. Missing names and Google
adgroups are unavailable, Meta/TikTok scope limits remain partial, never empty-complete.

Independent review closed atba51145. Root assembled cohort:
`pytest -ra tests/test_planning_target_catalog_api.py
 tests/test_planning_target_catalog_contracts.py
 tests/test_planning_target_catalog_projection.py
 tests/test_advertising_capabilities.py tests/test_planning_execution_boundary.py
 tests/test_planning_provider_transport_boundary.py tests/test_planning_customer_boundary.py`
with the approved disposable PostgreSQL configuration:183passed,69.67seconds, no skips.
This covers SQLite/PostgreSQL real MockHTTP inventories/ownership/session/source/expiry,
semantic-read preservation, shared budget data and default ad-write denial. All new
catalog tests are explicitly planning_boundary and cannot use retained-engine fixtures.
Raw log/JUnit:/workspace/inlet-evidence/20261008/planning-p02-integrated.{log,xml}.
Whole Ruff, prescribed mypy1001files and diff checks passed. No Full, hosted run, live
provider call, push, main merge or deployment. P01 remains separately qualified by its
207pass/1expectedskip assembled cohort; counts are not summed into distinct cases.

Next: new versioned metadata sidecar/composite digest with native display names, owned
provider-identifiable entity references and Google adgroups. Do not alter existing
inventory fields/defaults/digest domains. Canonical entity identity must be separate
from snapshot selection identity; neither is authority. Proposal is approved for
concrete interface freeze and implementation, with no UI consumer before that interface.
Comprehensive recommendation documents, priorities/scenarios/briefs, manual steps,
version/export/applied tracking and refreshed progress remain further work. No complete
planning-MVP or live/purchasable product claim follows from this catalog package.
