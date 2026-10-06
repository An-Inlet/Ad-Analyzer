# Customer Activity And Support

`/app/activity` is a public shell linked from the customer portal. Its private data
comes from authenticated `GET /api/customer/v1/workspaces/{workspace_id}/activity`.
Every request rechecks the customer session and active workspace membership. The
response is `no-store`; no provider calls or mutations are made by this endpoint.

## Evidence And Limits

The versioned `inlet.customer.activity.v1` response includes only saved records:

- Goal revision creation and confirmation timestamps, with revision number.
- Campaign revision creation and approval timestamps, with revision number.
- For current owners only, the validated latest receipt for each of the ten most
  recently dispatched provider attempts. Existing coordinator ownership, lineage,
  digest and supersession validation is reused without relaxing its authority.
  Only outcome, observation time, environment and evidence category are projected.
  Missing or inconsistent receipts produce an explicit unavailable count.

Each of the four revision sources selects at most 21 scalar rows and emits 20.
Attempts select at most 11 scalar rows and validate ten receipts. Selection ties
use timestamp and primary keys deterministically; output is sorted by recorded
UTC timestamp. Up to 90 summaries are returned. `truncated` signals omitted source
rows, not a complete-history guarantee. There is no offset pagination or promise
of a complete chronological journal. Recent attempts can have old or late evidence;
older attempts outside this window are not inspected. PostgreSQL statements have
a transaction-local two-second timeout, including the existing receipt reader's
workspace/run locks. Dependency session teardown releases those locks.

No goal definitions, campaign artifacts, raw provider payloads/errors, actor IDs,
resource identifiers, tokens, account identifiers or monetary totals are exposed.
Contract-test receipts are visibly distinguished from live provider evidence.
Nonowners receive revision history and an explicit owner-only receipt coverage
label. Closing workspaces are outside this view's active-workspace access; existing
owned closure/export recovery pages retain their separate historical authority.

Connections and billing remain current-state views in the existing workspace page;
this package does not fabricate connection events or payment history. Support links
to existing recovery pages. It explicitly has no configured contact/ticket service
and sends no messages. Approvals do not claim publication, receipts do not claim
sales/payment, and closure does not claim deletion or stopped advertising.

## Validation

Focused SQLite/PostgreSQL API tests cover real session exchange, foreign workspace
rejection, viewer coverage, membership suspension, session revocation, scalar
projection and bounded deterministic selection. Actual coordinator MockHTTP tests
exercise unknown to verified receipt supersession and reject corrupted projections.
Chromium exercises the production page/module with fixture fetch responses: workspace
switches, late success and late network failure, account replacement and revoked
session clearing. Browser and API evidence are separate tests; this is not a live
provider or deployed end-to-end qualification. The existing portal browser and route
boundary inventory are also checked. No Full validation or CI dispatch was requested.
