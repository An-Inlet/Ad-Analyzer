# Two-Brand Pilot: Exact Source DTO and Current Delta Contract

Addendum to `w1-two-brand-pilot-current-historical-split.md`, baseline d878264.
Design only; this supersedes its loose scalar list and session-revocation wording.
Counterpart A uses the actual default `inlet.descriptive-review.v3` generator in
`app/planning_documents/service.py`, preserving positive generation/read/manual
acceptance. Neither a historical generator nor an execution gate override substitutes
for that current path. Declared original baseline/native/reporting bootstrap remains
explicit fixture data, not evidence of OAuth/import qualification.

## Closed Source Result

Exact-key JSON, strict types, no extra keys at any level, maximum16KiB. `Id32` means
lowercase32hex string; `Digest64` lowercase64hex; `PositiveInt` excludes bool and is
1..2^63−1. Counts are strict integers0..256. No type coercion or arbitrary dictionary.
The source accepts no additional scenario arguments beyond the reviewed owned target
and output path. Source pin remains the literal2155ff3 commit and exact app/tests trees.

```text
TwoBrandReceiptSourceV1 {
  schema_version: Literal["inlet.test.two-brand-receipt-source.v1"]
  source_commit: Literal["2155ff3e3ab00cd62057dd86cb49d45359d4f49f"]
  brand_a: BrandA
  brand_b: BrandB
  execution: ActivationGraph
  counts: GraphCounts
}
BrandCommon {
  workspace_id: PositiveInt
  actor_id: Id32
  account_id: PositiveInt
  advertising_integration_id: PositiveInt
  store_id: Id32
  shopify_connection_id: PositiveInt
  shopify_integration_id: PositiveInt
  crm_connection_id: Id32
  crm_integration_id: PositiveInt
  goal_id: Id32
  goal_revision: PositiveInt
  simulation_mandate_id: Id32
  draft_id: Id32
  draft_revision: PositiveInt
  draft_digest: Digest64
}
BrandA extends BrandCommon {
  platform: Literal["google_ads"]
  crm: Literal["klaviyo"]
  native_connection_id: Id32
}
BrandB extends BrandCommon {
  platform: Literal["meta_ads"]
  crm: Literal["hubspot"]
  native_connection_id: PositiveInt
}
ActivationGraph {
  provider_mandate_id: Id32
  provider_mandate_revision: PositiveInt
  provider_policy_digest: Digest64
  provider_consent_id: Id32
  ledger_id: Id32
  reservation_id: Id32
  creation_review_id: Id32
  creation_review_digest: Digest64
  creation_plan_digest: Digest64
  creation_run_id: Id32
  activation_review_id: Id32
  activation_review_digest: Digest64
  activation_plan_digest: Digest64
  activation_run_id: Id32
  owned_attempt_id: Id32
  owned_request_digest: Digest64
  owned_receipt_id: Id32
  owned_receipt_digest: Digest64
}
GraphCounts {
  creation_attempts: Count
  creation_receipts: Count
  activation_attempts: Count
  activation_receipts: Count
  held_reservations: Count
  creation_provider_posts: Count
  activation_provider_posts: Count
}
```

`CommerceStore.id` and SourceConnection.id are String32; Google native connection is
String32, Meta native connection is integer. These distinctions come from the actual
models, not the output's apparent format. Every scalar is re-resolved under its real
workspace/FKs. Counts must equal actual rows and completed plan step/activation target
lengths; held_reservations must equal1, creation/activation runs share that reservation,
all expected receipt outcomes and digests are verified. Counts are not authority.
Parent independently snapshots all actual tables and media bytes; no unvalidated
child graph digest can replace that check. No identity attributes, session material,
credentials or arbitrary paths occur in the DTO. Current login reads the retained
user identity directly from the owned DB.

## Exact Current Delta Comparator

Take complete normalized row snapshots (including unexpected tables) at source end,
after each login, after closure preview, and after confirmation. No table-wide wildcard
exemption. The following are the only permitted differences. Missing expected deltas,
extra rows, changes to other columns or Brand B rows fail. Generated IDs/fences/times
are captured from actual responses/rows and validated, never omitted from comparison.

### Fresh Login ×2

Source: `app/api/customer.py::login`.

- Use fresh empty-cookie TestClients; preserve every historical CustomerSession row
  byte-for-byte. No historical revocation or rotation. Login same stored issuer,
  subject and email; returned user_id equals original actor_id. CustomerUser rows
  and memberships remain unchanged (email assignment writes the same value).
- Insert exactly one `customer_sessions` row per login for that actor: fresh64hex
  digest/csrf_digest, created_at at observed server time, expires_at exactly
  created_at+TTL_SECONDS, authenticated_at equal fake-provider verified auth time,
  revoked_at null. No session digest is emitted by the source or logged.
- `customer_token_exchanges`: remove exactly rows whose pre-call expires_at is at or
  before that login's server `now`; add exactly the fresh verified token digest and
  expiry. Reject any other deletion/update. Existing unexpired exchanges unchanged.
- No other row changes. Capture narrow real server-time request bounds; do not pin authentication
  wallclock or mutate stored historical times.

### Closure Preview

Sources: `customer_lifecycle.preview`, `lifecycle.service.begin/claim_inventory/
finish_inventory`. Fixed fresh idempotency key; existing lifecycle requests/steps
must be empty in this source graph.

- Insert one `customer_lifecycle_requests` row: A workspace/original actor, operation
  close, schema inlet.lifecycle.request.v1, state requested, revision1,
  disposition_policy null, exact SHA256 key/body digests, initial retention-policy
  blocker, generated32hex fence, observed created_at/updated_at.
- Insert `(request_id,"inventory")` LifecycleStep: A workspace, request_revision1,
  matching request fence, state complete, attempts1, lease_until null, exact digest
  of the actual preview inventory. No finance/customer/source changes.

### Closure Confirm

Source: `app/lifecycle/quiescing.py::quiesce`. Confirm the exact returned inventory
and revision. Use its captured UTC confirmation time for equality, not an arbitrary
clock-tolerance omission.

For **A only**, permitted column changes:

| Table | Exact allowed transition |
|---|---|
| workspaces | status active→closing; export_privacy_revision +1; updated_at within actual closure request bounds (SQLAlchemy onupdate=utc_now) |
| workspace_integrations | exactly A3 rows: status revoked; secret_manager_reference null; updated_at within actual closure request bounds (same ORM mixin); B unchanged |
| customer_source_connections | status disconnected; encrypted_grant/cursor/next_attempt_at null; staged {}; generation +1 |
| google_customer_connections | status disconnected; encrypted_grant/cursor/next_attempt_at null; staged {}; generation +1 |
| shopify_connections | status reconnect_required; encrypted_credentials empty string; cursor/next_attempt_at null |
| spending_mandates | paused true only |
| provider_execution_mandates | state revoked only; no revision/policy/highwater/ledger change |
| provider_execution_runs | for both previously uncanceled runs: state canceled and canceled_at confirmation time only |

Delete exactly A's existing `customer_source_authorizations` rows. The other four
quiesce authorization tables (`google_customer_authorizations`, `meta_oauth_states`,
`meta_pending_grants`, `shopify_oauth_states`) must be empty for A in the closed source;
assert this before confirmation, rather than permitting unspecified deletions.

Require the following quiesce update targets empty for A at source end and before
confirmation: `crm_connections`, `meta_connections`, `customer_context_checkpoints`,
`workspace_automation_controls`, `mandate_actions`, `session_automation_runs`, and
`google_customer_import_completions`. Thus their code paths authorize no fixture
row changes. B's Meta/CRM/Shopify records are nonempty and unchanged.

Semantic privacy erasure invokes current staging/presence/planning/candidate/initial
observation/feedback invalidators. In this fixed historical source all their A
owned rows/dependents must be absent before confirmation, so no extra deletion or
export-counter delta is accepted. Do not generate an optional plan in counterpart B;
current positive planning belongs to counterpart A. If authentic source inspection
finds any unexpected derived row, stop and refine this exact contract before tests,
not silently allow every table affected by an invalidator.

Update the closure request only: state blocked, revision2, fresh32hex fence,
updated_at confirmation time; all original identity/body/key/created_at fields
unchanged. Its blockers are the exact current inventory blockers plus fixed pending
blockers, de-duplicated by `(code,subsystem)`:
`retention_policy_unset/lifecycle/owner_policy`,
`legacy_scope_unclassified/inventory/implementation`,
`publication_unresolved/provider_exposure_reservations/operator_evidence`,
`provider_revocation_unverified/connections/operator_evidence`,
`billing_unresolved/billing/operator_evidence`,
`worker_not_quiescent/jobs/implementation`.
Assert no unknown/emitting steps introduce extra blockers in this successful source.

Insert exactly `(request_id,"analysis_queue_cancel")` step: A workspace,
request_revision2, new request fence, attempts1, state complete, lease_until null,
evidence_digest equals `local_work.evidence_digest` of schema
inlet.lifecycle.queue_cancellation.v1, exact workspace/request/revision and
rows_canceled0. Original inventory step remains unchanged. No local-work reconcile
endpoint is called; GET closure status computes observation without writing a step.

### Always Immutable / Repeated Reads

Every other row/column is unchanged, especially provider period ledger, exposure
reservation (amount and held state), revision policies, consents, review documents,
steps, attempts, receipts, acknowledgements, Google completion evidence, media bytes
and metadata, commerce facts, customer identity/membership/history/session rows.
Provider mandate state and run cancellation are the only explicitly permitted
protected operational-header changes; they are not monetary or receipt exceptions.

Snapshot comparison must detect deliberate test-copy alteration of a ledger amount,
receipt digest, historical session revocation, B integration status, or an unlisted
column on A's canceled run. Receipt ownership reads and B goal/HubSpot GETs change
nothing. Original receipts remain owned/readable after closure while both views keep
closed=false/data_erased=false. Current provider transports remain write tripwires.

## Review Gate

No implementation/tests yet. Followup source discovery may establish a concrete
additional row, but requires an explicit amended allowlist rather than a broad
finance exemption. No historical activation is current policy. Existing archive
source22dda68 remains incompatible; only low-level exact helpers may be reused.

The source scalar index resolves ShopifyConnection by the unique workspace and commerce_store_id pair. Its native id is distinct from CommerceStore.connection_id, which identifies the owned WorkspaceIntegration. Both links are checked independently. The first strict-validation run exposed the original DTO extraction conflation; its exact source DB and failure remain preserved in closure-sqlite-04. No source rows or prefix changed.
