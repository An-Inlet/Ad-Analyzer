# Provider Execution And Optimization Shared Ports

`execution_contracts.py` freezes separate `ProviderMandatePolicy`,
`ProviderMandateBinding`, `ExecutionAccount`, `ExposureEvidence` and
`NormalizedProviderReceipt`. These data models do not grant authority. Production
mandate persistence, durable claims, normalized receipt projection, activation and
settlement are next code, reserved migration0046 down0043.

Environment is explicit contract_test/live. Contract-scenario exposure cannot be
used live. The portfolio bound includes reported spend, unreported upper bound,
unchanged future exposure, proposed-owner exposure and existing reservations.
Unknown components cannot claim a bound. Aggressiveness changes a policy digest,
never its approved total cap. Source simulation lineage remains separate from
production mandate/consent/period-ledger identifiers.

The normalized receipt includes original attempt/fence/digests, explicit immutable
supersession sequence, exact scope/generation/source/goal/mandate consent lineage,
budget owner/target set and dispatch/observation times. A configured status readback
is not treatment time. Effect bounds remain null unless authoritative interval
proof exists; paused creation never supplies an effective interval.

`optimization_contracts.py` freezes `OptimizationTarget`, `BudgetOwnerRef`,
`MoneyContext`, `MetaCurrentState`, `TikTokCurrentState`, `OptimizationIntent`,
`OptimizationRequest`, `OptimizationContext`, `OptimizationResponse`,
`OptimizationReceipt`, `OptimizationValidation` and `OptimizationTransport`.

Only four action variants exist: MetaBudgetSetV1/MetaStatusSetV1 and
TikTokBudgetSetV1/TikTokStatusSetV1. Pause-only status mutations; no resume, create,
creative or arbitrary fields. Budget updates identify the real budget owner and
entire affected target set. Current states explicitly admit unavailable flags;
adapters must return unsupported when required topology/eligibility is unknown.
Provider CAS is explicitly unavailable, never invented from an SDK property.

Transport methods: read_current(scope,target,money,qualification_id,
qualification_revision,context,now), validate_only(request,context,now),
apply_once(request,context,now), read_back(request,response,context,now),
reconcile(request,original_attempt_history,context,now). All mutations are one shot.
Adapters do not compute authority or mint exposure proofs. No runtime factory is
active. Central coordinator will serialize every shared budget owner in the same
period ledger and preserve unresolved fences/reservations. Missing/old readback is
unknown, never proof that a delayed worker cannot submit.

## Durable Foundation Checkpoint

`execution_models.py` and migration0046 (down0043) define separate provider period
ledgers, execution mandates/revisions/consents, exact execution reviews/approvals,
exposure reservations, runs/steps/attempts/responses/receipts. Composite workspace
foreign keys retain lineage. One original attempt per run/step and one immutable
fence prevent clock-based replacement. A partial unique index reserves an unresolved
budget owner across periods in the same workspace/environment, not merely per child.

`execution_mandates.revise/consent/checked/suspend` implement exact customer consent
and current goal/owner/entitlement/account/native generation checks. Revisions and
additional mandates reuse the same exact period ledger; overlapping replacement
periods and environment changes are rejected. Pause/revoke preserve accounting.
These methods do not emit requests. Consent is distinct from B07 simulation records.

This checkpoint does **not** implement coordinator claims, exposure qualification,
provider execution-review preparation, activation, settlement or durable projection
queries. Those methods will use the reserved schema and must recheck current DB
state after every durable-claim commit before creating an original attempt. No route
or runtime factory is enabled, and no live-provider verification is claimed.
