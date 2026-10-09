# Current Candidate Receipt Append: Two-Case Proposal

Remaining test_optimization_candidates::test_receipt_append_erases_derived_only
bothDB cases. This is current receipt reconciliation/invalidation, not advertising
execution. New fixed Google-with-receipt child; no change to approved single-owner
no-receipt or dual-owner helpers, global fixture, or current advertising guards.

Exact PIN2155 original fixture(db, config, path, with_receipt=True) produces one
real mocked45m budget action and its original verified receipt. It returns existing
13CandidateReadIds scalars (provider_posts measured1 here), plus actual attempt_id
and receipt_id. ClosedproviderGoogle only, no arbitrary mode/callback. Same reviewed
source tree/PIN, freshalltable guard, currentSQLite/validatedloopbackUUIDPostgres,
180s/16MiB process bound,4096B strict field/types output. Child creates no candidate
job; no runtime/policy/proof body crosses. Table names unchanged, parent ownsDDL.

Parent reloads scope/runtime via existing load_candidate_read_fixture (not its
zero-effect contextmanager), then uses actual current owned outcome receipt to
rebuild original SourceFence fields:attempt_id,receipt_id,sequence,receipt_digest,
projection_digest=original currentdigest domain. Original fixture captures50m
read state before its45m action, so preserve exactly that controlled observation;
do not call it live measurement. Assert actual request action45m, single attempt,
single originalresponse/receipt, heldreservation and measured childPOST1. Current
MockHTTP server is newly constructed and must retain0writes.

Retain original current enqueue/process candidate suggestion, evidence_lock,
unknown(request,NOW+1second), record_receipt, and post-invalidation assertions.
Add independent before/final protected effect graph validation:
- All original provider rows unchanged except known run/step state transitions.
- Exactly one newly appended receipt, sameattempt/workspace, sequence2,
  supersedes originalID, exact unknown receipt digest/projection validated by
  current read_owned_outcome_receipt; original receipt unchanged.
- Only known run.state and its step.state transition verified_target_state→unknown;
  every other column/row remains identical. No newrun/step/attempt/response/review,
  mandate/reservation/ledger/charge or other financial row.
- Current guardfalse and currentserverwrites0; allow intended candidatejobs/results
  erasure through actual record_receipt. No global broad delta exception.

New helper fixture carries engine/IDs and snapshot; local current loader builds
work only. Test node names/params and every existing statement after setup remain.
Use deferred imports to avoid shared fixture cycles. Probe original2bothDB plus
unchanged86planning boundary cases, wholeRuff/mypy/diff, independentreview.
No credit for feedback snapshot/storage/directional families without separate
classification. This narrowly reviewed delta may inform their later interfaces.
