# V2 Exact Review: Pure Contract Freeze

Isolated from7d2c42c. No route, runtime registration, persistence or migration.
Existing preview and v1 review schemas/bytes remain unchanged.

## Callable Contracts

`initial_planning.review_v2_contracts` defines frozen, extra-forbidden:

- `InitialPreviewExecutionIntentV1(expected_preview_digest, mandate_id, mandate_revision)`.
  No client amount, native ID, qualification or proof accepted.
- `InitialPreviewExecutionPreparedV1`: preview/review/plan digests and exact frozen
  execution mandate binding; fixed review_required and spending_authority=none.
- `InitialPreviewExecutionProofV1`: workspace/preview/review identity, hashes of
  preview/profile/intent/native observation/semantic match/qualified state/qualification/
  plan, separately consented planning and execution bindings, created/expiry instants.
  Bindings require different mandate and consent IDs, same ledger and environment.
  No report, metric, native response or original-session secret is copied.
- `NativeReviewMatchV1`: original observation digest, qualified state digest, common
  semantic digest; its own digest commits all three. No authority is granted.

`review_v2_projection.native_review_match(observation: NativeBudgetObservationV1,
current: MetaCurrentState) -> NativeReviewMatchV1` revalidates typed inputs, then
requires supported campaign-owned DAILY USD/2 state and exact common semantics.
Mismatches raise fixed ValueError codes; future owned API boundary must sanitize them.
It does not validate runtime eligibility, observation freshness or financial proof.

## Actual Field Mapping And Limits

Exact common fields: scope/generation, campaign target, owner/mode/complete affected
set/topology digest, currency/exponent/timezone, amount, account/configured/effective
status, start/end bounds, sharing/scheduling/rebalance flags, unchanged-settings digest.
Affected sets are canonically sorted; acquisition timestamps remain separate evidence
and do not create false configuration drift. Full original observation digest remains.

Both readers use `meta.budget_snapshot.parse_meta_budget`. Its
`inlet.meta-optimization-settings.v1` digest includes objective and buying_type in
campaign/target mappings. Native observation lacks explicit objective/buying_type;
matching that digest plus requiring qualified OUTCOME_SALES/AUCTION and no unsupported
native reasons validates the existing supported codec profile, not a guessed field.
The digest deliberately excludes configured/effective statuses. Campaign-only parsing
passes the same campaign as row and parent; native configured_status is compared
explicitly and qualified parent_configured_status must equal configured_status.
No adset parent-status inference is supported by this slice.

Native observations have no financial period, qualification identity, independent
execution consent or ledger. These cannot be inferred by the matcher. The future owned
bridge must revalidate both policy documents, exact period/currency/account set/total,
non-enlarged per-plan/positive-change caps, goal/source/profile/session, provenance
origins0079/0080 and current financial readers under their existing fences. The proof
schema checks binding consistency only; possession or successful parsing is not proof
of database ownership or economic eligibility. Expiry minima and retained-original
reconciliation remain future service responsibilities. No new schema is reserved.

## Verification

Actual existing Meta MockHTTP readers produce both sides of the match using their
shared codec; mutation matrix rejects money, scope/generation, topology, status,
schedule, settings and unsupported-profile changes. Native bytes remain unchanged.
Pure proof tests enforce separate consent/same ledger, nested immutability, strict
client inputs and digest roundtrip. No financial source or live behavior is qualified.
