# Two-Brand Pilot: Exact Historical Test and Current Counterparts

Proposal only. Baseline `d878264936c8aad5af96f191617412692aecc307`.
No implementation, test execution, provider access or coverage closure is claimed.
The owner-approved planning MVP permits no advertising mutations. Historical
creation/activation must not be presented as current business policy.

## Preserve the Original Evidence

Keep the complete function
`tests/test_two_brand_pilot.py::test_two_brands_api_review_execution_and_closure_isolation`
under the existing literal historical commit
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`, with exactly its SQLite and PostgreSQL
parameter identities. Preserve its function AST, assertions and original fixture
behavior through the established closed historical wrapper/manifest mechanism.
Do not replace its activation assertions with a planning denial, edit the historical
function, or count the current replacements as additional original identities.
An additive two-node manifest and explicit coverage-map entries follow review.
Existing historical batches must not be rerun to qualify this package.

The original function contains independently valuable current assertions:

- Real login and idempotent signup of two unrelated owners/workspaces on one DB.
- Klaviyo versus HubSpot authorize/callback/select through actual HTTP adapters and
  local MockTransport. Cross-owner callback denies before the token HTTP call.
- Explicit fixture Shopify baselines and Google/Meta native connection bootstrap;
  these are not fresh OAuth/import or live integration qualification.
- Actual create/preview/confirm goal APIs and cross-workspace/cross-object denials.
- Offline draft review, then historical Google creation and separately approved
  activation. The simulation approval that precedes the draft is now prohibited.
- Current closure preview/confirmation blocked by held exposure; owned historical
  receipt stays readable, foreign owner is denied, Brand B remains usable, and no
  new advertising mutation occurs.

## Counterpart A: Current Two-Brand Onboarding and Planning

Proposed `test_two_brand_current_onboarding_planning_and_isolation`, both databases,
uses the assembled current app and one database with two distinct TestClients. Reuse
`login`, `signup`, `ProviderHTTP`/`adapter`, `install_fixture_baseline`, and the
original explicitly named `native_fixture` bootstrap only where exact-compatible.
Retain distinct Shopify IDs/domains, advertiser IDs, integrations, CRM grants,
accounts, users and workspace memberships. No ready plan/evidence bundle or
planning runtime getter override.

1. Repeat the original actual login/signup and CRM authorize/callback/select for
   Klaviyo/Google Brand A and HubSpot/Meta Brand B. Assert cross-owner callback404
   and unchanged HTTP call count; assert both legitimate selections succeed.
2. Install the declared baseline/native bootstrap boundary, then use actual current
   goal create/preview/confirm APIs. Persist the confirmed goal revision and assert
   `spending_authorized` false. Retain the original goal/source/activity ownership
   checks in both directions, including a foreign goal under the owner's route.
3. Exercise current positive planning through
   `/api/customer/v1/workspaces/{wid}/planning/plans`: create, generate, owned read,
   exact `accepted_for_manual_application` decision, events and version export.
   Use `CustomerInputs`/`CreatePlan` and exact version/document/action digests as in
   `tests/test_planning_documents_api.py`; do not retain obsolete `/mandates/approve`
   as the route to a current approval. Add foreign plan/read/version/decision/export
   denials with a valid foreign-owner CSRF token and unchanged event sequence.
4. Adapt only the low-level native HTTP/settings and owned reporting setup from
   `tests/test_planning_evidence_adapter.py` to the already API-created two brands.
   Its whole `setup_evidence` helper creates its own owner/goal and therefore cannot
   be called twice as a substitute for continuity. No native evidence callback may
   return an already-authorized plan. Explicitly record any normalized reporting
   fixture rows as bootstrap data; provider native catalog reads remain actual
   bounded adapters/MockTransport and must bind the chosen brand's account.
5. Assert both generated plans contain only their own goal/account sources; expected
   current plan freshness/decision succeeds, not merely a409. Manual acceptance has
   no provider execution meaning. Snapshot provider/financial tables before/after:
   no attempts, requests, activation records, consents or exposure movement appears.
   No source HTTP mutation after CRM connection establishment.
6. Revoke A's actual session, verify remembered A plan mutation/read protection and
   no additional provider reads after revocation. B's goal, CRM and plan remain
   available. Fresh A login uses the unchanged stored issuer/subject and recovers
   its own retained plan without copying a session or rewriting user identity.

This is a current API pilot, not a browser/live/full fresh-import pilot. The original
legacy campaign-draft assertions remain exact in the historical test; retained
current legacy draft editing is separately covered by existing campaign-review
source tests. New planning document approval is its explicit current counterpart,
not a claim that the old simulation approval became permissible.

## Counterpart B: Historical Two-Brand Graph, Current Privacy and Closure

Proposed `test_two_brand_current_closure_over_retained_activation`, both databases.
A separate **closed** source produces exactly the two-brand graph through the end
of the original activation/receipt-ownership stage, before closure. It uses real
historical API/services and MockHTTP. It must not call current blocked execution
services, insert hand-built receipts or copy a partial row subset.

Proposed files:

- `tests/two_brand_receipt_retained_fixture.py`: owned engine/lifetime, strict scalar
  decoding, current graph/identity checks. No callable historical runtime returned.
- `tests/fixtures/retired_execution/two_brand_receipt_seed_driver.py`: fixed scenario,
  imported literal historical app/tests, bounded child and output.
- `tests/test_two_brand_pilot_current.py`: both current counterparts.
- `tests/test_two_brand_receipt_source_guards.py`: source/target/output boundaries.

The driver accepts only an existing owned disposable target and a nonexisting output
file inside its owned artifact root. Scenario is fixed (Google activation for A,
Meta/HubSpot unrelated B); no provider/method/module/node/SQL/URL selector, arbitrary
input JSON, policy override, execution mode or alternate source pin. Target rules:
SQLite existing owned regular nonsymlink file, FK enforcement on; PostgreSQL approved
loopback disposable database plus exact random `inlet_test_<32hex>` schema. Reject
nonempty target before source writes. Parent installs actual current DDL first,
including constraints/triggers, and checks its physical schema fingerprint before
and after child execution. No schema downgrade, mapper fallback, trigger removal or
parent-side repair of finance rows.

Child validates literal PIN plus app/tests trees using `tests.retired_snapshot` and
its own imported package paths. A dedicated SourceLifetime profile must pin the new
driver/caller; existing bounded subprocess reaping and schema/target utilities may
be reused only with unchanged contracts. If current DDL rejects the authentic
producer, preserve that failure and resolve a narrow fixture/schema compatibility
proposal; never fill missing columns with fabricated authority or disable guards.

Driver output: exact-key, bounded JSON scalar manifest (maximum16KiB), version and
literal source identity; exactly two brand entries with integer workspace/account/
integration/store IDs, actor/goal/draft/source-connection IDs, fixed CRM/platform,
goal/draft revisions/digests; A's provider mandate/revision, consent, ledger,
creation/activation review and run IDs/digests, reservation ID and one exact owned
activation attempt/receipt ID+digests; bounded expected graph row counts/digest and
provider POST counts. IDs validate strict types/lengths; booleans cannot pass as ints.
No cookies, tokens, session digests, provider response bodies, callback functions,
engine, client, identity provider or media-store object crosses the child boundary.
Output is an index into the retained owned database, not a authority proof.

The entire graph stays in that database: owners/memberships, both source/store/account
chains and goals/drafts, immutable provider mandates/consents/ledgers, source media
metadata and bytes, creation graph steps/attempts/receipts, separate activation,
exposure reservation and dependent evidence. Owned media resides at a fixed child
artifact subdirectory; parent opens a current LocalMediaStore there after verifying
regular paths/hashes. Never export/import selected financial rows or relabel an
execution snapshot as a current producer.

Current consumer:

1. Validate every manifest reference against real rows, scopes, original source and
   receipt/request digests; validate full graph inventory and unchanged schema.
   Record immutable finance/request/receipt/reservation snapshots, not just counts.
2. Historical sessions are not reused as current credentials. Create two current
   sessions through actual login with the original stored issuer/subject/email;
   assert the returned user IDs exactly match retained owners. No identity rewrite,
   membership reassignment or direct session insert. Original historical sessions
   can be revoked through the ordinary test-owned session lifecycle; no live grants.
3. Read A's exact retained receipt through current `read_owned_outcome_receipt`:
   original A succeeds; B under A workspace and B under B workspace both fail.
4. Use current assembled HTTP closure-preview and exact confirm revision/inventory
   digest for A. Assert `closed=false`, `data_erased=false`, retained held reservations,
   current owned closure status200, foreign closure403/404. A's receipt remains
   readable after closure request, and every protected financial row/digest remains
   unchanged except explicitly inventoried closure/quiescing state transitions.
5. B still reads its own goal and HubSpot source; add its current planning read from
   a legitimately generated current plan if schema-compatible. No provider writes
   during current consumer: install tripwire transports where relevant, compare
   recorded attempts/receipts and request counts. Do not report the child's server
   count as proof that the parent made no calls.

This split does not claim current activation, a restored execution feature, or that
closure erased finance/history it must retain. It preserves the positive current
privacy/closure assertions over authentic historical records.

## Helper Coordination and Evidence Gate

The archive/privacy owner (`google_runtime`) confirmed its source is a different
fixed graph: two-brand Meta/Google optimization plus funded replacement and Meta
social confirmation. It is **not** compatible with this creation/activation source.
Do not broaden that producer or share a runtime/mode selector. Only independently
reviewed low-level lifetime/owned-target/schema primitives are candidates for reuse.

After review, run only new historical2 and focused current counterparts/boundaries
on both databases, with durations and preserved terminal logs. Cover wrong pin/tree,
foreign/nonempty/symlink target, malformed/extra output fields, foreign IDs, dropped
receipt/media, child failure/timeout and fresh-session ownership. Include physical
current-DDL equality and a changed-graph negative control. No aggregate or unrelated
historical rerun. A500MiB free-space preflight applies before heavy work; preserve
unique DBs, manifests and evidence, remove only verified disposable duplicates.

Current checks for this proposal: repository/code inspection and `git diff --check`
only. No implementation/tests executed. Neither original failure identity is closed
by this proposal. Root review precedes implementation; registry/coverage changes must
be coordinated with concurrent archive/fresh-pilot lanes rather than overwriting them.
