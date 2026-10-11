# Original-Session Selected Google Context — Proposed Shared Interface

2026-10-11, basec47e5ce, isolated branch codex/inlet-selected-owned-context in reused
/workspace/inlet-selected-catalog. No implementation yet. Reserved ownership:
app/google_connections/selected_owned_context.py (new),
tests/test_google_selected_owned_context.py (new), package-specific ledger and
interface docs. No customer routes, selection-storage schema/service or default
factory edits. Use selected_storage's existing current_scope/read_selection/
_aggregate validators rather than a new weaker aggregate check; if exposing that
private aggregate check as a public port is desirable, coordinate exact rename with
root/storage owner first. No need to change0091 schema.

## Concrete Callable Surface

Constructor, trusted composition only:

    OwnedGoogleReportingContext(
        sessions: Callable[[], Session],
        principal: CustomerPrincipal,
        identity_provider: IdentityProvider,
        workspace_id: int,
        account_id: int,
        oauth: GoogleHTTPRead,
        vault: Vault,
        clock: Callable[[], datetime],
    )

Capture original user ID, issuer, subject, session digest/authenticated_at and expiry
as immutable private scalar identity. Never retain/adopt mutable principal ORM rows
as fresh authority. Use planning_documents.read_context.snapshot and PlanningReadContexts with
authority.refresh before SQL, then authority.lock/final under SQL; additionally require
persisted session authenticated_at and expiry equal original captured values, not an
extended/replaced local session. Owner role is required, not admin. No original
session digest or secret in repr/serialization/logs/exceptions.

Methods (compatible with existing injected catalog/selected adapters):

* `catalog_request() -> GoogleReportingCatalogRequestV1`: load server-owned current
  Google ReportingScopeV1 under original owner/session checks; constructs request
  actor/session/start/v24. Starts/pins one bounded resolver operation. Reject later
  calls that would refresh its original scope or operation clock. No caller scope.
* `catalog_context(request) -> GoogleReportingCatalogContext`: existing callable
  shape. Require exact pinned catalog request and owned scope, resolve token with
  independent before/after snapshots; return digest-bound private context.
* `revalidate_catalog(request) -> None`: same exact request/scope/identity/grant checks,
  permissions and deadline; no OAuth, no token returned.
* `selected_context(request: SelectedCaptureRequestV1) -> SelectedGoogleContext`:
  existing ContextReader shape; require workspace/account, original actor's current
  owned scope, current stored selection and actual current aggregate/full manifest
  equal request. Bind exact request digest on first call, then refuse another
  capture/request on this resolver. Validate v24 producer/profile/family/same-customer
  owner before grant read. Request construction remains trusted service's job.
* `revalidate_selected(request: SelectedCaptureRequestV1) -> None`: same full exact
  current dependency check with original session, permissions, immutable operation
  deadline and pinned grant/login check. First call may pin selected request before
  context resolution because existing HTTP invokes revalidate first.

Use a fresh resolver per catalog acquisition or selected-page operation; reject
mixing catalog and selected modes on one instance. The capture request.started_at
may precede a later page operation, but must not be in the future; page-operation
lifetime is not silently the entire capture lifetime. No background session
substitution: original session must remain active for each subsequent page/finalize.
No token cache, either shared or per-resolver: each context call refreshes anew.

API composition later:

    resolver = OwnedGoogleReportingContext(...original principal...)
    req = resolver.catalog_request()
    catalog = GoogleReportingCatalogHTTP(
        resolver.catalog_context, resolver.revalidate_catalog,
        transport=explicit_injected_transport, clock=clock)(req)

    reader = GoogleSelectedHTTPRead(
        resolver.selected_context, resolver.revalidate_selected,
        transport=explicit_injected_transport, clock=clock)

No public request receives/accepts ReportingScope, native advertiser or connection,
request digest, selection object, campaign mapping, or token. DTO construction and
opaque catalog IDs remain untrusted until this resolver actually checks owned rows.

## Snapshot And Deadline Algorithm

1. Validate injected clock as actual aware datetime and normalize UTC. Pin operation
   start/deadline <=start+60s and original session expiry before authorization/I/O.
2. In fresh Session from sessions, use original-session locked identity fact (maximum age5s) workspace→user→
   session→membership then current account/source locks. Recheck original scalar
   identity/session bindings; paid_work at fresh time; ALL_DATA_SYNCS enabled.
3. Server-derive account/integration/native source/generation/privacy/currency/timezone
   from persisted active rows. Invoke selected_storage.current_scope to verify exact
   native/account/integration/source status and no source error. For selected mode,
   read_selection plus existing aggregate validator rehash full manifest/current
   pointer/sync time; compare exact request aggregate+selection+profile. No stale
   fallback, graph subset, historic completion or name join.
4. Snapshot encrypted grant and login ID privately; require nonempty stored grant,
   exact source ID/workspace Vault context. Initial grant/login become operation
   fences (not reporting evidence). Close SQL session/transaction before decryption
   and provider refresh. No caller transaction/commit is touched.
5. Vault.open outside SQL with original wid/source ID. OAuth must be explicitly
   injected v24 GoogleHTTPRead with nonempty developer token; no config fallback.
   Sample refresh-start UTC BEFORE access_context. Never log/return refresh material.
   Provider lifetime expiry=refresh-start+validated seconds; do not use completion
   time. Bound return context by operation deadline, original session expiry and
   provider expiry. Refresh token dies with call; no durable bearer storage.
6. After every blocking decrypt/refresh stage, fresh snapshot reauthorizes and matches
   exact original scope/grant/login and selected dependencies when applicable.
   Resample clock AFTER locks/identity check/entitlement waits. Reject expired evidence
   before another provider operation or context return. Context cannot extend the
   operation deadline even if later token lifetimes are longer.
7. HTTP adapters already guard before/after read and per response chunk. Resolver
   callbacks independently fence current authorization. Expected race semantics:
   revocation while external I/O runs prevents returning/finalizing evidence; local
   locks are never held across OAuth/catalog/selected HTTP. No claim of instantaneous
   provider-side revocation or atomic external snapshot.

Checks finish with original authorizer+paid gate then fresh UTC expiry sample, so
checking source does not permit a long entitlement/identity wait to admit expired
context. Error bodies/secrets/private IDs never enter exceptions. Preserve canonical
HTTP401/403/404 from authorization; invalid source/dependencies return fixed safe
unavailable409; unavailable injected compatibility configuration503. Actual OAuth
errors remain sanitized. Resolver performs no reconnect/status mutation.

## Boundaries For Dependent Confirmation Service

Root's docs/design/selected-customer-confirmation-interface-v1.md remains canonical.
The resolver grants no commit authority. Confirmation service independently repeats
current ownership/scope/head checks under locks before0091store_selection. Changing
choice uses separate exact-CAS invalidation committed once, real aggregate refresh,
fresh discovery and explicit confirmation. Never automatic restamping/reconfirmation.

For final capture storage, existing0091store_selected_capture validates graph but
not original session; service must call original authorizer again within final
transaction. Resolver revalidation in another session is insufficient for atomic
commit authorization. No new public finalize method is introduced by this package.

## Offline Evidence Plan / Limits

Actual original user/session/membership/account/integration/Google source + encrypted
Vault fixture on SQLite and disposable scoped PostgreSQL; actual MockTransport OAuth
and catalog/selected read calls. Cases: valid owned discovery/capture, foreign account,
nonowner, issuer/subject/session rotation or revocation during refresh, grant/login/
generation/privacy/account units changed during I/O, selected head or aggregate
manifest/current completion changed (including outside selected dates), paid/sync
pause, expired original session/provider lifetime after blocking authorization,
DST-aware clocks, denied future/coerced dates, exact context request digest and
no plaintext/repr/serialization leaks. No new broad baseline or live read.

Whole Ruff/mypy and focused pytest before local commit; scratch caches, durable logs
/workspace/inlet-evidence/20261011/google-selected-owned-context/. Current free space
workspace1422MiB/scratch5889MiB and available memory13472MiB; retain specified reserves.
No push/hosted/schema/API/default factory. Actual v24 capability, developer-token
compatibility, full September/August provenance and provider qualification remain
separate. No product decision, spending authority or historical evidence substitution.

Reviewed clarification: the collection service's entire-capture60s deadline from
request.started_at is authoritative. A resolver page-operation deadline can narrow
but never extend it: selected mode uses min(operation start+60s,
request.started_at+60s, original session expiry). Require actual GoogleHTTPRead
instance with version v24; duck-typed OAuth adapters cannot qualify this port.

## Review Correction: Identity Provider IO

The original bind_authority prescription was incompatible with this document's
no-provider-IO-under-SQL promise. Resolver now reuses PlanningReadContexts.open():
identity refresh runs before opening each SQL Session, then exact current owner/
original identity/session rows are checked under locks with a5s identity-fact bound.
Snapshot copies loaded user status and session user_id/revoked_at as well as identity
fields; no lazy SQL during refresh. Callers must release preparation transactions.
After context exit's final authority guard and SQL close, resolver samples operation
deadline again before returning scope or pinning grant. Vault/OAuth remain outsideSQL.
