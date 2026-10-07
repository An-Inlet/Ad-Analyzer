# Inlet Customer Sign-In

Offline implementation; Google provider provisioning and live qualification remain disabled.
The existing Google Cloud Identity Platform verifier and PostgreSQL revocable sessions
remain authoritative. Google sign-in creates a customer identity on its first verified
exchange and signs into that identity on subsequent exchanges. Email is contact data,
never a membership lookup. Workspace creation is separate and idempotent.

## Browser Contract

`GET /api/customer/v1/auth-config` publishes public Firebase web configuration only when
both `INLET_CUSTOMER_AUTH_ENABLED` and `INLET_CUSTOMER_BROWSER_AUTH_ENABLED` are enabled,
project/app/public API key and HTTPS customer origin are valid, and no auth emulator is
configured. Only Google is implemented. Enabled means configured, not live-verified;
the response explicitly returns `live_verified: false`. No admin credentials are exposed.
The auth domain is derived from the validated project ID; arbitrary origins are unsupported.

`auth.mjs` loads the self-hosted SDK only after enabled configuration. It initializes
Auth with `inMemoryPersistence`, never the SDK's default persistent `getAuth`. A Google
popup obtains a fresh ID token, which is submitted once to the existing origin-bound
`POST /api/customer/v1/session` with `X-Inlet-Request: 1`. The backend continues to enforce
verified email, recent authentication, revocation and a single-use token receipt.
Sign-out and app deletion run in `finally`, including popup/token/exchange failures.
Provider error details are never rendered or logged. No identity token goes into Inlet
local/session storage. JS garbage collection, rather than byte-level memory erasure,
reclaims token strings after references are released.

Before switching identities, any valid presented server session must be successfully
revoked with its CSRF cookie. Failed or uncertain logout blocks the provider attempt.
The portal clears customer DOM immediately and preserves its existing epoch guards.
An uncertain exchange is never replayed or automatically reconciled to a potentially
different principal. The customer explicitly chooses **Check Session Again** to inspect
the current server session. Server cookies remain Secure, HttpOnly (session), SameSite
Strict and host-only. SDK sign-out does not revoke the server session; Inlet's logout does.

## Reproducible Delivery And CSP

Firebase JavaScript **12.19.0** and esbuild **0.28.2** are exact pins in
`browser/auth/package-lock.json`. Build with `npm ci --prefix browser/auth --ignore-scripts`
and `npm run --prefix browser/auth build`. The generated ESM asset is committed with its
license notices. CI rebuilds and requires no asset diff. No CDN import is used.

Self-hosting the SDK does **not** eliminate Firebase's Google-hosted popup bootstrap.
The official SDK resolver loads Google gapi modules from `https://apis.google.com` and
an iframe on the exact `{project}.firebaseapp.com` domain. Enabled-only CSP permits
those fixed script/frame origins and `identitytoolkit.googleapis.com` plus
`securetoken.googleapis.com` connections. It adds no wildcard, inline or eval allowance.
Disabled configuration keeps external scripts, frames and connections blocked. Google
popup navigation happens in its own browsing context. Default-disabled portal startup
makes no provider requests.

## Evidence And Remaining Qualification

Focused checks include actual Chromium DOM sign-in/logout/uncertain exchange/session
recheck with a mocked SDK and HTTP seam; Node error/cleanup/one-exchange checks; actual
SQLite and PostgreSQL API signup, owner provisioning, repeated workspace request,
replay denial and revocation; public-config/CSP fail-closed checks. No live identity
provider was contacted. SDK persistence is supplied explicitly and mocked assertions
check that contract; production popup persistence/cross-browser behavior still needs
qualified testing with an authorized test project.

Deployment requires separately authorized Identity Platform/Google provider setup,
public web app configuration, authorized application domain, HTTPS origin and workload
identity for the existing Admin SDK. No project, grants, credentials or deployment were
created. Popup blocking, third-party iframe restrictions, Google bootstrap CSP and
browser return behavior remain live qualification gates; there is no redirect/password
fallback and no claim of a purchasable production service.

Primary references checked 2026-10-06:
- https://firebase.google.com/docs/auth/web/google-signin
- https://firebase.google.com/docs/auth/web/auth-state-persistence
- https://firebase.google.com/docs/auth/admin/manage-cookies
- https://firebase.google.com/support/release-notes/js
- https://firebase.google.com/docs/auth/web/redirect-best-practices
