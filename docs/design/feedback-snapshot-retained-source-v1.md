# Feedback Snapshot Retained Source V1

Proposal only, base `bf0d240`. No code, test run, or new closure credit.

## Exact Scope And Classification

Original failed XML identities contain these four functions, each on SQLite and
PostgreSQL (eight cases) in `tests/test_feedback_snapshot.py`:

- `test_owned_snapshot_default_empty_active_replay_retraction`;
- `test_current_session_and_original_plan_required`;
- `test_zero_signal_is_not_empty_and_policy_race_rejects`;
- `test_actual_unqualified_receipt_and_source_do_not_create_feedback`.

These are current owned-reader, feedback-policy, session and source-integrity
contracts. None is a blanket historical execution test. The first three call
`prepare`; the fourth calls the local imported `fixture` directly. Both source
paths request `test_optimization_candidates.fixture(..., with_receipt=True)`.
That fixture creates a genuine original 45,000,000-micro Google budget-setting
attempt, receipt and held reservation; the candidate no-effect source is therefore
not a substitute.

`prepare` then uses CURRENT `CommerceSyncService` to append the second publication
at NOW+one hour, resolves the current owned snapshot, applies the already explicit
synthetic effective-time fields and independent numeric facts, and persists the
current assessment with both actual publication dependencies. These operations and
all original assertions remain current and unchanged. Synthetic facts do not
establish live qualification, measured effect timing, or causality.

## Reuse After Exact Lineage Review

`tests/fixtures/retired_execution/candidate_receipt_seed_driver.py` already invokes
the unchanged literal PIN `2155ff3e3ab00cd62057dd86cb49d45359d4f49f` candidate fixture
with receipt enabled. It returns strict `CandidateReceiptIds`: workspace, actor,
original session digest, mandate/revision/consent/policy/ledger/account/store and
publication, provider/posts, original attempt/receipt. No runtime, callback,
assessment or authority object crosses the subprocess boundary. Its existing
loader `load_receipt_candidate(db, ids)` reconstructs current owned candidate
scope via `load_candidate_read_fixture`, reads the actual original receipt,
requires sequence1 and verified_target_state, and binds its current typed digest
to source/work/observation. That is the exact required existing lineage.

The existing `receipt_candidate_source` fixture cannot simply be reused: its
finalizer REQUIRES exactly one current reconciliation append and associated
run/step state changes. None of the eight snapshot cases should reconcile or
mutate provider history. Do not add a lax reconciliation-or-unchanged outcome union.

Proposed minimal private seam in `tests/candidate_receipt_fixture.py`:

```
@contextmanager
retained_receipt_source(
    customer_engine: Engine, artifacts: Path
) -> Iterator[tuple[Engine, CandidateReceiptIds, dict[str, list[dict[str, Any]]]]]
```

Extract only existing owned source creation, strict scalar/row validation and
resource cleanup into this context. The third value is its pre-consumer protected
provider snapshot, not authority. Existing `receipt_candidate_source` remains a
wrapper with its EXACT existing `reconciled(engine, ids, before)` finally check;
its consumers/expectations do not change. A new `snapshot_receipt_source` wrapper
requires exact protected-history equality in finally. There is no caller-selectable
provider, receipt mutation mode, callback policy or authority override.

Reuse the existing closed `candidate_receipt` SourceLifetime profile/helper/driver
rather than register arbitrary extraction. Harden the shared child SQLite boundary
to plain sqlite/no query/existing nonsymlink owned `output.parent/current.sqlite`
BEFORE engine creation, matching the reviewed feedback-erasure fix. Keep parent
and child disposable-loopback URL validation, no query, exact engine URL and UUID
schema, all-table initial emptiness, unchanged physical schema, 180-second child
bound and bounded 4096-byte scalar JSON. Add parent all-table emptiness if only
its provider-graph check currently runs there. No row copying, migrations, trigger
relaxation or aggregate DB usage. Shared compatibility tests must qualify this
small extraction and child-boundary tightening.

## Current Consumer Seam

New local fixture module `tests/feedback_snapshot_retained_fixture.py` exposes
`snapshot_receipt_source(customer_engine, tmp_path, configuration, monkeypatch)`.
It yields the actual source engine (the same separate file SQLite engine, or
original isolated PostgreSQL engine). It sets only the existing original per-test
commerce read setting, because child settings do not cross processes.

Its scoped replacement is ONLY `tests.test_feedback_snapshot.fixture`, the local
imported legacy setup alias. The replacement has the original `(db, config, path,
with_receipt=True)` calling shape, rejects any non-True receipt/provider extension,
checks that `db.get_bind()` is the yielded engine and config is the fixture's
configuration, then returns `load_receipt_candidate(db, ids)`. The global
`test_optimization_candidates.fixture`, all capability guards, and all current
owned authorization/source/receipt readers remain untouched. A small invocation
counter proves this seam was actually used exactly once in each selected case.
The returned current mocked server must have zero current writes.

Each of the four tests adds this explicit fixture argument and uses its engine
before the existing Session. Add the planning_boundary marker only to these four.
Do not edit `prepare`, its nested synthetic snapshot/independent facts, or any
existing assertion/parameter/decorator besides that marker. AST proof normalizes
only added source argument, engine assignment and marker; all other statements
must match the predecessor. Shared consumers outside these four are not silently
adapted by the scoped fixture.

## Protected Graph And Allowed Mutations

For the NEW snapshot wrapper, snapshot every current `Base.metadata` table whose
name starts `provider_`, plus these exact additional historical tables:
`spending_mandates`, `spending_mandate_revisions`, `mandate_actions`, `mandate_audits`,
`customer_campaign_drafts`, `customer_campaign_revisions`, `customer_media_objects`.
Record the actual sorted concrete table-name list in implementation evidence;
compare every row/column ordered by primary key, not counts alone. Check current
advertising capability false before and after. Require exactly one original
attempt/response/receipt/held reservation, all in the owned workspace, and actual
45,000,000-micro action/returned original IDs. No second receipt is allowed.
Do not broaden the existing reconciliation wrapper's allowed graph mutation.

Allowed current persistence is commerce sync/publication/history, current V3
assessment/dependency/feedback/contribution and associated privacy revisions.
The original session test temporarily corrupts then restores review.plan_digest;
its revoked session is outside provider history. Existing test Session close
rolls back outstanding transient mutations before final graph comparison. Keep
these negatives and their actual current rechecks; do not suppress or precompute
their results. A persistent provider change must fail the new finalizer.

## Deferred Directional Families

The eight `test_directional_feedback.py` failures are not homogeneous:

- Three functions (six cases) call `assembly`, which captures the original
  candidate tuple through the snapshot module's fixture alias. Current owned
  directional reads, explicit calibration/qualification facts, contribution
  retraction, retained-original checks and policy/age negatives follow. These
  likely share the new source but need their own scoped assembly interface and
  graph policy. In particular the held-head case deliberately flushes reservation
  state=settled; its transaction rollback must be distinguished from any allowed
  persisted mutation. They are NOT included in the first eight-case package.
- `test_newer_held_original_without_receipt_blocks_old_qualified_anchor` (two)
  captures the original execution runtime, then actually prepares/approves/claims
  a second 46,000,000-micro action before a CURRENT old-anchor rejection. The
  scalar first-receipt source cannot supply that runtime or original pre/post
  observation sequence. This needs a separately reviewed second-held-original
  producer/current-read split, or precise historical/current paired coverage.
  No retained marker or runtime reconstruction is authorized by this proposal.

All six `test_directional_candidate_adapter.py` cases call `prepared`→`assembly`
and also capture `candidate_fixtures.ready` to obtain the original mock server.
A retained subprocess intentionally cannot return that server/runtime. They need
an explicit current read-only Google server reconstruction, initial native state
matching the original source, and unchanged real `GoogleOptimizationTransport`
reads. Their current queue, committed retraction, original-session and stable
opportunity assertions must remain; no generic receipt-source substitution or
blanket historical classification. Defer until snapshot source qualification and
an exact server/assembly interface are reviewed.

## Bounded Qualification

After interface approval: owned SQLite URL rejection tests, one actual snapshot
positive on both databases, then exactly eight snapshot cases +86 default boundary
cases. Include existing receipt-reconciliation consumer cases (same existing
assertions) and SourceLifetime focused compatibility because its wrapper is
factored. Preserve every failure and stop on semantic incompatibility. Whole
Ruff, bare mypy, diff, exact original XML intersection and AST preservation proofs
before freeze. No new Full/aggregate, hosted/provider call, approval bypass or
public capability claim. Later directional packages require separate approval.
