# Customer Portal Review Repairs

Base: PR78, `8b4b727c926b06baa1b68b2a3c40dcf144c55ff6`.

## Customer Session Isolation

Session checks and logout erase workspace selection, stores, goals, selected goal,
review state, form values, connections, mandate balances and billing text before
asynchronous work. Workspace refresh clears the prior workspace before fetching.
Every customer request captures an epoch; responses and errors from an earlier
epoch cannot repopulate or sign out a newer session. A 401 clears all customer
state. Chromium fixtures cover logout followed by another customer with no
workspaces, failed session refresh, late prior-customer responses, and 401.

## Atomic Goal Creation

`POST /api/customer/v1/workspaces/{workspace_id}/goals` now requires an
`Idempotency-Key` header: 8–128 ASCII letters, digits, underscores or hyphens.
Existing unkeyed clients must supply this header; omission rejects with 422.
Current membership and edit permission are checked before receipt lookup.

Migration `20261006_0032` adds receipts keyed by workspace, customer user and key,
bound to a SHA-256 fingerprint of the normalized, canonical goal definition.
Receipt, goal and revision commit together. Conflicting input returns 409.
Concurrent equal requests resolve to the same goal without orphan revisions.
Replay returns that goal's current state, including later edits; it does not
create or overwrite a revision. Receipts cascade with goal deletion.

The portal retains an uncertain creation key and input in memory within the
current session/workspace. Retrying the same save reuses the key; altered input
is blocked while the outcome remains unknown. It does not persist customer data
in browser storage. After a page reload, signout or session recheck, customers
must inspect the loaded goal list to find a previously committed draft before
creating another. Cross-reload automatic retry recovery is not claimed.

## Evidence

Before fixes, the Chromium logout-erasure assertion and both SQLite API
lost-response replay variants failed (three failures). API responses had distinct
goal IDs despite identical input and key.

Focused validation covers SQLite and disposable PostgreSQL, including real
concurrent file-backed SQLite and PostgreSQL creation, actor/workspace isolation,
input mismatch, suspended membership, missing headers, failed source rollback,
outer transaction rollback, and populated migration downgrade/upgrade.
The Chromium journey uses mocked fetch and sends no customer/provider traffic.

Final focused run: **54 passed**, no skips, on SQLite and disposable PostgreSQL.
Ruff passed; mypy passed across 250 source files; `git diff --check` passed.
Three Alembic configuration deprecation warnings are unrelated to the changes.

Full repository validation and hosted CI are tracked by the parent executor and
remain pending at this repair checkpoint. No live verification or deployment.

## Retry Follow-Up

Two additional Chromium repros exposed retry-state lifecycle defects: editing an
existing goal could discard another uncertain creation key, and a definite 422
validation rejection prevented saving corrected input. Keys now settle only for
the matching successful creation, or its explicit pre-commit validation rejection.
Successful edits leave pending creation receipts intact. Network failures and
5xx results preserve uncertainty. Fixtures exercise a committed-but-lost 503,
editing another goal, retrying the original save, and correcting rejected input.
API checks cover 422 followed by corrected creation and exact replay.

The Full run/CI for earlier head `18bc4f22` must not be cited as verification of
this follow-up. Its focused checks and later Full/CI are reported separately.
