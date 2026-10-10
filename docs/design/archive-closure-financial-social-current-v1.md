# Archive And Closure Financial/Social Two-Case Split

Proposal only, based on `d878264936c8aad5af96f191617412692aecc307`.
No implementation, test execution, producer execution or default capability change.
The planning MVP prohibits advertising writes, including advancing a retained run.
Historical successful forwarding is preserved separately from current privacy acceptance.

## Exact Original And Coverage

The only original function is
`tests/test_archive_closure_financial_social.py::test_owned_archive_then_closure_retains_replacement_and_social_evidence`,
with its existing SQLite and PostgreSQL parametrization (two original identities).
At the current baseline its entire file is byte-identical to PIN
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`:

- File SHA256: `15049bf103f6f9178c41622cad79c2c3d2ef75ef574191daa07c801eec2ed4b3`.
- Function AST SHA256: `36ba3f74cb7f08b5e9db750ee83d270b73d9b1ef5cbb8fed53911779a8f60199`.
- First two function-body nodes AST SHA256:
  `f58209c8b6a20b1fffbe0fa202feec8fe466e0889f5475426aadc893e7e07cf2`.
  This is `store = LocalMediaStore(tmp_path)` and the complete initial
  `with Session(export_engine)` block, ending at line266 in that exact file.

Archive and run the unchanged original function as a new exact historical2 batch
through the existing retired regression mechanism. Its Alice denial and Bob advance200/
second provider effect remain historical assertions; neither becomes current authority.
Do not rerun previous batches or count these two original identities as both direct
and historical/current. The current counterpart below supplies current privacy evidence.

## Closed Source Boundary

Add a dedicated `archive_financial_social` SourceLifetime profile, helper
`tests/archive_financial_social_retained_fixture.py` and fixed seed driver under
`tests/fixtures/retired_execution/`. It has one producer phase and no caller-selectable
provider, callback, operation, mutation phase, code string or table exemption.

The child imports the exact pinned original module and executes only the two
AST-verified body nodes above using that module's original globals and helpers.
Verify the full original file/function/prefix hashes before compiling the prefix;
reject source drift, missing source or altered imports. Do not recreate its financial
records by hand or copy an arbitrary caller-provided setup. The boundary is before
`monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)`, app construction,
login, exports, closure and either advance request. No child HTTP/privacy operation.

The prefix legitimately creates two owned brands, actual predecessor optimization
attempts with verified receipts, exact approved repeat reviews and funded reservation
transfers, then the Meta brand's genuine approved source and no-DSA social confirmation.
Both successor runs are reserved and unclaimed. Its original `successor_claim = None`
is a source assertion, not permission to manufacture an unknown attempt.

The original prefix's identity/domain/slug assignments are unchanged historical
fixture provenance. No NEW assignment is allowed in the producer or current consumer
to force identity, ownership, source binding or login. Preserve those actor rows exactly.
The child exits and is reaped before current code reads or makes any request. No live
provider endpoints or child runtime, transport, server, callable, Session or Engine
crosses the boundary. Historical fake-provider effects are explicitly source-only.

## Current Physical Schema And Closed Output

Use a fresh exclusively owned current-schema target. SQLite is a regular, non-symlink
file in the exact artifact directory, FK checks enabled and the current metadata/DDL
installed by the parent. All later sessions and API dependency overrides use that
same engine, not an unrelated empty `export_engine`. PostgreSQL uses the existing
explicit disposable loopback database and independently generated owned schema;
validate database URL and exact current_schema before child access. Reject populated
nonbootstrap targets, foreign schemas, arbitrary URLs, paths, symlinks and stale files.

The child must not create/drop tables, run migrations, alter constraints/triggers,
downgrade a target or enable current advertising capability. Snapshot actual columns,
keys, constraints, indexes, triggers and migration versions before and after. Only
historical row production uses the pinned interpreter; parent reads current models.
Preserve exact approved bootstrap rows and require every other initial table empty.

The exact field names/types/nullability in the
[additive contract](archive-closure-financial-social-exact-contract-v1.md) supersede this
summary. A bounded strict JSON envelope returns only a version, exact pin/prefix digest and
ordered `brand_a`/`brand_b` scalar records: provider, positive workspace/account/
integration integers; actor/native connection, goal, simulation mandate, provider
mandate/consent/ledger, original review/run/attempt/response/receipt, predecessor hold,
repeat review/successor run/successor hold/replacement IDs; expected digest fields;
Meta source draft/revision/media/social review/approval references. Nullable fields
are permitted only for Google-inapplicable social fields. Require exact field sets,
actual integer types (reject bool), literal provider order, bounded IDs/digests, no
unknown keys/coercion/duplicates, and no runtime, bearer material, identity rewrite
instructions or DB URL. Reject malformed output before connecting through returned IDs.
A bounded producer-only effect count must equal one original fake mutation per brand;
it is not a current runtime or assertion about future provider behavior.

## Independent Current Source Validation

Parent reloads every referenced record and verifies the full database graph, not only
child-declared IDs. Capture all registered table rows in stable primary-key order;
no table-wide exemptions. Verify distinct actual owners/workspaces, memberships,
scoped integrations/native accounts/generations and original goal/mandate relationships.

For each brand require exactly one original acknowledged/verified attempt and its exact
response/receipt chain; parse the saved request/response, `OptimizationReceipt`,
normalized owned receipt and original/repeat review using their current strict types.
Recompute canonical digests, resource/account ownership, fences, original request links,
review/plan/intent links and receipt outcome. Do not accept raw JSON or a digest string
without validating its typed document and associated rows. Exact provider/context IDs
are graph evidence, never customer-entered replacements.

Parse `ReplacementAuditDocument` and `RepeatOptimizationReview`; verify predecessor
superseded, successor held40m (the reviewed setting is44m), exact transfer audit, original run canceled as recorded,
successor reserved with no attempt/response/receipt, same ledger and covered ownership.
Require both brands' complete hold sets, spent high-water/action counts and charges to
match authentic source expectations and their complete graph. Do not infer release,
terminality or zero exposure merely from the status; preserve all source financial facts.

For Meta independently load the campaign artifact/approval and private supplied image,
validate actual file hash/size/owned media binding, parse the exact current
`SocialConfigurationDocument`, recompute configuration/approval digests and require its
original strict no-DSA profile/wording/answer. Exactly the prefix's review+confirmation
exists; Google has no substituted social document. Schema is unchanged; the exact contract requires an initially empty target, with no
migration bootstrap row exemption.

## Current Customer Privacy And Authentication

Current code uses normal customer session issuance and the retained persisted issuer,
subject and email, with per-provider fake identity configured from independently checked
source expectations. Alice/Bob IDs must equal their original actors. No row rewrite,
TTL extension, current clock patch, role bypass or source runtime dependency override.
Capture bounded real issuance intervals; validate exact two owned session/token-receipt
deltas, real CSRF values and unchanged identity/membership rows. Keep cookies/tokens out
of output evidence. Current export uses actual private media and ordinary current clock.

Run the original HTTP archive/privacy sequence in current code and retain its assertions:

1. Actual Alice export creation200 and actual download200; manifest
   `supported_customer_data_complete` true; every section accounted for.
2. Bob cannot download Alice's archive. Every exported workspace-scoped record belongs
   to Alice; replacement/social review/approval sections contain their exact one row,
   exact documents/digests, Alice social ID, and no Bob successor identifier.
3. Actual closure preview and exact inventory confirmation200; state blocked and
   `closed=false`. Both sessions remain usable. Bob cannot read Alice's closure;
   Alice's owned status remains blocked. Do not simplify this to merely a planning409.
4. Both Alice and Bob advance requests return exactly409 with
   `advertising_writes_disabled_in_planning_mvp`. No injected optimization runtime is
   required or supplied. Use a fail-if-resolved dependency sentinel only if needed to
   prove the early route boundary; never provide the historical runtime.
5. Retain every original post-closure hold-state/amount, replacement ID/document,
   social review document/confirmation digest, protected receipt ID and ledger
   high-water/action-count assertion. Extend protected checks to both brands.

Before and after each advance compare the entire current database graph and schema:
no new attempts, responses, receipts, charges, holds, approvals, workers or outboxes;
no changes to either brand. The source fake server cannot measure this phase because
it no longer exists; do not equate its historical count to a current emission spy.
Default capability remains false; transport/default-boundary tests remain separate.

## Full-Graph Privacy Delta, Not A Broad Exception

Bracket actual login/export/closure stages with exact snapshots. A dedicated fixed
validator derives permissible changes from the independently validated source and
known request inputs, not by blessing whatever the service returned. Validate generated
IDs/fences, current timestamps within request intervals, revision progression, exact
scope and cross-links. Compare every other field/table exactly, including Bob's graph.

Export may append only its exact lifecycle request/step/evidence/privacy-fence changes
and must bind the built manifest and successful owned stream; no secret or foreign data.
Closure may apply Alice's actual `quiescing.py` field transitions: workspace closing,
owned integration revocation, connection credential clearing/generation retirement,
mandate pause/revocation, run cancellation and exact blocked lifecycle records. Handle
only rows actually present in this closed graph; assert absent work families stay empty.
The additive [exact contract](archive-closure-financial-social-exact-contract-v1.md)
freezes field types, empty-target requirements and every permitted privacy transition,
including privacy revision increments and the zero-row queue cancellation receipt. No wildcard allowed-table list,
wholesale snapshot acceptance, unrestricted callback, silent extra rows or source edits.
Protected financial/social/media/receipt documents remain exact through these changes.

## Compatibility And Qualification Plan

Reusable unchanged primitives: `retired_snapshot.extract/run_bounded`, exact original
batch harness, `SourceLifetime`, physical `schema_snapshot`, fresh/bootstrap checks,
owned URL/path validation, and current archive unpacker. Their scope/ownership checks
must remain active. Current SQLite fixture adaptation is local to this file.

Existing social producer stops before publication/replacement and has a different
source/identity graph. Google-created is single-provider creation; directional-held
adds a successor claim and is staged; optimization-source intentionally has no holds
or receipts; financial-origin has no two-brand replacement/social graph. None is
compatible wholesale. Do not add archive modes to those helpers or accept child
runtimes. Two-brand activation pilot needs its own proposal, not a mode here.

After review only: parser/source lifetime/foreign-path/dirty-schema/wrong-pin guards;
actual current SQLite+PostgreSQL consumer2 with full assertions; exact unchanged
historical2 separately; directly affected default write-boundary checks; narrow AST/
coverage registry verification and static checks. Run no prior batches or aggregate.
Preserve source IDs, logs, DB/media and numbered XML evidence; reuse approved lifetime
cleanup only for verified duplicate extracts. Require at least500MiB free before heavy
checks; no cache/evidence deletion or copying large source trees merely for this design.

Remaining review gate is this test-source/consumer contract, not a product decision.
No current forward-execution promise, provider qualification, live operation, hosted
run, push, merge, deployment or new automatic execution work is proposed.

## Approved Access-Order Refinement (2026-10-10)

The first current SQLite privacy gate passed source typing, both real logins, the
complete archive and exact closure graph, then established Alice's post-closure
advance returns404. `app/api/planning_boundary.py::deny_advertising_mutation` calls
`bind_authority` before the planning write guard. Thus the precise revised contract
is both ACTIVE brands409 before closure, then closing Alice404 (`workspace not found`)
and still-active Bob409 afterward. Every advance has a full zero-delta snapshot.
This supersedes earlier wording requiring both post-closure responses409; no production
authority or guard is changed. Parent approved the refinement before continuing.
Original failure XML and exact source DB/media/DTO/lifetime/producer log are preserved
in `/workspace/inlet-evidence/archive-current-contract-01/`.
