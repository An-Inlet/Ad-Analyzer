# Offset-aware catalog receipt scalar repair

Q05's actual target-catalog API request used its original New York September
reporting timestamps. SQLite discarded their offsets when persisting DateTime
columns, and the strict historical reader interpreted reloaded naive midnight as
UTC. Immediate retained receipt validation correctly rejected the mismatched
instant. This defect is distinct from the earlier unexplained PostgreSQL browser
409; it does not diagnose that original failure.

The narrow correction converts all six SQL receipt timestamp scalars to UTC before
persistence and normalizes expected timestamp comparisons/min/max operands to UTC.
Canonical inventory/metadata payload, original offset representation, payload hash,
composite digest and schema are unchanged. No authentication freshness threshold,
source fence, integrity check, historical row repair, or migration is introduced.
Existing corrupt/stale rows remain fail-closed; normal fresh reads can create new
receipts. No fixture timestamp normalization hides the Q05 request.

Evidence lives under `/workspace/inlet-evidence/20261011/creative-q05`:
- Initial Q05 `sqlite-01` omitted a real fixture router (404), fixed by registering
  the ordinary route. `sqlite-02` omitted Google mock token delegation, fixed only
  for exact OAuth token POST alongside exact read-search endpoints.
- `sqlite-03` reached the actual receipt integrity409. Narrow `catalog-04` retained
  HTTPException→CatalogReceiptUnavailable(integrity_unavailable)→scalar mismatch.
- Diagnostic `catalog-05` had an observer import typo, retained as collection error.
  Corrected `catalog-06` proved only reporting-start/end instant comparisons false;
  observation/expiry/creation comparisons true. No raw payload or auth retained.
- Focused `receipt-utc-before-01` reproduced409 with the new actual API regression
  before production edits. `receipt-utc-after-02` passed SQLite after the repair.
- `receipt-utc-both-03`: six cases passed on SQLite/PostgreSQL: new offset API
  regression, unchanged UTC save/generation path and unchanged scalar/payload
  tamper denials. Final regression uses a fixed -04 offset (not season-dependent
  ZoneInfo) while preserving actual wall/auth clocks.

The regression reloads via a new Session and expires its identity map; asserts
exact UTC scalar instants, original -04 payload timestamps/canonical bytes/hash;
then saves and generates through actual selection APIs without further native IO.
Q05 fixture/artifact qualification is separate and still pending at this repair.

Final evidence: six-case compatibility/tamper cohort passed22.688s; fixed-offset
regression2cases passed9.288s; added explicit detached reporting-start+1hour
corruption denial2cases passed9.109s. Canonical payload/hash stays unchanged even
on rejected detached corruption. Whole Ruff and configured mypy passed (1418files
in this worktree, including two uncommitted Q05 fixture/test files); diff passed.
The repair commit contains only receipt implementation, focused regression and
this ledger. No Q05 success or original browser409 resolution is claimed.
