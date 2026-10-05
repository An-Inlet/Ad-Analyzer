# Inlet Customer Foundation Contract

Status: approved B02–B04 contract, updated 2026-10-05. B02 backend implementation
and acceptance are recorded in `inlet-customer-auth.md`; B03/B04 follow. This is
not evidence of live SaaS readiness. The baseline
is the Inlet MVP Audit and Build Plan and main `ea3591c5086fbf2cee8038bf9208ac7f0050de75`.

## Existing Boundaries To Preserve

- Keep FastAPI, PostgreSQL, SQLAlchemy, Alembic and existing workspace compound
  foreign keys. Preserve independent-source analysis when CRM is absent.
- `/api/v1` remains an operator interface. Its shared bearer token cannot
  authenticate a customer. Existing IAP operator access remains separate.
- Customer access must never inherit the development-mode platform-admin
  shortcut in `app/workspaces/access.py`.
- Collectors remain read-only. No authentication or provisioning change grants
  advertising mutation rights, enables flags, or changes a production account.

## Shared Interfaces

| Interface | Required Fields And Rules |
| --- | --- |
| Verified identity | Configured trusted issuer, immutable subject, verified email as display/contact data. Unique `(issuer, subject)`; never merge identities or grant membership by an unverified email. |
| Customer principal | Internal user ID and current session ID. Workspace membership is loaded from the database on every protected request, not trusted from a client-selected ID or stale token role. |
| Shared session | Random opaque cookie; store only its digest, user ID, expiry, creation time and revocation time in PostgreSQL. No per-process authorization cache. Secure, HttpOnly, SameSite cookie, bounded lifetime and CSRF checks on mutations. |
| Workspace access | Authenticated user plus explicit workspace ID and requested permission. Require active user, unexpired/unrevoked session, active workspace and active membership. Reads return a uniform not-found result for inaccessible objects. |
| Provisioning command | Verified internal user ID, stable signup idempotency key and validated company details. Atomic workspace/configuration/owner insertion; unique signup receipt; reject key reuse with different input. Never default to workspace 1. |
| Connection scope | Internal connection ID, workspace ID, provider, status and credential reference/version. Bind provider-specific connection records to this owner. Never infer owner from the first active connection. |
| Advertising import scope | Workspace ID, connection ID, internal advertising account ID and provider. Database and worker validate that all belong together before requesting data. External account IDs alone are not internal ownership keys. |
| Job envelope | Version, unique job ID, workspace ID, connection ID, optional advertising account ID only for non-ad sources, job type and deduplication key. Reload current ownership and connection state at execution; reject absent/mismatched scope. |

These are interface requirements, not serialized production payloads. Final
schemas and migrations must land with their focused acceptance tests before
dependent adapters are assigned.

## B02 Implementation And Acceptance

Add a dedicated customer authentication package, identity/session models and
Alembic migration. Add `/api/customer/v1` routes and dependencies with no fallback
to operator authentication. Use a managed identity provider rather than storing
passwords in Inlet. The managed-provider choice and its issuer/audience/callback
configuration require the owner security decision described below.

Test two unrelated users against two separate app instances sharing PostgreSQL:
login identity remains bound to the right session, cookies cannot cross identities,
logout on one instance revokes access on the other, expired/revoked sessions fail,
suspension takes effect immediately, CSRF is required, and neither customer can
enumerate or mutate the other's workspace or access operator endpoints. Test
unknown issuer, wrong audience, invalid signature, replay and email changes.

## B03 Implementation And Acceptance

Provision workspace, configuration, owner membership and signup receipt in one
transaction. Tie the owner to internal user identity rather than only an email.
Do not reinterpret existing operator memberships during migration. PostgreSQL
uniqueness handles replay and concurrent signup, with a read-back after a conflict.
An aborted transaction leaves no partial company. A replay returns the original
workspace and owner; a conflicting request cannot claim somebody else's company.

Test sequential replay, concurrent identical signup, two users, slug collision,
transaction failure, retry after failure and suspended owners. Avoid silently
reactivating a suspended account during signup replay.

## B04 Implementation And Acceptance

Replace `AdsRepository.create_job_run(... workspace_id=1)` and global-account
dispatch with explicit connection/account scope. Replace CRM's default workspace
and first-active-connection selection. Scope deduplication and locks by the same
ownership tuple. Validate ownership again before persistence, not only at ingress.
Use a versioned queue rollout: old unscoped messages are quarantined with a
sanitized reason, never guessed into a tenant. Document deployment ordering and
backfill existing owner relationships before enforcing new non-null constraints.

Tests must include two workspaces with the same provider-side IDs, two active CRM
connections in one workspace, missing scope, mismatched connection/account,
revoked connections after enqueue, duplicate delivery, concurrent claiming and
partial import retry. Successful import must not repeat because downstream
analysis failed. Shopify plus Klaviyo, HubSpot and Omnisend remain distinct sources;
Shopify supplies canonical order/refund history.

## Approved Owner Decisions — 2026-10-05

The owner explicitly approved both decisions. Implementation may proceed on the
existing B01 branch/PR through sequential B02–B04 commits before its merge; human
review, merge and deployment remain separate. The following records the rationale.

1. **Customer identity provider:** Google Cloud Identity Platform under
   An Inlet's cloud ownership, subject to account setup and billing review. This
   recommendation follows the repository's existing Google Cloud deployment;
   [Google documents its OIDC sign-in support](https://docs.cloud.google.com/identity-platform/docs/web/oidc).
   Recommended architecture is provider-verified login
   with PostgreSQL-backed revocable Inlet sessions as specified above. Credentials
   remain externally managed; do not put them in chat or the repository. This is
   a security/architecture decision under `docs/automation-policy.md`.
2. **Review sequence:** the policy permits one dependent product PR at a time
   and forbids starting the next dependent PR before its predecessor merges.
   Review and merge B01 through the normal human gate, or explicitly extend the
   integration-branch exception to the Inlet buildout. Recommendation: review B01
   separately, then use one customer-foundation integration branch with sequential
   B02/B03/B04 commits and acceptance records. Neither option grants merge or
   production-release authority to the assistant.

Provider setup and customer signup are not live-verified. Public early-access
email links and the illustrative demonstration remain separate from these APIs.

## B04 Implemented Contract

Canonical connections reuse `WorkspaceIntegration`; advertising imports carry the
explicit workspace/connection/account/platform tuple. CRM version 2 messages carry
workspace/connection/provider and use connection-scoped signatures and deduplication.
Native Meta/Shopify ownership is preserved and bound to the same registry. Historical
unbound rows remain readable, but unscoped new imports fail closed. See
[inlet-import-ownership.md](inlet-import-ownership.md) for migration and rollout gates.
