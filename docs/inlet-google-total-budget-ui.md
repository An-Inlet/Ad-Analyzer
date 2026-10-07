# Google Campaign Total Budget Customer Review

The existing Campaign Execution page now offers an explicit Average Daily Budget
or Campaign Total Budget choice. Daily remains the initial choice and retains the
legacy request shape without a new discriminator. Amounts are not converted or
filled automatically when switching modes. Total requests use the frozen
`campaign_total_v1` intent and no daily amount.

The customer sees the total separately from the reservation, account time zone,
and exact campaign dates. Changing budget mode or amount invalidates pending
review/approval context, including a response already in flight. The total cannot
raise the customer's consented reservation or overall limit. Creation stays
paused; the existing separate activation approval remains required.

The page describes Inlet's current qualification subset: 4–89 inclusive local
days, local midnight through 23:59:59, with 72 hours to 90 days elapsed UTC.
This does not claim Google rejects other periods. Dates come from the previously
reviewed campaign draft and cannot be silently overridden here.

## Offline Evidence

Actual HTTPS Chromium journeys use persisted customer sessions, both SQLite and
PostgreSQL, the real customer APIs/coordinator, and Google HTTP MockTransport.
The total journey confirms an exact 30-micro campaign total against a distinct
40-micro reservation, holds a real API response while changing budget mode,
rejects that stale review, approves a fresh exact review, creates paused resources,
reads durable receipts, recovers the saved run, and clears data on logout.
The mock confirms no activation requests and no enabled resources. Existing daily
creation, separate activation, context-race and lost-response journeys remain green.

No live provider credentials, factories, financial qualification, permissions,
or advertising were enabled. This is offline customer-path verification, not a
live purchasing or advertising qualification.
