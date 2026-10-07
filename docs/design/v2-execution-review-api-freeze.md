# V2 Execution Review API Freeze

Pure types/callable protocols only, based on41dd530. No route is installed yet.
Existing three-field InitialPreviewExecutionIntentV1 and prepared response unchanged.

Under `/api/customer/v1/workspaces/{wid}/initial-planning/previews/{preview_id}`:

- GET `/execution-review-options` returns InitialPreviewExecutionOptionsV1 with exact
  owned preview ID/digest, up to50 separately consented matching0080 mandate options,
  explicit truncation, available/unavailable status and fixed unavailable reason.
  Options carry opaque mandate ID/revision/policy digest, owned account/target labels,
  exact USD period/timezone and total/per-plan/positive-change caps. No native IDs,
  profile knobs, raw proof or financial headroom. Availability is explicitly
  financial_qualification=not_checked and spending_authority=none.
- POST `/execution-review` accepts ONLY expected_preview_digest, mandate_id and
  mandate_revision. Returns the frozen InitialPreviewExecutionPreparedV1; no amount,
  target, proof or consent is silently supplied by the customer or created by this API.

New module `review_v2_api_contracts` freezes InitialPreviewExecutionRuntime(planning,
optimization), immutable option/result models and callable protocols. Concrete service
functions will have these exact signatures:

`execution_review_options(runtime, principal, identity_provider, workspace_id,
preview_id) -> InitialPreviewExecutionOptionsV1`

`prepare_preview_execution(runtime, principal, identity_provider, workspace_id,
preview_id, intent) -> InitialPreviewExecutionPreparedV1`

Both use original per-request principal and actual engine-backed runtime; services own
short sessions and final fences, never commit unrelated caller transactions. Runtime
optimization may be None; GET then reports execution_runtime_unavailable. Absent0080
consent reports separate_execution_consent_required; existing but incompatible consent
reports matching_execution_mandate_unavailable. Missing/foreign/retracted/expired
preview remains the existing sanitized owned-read error, not an option to execute.

GET has no provider mutation or financial qualification claim. It must require a
current owned proposed native-v2 preview and same-ledger compatible saved consent;
POST must independently repeat all guards and obtain fresh actual native/financial
facts. Truncation is not proof no further matching mandate exists. UI links missing
consent to Existing Campaigns; it never converts0079 consent into0080 consent.

V2 guard/writer implementation, actual configured API acceptance and frontend remain
next dependent work. Proof expiry must be the minimum of retained dependencies and
fresh applicable bounds, and inner hash domains remain exactly41dd530. Legacy v1
routes/bytes and historical reconciliation are unchanged by this interface freeze.
