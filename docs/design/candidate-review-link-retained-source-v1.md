# Candidate Review Link Retained Source

Design only from `ea295ec`. Initial consumers are exactly two current provenance
export cases and one separately explicit current migration case. No retained
execution override, production change or implementation is authorized by this
proposal alone.

## Exact Consumers And Preserved Current Work

1. `tests/test_candidate_review_bridge.py::test_provenance_export_contains_no_session_or_measurement_body[sqlite/postgres]`:
   replace only historical setup/prepare with scalar IDs. Current Session selects
   the actual CandidateReviewLink table mapping and invokes the CURRENT lifecycle
   serializer. Preserve every existing assertion: no missing fields, correct
   review ID, no original_session_digest key/value, no dict/list measurement bodies.
   Read the private session digest only from the actual current row to exercise the
   original negative assertion; do not put it in child output. Mark this function
   planning_boundary, not the mixed module retained.
2. `tests/test_candidate_review_migration.py::test_candidate_review_migration_roundtrip`:
   keep actual0068 upgrade→0062 downgrade/table absence→0068 upgrade→heads intact.
   Only then invoke the same closed producer in that existing schema. Current
   CandidateReviewLink readback, actual populated downgrade refusal and surviving
   link assertion remain unchanged. Do not move DDL into the child, substitute a
   schema stamp, or create only ORM tables for this PostgreSQL case.

The frozen W1 coverage1016 overlay lists exactly these three identities not yet
covered. Both failed in legacy preparation before their current privacy/DDL work.
The earlier review bridge historical execution cohorts stay unchanged.

## One Fixed Original Producer

New helper `tests/candidate_review_link_retained_fixture.py`; fixed driver
`tests/fixtures/retired_execution/candidate_review_link_seed_driver.py`. No mode,
provider, callback, caller PIN or policy argument. Literal2155 and its already
verified app/tests/scripts tree hashes; original Google provider only.

In the exact pinned imports the driver calls untouched
`tests.test_candidate_review_bridge.assembled(db, config, path, 'google_ads', patch)`
then original `review_bridge.prepare_candidate_review(db, principal, wid, intent,
runtime)` exactly once. `assembled` uses original durable.ready and selected
candidate processing to produce the genuine source job/result/decision. Its own
scoped ready-capture monkeypatch is part of the original fixture; no additional
capability/privacy/runtime substitution is allowed. The original bridge writes the
actual protected link and marks the actual execution review candidate-provenance
required. Commit/close before returning scalar IDs. Never call approve/create_run/
claim/execute/cancel/settlement; do not manufacture protected rows.

Require returned status review_required; measured len(actual Google MockHTTP
server.writes)==0. Require zero ProviderExecutionApproval, ProviderExecutionAttempt,
ProviderExecutionReceipt, ProviderExecutionResponse and ProviderExposureReservation
rows (and no execution run/step). Genuine existing execution mandate consent from
original ready is permitted; it is not an optimization approval or spend.

## Scalar DTO And Parent Readback

Frozen `CandidateReviewLinkIds` fields:
workspace_id (positive integer), actor_id, job_id, result_id, review_id (32-hex),
candidate_digest, input_digest, selection_digest, policy_digest, evidence_digest,
source_digest, review_digest, plan_digest (64-hex), provider_posts (exact integer0).
No session digest, source documents, raw measurement/provider bodies, old runtime,
ORM objects or callable crosses the boundary. Exact keyset and bounded JSON≤4096.

Current parent rereads owned completed CandidateJob, actual CandidateResult and
ProviderExecutionReview plus CandidateReviewLink. Verify workspace/actor/job/result
relationships, all eight retained scalar commitments, review/plan digest and
candidate_provenance_required. The row's original_session_digest must bind the
actual current stored CustomerSession owned by actor, but stays private to the
DB; no identity-provider call/current authority grant is needed for this fixture
readback. Assert current default writes disabled and the same zero effect tables
before yielding and on exit. Yield only current engine and DTO. Serializer test
uses the actual row and its unchanged assertions, never a DTO-built mapping.

## Owned Schema, Bootstrap And Lifetime

For the two ordinary customer cases use the existing empty unique customer schema;
SQLite needs a unique file-backed current ORM engine with FK enforcement, as the
existing retained-source fixtures do. Keep all current user assertions on that
yielded engine. PostgreSQL validates the disposable loopback base URL and actual
`inlet_test_<32hex>` schema. No arbitrary query keys.

For migration only, accept exactly `inlet_candidates_<32hex>` and sole query
`options=-csearch_path=<that exact actual schema>` (or ordinary empty query where
applicable). Reject additional keys/values/multiple values/options before connecting;
then bind to actual current_schema. Do not broaden existing financial/helper schema
allowlists. Require actual alembic_version heads and exact original revision set
before/after. Both parent and child validate all tables empty except real migration
bootstrap rows from the existing fixed expected_bootstrap data, then preserve full
bootstrap rows by primary key including timestamps. SQLite stays all-empty. Parent
schema snapshot before/after includes actual tables/columns/FKs/checks/indexes/
triggers/revisions. No source generation, privacy or schema adapters.

One new closed `candidate_review_link` SourceLifetime profile binds this helper,
fixed driver, literal2155, source leaf and historical-source.tar. Retain IDs/logs/
media/current.sqlite/provenance as siblings; use unchanged180s bounded child runner
and conservative post-reap cleanup. Generic runners/extractors/historical batches
stay unchanged. Child errors retain raw logs and stop semantic reinterpretation.

## Qualification And Broader Survey

Probe the SQLite current serializer first, then the actual PostgreSQL migration
case; stop on pin/schema/lineage incompatibility. Once qualified, run all three
cases alongside the existing86 default planning boundaries, Ruff/bare mypy/diff.
Prove original assertion AST and parametrization preserved, exact three frozen
failure identities, measured zero POST/effects and source cleanup evidence.

No additional current consumer is included initially. Remaining four
`test_feedback_review_composition::test_dependency_retraction_blocks_forward_preserves_protected_history`
cases require later genuine optimization approval, claim/emission and feedback
assessment dependencies; this zero-attempt review-only source is insufficient.
They need a separate closed producer/current-verifier contract. Existing bridge
retraction/qualification/race tests need original runtime callbacks or additional
execution state and are already separately partitioned; a scalar export fixture is
not a substitute. Session/initial-rule consumers likewise require additional state.
The exact same source supports the specified migration case without extending
producer semantics; future uses still require separate consumer review.
