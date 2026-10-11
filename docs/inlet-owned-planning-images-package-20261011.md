# Standalone Owned Planning Image Reader — 2026-10-11

Base `38ecf1c`, with reviewed standalone creative DTOs. Implements the approved
[owned-image reader interface](design/planning-owned-image-reader-interface-v1.md).
Only production addition: `app/planning_documents/creative_basis_reader.py`.

## Frozen Port And Behavior

`OwnedPlanningImageReader(sessions, *, principal, provider, store, clock)` exposes
`collect(ticket: GenerationTicket, requested: CreativeInputV1) -> CreativeBasisV1`.
`PlanningImageUnavailable(ValueError)` has a fixed sanitized message.

The constructor copies the loaded original identity. Collection validates the
original ticket actor/session and uses fresh `PlanningReadContexts` before/after
storage. Those contexts check identity outside SQL and authority after lock waits.
Both passes check paid access, exact current confirmed goal and ticket privacy.
Selected rows are scoped and ordered, including creation actor/time in their private
comparison. Strict metadata and total-library bounds apply before any storage read.

Every private `read_exact` runs after the reader SQL context closes. Returned values
must be exact bytes with matching length and SHA256. Video is rejected; the existing
bounded image inspector must agree on MIME and dimensions. Observation time is
recorded after decoding; raw bytes are absent from the result. Final fresh rows must
match all initial metadata. Empty input still checks both authority contexts.

Cooperative monotonic checks bound collection to60seconds and reject backwards
monotonic/observation clocks, including after final context exit. They do not provide
hard cancellation of blocked storage. Known goal409/image413/422 failures become the
fixed media error; auth/payment and unexpected HTTP failures propagate. Storage
OSError and expected validation errors expose no private paths or raw error text.

No caller commit, storage mutation, advertising access, current API/policy/composer,
persistence or archive wiring is added. Requested inputs are not yet bound to a
saved plan. Integrity at observation time is not perpetual storage availability,
product depiction, image suitability, rights or provider approval.

## Qualification

Actual owned upload, private local bytes, original customer identity, confirmed goal
and fixture billing reconciliation are used on SQLite/PostgreSQL. Only fixture
provider behavior/storage is injected; no ready media witnesses or authority guards
replace the production reader.

Evidence: `/workspace/inlet-evidence/20261011/owned-planning-images/`.

- SQLite initial29cases passed, zero skips,16.430seconds (`sqlite.xml`).
- PostgreSQL30cases plus added SQLite empty-input authority case passed:31, zero
  skips,74.554seconds (`postgres-plus.xml`).
- Additional two-image/identity-I/O and post-final-context deadline cases passed
  on both databases (`final-boundaries.xml`); typing-refined rerun passed4cases, zero skips,5.204seconds
  (`final-boundaries-typed.xml`). All32unique scenarios passed on both databases.
- Coverage includes missing/foreign selection/hash, metadata bounds, byte type/size/
  digest/decode/MIME/dimensions, row deletion/actor/time changes during I/O,
  privacy/goal/session/role/payment changes, zero-image revocation and clocks.
- Initial mypy test-annotation failures were fixed; failed logs retained. Final
  whole Ruff and configured mypy passed (1,373 source files); diff check passed.

No live calls, default runtime activation, remote push, hosted checks, merge or deploy.
