# Private creative image collection — 2026-10-11

Isolated child of `d7f09f8`; implements only the reviewed private collection port.
No API, policy registry, service finalization, public evidence, persistence schema
or runtime activation changes.

New dependency-light `creative_image_collection.py` contains:

- `PlanningImageRowPinV1(witness, created_by)`. `identity()` revalidates copied
  objects and returns all witness fields plus creator, excluding only observed_at.
  In particular creation time and creator are retained and compared.
- `CollectedCreativeBasisV1(basis, rows, ticket_digest)`. Rows exactly equal the
  complete ordered basis witnesses, including their inspection observation times.
  Empty selections still produce an envelope. `assert_ticket` locally imports the
  ticket type, revalidates both values, checks its full digest and explicit saved
  creative input, workspace, goal currency and privacy. A subprocess regression
  verifies importing the envelope module does not import ports.

`OwnedPlanningImageReader.collect_pinned(ticket, requested)` rejects missing or
substituted ticket creative input before identity-provider or storage I/O. Both
public methods call one `_collect` implementation. Existing session/role/paid/
goal/privacy checks, no-storage-I/O-in-SQL rule, byte length/hash/image decoding,
complete row comparison, clock reversal and 60-second deadline checks remain.
Rows in the envelope use the original creator and creation time plus the actual
final inspection-time witnesses. The final checkpoint runs after envelope binding.
The legacy `collect(ticket, requested)->CreativeBasisV1` still supports its existing
standalone request semantics; pinned collection does not weaken those checks or
inspect selected bytes twice.

## Evidence

`/workspace/inlet-evidence/20261011/creative-image-collection` retains logs/JUnit.
Initial `sqlite01`: 15 passed, 7 PostgreSQL cases deselected, 6.88s. New tests cover
pure binding/order/creator/time tampering, actual empty/single/multiple collection,
exact original identity refresh outside SQL, one inspection per image, unchanged
standalone collection, pre-I/O input refusal and mid-read creator/time/session
changes. Database fixtures use actual owned upload, confirmed goal and original
session; ticket creative input is explicitly constructed for this private port,
not claimed as a new public saved-input/generation journey.

Final qualification includes the entire unchanged owned-image reader guard suite
on SQLite and per-test-isolated disposable PostgreSQL. This covers privacy, goal,
paid/session/member changes, malformed bytes, decoded metadata, reverse clocks,
bounded collection and error classification. Final `both01`: **106 passed, zero skipped, 154.88s**, terminal exit 0.
Command: `pytest tests/test_creative_image_collection.py tests/test_owned_planning_images.py
--basetemp=/tmp/inlet-creative-collection-both01 --junitxml=<evidence>/both01.xml
--durations=20`, using the existing disposable PostgreSQL test database with
per-test isolated schemas; no database reset. Final whole `ruff check .` passed;
configured `mypy --cache-dir=/tmp/inlet-creative-image-mypy` passed all **1381**
source files; `git diff --check` passed. The initial `mypy01.log` retains two
new-test callback return-typing failures; explicit Session/bytes assertions fixed
them, with final results in `ruff-final.log`, `mypy-final.log`, `diff-final.log`.
No pytest failure occurred. No previous evidence was removed.

Future finalization must independently recheck original authority, goal, paid
access, privacy and every pinned metadata field under its own transaction. This
envelope neither guarantees permanent blob availability nor establishes visual
suitability, rights or publication approval. Creator/session/ticket data remains
private. No live services, Full, hosted CI, remote push or deployment occurred.
