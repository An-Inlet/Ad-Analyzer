# Q13 Field Comparison Boundary

Q13 requires customer report/correction/retraction history to remain separate from
independent exact/partial/conflicting/unavailable reads. Matches do not prove who
changed a setting, when, delivery or business lift. Current code has reserved
`ReadObservedStatus` storage/read contracts but no production supported `ProposedField`
constructors, qualified field-read producer or observation writer. This package is a
pure boundary and read-only rendering prerequisite, not full Q13 acceptance.

## New Pure Interface

Preserve existing event DTOs/bytes/digests. Add normalized `FieldFactsV1` containing
exact target, explicit extraction-contract identifier, original observation interval,
expiry and bounded unique typed values. A `FieldSnapshotV1` pairs those facts with
existing ObservationEvidence. Exact schema and facts digest must equal the source
reference; target and timestamps must match. This binds values to the normalized
snapshot bytes; it does not authenticate the provider or validate extraction semantics.
Missing fields stay absent; no coercion/default value. Duplicate field names or country
codes refuse. Country order and URLs compare exactly, without invented canonicalization.
No raw/effective status mapping is supplied by this interface.

`ComparisonAdmissionV1` supplies explicit server-side admission context: exact original
VersionBinding, current privacy revision, expected source binding, extraction-contract
identifier, event ID and completion time, all explicit inputs. It is ordinary pure input, not a capability or proof
that authorization occurred. Future service code must derive it from fresh original
session, paid access, current owned account/connection generation/privacy and an
independently qualified adapter, never browser JSON. No registry/default qualification.

The comparator revalidates document, admission and optional snapshot. Exact action
binding and stable full target identity/topology (account including connection generation,
provider reference, kind, canonical key, budget owner) must match. Snapshot selection
key, evidence key and display name may change. Native source binding and current privacy
must match admission; observation begins no earlier than plan generation and finishes
before comparison, which must precede source expiry. Each supported proposal gets
exactly one expected/observed pair. Absent snapshot/field yields fixed unavailable
reason. Additional known typed source fields without proposals may be present but never invent extra comparisons.
Unsupported proposals remain explicit limitations and never become numeric comparisons.
No supported proposals means unavailable, even if a snapshot has values.

Status precedence: any observed unequal value → conflicting; otherwise some observed
and some missing → partial; all supported observed equal → matching; no observed fields
→ unavailable. Output uses existing ReadObservedStatus; always no advertising authority,
causality not assessed, applied_by null and mandatory semantics/time limitations.

## Acceptance And Later Joins

Current ManualAction kinds permit one field with unique field names. Thus partial
and mixed supported/unavailable comparisons cannot arise from a valid current action.
Do not weaken that schema or forge a positive fixture. Multi-field admission is a
separate prerequisite for full Q13 partial-match acceptance. Pure tests cover reachable
matching/conflicting/unavailable statuses, unsupported-only actions, exact snapshot/digest/schema/
contract/privacy/source/ownership/topology/time refusals, absent versus zero-like/status
values, duplicate country/field inputs, exact ordering/URL semantics, unsafe model copies,
new plan inputs/versions, report/retraction independence and stable serialization.
Existing event/storage/history/export and DOM guards must remain compatible. Positive
fixtures are synthetic normalized evidence, not native producer qualification.

Before any writer: qualify exact field extraction from owned native reads; define no-SQL-
across-IO admission and original-session/source rechecks, atomic append-only observation
and idempotent result semantics; bind retained proof, erasure and reader-floor behavior;
add separate browser observation variant. Then qualify real API/database/browser joins
for observations alongside report edits/retractions/history/export. Do not seed a fake
producer into production to manufacture full acceptance. No migration, route, provider
call, status normalization, v6 activation or change to default planning in this package.
