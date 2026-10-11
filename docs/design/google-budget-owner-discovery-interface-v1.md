# Receipt-backed Google owner discovery: concrete first slice

This amendment implements only discovery from the reviewed consumer-port design.
No input, action, PlanVersion or UI activation is included.

## Files and ports

`google_budget_owner_discovery_contracts.py` defines:

- `GoogleBudgetOwnersRequestV1`: strict `account_id: Positive`,
  `catalog_composite_digest: Digest`, `reporting_window: ReportingWindow`.
- `GoogleBudgetOwnerOptionV1`: `account_id`, opaque `owner_selection_id`,
  `expected_observation_digest`, `expected_owner_facts_digest`, `representative:
  TargetRef`, `affected_campaigns: tuple[TargetRef,...]` (2..200),
  `current_amount_micros`, `currency`, literal `cadence='daily'`, `unit='micros'`,
  `observation_started_at`, `observed_at`, `expires_at`, and fixed
  `economic_qualification='not_assessed'`, `review_only=True`, no-authority fields.
- `GoogleBudgetOwnersViewV1`: `account_id`, `status='available'|'unavailable'`,
  `owners` (at most20, no truncation), fixed optional reason
  `google_budget_owner_unavailable`, fixed recovery text requesting fresh targets
  and review. Available requires nonempty owners and no reason; unavailable
  requires empty owners. Unavailable never means no shared budgets exist.

`google_budget_owner_discovery.py` defines:

```
owner_selection_id(*, principal: CustomerPrincipal, source: SourceFence,
                   witness: GoogleDailyBudgetOwnerWitnessV1) -> str
read_google_budget_owners(configured: PlanningDocumentService,
                         principal: CustomerPrincipal, workspace_id: int,
                         intent: GoogleBudgetOwnersRequestV1
                         ) -> GoogleBudgetOwnersViewV1
```

The helper validates the witness and uses domain
`inlet.google-budget-owner-selection.v1`. Its payload includes exact workspace,
account, connection, full AccountRef, source revision/binding/privacy, actor,
original session digest and authenticated UTC instant, original composite digest,
full witness digest, owner key and both reporting-window UTC instants. Source,
account, and witness reference must match exactly. Private inputs are neither
returned nor logged. Observation digest is the full original witness digest.

New `api/customer_planning_budget_owners.py` registers the CSRF-protected POST
`/api/customer/v1/workspaces/{workspace_id}/planning/google-budget-owners`.
It snapshots the original principal before dependency rollback, calls the actual
`customer_planning_documents.service` factory, and passes that configured service
to the read port. Only exact canonical private V5 capability is supported;
default V3 is unavailable. Existing DTO bytes and routes remain unchanged.
`main.py` receives only the router import/registration.

## Transaction and evidence rules

External identity refresh happens before SQL via PlanningReadContexts. Inside its
single original-authority transaction, resolve owned account/source and paid
eligibility, then select the one original CatalogReceiptRow by workspace/account,
actor/session and composite digest. Existing `_load` validates raw payload,
original session, source/privacy, currency, expiry and requested window. Additional
UTC comparisons bind native, metadata and reference reporting windows to the
request; no wall-clock fold equality is trusted.

Derive candidates from distinct native campaign owner keys using the existing
strict witness constructor. Only its explicit GoogleBudgetOwnerUnavailable is
classified as ineligible; malformed/ambiguous data aborts. More than20 eligible
owners aborts; members are never truncated. After all pure work, re-resolve source,
paid eligibility and original authority; reload the same receipt and compare exact
evidence, UTC expiry and current clock. Final context authorization follows all
SQL and clock work. No commit, cleanup, provider read, or new row occurs.

Tests use genuine API-acquired receipts and actual configured private V5 service;
cover original-session/foreign/expiry/source/window/tamper/default-policy refusal,
read replay, full affected members, and zero native/financial/persistence effects.
Pure opaque-binding tests change each committed dimension without exposing values.
