# Joint Native Spending Envelope — Contract Proposal

2026-10-06. Approved for durable documentation only; runtime implementation and policy choices remain unapproved. No model/runtime/migration change or qualified profile is introduced. This complements the separately reviewed repeat-optimization design; it does not replace that design's original-request closure or atomic successor-hold requirements, summarized below. Current [Google native diagnostics](../inlet-google-native-inventory.md) ([PR167](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/167), `16fd3b907177b0446ffda63a694ff6fb753baa2e`) cannot construct any authoritative type below.

Related: [native exposure assessment](google-native-exposure-qualification.md) and [current exposure composer](../inlet-exposure-qualification.md).

## Problem And Invariant

The present component proof adds `R + H + U + F + P`. A genuine whole-account native cap instead bounds a joint set of costs: already reported, unreported, unchanged future and proposed-owner future. Putting that joint residual into `U` while setting `F=0` is false component evidence. Subtracting reported spend from a cap also assumes compatible, non-reversing accounting; ordinary Google cost metrics and later adjustments do not establish that.

Introduce a separate discriminated proof mode only after review: `qualified_joint_native_envelope.v1`. Its upper amount covers the **whole** defined obligation set over an enforced window, without subtracting observed spend. Independent component mode retains its existing schema, hashes and semantics. Neither is accepted merely because it deserializes. Server-qualified source/profile registration is mandatory and absent by default.

## Proposed Typed Source Documents

Notation describes strict typed schemas; it is not executable code. All amounts are bounded nonnegative integer micros, currency is exact ISO code, IDs/digests use existing bounded types, account sets and lists are bounded/deterministically ordered, and unknown discriminators reject.

```text
AccountingBasisV1 {
  kind: gross_served_media | net_billed_media | all_in_cash
  currency: Currency
  provider_metric_mapping_version: RegisteredMappingId
  adjustment_policy_digest: Digest
  tax_fee_policy_digest: Digest
  period_attribution_rule_digest: Digest
}

WriterBoundaryEvidenceV1 {
  evidence_id: Id
  immutable_evidence_digest: Digest
  qualification_profile_id: RegisteredProfileId
  profile_version: int
  mechanism: provider_enforced_cap_lock | qualified_exclusive_writer_fence
  covered_accounts: ExactExecutionAccountSet
  covered_native_cap_resources: NonemptyResourceSet
  effective_from: AwareDatetime
  effective_until: AwareDatetime
  native_fence_or_enforcement_reference: ServerEvidenceReference
  permitted_mutations_digest: Digest
  invalidation_contract_digest: Digest
  independently_verified_at: AwareDatetime
}

NativeCostDomainV1 {
  domain_id: Digest
  exact_accounts: ExactExecutionAccountSet
  accounting_basis: AccountingBasisV1
  enforced_window_start: AwareDatetime
  enforced_window_end: AwareDatetime
  native_time_zone: IanaZone
  cost_membership_rule_digest: Digest
  includes_already_reported: true
  includes_unreported: true
  includes_existing_and_new_campaigns: true
  includes_current_configuration_continuing: true
  includes_requested_operation_delayed_or_never_applied: true
  includes_overdelivery_adjustments_on_declared_basis: true
}

JointNativeEnvelopeV1 {
  kind: qualified_joint_native_envelope.v1
  evidence_id: Id
  environment: Environment
  workspace_id: int
  ledger_id: Id
  mandate_binding: ProviderMandateBinding
  plan_or_intent_digest: Digest
  before_state_digest: Digest
  proposed_operation_digest: Digest
  target_set_digest: Digest
  native_budget_owner_key: ExactNativeOwnerKey
  domain: NativeCostDomainV1
  total_upper_micros: Amount
  native_cap_resource_versions_digest: Digest
  approved_adjusted_pending_future_coverage_digest: Digest
  writer_boundary: WriterBoundaryEvidenceV1
  qualification_profile_id: RegisteredProfileId
  profile_version: int
  provider_evidence_digest: Digest
  observation_started_at: AwareDatetime
  observed_at: AwareDatetime
  expires_at: AwareDatetime
}
```

`immutable_evidence_digest` makes the evidence record tamper-evident; it does **not** make provider configuration immutable. The registered mechanism must actually establish the advertised preventive property throughout the future exposure window, including cap replacement, new cap creation, billing-setup changes, scheduled changes, automated recommendations and all relevant human/API writers. Its validity cannot merely equal a five-minute polling interval when costs continue afterward. Invalidation detection after a cap increase does not retroactively preserve a hard ceiling. A customer's promise, an operator checkbox, a dedicated account, a current access list or a signed snapshot alone is not this mechanism. **No Google mechanism currently reviewed here satisfies this port. Typed fields alone cannot close the strict-cap acceptance gap.** The discriminator names possible proof categories, not claims of available Google features.

The enforced window must cover all cost attributed to the mandate interval on the chosen basis. If native budgets span a larger interval, charge the full covering upper bound conservatively; do not prorate. Multiple sequential budgets must include every overlapping effective/replacement interval and pending transition, with a proof that no gap or uncapped alternative exists. A resource's currently proposed limit does not establish an enforced upper amount. Currency conversion is outside this first contract.

## High-Water And Reservation Composition

```text
CompatibleHighWaterV1 {
  ledger_id: Id
  accounting_basis_digest: Digest
  period_rule_digest: Digest
  monotone_amount_micros: Amount
  source_evidence_digest: Digest
  revision: int
}

HoldContainmentV1 {
  reservation_id: Id
  immutable_reservation_digest: Digest
  exact_run_attempt_lineage_digest: Digest
  envelope_evidence_id: Id
  native_owner_key: ExactNativeOwnerKey
  obligation_membership_proof_digest: Digest
  includes_unknown_and_delayed_effects: true
}

JointPortfolioProofV1 {
  kind: joint_portfolio.v1
  exact_current_ledger_snapshot_digest: Digest
  accounting_basis: AccountingBasisV1
  mandate_binding: ProviderMandateBinding
  plan_or_intent_digest: Digest
  high_water: CompatibleHighWaterV1
  envelopes: BoundedList[JointNativeEnvelopeV1]
  uncovered_component_domains: BoundedList[ExistingQualifiedComponentDomain]
  held_inventory_digest: Digest
  contained_holds: BoundedList[HoldContainmentV1]
  independently_counted_hold_ids: BoundedIdSet
  portfolio_upper_micros: Amount
}
```

Rules under current workspace-first/ledger/native-owner locking:

1. Re-read exact current accounting account set, policy, generation, currency, ledger high-water and **every held workspace/environment reservation across periods**. Compare the full snapshot after external source IO using fresh session/role/authority and clock. No caller-supplied proof or source-controlled lock release.
2. Every relevant obligation belongs to an explicitly covered domain or remains independently counted. Domain overlap may conservatively double count; it must never omit exposure. A source must not combine a component proof that already embeds holds with another hold sum. First implementation should reject mixed component/joint domains unless their cost/hold coverage manifests are unambiguous.
3. A held reservation is counted exactly once: either its full amount independently, or within a joint envelope backed by **specific containment proof**. Same account/owner identity alone is insufficient. Unknown old effects are contained only if the envelope demonstrably bounds them on the same period/basis and cannot be escaped by delayed execution. If that proof is absent, retain the full hold in addition to the cap; conservative overcount is allowed.
4. Containment changes portfolio arithmetic only. It does **not** mark a reservation settled/released/superseded, cancel an old attempt, permit another same-owner operation, refund cumulative positive changes, or skip per-plan/action/cooldown limits. Cross-period holds remain independent unless an explicit proof includes their full outstanding obligations; no roll-forward by timestamp.
5. Compute `portfolio_upper = sum(envelope.total_upper) + sum(uncovered complete-domain uppers) + sum(independently counted holds)`. Do not subtract `R`, credits, high-water, held amounts or a previous cap from a native envelope. Do not add the same plan's future again if exact domain containment already covers it; if membership is unproved, reject or count it independently with its own qualified bound.
6. Validate compatible high-water against the claimed covered upper amounts and reject contradictory evidence. Never silently convert basis or lower high-water. A legacy ledger whose basis is unspecified cannot enter this mode. Changing basis requires a separately reviewed migration/closure procedure; existing historical exposure cannot disappear.
7. Require resulting upper <= the existing total mandate and all independent policy limits. A finite account cap larger than the mandate does not become safe by reserving only its unused part. Missing/expired writer enforcement, unbounded adjustments, unknown coverage, contradictory cost, or stale lineage leaves the source unqualified.

Example: a proved immutable billed-media envelope of 100 covering all of an account's mandate costs already contains its observed 40, delayed costs and future costs. It contributes 100, not `100 - 40`. A held amount of 20 for another account contributes another 20. A hold of 30 in the capped account is not automatically subtracted: either it has specific full containment proof and remains held but counted within the 100, or it adds 30 conservatively. This example assumes a real compatible profile and writer mechanism; today's Google collector cannot assert either.

## Sequential Rebudget Compatibility

The joint portfolio proof is a possible future authoritative input to the scheduler's replacement protocol, not an alternative to it. The protocol must still close every predecessor original request against later effects, bind the exact predecessor/receipt snapshot, and transfer to one successor hold atomically with inherited-exposure lineage. The successor transition domain must include the old/current configuration continuing if the new mutation is delayed or never applied, plus every possible permitted effect of the successor. A joint cap does not establish old-request finality or idempotent retry.

A canceled successor with no local attempt still inherits live campaign obligations. No local zero-attempt settlement shortcut may erase them. Cancellation, session revocation, mismatch or source contradiction retains the hold chain and blocks further replacement; none is a native pause. Supersession and terminal settlement remain separate states. No `max(old_budget, new_budget)`, ratio-based residual, reporting-SLO reserve or optimistic timeout rule is introduced.

## Source/Coordinator Port

```text
JointEnvelopeSource.read(
  exact_authorized_snapshot: FrozenAccountingSnapshot,
  exact_proposed_plan: FrozenSupportedPlan,
  now: AwareDatetime
) -> UnqualifiedDiagnostics | JointPortfolioProofV1
```

The source runs outside DB locks with an explicitly bound credential context; it can read provider evidence, never mutate providers/ledger/authority. The coordinator rechecks the exact snapshot after IO and derives the arithmetic itself. It never trusts `portfolio_upper_micros` without recomputation. Profiles are server-registered with versioned native semantics, allowed accounting basis, writer mechanism, freshness and domain membership rules. Contract-test profiles cannot become live profiles through a setting. Current default is no live joint source.

## Owner Decisions And Required Evidence

Owner decision one: define the monetary promise—net billed media, gross served media or all-in cash. Recommend preserving the current strict ceiling while explicitly deciding the basis for future qualification. Do not retrofit existing ledgers to a new basis silently.

Owner decision two: if a genuinely enforceable writer boundary requires narrower supported customer account configurations, decide whether that restricted launch profile is acceptable. First establish the actual provider mechanism and operational evidence; no customer agreement can manufacture an unavailable hard-control mechanism. A best-effort/external-change disclaimer would change the product guarantee and is not this proposal.

Provider facts underpinning the gap are recorded in the [native exposure assessment](google-native-exposure-qualification.md): [billed versus served limits](https://support.google.com/google-ads/answer/10486637), [non-deterministic reporting freshness](https://support.google.com/google-ads/answer/2544985?hl=en), [mutable/adjusted/pending account budgets](https://developers.google.com/google-ads/api/docs/billing/account-budgets), and [Search campaign total-budget support](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview). No new provider capability is asserted here.

Before implementation: root/scheduler review the domain and hold-containment definitions; freeze typed ports; supply a qualified source specification with actual enforcement evidence or keep the result unqualified. Required adversarial tests include raised/replaced caps, future budgets, delayed/unknown effects, cap versus cost basis mismatch, credits/reversals, partial-day intervals, other-account and prior-period holds, stale generation, inconsistent containment, and concurrent snapshot changes. Current work is documentation only; no runtime tests or live verification are claimed for this proposal.
