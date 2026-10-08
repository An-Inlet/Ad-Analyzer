# Exact Catalog Receipt Runtime Integration

This package connects reviewed schema0088/helpers/archive behavior to the existing
V2 catalog endpoint and customer planning service. V1 is unchanged. The V2 route copies
loaded identity before closing its authentication transaction; runtime identity/native
IO occurs outside SQL transactions. A separately committed owner-authorized maintenance
transaction removes at most100 expired unused receipts before native IO. Final original
source/privacy/session/expiry checks atomically save complete receipts and selectors.
Disabled feature/future-window checks follow owned workspace authorization.

Target-bearing create/edit resolves the exact submitted snapshot, applies ordinary input
validation, and atomically saves immutable input plus receipt links. A second request
receipt lookup under the final lock preserves concurrent same-key replay without adding
links twice. Generation reuses targeted-account receipt catalogs with original deadlines;
other accounts still read normally. Final commit rechecks saved receipt/input bindings
alongside actual reporting/commerce evidence. Same-owner new sessions can read history
but cannot newly use an old session's target receipt. No rebind or expiry extension occurs.

The generic evidence reader retains legitimate pre-persistence no-target collection.
Target-bearing tickets always require the actual saved input/receipt graph. Existing
persisted no-target tickets also validate complete empty links; core final persistence
rechecks the actual input even for the generic pre-persistence path.

Executed checks:

- Actual HTTP V2→read-again→original selection→create→generate→replay→new-session denial:
  **12 passed in53.18s**, allocation/exclusion × all3providers × SQLite/PostgreSQL.
  Targeted generation makes no additional native request; exact original references remain.
- SQL transaction instrumentation: **2 passed in5.70s**, actual identity and native HTTP
  callbacks run outside SQL after route authentication rollback on both databases.
- Mixed Google retained selection + fresh Meta account generation: **2 passed in8.25s**,
  both databases, only the untargeted account makes new native reads.
- Actual PostgreSQL concurrent same-key targeted creation: **1 passed,1 expected SQLite
  concurrency skip in4.26s**; one plan/input/receipt-binding graph and identical results.
- Existing V2 metadata adversarial API, customer planning API and concrete evidence-adapter
  compatibility cohort: **206 passed in230.33s**. Historical-clock fixture was advanced to
  current server time because receipts must respect the actual database expiry clock.
  Initial compatibility attempts exposed that fixture issue (1failure), then authorization
  ordering for foreign workspace with disabled feature (1failure/3passed); production
  ordering was repaired and the final full affected cohort passed. Both failed logs retained.

Evidence prefix `/workspace/inlet-evidence/20261008/catalog-receipt-runtime-` with
initial/io/mixed/race/compat[-current,-authorized] logs and XML. No Full suite, live provider,
remote operation, deployment or target-selection browser acceptance is claimed here.
Independent review and root integration remain separate gates.

Final whole Ruff/mypy1064 and diff checks passed. A test-only explicit import fixed a
mypy module re-export complaint; its affected actual IO cohort reran **2 passed in4.47s**
(`io-final`). Earlier inferred empty-tuple annotations were corrected without runtime
behavior change. Capacity errors now clearly say that additional reads are unavailable
while existing plans remain preserved; other stale selection errors require fresh reads.
