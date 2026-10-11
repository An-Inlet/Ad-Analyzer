# Customer Reporting Portal Interface V1

## Owned Files And Frozen Dependencies

Own new `app/portal/static/reporting.html`, `reporting.mjs`, a `/app/reporting`
shell route in `app/portal/router.py`, the existing portal navigation link, and
focused local TLS browser/API tests. Root owns `app/main.py` API registration.
Consume existing session/workspace/account listing and the frozen customer reporting
APIs without changing their request or authority contracts. Root may integrate
backend review repairs before final qualification. No schema or default runtime.

## Explicit Customer Flow

1. Load the current session and owned workspaces; select an owned Google account
   from server account options. Native provider IDs are not editable inputs.
   Show account currency/time zone where supplied. Changing workspace/account
   clears all displayed receipts/options and invalidates pending UI responses.
2. Read GET `event-selection?account_id=...`. If a selection exists (including
   refresh-required), require an explicit **Invalidate Current Choice** action,
   POSTing its exact selection ID/digest to `event-selection/invalidate`. Only
   a successful server response unlocks range refresh. Never invalidate implicitly
   as part of a failed read, retry or account switch.
3. Enter inclusive closed account-local dates (example August 1–September 30).
   POST `aggregate-range` with account, dates and one cryptographic 32-hex request
   ID. Retain the exact body in page memory across unknown transport outcomes;
   **Retry Same Request** resends it. Do not create a new ID automatically.
   Dates lock while the outcome is unknown; an explicit abandon clears local state
   with copy that the server may already have completed the request. Reload loses
   memory; no permanent client deduplication is claimed. Server validates dates.
4. Display only the successful returned range receipt: exact dates, completed state,
   row count and completion ID; explain aggregate conversions are not yet selected
   event facts. No optimistic receipt or locally manufactured completion.
5. Explicit **Discover Events** POSTs `event-options`. Render named options with
   metric-family labels using textContent; no first-option default. **Confirm Event**
   POSTs the opaque option ID and expected null selection pair after invalidation.
   A conflict requires a fresh state read; never silently replace another choice.
6. POST `captures` only after successful confirmation, binding exact selection
   ID/digest and the same inclusive range. Generate a separate stable request ID;
   apply the same unknown/retry policy as range acquisition. Display the actual
   capture ID, exact dates and returned-row count only after server success.
7. Show **Capture Ready For Planning** as a receipt handoff, not an implemented
   full plan workflow. The later selected-input V4 consumer remains separate.
   Always state that these reads do not authorize advertising changes or spend.

## Session, Rendering And Failure Boundaries

Reuse portal original-session preflight/epoch/cookie-CSRF patterns. Before each
mutation re-read the session; changed identity/workspace/account or late responses
clear sensitive rendered state and cannot act on a new selection. Same-origin fetch
only, no credentials or OAuth tokens in JS, no local/sessionStorage, no innerHTML
for server labels, no raw error bodies. Disable competing actions during requests;
unknown request bodies are immutable until replay/explicit abandonment. HTTP
401/403/404/409/422/503 have truthful bounded messages, including the disabled
runtime state. No client claim that missing rows are zero conversions.

## Browser Acceptance

Use actual local HTTPS application/session/CSRF/SQL routes with injected Google
MockTransport and both SQLite/PostgreSQL fixture ownership. Prove 61-day range
publication → named nondefault event confirmation → selected capture; server
receipt IDs match DB. Prove dropped response replays the same body/ID with no
second acquisition, existing-choice invalidation is explicit, session/account
changes discard stale responses, hostile labels remain text, and unavailable
runtime never shows success. Reuse current browser target-discovery and readiness
harness; no live provider browser/consent or fake frontend API responses.
