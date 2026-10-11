# Private Creative Image Collection V1

Preparatory server-only envelope, not a document/API schema or runtime activation.
Extend the reviewed owned image reader without weakening original-session, paid,
goal, privacy, byte/hash/decoder, final row identity or deadline checks.

Add a dependency-light `creative_image_collection.py` with strict frozen values:

- `PlanningImageRowPinV1(witness:OwnedPlanningImageV1,created_by:Id)` records all
  observed owned row fields. `identity()` returns the complete row identity,
  excluding only observed_at; created_by and created_at are mandatory.
- `CollectedCreativeBasisV1(basis:CreativeBasisV1,rows:tuple[PlanningImageRowPinV1,...],
  ticket_digest:Digest)` requires exactly one ordered row for every basis image,
  exact witness equality (including original observed_at), no extra/missing rows,
  and the same bounds as the basis. The empty selection still has an envelope.
- `assert_ticket(ticket:GenerationTicket)` revalidates both values, requires the
  exact full ticket digest, and checks basis.requested equals the explicit saved
  ticket.inputs.creative; workspace, goal currency and privacy must also match.
  No canonical policy registration is implied. Use local/TYPE_CHECKING ports imports
  to avoid a future PlanVersion import cycle.

Expose `OwnedPlanningImageReader.collect_pinned(ticket,requested)` returning this
private envelope. Require explicit saved creative input and exact requested
identity before any provider/storage I/O. Call one shared collection implementation,
not two inspections. It returns the actually observed basis plus original complete
row pins, after existing final row checks; pin witnesses carry the final image
inspection times. Bind the full original ticket and assert it before returning.

Preserve `collect(ticket,requested)->CreativeBasisV1` and its existing standalone
semantics for current callers. Refactor `_Row` only as necessary; do not duplicate
security-sensitive collection logic. Neither method starts persistence, grants
finalization authority, or claims current/permanent blob availability, visual
suitability or rights. Raw bytes are not returned or retained.

Future SQL finalization must independently compare every pinned metadata field
under its own transaction and original session/goal/paid/privacy guards; this
package does not implement that finalization or historical proof persistence.
Do not expose creator/session/ticket data in public plan evidence.

Tests: ordered/multiple/empty pins; full ticket/input/hash/workspace/privacy/currency
binding; creator/time-only tampering; copied-model revalidation; collect compatibility;
original-session actual SQLite/PostgreSQL pinned collection; unchanged no-I/O-in-SQL
and bounded collection behavior. Run whole Ruff/configured mypy. No service wiring,
policy/default changes, migrations or live operations.
