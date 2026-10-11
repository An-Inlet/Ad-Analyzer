# Shared Selected Reporting Reader — 2026-10-11

Base `1a2b7b05e9955085d01e5ec2b4a5381e5418737d` implements the approved
[collection-only interface](design/shared-selected-reporting-reader-interface-v1.md).

Only three production consumers change: selected_plan_bundle, selected_plan_local,
and selected_plan_adapter. They use the shared canonical selected policy validator,
validate the matching creative-input contract and require explicit selected selectors.
The adapter validates its supplied composition policy against the actual ticket
before original-session authority or native I/O. Local failures remain conflicts;
pure bundle failures remain ValueError. No provider/clock errors enter these new
pure-validation handlers.

Genuine v5 collection retains its actual policy digest, creative input, input digest
and context documents. It does not manufacture v4 tickets or strip creative input.
Selected/traffic observation proofs retain existing semantics. Explicit empty
selectors remain a deliberate no-capture request; explicit empty creative input
is a valid collection context, not image inspection or creative readiness.

Composer, PlanVersion, capability registry, retained witnesses/history, service
routing and default v3 remain unchanged. V5 composition, documents and registration
remain unavailable. This collector is not the complete v5 evidence/runtime.

## Evidence And Test Corrections

Evidence directory: `/workspace/inlet-evidence/20261011/shared-selected-reader/`.
Initial SQLite comparison incorrectly assumed separately acquired native catalogs
share an expiry. A second comparison also assumed the catalog-bound target
selection_key remains unchanged; the completed cohort showed only that expected
fresh composite binding differs. That assertion failed; its log/XML remain preserved. Comparison
must retain immutable reporting proof/content while respecting fresh native catalog
metadata. No stored snapshot or product contract was relaxed.

The existing pure cohort exposed a stale test asserting v4 was unregistered.
Exact base policy_capabilities.py already registers v4 as selected_requested_window
with local_reporting_v3. Root explicitly authorized correcting only that assertion
to the actual v4 state and continued v5 rejection. The original failed cohort is
preserved in pure-legacy.xml/log; all other cases passed.

Qualification results:

- Both-database collector cohort:54passed/2comparison-fixture failures, zero skips,
  248.119seconds (`both-db.xml`); both failures described above and retained.
- Corrected complete new shared-reader module:10passed, zero skips
  (`shared-final.xml`), including genuine v5 paired collection on both databases,
  explicit empty selectors, preserved context/proof and continued generation denial.
- Existing pure bundle/composer/contract cohort:81passed/1stale registration assertion;
  authorized corrected registration case passed (`registration-repair.xml`).
- Unchanged v4 child-location byte/digest regressions:12passed, zero skips,
  3.068seconds (`v4-golden.xml`). No golden snapshots changed.
- Whole Ruff and configured no-path mypy passed (1,382 source files), diff check clean.

All existing adapter/paired-reader cases passed. The only production changes are
canonical collection guards; neither test comparison repair changed production.

No external calls, PostgreSQL reset, aggregate/Full run, remote push, hosted checks,
merge, deployment or runtime activation.
