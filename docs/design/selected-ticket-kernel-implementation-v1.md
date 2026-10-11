# Selected ticket kernel implementation boundary

This supersedes the eighty-class runtime inventory proposal in selected-ticket-checked-kernel-v1.md. Pure prechange evidence is frozen at07c60d0: sixteen distinct successful cases, with the original extra-field hypothesis failure preserved. Six exact synthetic fixture JSON artifacts, their original digests, four original production source copies and reproducible capture script are in `/workspace/inlet-evidence/20261011/selected-ticket-kernel-baseline/`. No production edit yet.

## Scope and original order

Only selected_plan_bundle.py, selected_paired_evidence.py, selected_plan_local.py and selected_paired_local.py plus focused tests. All public signatures, every SQL-separated assertion, source/receipt/media/goal/paid/privacy/session check and five-second authority guard remain unchanged. No generic cache, prepared token, public context flag or new authority.

Selected public assert_ticket retains exactly its first type(self).model_validate then GenerationTicket.model_validate, and delegates the unchanged remaining invariant statements to a private function. Paired public assertion retains its same prefix. At the original nested selected.assert_ticket position, a private eligibility predicate may select the selected invariant body directly; otherwise it executes that original nested public call. Paired remaining invariants are a separate private body, preserving order without a trusted boolean argument.

Each reader keeps its original ticket validation then declared bundle validation once. Eligibility is evaluated on those actual returned values at the original assertion position. Eligible values use private invariant bodies; other values call the original bundle.assert_ticket(ticket). No restart of validation prefix and no extra custom callback on fallback. Public subtype dispatch uses original type(self); reader declared downcast remains its existing distinct behavior. Private return values remain ordinary local DTOs with no extended lifetime or authority.

## Callback-free scalar exclusion, not graph trust registry

Place one small private predicate in selected_plan_bundle.py, shared by paired code. Its only job is to exclude surviving custom behavior from the already mandatory validated domain. It does not validate fields or confer trust.

- Exact scalar types str, int, bool, NoneType, Decimal and date are inert leaves. Exact datetime is handled before date; obtain its tzinfo through the built-in datetime descriptor only. Permit exact datetime.timezone, exact zoneinfo.ZoneInfo and exact imported pydantic_core.TzInfo. No module/name duck typing, no datetime/tzinfo subclass acceptance, no utcoffset/fromutc/serialization/repr calls.
- Traverse exact tuples and resident BaseModel dictionaries only. Use the built-in BaseModel `__dict__` getset descriptor directly, bypassing custom __getattribute__ or a shadowing property. A non-model yields the descriptor's TypeError and is ineligible; do not catch unrelated unexpected exceptions. Require the returned resident dictionary to be exact dict and inspect only its stored values; no arbitrary getattr/property/serializer. A custom container or other scalar is ineligible.
- The only legacy model families lacking always revalidation in the frozen declared graph are GoalDefinition, MeasurementWindow, GoalSalesProgressV1 and ClosedDayCoverageV1. Encountered instances in these families must have the exact base type; subclasses select the original suffix. Inspect the class's built-in MRO tuple through type.__getattribute__ and identity comparisons, not overloaded equality or arbitrary instance attributes. This also catches a custom legacy serializer returning a nested model instance instead of plain values. Both goal windows, commerce target window and non-null coverage are naturally visited.
- Bound the walk to100,000 pending/visited values; on excess select original suffix, never reject a previously valid domain value. An empty tuple needs no identity tracking. Repeated nonempty model/tuple identities may conservatively select fallback (including cycles), rather than introducing a graph cache. No identities escape the call. Tests must verify genuine constructed and JSON-roundtrip fixture graphs actually use the kernel; a universally falling-back predicate is not a repair.

The predicate does not establish canonical model types from a generic isinstance check. That property comes from the unchanged mandatory declared parsing plus the reviewed three always bases and explicit legacy reparse/type boundaries. Tests freeze the annotated field/configuration closure and named legacy exceptions; future unknown/untyped field expansion fails those tests for review. There is no production eighty-class list or serialized projection. Unknown shapes are fallback, not new domain errors. These mechanics require independent source review before implementation.

## Test inventory and parity requirements

Use a test-only recursive annotation inventory (including Annotated/Union/tuple/Literal and named aliases) to freeze reachable model fields/configuration and the exact non-always legacy set; it must not become runtime code. Compare against the existing AST audit rather than claim an actual fixture samples every optional branch.

Focused patch tests must prove:

- Original synthetic JSON/digest baselines unchanged for selected, paired and V6 owner fixtures, including a JSON parse roundtrip whose builtin timezone is TzInfo. Genuine selected+traffic fixture uses eligible path and removes the documented immediate public reparses; all public entries still invoke mandatory validators.
- Exact-root public subtype behavior and declared reader downcast/order match original. The three extra-bearing nested subtype refusals stay exact. Same-fields nested subtypes still canonicalize normally. Unsafe copied bool/int/count/timestamp values reject before eligibility can grant anything.
- Non-null ClosedDayCoverage and nested legacy-window subtypes inserted by a custom document serializer select original suffix if they survive mandatory parsing; exact declared parsed coverage remains eligible. Test both original refusal/serialization errors and safe accepted models, without redefining legacy semantics.
- Stateful custom timezone and datetime-subclass cases: original common prefix executes once, ineligible suffix invokes exactly the old public call, and the same sentinel exception/order is preserved. No scanner timezone callback. Test a shadowed attribute/property object as an unknown leaf without invoking it.
- Walk bounds/cycles/custom containers select fallback, not refusal; exact fixtures do not fall back accidentally due identity reuse. No public trusted flag or external caller-provided scan result.
- AST expansion of extracted invariant bodies equals the original source remainder. Existing actual after-SQL source/media mutation, currentness/retained and delayed-rollback tests remain for the separately reviewed changed-runtime cohort; no removed guard or moved SQL statement.

No claim that the full measured0.685s is removable. Qualification must demonstrate actual dispatch/reparse count reduction and later bounded normal-clock generation/rollback acceptance on a coherent integration. This design does not close historical incidents or alter a deadline.
