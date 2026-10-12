# Q13 V24 Mock HTTP Admission Contract

From b273e3e4. Introduce a separate `inlet.google-budget-http-observation.v1` event,
server-only HTTP-profile intent and `budget_http_observe` receipt operation. The new
route `/budget-http-observations` accepts the existing strict customer intent shape;
the server selects profile/provenance. It never silently falls back to v22 or real HTTP.
Old schema classes, stored JSON, digest domains and receipt operations stay valid.

The existing immutable v24 ticket/proof remains unchanged. A new projection derives
the comparison witness directly from validated v24 rows, original ticket and the saved
document's reporting window; it never constructs a v22 proof. Event validation repeats
the exact proof/witness/binding/privacy comparison. Top-level mock_http and not_verified
are mandatory, with implementation/current reliance not_assessed and no write authority.

Reuse scoped SQL append/CAS and strict prepared receipt/history readers. The HTTP service
refreshes identity and verifies owner/paid/source/privacy/goal/head before acquisition,
around each mocked IO through the transport callback, and again before atomic append.
No SQL transaction spans HTTP. The original 60-second ticket deadline is not renewed.
Replay returns the exact original result without reacquiring; changed intent conflicts.
Configuration identity checks bracket acquisition and inserts. History/recovery remain
available when acquisition is disabled, subject to current authority and erasure.

An immutable in-process mock bundle contains bounded pages, workspace, source digest
and privacy only. It creates only exact MockTransport with synthetic header context;
no supplied credentials, vault, network factory, refresh, real provider mode or upload
endpoint. It requires existing disabled-by-default mock_http mode plus V6 and explicit
app-state installation. The legacy fixture runtime remains separate.

Strict storage schema dispatch, response unions, receipt recovery, workspace archive
serialization and browser history admit only the explicit new event. The portal labels
mock HTTP as synthetic and not live-verified, including recovery. Unknown versions or
cross-version proof/provenance substitutions reject. Existing plan-document download
remains its original version-only artifact; observation export uses the owned workspace
archive, with full retained canonical event/proof and privacy/erasure gates.

Qualification: frozen components for both schemas, relabeling/tamper and legacy bytes;
assembled API request through mixed durable history, exact replay/recovery and archive
on SQLite then PostgreSQL; source/privacy/identity/runtime changes, atomic rollback,
cross-workspace/actor and erasure refusals; browser new-event rendering/recovery plus
legacy regressions. Preserve reserves, one heavy runner and all original failure evidence.
Independent contract/source/evidence review before local commit. No push, hosted CI,
live credentials/calls, merge/deploy, ad writes or spend. V3 default, V6/V7 qualification,
expert decisions and INLET-REL-20261012-01 remain open.

Review clarifications: v24 invalidation is excluded; never reuse the v22 invalidation
schema. Current reliance remains not_assessed. Disabled POST, including replay, refuses;
authorized history/receipt GET remains available. The original 60-second deadline covers
IO, proof/event preparation, lock waits and the post-insert check without renewal. Each
IO revalidation closes SQL before dispatch and checks the original bundle identity.
Receipt dispatch uses exact schema/operation/proof mapping, not a binary old-schema test.
