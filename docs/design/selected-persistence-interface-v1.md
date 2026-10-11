# Selected Reporting Persistence Interface V1 — 2026-10-11

Reviewed baseline: shared contracts68b96b7, raw parsers1e69125. This is the interface
for the next offline package, not a deployed customer feature. No API can accept a
client-authored ReportingScope or provider-ownership assertion. Keep old V3 and
canonical aggregate equality unchanged.

## Package Boundary

Reserve Alembic0091 centrally for four scoped tables: immutable customer-event
selections, CAS current-selection heads, immutable selected captures, immutable
selected campaign/day facts. Use the reviewed contracts as canonical payloads;
store indexed scalar scope/dependency/digest/byte fields and verify exact agreement.
Composite account/workspace/connection, selection scope, aggregate scope and
campaign/account FKs must prevent foreign joins. Confirming customer IDs are UUIDs.
New data is erasable workspace data; no financial-history classification or new
retention duration. Immutable UPDATE refusal, scoped deletion invalidation and
strict complete-graph export/erasure belong in the same package as registration.
Use frozen migration DDL, never imports of mutable application model code; refuse
lossy populated downgrade. Test SQLite and disposable PostgreSQL only.

This package implements internal storage/validation ports; it does not activate
public selection confirmation before an observed owned event catalog exists.
No name/goal/default/pixel/aggregate inference can supply catalog proof.

## Ports And Caller Obligations

- `store_selection(db, selection, expected_selection_id, expected_selection_digest)`
  writes a server-created immutable CustomerEventSelectionV1 and atomically advances
  the account head under workspace/account locking. Both expected values are null
  for first confirmation. Exact current replay returns the stored graph unchanged;
  changed expected binding conflicts without partial writes. Reused selection ID
  with changed bytes always rejects. No caller commit. Original session/owner role,
  provider catalog option and latest scope must be proved by the calling service
  before this port is exposed to customers. Storage independently checks account,
  connection, native source/generation/privacy and confirming member bindings.
- `read_selection(db, workspace_id, account_id)` returns the exact immutable current
  selection or unavailable; revalidate current ownership/source/privacy rather than
  adopt a new scope. This internal reader is not session authorization.
- `store_selected_capture(db, capture)` accepts only a complete bounded graph tied
  to the exact current owned aggregate and stored current selection. Recompute the
  entire aggregate manifest/current source binding and selected request/fact graph;
  reject different replay. Validate all native/local campaign mappings and periods.
  Insert header/facts atomically in the caller transaction. No independent mutable
  current-capture pointer. No provider or session authority is inferred from DTOs.
- `read_selected_capture(db, workspace_id, account_id, capture_id)` verifies complete
  graph, scalar/payload/digests/counts and exact current selection/aggregate/native
  source/privacy. Any changed dependency fails closed; no stale fallback.
- Export validates the historical complete immutable graph under the existing
  archive snapshot/privacy fence, without falsely labelling it current. Erasure
  removes all new data under existing workspace lifecycle locks and invalidates
  dependent outputs/prepared exports. No new retention policy.

Currentness validation must reuse or factor existing proven account/source checks;
never bypass manifest/current-pointer, native ID, currency/timezone, generation,
status/error, integration status or sync-time checks. Public wrappers, when added,
will require original customer session checks before/after I/O and at final commit.

## Privacy Transition Decision

Use the existing privacy counter; do not create a second export/privacy epoch.
Invalidate obsolete selected/derived evidence under existing locks, then read the
final counter before a new confirmation. If invalidation advanced it, a genuine
aggregate refresh and explicit confirmation against the fresh scope are required.
Never rewrite old completion/selection privacy or silently rebind old selected
facts. Internal storage rejects stale pre-invalidation scope. A future customer UI
must show Refresh Required/Confirm Reporting Event, preserving historical choice
as history only. No new owner approval is needed for this fail-closed engineering
behavior; product usefulness remains subject to the established human review gates.

## Dependencies Not Claimed By This Package

Catalog acquisition and customer confirmation routes; original-session orchestration;
Google/TikTok HTTP page/staging integration; actual query/API capability; privacy
transition retry UX; immutable August/September range provenance; customer plan
consumer and comparator. Storage fixtures are not Q01/Q02/provider qualification.
No publication/ad-account mutations, live calls, spending authority or changes to
existing recommendation/forecast/budget semantics are introduced.

## Implemented Explicit Invalidation Transition (0091)

The mutable current head has an exact boolean `invalidated` flag. Under the
workspace→account fence, `invalidate_selected_account(db, workspace_id, account_id)`
changes an active head to invalidated, erases its captures and account calibration
outputs, and advances the existing workspace export/privacy counter transactionally.
Repeated invalidation is a no-op. The caller commits this transition before a real
aggregate refresh and explicit new confirmation; a failed confirmation must not roll
back the already requested invalidation. Old immutable choice bytes are not rewritten.

Replacing the head requires its exact previous ID/digest, an invalidated head, and a
new selection ID whose canonical scope matches the actual current privacy counter,
owned account and active integration/source generation. Database predicates enforce
these conditions independently of the service: raw active A→B and stale A→B→A are
rejected. Deleting a head erases its capture graph and fences prepared exports.
Historical export labels retained choices/captures as historical, never current.

Internal storage does not authenticate a browser session. Future public callers must
hold/recheck the actual original session and owner membership using existing customer
access fences; `confirmed_by_customer_id` alone is not authentication. No caller may
use these ports as a replacement for an owned event catalog or provider capability.

Export validates each complete capture once per read-only snapshot transaction,
then indexes its bounded facts. It retains only one capture index, rejects a changed
transaction, and uses primary-key capture ordering. Delivery still passes the existing
workspace privacy guard. No retention period or expiration policy is introduced.
