# B06 Goals And Offline Interpretation Contract

Approved 2026-10-05 22:20:59 UTC; builds on B05 head f8b1c203. B06 implements
customer APIs and persistence, not a customer portal or live AI integration.

## Goal State And Measurement

Routes live under `/api/customer/v1/workspaces/{workspace_id}/goals`:
create/list; read/update a goal; read history; preview its historical baseline;
confirm an exact revision/preview with an idempotency key; interpret a milestone;
and read workspace interpretation usage. All writes use current customer membership,
CSRF and origin validation. Owner/admin confirm, analyst may draft/edit/preview/
interpret, viewer may read. Operator bearer credentials are not accepted.

A draft may have no definition. A complete definition binds the approved
`shopify_merchandise_net_sales_v1` metric, owned store, positive absolute target in
currency micros, target and historical baseline MeasurementWindows, inclusive local
deadline, budget amount and half-open budget period, and an aggressiveness label.
Revenue goals use the verified store currency/timezone; no FX, profit, attribution,
new-customer or relative-growth metric is invented. Both windows must have the same
basis. Monthly windows are exact local calendar months; cumulative baseline and
target windows have equal duration. Baseline must end before target starts.
Deadline is the target window's last included local date.

Every edit creates an immutable numbered definition and clears current confirmation.
Confirmation requires the exact revision, a complete historical baseline preview no
more than 15 minutes old, unchanged source revision/watermark/value, and a nonexpired
goal deadline. Missing, stale, importing, revoked or privacy-suppressed sources cannot
confirm. Future target months do not become zero; they are not used as historical
baselines. Zero complete historical revenue is valid for an absolute goal; no growth
percentage or feasibility guarantee is calculated. Idempotent replay cannot reconfirm
an edited revision, and changed content under the same confirmation key conflicts.
The confirming customer and time are recorded on the exact revision.

Preview returns the B05 snapshot ID for review through the existing scoped commerce
snapshot endpoint. Goal history never copies baseline sales or customer facts: previews
reference snapshots with ON DELETE SET NULL. Privacy erasure/retention therefore makes
the assessment unavailable without losing the customer's nonfinancial goal intent.
A recorded confirmation and a currently available baseline are separately represented.
All responses specify `spending_authorized=false`; the aggressiveness policy remains
unvalidated. Labels conservative/balanced/assertive do not activate 5/10/20% policies.
Budgets do not create, alter or increase an advertising mandate. B07 is separate.

## Interpretation And Usage

`GoalInterpreter.interpret(milestone) -> JSON` is an injected **offline-only** adapter.
The default adapter honestly requests structured clarification; it does not pretend to
understand arbitrary language. Validated output is an editable suggestion, never an
automatic goal update. It cannot specify workspace/store identity, baseline facts,
permissions or executable actions. Unsupported/malformed output leaves manual editing
available. Input is bounded to 4096 characters; output to 8192 bytes and five bounded
questions. These are offline payload bounds, not live-provider token/cost guarantees.
There is no provider SDK/client/configuration enabling external calls in B06.

SQL policy rows and reservations enforce default caps of 100 calls/workspace/UTC day,
1000 global/UTC day and 20 calls/user/workspace/rolling hour. The global policy lock
serializes reservation checks across replicas; workspace/goal ownership is constrained.
Reservations commit before adapter execution and database locks are released. Only one
reserved/uncertain request may remain outstanding per goal. Request fingerprints reject
idempotency-key reuse with different content; repeated keys do not call the adapter again
and return 409 with usage state rather than storing/replaying raw model output.

A two-second default timeout or ambiguous exception leaves an uncertain reservation,
which counts against caps and blocks automatic retry. Late thread completion cannot
apply a goal or clear the reservation. Manual editing/confirmation remains available;
no unverified automatic timeout expiry or operator reconciliation feature is claimed.
The offline adapter runs in a bounded-time caller; an injected test adapter may finish
later in its worker thread. No production external adapter is supplied or authorized.

External/paid adapters are rejected before reservation or execution. Database constraints
require policy, reserved and charged monetary amounts to be zero. Nonzero pricing,
settlement and provider-specific token accounting are deliberately not implemented as
though authorized. Live activation requires separate provider/data-processing/cost-cap
approval and a subsequent implementation package. No prompts or model outputs are stored
or logged; usage stores a request digest, scoped IDs, version, timestamps and outcome.
Workspace deletion cascades goal/revision/reservation data. Limits are independent of
ad budgets and future subscription billing; this package creates no customer charges.

## Acceptance And Release Boundaries

Offline tests exercise full/future/stale/changed/deleted baselines, monthly/cumulative
validation, confirmation idempotency and concurrent edits/confirmation, CSRF/membership/
role/source isolation, strict model output, paid/external rejection, quota and duplicate
reservation races, unknown outcomes and timeout, and populated PostgreSQL migration.
Existing B05 privacy tests continue to apply. Required Full and exact-commit CI results
are recorded in PR64 and the progress ledger. No live provider or browser portal behavior
is claimed verified. The approved integration exception ends at B06; B07, merge,
deployment, live model activation and CRM gateway architecture remain separate gates.

Repeated confirmation of the same preview under a different request key preserves
the original confirmer/time; the extra key is a replay receipt, not a new approval.
The usage response distinguishes today's reserved calls from all-age outstanding
reserved/uncertain requests. UTC midnight never hides or releases unresolved work.
