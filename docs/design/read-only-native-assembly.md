# Runnable Owned Native Diagnostics

Review baseline: root `9e8d9f5018fb1098bca8b9800fd8f97ecf62990f` in `/workspace/inlet-mvp-next`.

## Actual state and boundary

`NativeDiagnosticService` already assembles real Google refresh-token exchange, scoped Google/Meta/TikTok vault reads, current authorization, billing/mandate/generation checks and the three actual fixed-endpoint native inventory collectors. It has no route or runtime factory consumer. Its request requires a consented execution mandate. Merely routing it would not close a first-customer journey: current customer mandate construction/consent depends on unavailable execution runtime assembly.

`get_customer_execution_runtime`, `get_customer_optimization_runtime`, `get_optimization_runtime` and `get_session_automation_runtime` return None. Existing adapters and durable coordinator journeys are executable with contract-test sources. This is not a qualified production optimizer. Concrete reviewed native inventories explicitly retain null reporting watermark and U/F/P bounds; no preventative external-writer control or original terminal source can be fabricated. Directional association also cannot supply a qualified calibration/count source or production policy merely by registration.

Billing has a concrete configured Stripe receipt reader; paid entitlement is an admission prerequisite, not financial exposure proof. OAuth/vault configuration is access, not proof either.

## Proposed bounded implementation

Implement a customer-triggered read-only account diagnostic journey that does not require or create a spending mandate. No scheduler, execution runtime or mutation adapter is activated by it.

1. Add strict versioned provider account-observation request variants alongside the existing mandate-bound v1 inventory requests. They contain server-resolved exact ExecutionAccount, server-resolved account currency/timezone, bounded requested observation start/end and an explicit `purpose=account_diagnostics`, `spending_authority=none` discriminator. Preserve existing v1 serialized bytes/digests. Existing collectors accept the explicit old/new request union and retain the same fixed queries, resource/page/time bounds, private transport and unqualified result semantics. No synthetic ProviderMandateBinding or optional null mandate in historical v1.
2. Refactor only the existing diagnostic credential assembly into a concrete account-scoped read path. Resolve `customer_intents.account` under workspace-first original-session authorization; require current paid entitlement appropriate to configured environment and existing all-data-sync permission. Recheck exact source/account/generation/currency/timezone and original session after OAuth, between collector pages through current context checks, and before returning. No locks span HTTP; revoked credentials or changed scope fail closed. Preserve original mandate-bound path and its tests.
3. Expose CSRF-protected POST `/api/customer/v1/workspaces/{wid}/execution/diagnostics` with only `{account_id, starts_at, ends_at}`. The route derives all scope/environment/credentials; never accept actor, token, native IDs, policy, mandate, evidence or runtime. Fresh owner session required. No-store result. Bounded response presents provider, owned account display name, observation timestamps, inventory counts, fixed diagnostic reason codes and plain-language descriptions; `optimization_available=false`, `cap_semantics=unqualified`, null financial bounds. Do not label reported/native counters as safe available spend or mature performance learning.
4. A concrete settings-backed read-only service factory constructs real HTTP transports and provider OAuth/vault dependencies only after enabled/configured read access and owned authorization. Default switch remains off; unavailable response is truthful. Tests inject MockTransport at this actual composition seam, not a replacement service or fabricated financial reader. No arbitrary URL/header configuration. Close created transports deterministically.

This is useful read/diagnostic production code, not completion of the automatic optimization path. It creates no new table, approval, reservation, recommendation or measurement cache. Source/privacy deletion leaves no persisted derived diagnostic document.

## Required tests

Actual HTTPS customer session + CSRF + configured encrypted synthetic vault credentials → real all-three collectors via MockTransport → bounded diagnostic projection. Cover disabled factory makes zero transports/reads; foreign workspace/account, wrong generation, expired/revoked original session before/after OAuth and page IO, changed billing/closure/control state, missing/expired credentials, invalid/oversized periods, partial inventory semantics, and secret/native-response omission. Existing mandate-bound/v1 byte fixtures remain unchanged. Ruff/mypy and focused PostgreSQL/SQLite tests; no Full or live calls.

## Explicitly not solved

Production financial envelope/terminal/replacement qualification, independently calibrated directional sources, production numeric policy registration, automatic execution factory assembly, and logout-independent delegation remain separate. Under the current strict spending promise with arbitrary outside writers, source qualification is not demonstrated; wiring a fake reader or enabling the actual mutation transports cannot remedy that. The separate product guarantee decision is required if the owner wants a different supported control boundary. No such decision is implied by this read-only proposal.

Scope approved by parent; implemented on codex/inlet-account-diagnostics.

## Exact shared interface for approval

Customer body `AccountDiagnosticIntentV1(StrictModel)`:
- `account_id: int` strict positive
- `starts_at: AwareDatetime`, `ends_at: AwareDatetime`; `0 < ends_at-starts_at <= 366 days`; end must not be after final server clock (this is observation, not forecast).

New collector requests: `GoogleAccountObservationRequestV2`, `MetaAccountObservationRequestV2`, `TikTokAccountObservationRequestV2`, each with exact fields:
- `schema_version: Literal['inlet.<provider>-account-observation-request.v2']`
- `purpose: Literal['account_diagnostics']`, `spending_authority: Literal['none']`
- `account: ExecutionAccount`
- `currency: str` uppercase three-character owned account metadata; `time_zone: str` validated ZoneInfo
- `period_start: AwareDatetime`, `period_end: AwareDatetime`, same maximum366days
- `digest()` domain-separated by its explicit schema_version.

Each existing provider inventory result's `request` becomes an explicit `ExistingNativeInventoryRequest | NewAccountObservationRequestV2`; existing v1 serialization does not acquire a discriminator/default field. Provider collector/context validation retains exact request digest/account binding. No request variant is accepted by a financial qualification port.

Concrete `NativeAccountDiagnosticService.read(workspace_id, actor, account_id, starts_at, ends_at)` is constructed server-side with `session_factory`, `bind_authority(original_principal, identity_provider)`, fixed provider transports/OAuth and clock. It owns all current-scope reads. It reuses existing vault assembly rather than exposing a credential-return API. Service construction and use are per HTTP request and context-managed for deterministic transport closure.

`get_native_account_diagnostic_service` is a concrete context-managed factory called by the FastAPI route after deriving the original principal/provider and checking owned scope. It yields a real configured service or raises fixed503 before credential/transport construction when disabled. Proposed setting `INLET_CUSTOMER_NATIVE_DIAGNOSTICS_ENABLED=False`; this is read access only and cannot enable any execution setting. Tests override only low-level HTTP transport construction/clock with actual MockTransport; do not override the service, route, session or vault.

Response `AccountDiagnosticViewV1(StrictModel)` exact keys:
- `schema_version='inlet.customer-account-diagnostics.v1'`
- `account_id: int`, `account_name: str` bounded160, `platform` literal Google/Meta/TikTok
- `observed_at`, `expires_at` aware timestamps
- `inventory_counts: list[DiagnosticInventoryCountV1]` max4, each `kind` fixed enum campaign/campaign_budget/account_budget/billing_setup/adset/adgroup and nonnegative bounded `count`<=200
- `read_complete: bool` (completed bounded inventory read only; explicitly not full financial coverage)
- `cap_semantics='unqualified'`, `optimization_available: Literal[False]`
- `reporting_watermark: None`, `unreported_upper_micros: None`, `unchanged_future_upper_micros: None`, `proposed_owner_upper_micros: None`
- `reasons: list[DiagnosticReasonV1]` max20; each server allowlisted `code` and mapped bounded customer-readable `message`.

First response deliberately omits native monetary counters and resource IDs entirely; counts and fixed reasons are sufficient for the usable diagnostic journey without presenting unqualified units as money. Underlying typed inventories retain their explicit native/unqualified units for internal tests. No raw inventory serialization in API/logs. Capabilities GET on the same namespace can expose per-provider configured/read-enabled booleans only after owned session validation; it must not disclose secret configuration values or advertise optimization readiness. This is optional UI discovery only if consumed in this package; otherwise omit it.
