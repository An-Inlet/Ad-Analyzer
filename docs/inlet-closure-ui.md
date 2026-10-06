# Customer Workspace Closure UI

`/app/workspace-closure` is linked from Settings. Its authenticated APIs list only
active workspaces with current owner membership. The owner requests an inventory
preview using the existing idempotent API, sees the exact name and numeric workspace
reference, and must type that exact name and acknowledge the reviewed inventory
and irreversible local effects. Confirmation submits the exact preview revision,
inventory digest and workspace ID; the UI never generates a completion flag.

The explanation distinguishes removal of locally held credentials and disabled new
work from unverified in-flight work, retained history/media/reservations/audit data,
unchanged external advertising/provider permissions and uncanceled subscriptions.
No complete erasure, full closure, provider revocation or billing cancellation is
claimed. Inventory counts have customer-facing labels; internal table/field names
are not shown. Workspace names and all dynamic strings use textContent.

A dedicated receipt shell at `/app/workspace-closure/{workspace_id}/{request_id}`
reads the existing owner-authorized status API directly, even after the workspace
leaves the active selector. The shell itself contains no private data. Each refresh,
page restoration or sign-in recovery reauthorizes; role loss/logout clears private
DOM state. Closure does not revoke the global session or affect other workspaces.
The status URL is stored in browser history before confirmation, allowing recovery
if a response is lost after commit. No receipt or workspace data is placed in
localStorage. An explicit user sign-out revokes the session through the existing API.

This client recognizes the frozen lifecycle v1 contract: `blocked`, revision 2,
with false completion/erasure/provider-verification flags is the local closure
receipt issued by `quiesce`. It never interprets arbitrary blocked or future-version
states as success. Unsupported state/version evidence fails closed. Historical
names are not returned by the status API, so recovered receipt pages identify the
numeric workspace and request reference rather than inventing a name.

Validation uses actual HTTPS browser/API journeys on SQLite and disposable
PostgreSQL: two workspaces, escaped name, explicit wrong-name denial, exact digest
confirmation, idempotent replay, closing-workspace selector removal, preserved
other-workspace/global session, current-role denial, logout, reauthentication and
saved status recovery. Existing closure/lifecycle and Google authorization suites
verify the parent-branch integration. No production closure or provider actions ran.

Branch ancestry combines PR122 `9088dbd` and PR118 `216fda2`. One inherited Google
authorization conflict preserves both behaviors: lock-free preflight when requested,
and workspace-before-authorization row locking when final mutation locks are used.
No new backend/schema contract was introduced; the closure UI commit is separable
from that parent merge. Bounded export remains owned by the independent export work.
