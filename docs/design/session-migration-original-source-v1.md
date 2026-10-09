# Session Migration Original Source

Proposed bounded repair for the single frozen failure
`test_session_automation_migration::test_0072_empty_roundtrip_and_populated_refusal`.
The test remains current migration coverage; do not mark it retained execution.

Preserve actual PostgreSQL 0072 upgrade, 0068 downgrade and table-absence assertion,
then current heads upgrade. Replace only the original `automatic_fixture` and
`service.start` setup with a closed original producer. The current populated
downgrade must still raise `cannot be discarded`, and the actual original run must
survive. No migration runs in the producer; no schema stamp or DDL adapter.

One fixed driver invokes exact PIN2155 `test_session_automation.automatic_fixture`
for Google and original `session_automation.service.start` once. It never invokes
the worker, approval, admission, claim or executor. Original setup creates its
candidate to derive policy and deletes it before Start, as the original fixture
does. Check actual MockHTTP writes remain zero and no candidate jobs/results,
automatic admissions, provider reviews/approvals/runs/steps/attempts/receipts/
responses/reservations remain. Existing original mandate consent is source history,
not newly granted current authority.

Output exact bounded scalar DTO: workspace_id (positive integer), actor_id,
run_id, mandate_id, consent_id, ledger_id, policy_id (32hex), mandate_revision,
policy_revision (positive integers), mandate_digest, policy_digest (64hex), and
provider_posts (exact integer zero). Never output the original session digest,
policy body, runtime, ORM objects or callbacks. Parent reads the actual current
SessionAutomationRun and compares every field; resolves its actual stored session
and actor ownership privately, and checks mandate/consent/ledger ownership. Current
reads are structural history verification, not a claim that the old run/session is
currently eligible for automation. Current advertising capability remains disabled.

Parent and child accept only the explicit disposable loopback PostgreSQL URL,
with parent sole options query exactly `-csearch_path=inlet_auto_<32hex>` matching
actual current_schema. Reject arbitrary options and mismatched schemas before
source extraction. No SQLite support or generic schema allowlist extension.
Require current Alembic heads, preserve full schema snapshot before/after source
(tables/columns/FKs/checks/indexes/triggers/revisions). Require empty tables except
the exact known migration bootstrap; snapshot and preserve original bootstrap rows
including timestamps. Reuse existing financial fixture pure snapshot/fresh/unchanged
helpers where appropriate without modifying their target allowlists. Child reads
only fixed bootstrap constants from the executor driver root.

One new closed SourceLifetime profile `session_migration` owns the fixed driver,
helper, PIN2155 source and archive. Keep output/log/provenance siblings, bound child
to180s, and clean only confirmed reaped immutable extraction. No generic harness or
historical manifest changes. Parent compares zero-effect tables again after current
migration refusal. No current start call or write guard bypass is permitted.

Qualification: original assertion AST preserved; actual single PostgreSQL migration
case plus86 existing planning boundaries, exact frozen XML identity, source cleanup
evidence, whole Ruff/mypy/diff. Preserve failed attempts. Independently review this
interface before implementation.
