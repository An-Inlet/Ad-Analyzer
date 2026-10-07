# Google Grant Lifecycle Preparation

Base: TikTok runtime `01aa869b7df73bcdf1dca5fc25391a43f0af4efc`. No live calls,
credentials, permission changes, advertising writes or deployment occurred.

Implemented:
- Optional `GoogleGrantLifecycle.revoke(refresh_token)` transport protocol and real
  fixed OAuth revoke endpoint, form body (never token URL), bounded timeouts,
  redirects/proxies disabled. Empty HTTP 200 succeeds; all other statuses/timeouts
  remain unconfirmed and sanitized. No customer route/job invokes this method.
- Typed current-customer authorization failure for refresh `invalid_grant` and Ads
  HTTP 401. This stops the current connection's retries, persists
  `reconnect_required`, increments generation, clears unusable encrypted grant and
  incomplete staged pages, and preserves previously published data.
- Transient/other configuration errors retain bounded retry behavior and staged
  cursor/pages. `invalid_client` is not misclassified as revoked customer consent.
- Local disconnect re-reads the connection under the existing workspace lock before
  updating generation, clears grant/staging/scheduling, and commits independently
  of remote revocation availability. Reconnect never revokes the previous token.
- Existing workspace/connection lock spans reads; outdated queued generations are
  rejected before HTTP and cannot invalidate subsequently selected consent.

Remaining grant-level revocation orchestration is actual implementation work, not
just a credential gate. Google's documented revocation scope spans scopes and tokens
for the project, potentially affecting multiple connections/workspaces. A per-account
`revoke_provider_grant` switch would exceed that account's ownership boundary.
Recommended design: represent verified grant ownership and affected connection scope,
show the affected set to the grant owner, explicitly authorize grant-wide removal,
and fence outstanding consent/selection/jobs against that revocation. This needs
an ownership/privacy design and owner decision before exposing remote revocation.
No retry queue retaining supposedly deleted grant tokens was introduced. Local
credentials are deleted immediately on disconnect, so remote revocation cannot later
be retried without newly authorized grant material.

Validation: 60 focused lifecycle/Google HTTP/customer-connection tests passed with
explicit disposable PostgreSQL (27 new lifecycle/review cases including SQLite/PostgreSQL
variants). Ruff, mypy across 251 files and whitespace checks passed. Full/hosted CI
remain outstanding. Test cases include response classification, successful/failed/
timeout revocation, durable reconnect-required transitions despite caller rollback,
stopped scheduling, obsolete generations, stale ORM disconnect, and never revoking
a broader grant during reconnect/disconnect. Existing transient retry tests remain.

Official references consulted October 6, 2026:
- https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke
- https://developers.google.com/identity/protocols/oauth2#expiration

Revocation success does not imply immediate provider-wide propagation. Generic Ads
403 errors are not classified as customer revocation because application/developer
configuration may cause them; richer permission-error classification is a remaining
qualification task. No live behavior is verified here.

Review repair: the official developer-token migration page, updated September 30,
2026, confirms the September 9 sunset. OAuth-client Cloud project access determines
API access; legacy developer-token headers are optional and ignored. Factory and
HTTP constructor now allow no legacy token while still requiring explicitly enabled
runtime, pinned API version, client ID/secret and successful OAuth/provider access.
Previously configured legacy headers remain compatible. Mock v25 checks cover no
legacy header, valid OAuth forwarding, missing OAuth configuration and denied Cloud
project access. Existing legacy-header tests remain. No Cloud/project setup occurred.
Reference: https://developers.google.com/google-ads/api/docs/api-policy/developer-token
The older REST auth overview still describes a required token; the dated migration
policy supersedes that wording. Future-major rejection of legacy headers is a release
compatibility check, not assumed for the explicitly pinned current version.


Import review repair: rollback recovery re-locks the current connection and checks
workspace, generation and connected status before scheduling five-minute backoff.
Semantic/publication failures clear only invalid staged pages/cursor and mark
`import_rejected`; already published rows and last successful sync remain intact.
A typed exception from the current transient read preserves pages. An old
`read_unavailable` marker cannot misclassify a new semantic failure. Tests cover a
campaign appearing between inventory and metrics pages, limit-one healthy-tenant
progress, preserved published data, transient retries and reconnection between queued
selection and failure handling.


Pending analysis invalidation: reconnect, disconnect and terminal authorization loss
atomically delete pending outbox entries selected by exact job workspace, integration
and advertising-account ownership under the import workspace/connection lock.
Completed/delivered work and other customer scopes remain untouched. Reconnect also
refreshes an existing ORM connection under its row lock before incrementing generation.
The scheduler package must independently lock/recheck completion existence before
claiming delivery; pending deletion alone cannot cancel analysis already running.
No timestamp-based generation inference or token-retaining queue is introduced.
