# Inlet Customer Application Preparation

Branch `codex/inlet-customer-portal` starts from billing-management commit
`a8a35fccf871cf2870336a0850eebf58346df409`. This application is separate from
the owner-managed public webpage and the existing operator dashboard.

## Implemented Journey

`/app` and `/app/settings` serve the same customer shell. The shell contains no
customer data; existing customer APIs authorize every read and mutation.
An existing verified customer session can:

- List/select owned or member workspaces, create a workspace with a stable retry
  key, and sign out through the revocable-session API.
- View scoped Shopify, Google, TikTok, Klaviyo, HubSpot and Omnisend connection
  status. Meta customer connection status is explicitly unavailable in this UI.
- Create/edit monthly Shopify net-sales goals with exact decimal-to-micros amounts,
  store currency/time zone, baseline month, budget period and aggressiveness.
  Existing cumulative goals are viewable but cannot be silently rewritten by the
  monthly editor.
- Review the exact saved goal revision and its persisted baseline snapshot before
  confirming. Local edits invalidate review; backend revision checks reject stale
  confirmation. Confirmation never authorizes spending.
- Inspect current assessments and simulated mandate definitions/reservations.
- View billing status. Owners can open configured Stripe test checkout/management
  through fixed Stripe destination allowlists. Fixture/unavailable/live modes never
  navigate; no price or production offer is invented.

## Security And Validation

User-controlled values use `textContent`/DOM option nodes, never `innerHTML`.
Mutations send the existing CSRF cookie in `X-CSRF-Token`, use same-origin credentials,
and reject HTTP redirects. Customer data is not stored in browser persistence.
The shell/assets use no-store, same-origin script/connect CSP, no inline execution,
no framing and no-referrer. Session failures hide customer content. Existing API
membership and role enforcement remains authoritative.

Checks run: `pytest tests/test_customer_portal.py` (6 passed, including Chromium
DOM journey and Node contract suite); embedded Node suite has 5 passing tests.
`ruff check .`, `mypy` (253 files), and `git diff --check` passed. Browser fixture
uses synthetic fetch responses and localhost only; it verifies workspace creation,
malicious workspace text escaping, goal save/edit/review/confirm, review invalidation,
exact revision and CSRF, unavailable checkout, cumulative-editor protection and
signout. Node checks cover redirects, amounts, dates, CSRF and sanitized API errors.
Chromium/Node checks explicitly skip when those executables are absent.

Full repository validation and hosted CI are delegated to the integrating root.
No database-backed end-to-end browser journey or live provider behavior is claimed.

## Remaining Work

Browser identity signup/sign-in is not implemented: the UI honestly requires an
existing verified session and never asks customers to paste credentials/tokens.
Natural-language milestone interpretation, cumulative goal editing, connection
setup/OAuth callbacks, Meta status, mandate creation/edit/approval and readable
progress charts remain UI work. Current detailed status/review uses structured
JSON panels. Billing is test-only; real purchasing requires product policy,
configuration, provider verification and release approval. No ad actions,
publication, deployment, credentials or live calls occurred in this package.
