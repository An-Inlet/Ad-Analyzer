# Inlet Customer Authentication

B02 introduces a customer API separate from the existing operator dashboard and
`/api/v1`. It does not yet provide a signup screen, billing, or production setup.

## Configuration And Trust Boundary

Authentication is disabled by default. The deployment owner must separately
configure Identity Platform in their Google Cloud project, approve deployment,
and supply these non-secret settings through deployment configuration:

- `INLET_CUSTOMER_AUTH_ENABLED=true`
- `INLET_IDENTITY_PROJECT_ID`: the exact trusted Google Cloud project ID
- `INLET_CUSTOMER_APP_ORIGIN`: exact HTTPS origin, without path or trailing slash

The Admin SDK uses application default credentials/workload identity and a
five-second HTTP timeout. Inlet accepts no service-account key in its configuration.
No cloud project, credentials, IAM permissions, or production configuration were
created by this implementation. Firebase emulator mode is rejected. Provider
tenants are rejected until explicitly supported; the trusted project is the
identity boundary. Changing that project invalidates existing Inlet sessions.

The Google Admin SDK verifies the signed ID token, issuer/audience/expiry and
revocation. Inlet additionally requires verified email, a bounded immutable
subject and authentication within five minutes. Email is contact data only:
matching/changing emails never claims another identity or operator membership.
References: [token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens),
[provider revocation](https://firebase.google.com/docs/auth/admin/manage-sessions).

## API Contract

All endpoints are under `/api/customer/v1` and require HTTPS.

- `POST /session`: JSON `{ "id_token": "<provider ID token>" }`, exact `Origin`,
  and `X-Inlet-Request: 1`. Exchange each provider ID token only once. A replay,
  including concurrent delivery on different replicas, fails closed. A concurrent
  first login for an identity can also fail closed; retry with a fresh provider
  token. Reauthentication rotates/revokes the session cookie presented at login.
- `GET /session`: current internal user ID, contact email, absolute expiry.
- `DELETE /session`: revoke this session in PostgreSQL and remove its cookies.
  Requires exact `Origin` and `X-CSRF-Token` matching the session's CSRF cookie.
- `GET /workspaces`, `GET /workspaces/{id}`: only active customer memberships and
  active workspaces; inaccessible IDs return the same 404 as missing IDs.

The opaque `__Host-inlet_session` cookie is Secure, HttpOnly, SameSite=Strict,
host-only, path `/`, and expires after eight hours without sliding renewal.
`__Host-inlet_csrf` is readable by the future same-origin client, with otherwise
matching restrictions. Only SHA-256 digests of random 256-bit session/CSRF secrets
are stored. Provider tokens are never stored; exchange receipts contain a digest
and expiry. Expired receipts are pruned during successful exchanges. Expired and
revoked session rows remain for a future explicit retention/cleanup policy; they
cannot authorize access. Customer responses are marked `Cache-Control: no-store`.

Every protected request reloads user/session state from shared SQL and checks the
provider's current disabled/email-verification/revocation state. Workspace reads
reload membership state; no process-local authorization cache exists. Provider
outages fail closed with a generic 503, including logout; local expiry and
revocation never depend on provider availability. This trades provider latency
and availability for immediate provider-state enforcement. A future operational
package must measure this dependency and configure ingress abuse controls before
public launch; this code alone is not a live launch acceptance result.

## Data And Migration

Migration `20261005_0020` adds customer users, sessions, token-exchange receipts and
customer memberships. Existing operator/email memberships are unchanged and do
not grant customer access. Customer cookies do not authenticate operator APIs,
and operator bearer/IAP credentials do not authenticate customer APIs.

B03 adds atomic workspace/owner provisioning next. B04 carries explicit ownership
through imports and background jobs. Neither is implied by B02 session issuance.

## Acceptance Evidence

`tests/test_customer_identity.py` exercises two distinct FastAPI app instances
sharing SQL, with independent request sessions. The same acceptance suite runs on
SQLite and isolated PostgreSQL schemas; a PostgreSQL-only concurrency assertion
proves a single winner for simultaneous exchange of one token. The identity
provider is injected; SDK adapter checks are mocked and no third-party credentials
or network are needed. Real Identity Platform login, workload identity and browser
signup remain unverified until separately approved staging setup exists.
