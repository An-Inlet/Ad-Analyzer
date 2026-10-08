# Customer Planning HTTP Integration

The registered customer router exposes the frozen planning service intents and owned
reads at `/api/customer/v1/workspaces/{workspace_id}/planning/plans`. Owner mutations
use existing CSRF protection; retained reads allow current read roles. Request bodies
accept customer intent only. The route factory detaches already-loaded principal rows
before rolling back its authentication read transaction, preventing lazy identity SQL
during service provider checks. The global authentication dependency itself is unchanged.

Create/edit/generate, separate decisions/manual reports, explicit request-result lookup,
list/version/event pagination and JSON version-artifact export call the actual service.
Comparison reads two authorized consecutive saved versions and derives an exact pure
diff. All successful responses are no-store; the existing production customer middleware
also covers errors. Artifact export is explicitly not a complete event-history archive.
No advertising execution runtime is selected. Target-bearing inputs remain explicit409
pending catalog receipts, and descriptive recommendations are not expert-qualified.

Executed checks (actual router/service/storage and configured MockHTTP native sources,
no fake planning service):

- Initial **8 passed in25.910s**, SQLite/PostgreSQL. Three-platform create→generate→read,
  immutable same-key replay without another native call, decision/manual report/history,
  artifact export, edit/new version/comparison/no decision carryover, foreign workspace
  denial through a second registered replica, CSRF/forged body/path bounds, zero execution
  rows. Two actual service-factory cases prove detached unexpired principal and released
  authentication transaction during provider refresh.
- Follow-up **2 passed**, SQLite/PostgreSQL: semantic invalid input422 with empty listing,
  current viewer reads/export with no native calls, viewer mutation403.
- Whole Ruff and mypy **1053 files** passed; diff check passed.

Evidence `/workspace/inlet-evidence/20261008/planning-documents-api-initial.{log,xml}`
and `planning-documents-api-errors.{log,xml}`. Core9682753 independent review is closed;
router review and root integration are separate gates. No live provider or customer
browser/controller journey is claimed. No Full suite, hosted run, remote push or deploy.
