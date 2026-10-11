# Retained Capture Boundaries After Acceptance08

Source-only assessment at `6df589b`; no implementation, tests or diagnostic execution.
Parent evidence: changed-source uninstrumented Acceptance08 first SQLite zero case
failed409 `planning_authority_expired`, request17.30s/process24.831s;27 cases unrun.
No observer was active, so failing guard location, fact age and phase costs are unknown.
It must not be assigned the previous pre-CAS or post-flush failure location by analogy.

## Exact Capture Chain And First I/O

| Boundary | Pure validation before this boundary | First DB/extension access and consequence |
| --- | --- | --- |
| `retained_sources.capture_retained_sources` | Full PlanVersion at entry; exact V6 dispatch. | No SQL before entering owner wrapper. Its existing exception mapping surrounds the delegated call, not the initial model validation. |
| `capture_owner_review_retained_sources` → `_Context` | Another full PlanVersion and exact owner pair/creative-policy/time checks. | `_Context` next reads Session transaction state and `db.connection()`; connection acquisition can invoke engine hooks. `context.guard()` then invokes customer guard, goal refresh, privacy/time SQL, guard again. |
| Owner `_owner_evidence` | Original input checks and retained receipt validators. | `_validated_retained_input_receipts` reads saved input, input links, actual receipt rows, retained receipt integrity. Entire results are new SQL-derived data, not covered by entry document parsing. |
| Owner → `_capture_creative_retained_sources` | A new `_Context` fully validates document. | This is AFTER owner guard and original-receipt reads. Reusing the initial parse would cross SQL/callback boundaries. Shared context then guards again. |
| Creative → `capture_selected_reporting_sources` | Another full PlanVersion at entry. | Already after creative guard SQL. Selected helper obtains root, guards, reads privacy/time/goal, derives current selected/traffic proof, creates witnesses/commerce, derives proof again and final guards. Both proof passes remain. |
| Creative → `_capture_creative_retained_source` | Full PlanVersion, creative policy/proof and time checks. | Already after selected SQL proof. It obtains transaction/connection, independently guards and compares actual image metadata. Earlier document checks cannot be reused across this boundary without a new ownership/mutation contract. |
| Creative result → `_creative_local_witness` / owner final | Pure witness/document comparisons interleaved with guards. | Prior SQL and current image proof separate these from original parse. Owner re-reads original receipts and guards; this cannot reuse first receipt data. |

The one plainly adjacent full-document duplicate before ANY SQL is top dispatch's
PlanVersion parse followed by owner `_Context`'s PlanVersion parse. Replacing this with
an invocation-private checked-document/context handoff can remove one parse while
retaining direct public entry validation. It also needs to preserve the distinct raw
initial error versus delegated normalized error locations and reject unsafe copied
values in every public entry. This is technically plausible but is another small
local reduction, with no evidence it provides sufficient margin. It is **not** the
recommended next stand-alone run-and-retry package.

The larger repeated parse count is mostly separated by actual SQL or extension
boundaries. Moving the same checked context through those boundaries would require
deep ownership plus mutation checks or a revised trust contract. Labeling that reuse
'private' does not make it safe automatically. Do not turn this call map into a plan
to delete all repeated validators.

## Concrete Query-Batching Candidate And Its Limitation

`catalog_receipts._validated_retained_input_receipts` fetches each actual linked receipt
with `db.get(..., populate_existing=True)` inside a bounded <=20-link loop. One scoped
`SELECT ... workspace_id=... AND id IN (...)` with populate-existing, exact cardinality,
explicit original link ordering and unchanged per-row validation could batch these
row fetches **within each individual call**. No cross-call cache is needed; both owner
receipt passes would issue their own batch. Missing rows, duplicate links, ownership,
opaque commitments and immutable catalog parsing must still be checked separately.

This saves at most19 receipt-header round trips per call; a single-account/receipt
zero fixture saves zero. Retained receipt validation may still execute its own queries.
It is not a demonstrated explanation or meaningful remedy for Acceptance08. The supplied
measurements do not attribute the hundreds of other SQL calls sufficiently to justify
another batching implementation. Normalizing query count alone is not latency evidence.

## Recommendation: Stop Tiny Acceptance-Retry Slices

No source-proven **meaningful enough** reduction is identified under the present rule
that all cross-SQL parses/currentness passes remain untouched. The adjacent dispatch
parse and bounded receipt batch above are safe candidates for future maintenance,
not a credible claimed resolution of the normal five-second acceptance failure.
The actual flow remains unqualified. This does not prove five seconds is impossible
on every machine or input; it means our tested bounded workload is not reliable enough
to declare completion, and repeated successful probes cannot establish that reliability.

Choose one coherent engineering redesign proposal next, before code or another run:

1. **Original-graph pure validation before the existing refresh.** Return to the reviewed
   preparation envelope with a strictly limited, concrete model-specific implementation,
   not a generic102-model bypass. Preserve provider-error precedence with original entry
   validation for unsupported/invalid graphs; prove full ownership of candidate, ticket,
   actual bundle and callback candidate. Original current SQL/receipt/selected-image-
   selected/retained validation stays. Before implementation, enumerate exactly which
   model-specific pure checks move and which remain. The previous conservative fallback
   may retain most expensive work; do not advertise savings until that inventory shows
   material removable cost. No new fact or deadline is permitted. This remains routine
   engineering requiring technical review, not an owner request for weaker protection.
2. **Reduce mandatory work structurally while retaining semantics.** A larger reviewed
   validation architecture could replace repeated nested whole-document parsing inside
   each *fresh* pass with strict per-domain validated inputs, scoped to that invocation.
   This requires explicit ownership/type/error-phase invariants and complete public-entry
   validation; no hidden cache. It is more consequential engineering than one duplicate
   removal and needs a full source contract before any code. It must still prove every
   current SQL-dependent invariant, not merely trust prior hashes.
3. **Authority architecture change, only by owner decision if needed.** A renewed fact,
   longer max age, asynchronous commit or removing a fresh pass changes the accepted
   authority model. These are not authorized remedies. If options1/2 cannot provide a
   defensible design, bring measured bounds and precise changed threat/acceptance criteria
   to the owner. Do not ask for a generic performance waiver or infer permission from
   the product deadline. Recommendation remains preserve the current guard pending an
   explicit decision; reject expired work atomically.

The next technical decision should choose and review a coherent option1/2 implementation
boundary; no additional tiny fix plus full28 retry is recommended by this assessment.
No new owner decision is required merely to conduct that source/design work. No live
account access, credentials or provider approval can solve this offline blocker.
