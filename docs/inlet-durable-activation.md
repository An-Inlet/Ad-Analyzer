# Durable Exact Activation Checkpoint

Activation is a separate customer approval over the original reviewed paused graph.
`activation_review.prepare_activation` obtains real adapter readback for every original
step, including non-activatable budget/creative/media/configuration resources, and
server-compiles all activatable targets in reverse graph order with campaign last.
It persists an immutable activation review; `approve_activation` binds both review and
plan digests. `create_run` reuses the original held exposure reservation and permits
only one original activation run for the parent graph.

`activation.ActivationRuntime` supplies concrete Google/Meta/TikTok activation adapters
and a server-owned scoped context factory. The default factory returns `None`.
`claim_step`, `execute_claim`, and `reconcile_attempt` keep one original attempt/fence
per step. Admission rechecks current owner, source approval, account generation,
production consent, entitlement/master control, qualification, ledger and portfolio.
The parent admission commit is followed by revalidation. Every emission also reads the
entire graph outside database locks and revalidates authority with a fresh clock after
that blocking work. Status readback establishes only `verified_target_state`, never
causal treatment/delivery time. Unknown/absent/old-paused readback cannot authorize a
replacement mutation. Cancellation blocks future emission; late evidence remains
append-only. External provider UI changes are not protected by a provider CAS.

The existing `coordinator.read_owned_outcome_receipt(db, workspace_id, attempt_id,
actor)` boundary now recognizes activation through scoped database joins and returns
the latest exact immutable projection. The existing projection schema is unchanged;
activation effective time remains unavailable. Historical success never overrides a
newer unknown or conflicting observation.

## Exposure Interface

The frozen activation reader is
`ActivationExposureReader(db, binding, original_creation_plan, reservation_id, now)`.
It returns `ExposureEvidence` from server-derived qualified facts. Its other held
reservation total excludes exactly the retained parent reservation; proposed owner
upper bound must equal that reservation's original amount. Current database totals
are rechecked at review, approval, run creation, claim and after blocking preflight.
A live native-cap/reporting-delay qualification source remains missing implementation;
mock contract-scenario evidence is explicitly labeled and cannot become live evidence.
Root may implement the independent source behind this port without editing coordinator
or granting new containment authority. Settlement is a following package: neither
period end nor a paused status automatically releases held exposure.

## Verification

SQLite and disposable PostgreSQL: **73 passed, 1 expected SQLite concurrency skip**
across activation review/coordinator, Google/social actual HTTP activation adapters,
and existing creation coordinator. Includes separate approval, same reservation,
complete Google graph activation, duplicate dispatch, unknown/delayed response original
fence reconciliation, cancellation after claim and in the admission commit gap,
non-activatable budget drift, expiry during provider preflight, and owned projection.
Whole repository Ruff passed; mypy passed for 384 source files. No Full suite or live
provider operation was run. Logs: `/tmp/inlet-activation-checkpoint.log`,
`/tmp/inlet-activation-ruff.log`, `/tmp/inlet-activation-mypy.log`.

Social adapters are inherited from PR145; persisted social activation journey tests
remain a dependent package. Settlement and existing-campaign optimization durable
coordination remain incomplete. The separate containment policy proposal is in
`inlet-containment-policy-decision.md`; no exception is implemented.
