# Selected planning input foundation — 2026-10-11

Base: `6b6c272`. This implements step one of the frozen
`selected-plan-evidence-interface-v1.md`, with no new table or runtime activation.

`planning_documents.selected_inputs.SelectedCaptureSelectorV1` carries only a
strict local account ID and opaque capture ID. Both CustomerInputs and
PlanInputRevision retain `selected_reporting`: None is legacy, an empty tuple is
explicitly no selected captures, and nonempty tuples select at most20 unique
included accounts. These selectors carry no provider proof or currentness claim.
The actual prepare/resolve path retains the exact tuple and refuses a mismatched
prepared/intent tuple. Existing input revision and request receipt commitments
therefore bind it without a transient GeneratePlan field.

Wrap serializers omit only the new field when None, including nested Python and
JSON serialization. Golden hashes captured before edits on6b6 prove unchanged
Python dumps, model JSON bytes, canonical JSON and digests for an old input,
CreatePlan request and complete nested PlanVersion. Defaults remain present just
as before; explicit empty/nonempty fields remain serialized and change digests.
Unsafe copied nested selectors fail revalidation at the existing digest boundary.

The exact v4 policy/generator constants are reserved but not registered. Matching
legacy v1/v2/v3 pairs reject non-None selectors at input save and generation,
with direct legacy composers guarded too. Current legacy creation rejects before
native catalog IO. Historical reads are unchanged. Unknown/mixed pairs and v4
remain unavailable through the unchanged capability registry. There is no selected
reader, witness, recommendation or customer-visible v4 generation claim here.

## Evidence

Durable evidence: `/workspace/inlet-evidence/20261011/selected-inputs`.

- `legacy-golden.txt`: pre-edit hashes from untouched6b6c272.
- `pure01`:63 passed,3.588s; `final04`:108 passed,12.291s including existing v1/v2
  and requested-window composer regressions and direct selected-input rejection.
- `api02`:2 SQLite API cases passed4.398s; `api03`:2 SQLite cases passed3.982s after
  adding actual internal input-writer/immutable-row/request-receipt retention.
  Both explicit empty and nonempty selectors are rejected by actual legacy HTTP
  with no native requests or new input row. Internal prepare/resolve/save/read
  retains them exactly; that test does not activate a generator or public API.
- Whole Ruff passes (`ruff05.log`); whole mypy1310 passes (`mypy04.log`);
  `git diff --check` passes. The intermediate import-format finding is retained.

No live calls, remote actions, schema changes or aggregate qualification runs.
After the publisher released PostgreSQL, `pg06` passed both PostgreSQL cases
with zero skips or failures. The final package has108 pure cases plus4 actual
SQLite/PostgreSQL API and internal persistence cases passing. The slot was
released after completion.

## Independent typed-document review repair

The reviewer found that service/composer rejection alone left the typed legacy
PlanVersion parser able to accept selected inputs. The document validator now
rejects non-None selectors for every exact legacy v1/v2/v3 pair, including
historical/export parsing and unsafe-copy digest calls. Draft input persistence
remains allowed; the nested serialization positive uses a non-authorizing input
wrapper rather than an invalid legacy plan. Six Python/JSON/digest negatives and
all legacy golden/composer tests pass in `review07` (114 cases). Whole Ruff and
mypy1310 pass in `*07.log`. No database/runtime interfaces changed in this repair.
