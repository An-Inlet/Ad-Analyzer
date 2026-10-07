# Candidate Recommendation Reads

Existing Campaigns now includes a separate read-only recommendation section.
Customers explicitly load named server policies and already consented spending
mandates, request a bounded read batch, then refresh owned worker progress. No
polling automation or automatic mode is started. Policy selection is an opaque
reference; the browser supplies no evidence, native IDs, numeric calibration,
qualification, or source proof.

Unqualified evidence displays a blocked explanation. A suggested result can prepare
its exact review, then link to the ordinary review page for separate approval.
Preparation does not approve, admit, or dispatch. Contract scenarios are explicitly
labeled fixture qualification, not live evidence. The exact amount, currency and
period are shown in the ordinary financial review, not inferred from incomplete
candidate display data. The overall spending limit remains unchanged.

The additive `CandidateReadStatus.decision_digest` is computed by the server and
validated against the canonical decision; it is null exactly when the decision is
absent. The browser passes that digest back verbatim. Existing decision bytes and
hashes are unchanged. There is no client hashing implementation.

Workspace/session resets remove owned results. Selection edits invalidate pending
responses. Request failures are never automatically replayed; unavailable or lost
responses require explicitly reloading current choices. This slice does not add a
history endpoint for lost enqueue responses or enable automatic scheduling.

Actual HTTPS tests use configured native adapters with MockTransport, original
customer login, ordinary mandate preparation/consent, API-created jobs and the real
scoped worker. No runtime getter override or candidate/execution record seed is
used. Both databases cover unqualified blocked results and an explicit contract
scenario through exact review and separate approval, with zero provider writes,
attempts, receipts, or exposure reservations. Fixture qualification is not empirical
production qualification. Genuine registered learning sources remain unavailable.
