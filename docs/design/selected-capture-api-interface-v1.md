# Selected Capture API And Retained Receipt V1

This depends on the original-session customer service, reviewed storage0091 and
bounded Google collection. No new staging table or background authority is needed.

POST `/api/customer/v1/workspaces/{workspace_id}/reporting/google/captures` accepts
only strict account ID, request ID (32 lowercase hex), expected selection ID/digest,
and inclusive account-local `starts_on`/`ends_on`. The request ID becomes the capture
ID: an untrusted scoped selector, never authorization. Dates must be closed and
within the genuinely acquired current aggregate. Scope, aggregate, attribution,
producer/profile, mapping and timestamps are constructed on the server.

The response contains capture ID, account ID, selection ID/digest, requested dates,
completion time, returned-row count and `spending_authorized=false`. It confirms
stored reported observations, not zero coverage, provider capability, attribution
comparability or advertising changes. No provider/native IDs, session data, private
grant, raw source document or campaign mapping appears in the response.

## Replay And Commit

The immutable capture is also the retained request receipt. Under current original-
session owner authorization, locate the exact ID within the workspace/account and
compare the semantic body: account, expected selection ID/digest and date range.
Use `read_selected_capture` to prove the entire graph and current dependencies.
Return an identical retained result without provider I/O; stale evidence gives409
and is never automatically refetched. A changed body or foreign ID collision gives
a generic409 without disclosure. Server timestamps are not regenerated for replay.

For a new request, pin the exact current selection, aggregate completion/manifest,
full native/local campaign map and source/privacy state before I/O. Close SQL, then
collect through the injected original-session context. On finalization reacquire
original authorization and the existing workspace/account/source locks, check all
original dependencies and mapping, and recheck any concurrent receipt winner before
inserting. An identical current winner returns its stored result; a different winner
conflicts. Never adopt a replacement aggregate or session after external reads.

Final original-session/paid/sync and deadline checks precede atomic storage/commit.
Revocation after I/O denies even if a concurrent winner exists. Failed finalization
rolls back header/facts together. Network-unknown outcomes retry the SAME request ID
and body; no automatic new ID. This idempotency lasts while the capture is retained;
privacy erasure also erases its receipt. Permanent deduplication is not promised.

The capture stores selection-confirmer provenance, not acquisition-actor provenance.
A current owner's authorized replay is a shared workspace read and must not claim
that owner originally initiated acquisition. Additional actor audit attribution
would require its own reviewed storage contract.

## Checks

Actual HTTPS API with mocked OAuth/account/action/selected HTTP: positive, explicit
zero, absent rows/fields, pagination, duplicate/cursor errors, foreign access, CSRF,
same-ID replay/changed body/concurrent winner, selected/source/aggregate mutation,
role/session revocation, atomic rollback and no advertising-write requests. Inspect
stored graphs and response exclusion. TikTok selected mapping remains unsupported.
