# Pre-CAS validation census after diagnostics01

Source-only from diagnostic freeze d99b0ea. No executions, optimization, cache,
authority renewal or timestamp/guard changes. Diagnostics01 recovered generate /
pre_cas / fact_age_outside_window; session predicate was not evaluated. It did not
measure this call tree or attribute time/SQL to its members.

## Explicit PlanVersion validation call tree

The following is a static count of direct PlanVersion.model_validate calls on the
ordinary new V6 generation path through the pre-CAS guard, not a runtime total.
It excludes nested serializers/digests, model validators, conditional parent/history
loads and public V4/V5 wrapper branches not used by this genuine V6 path.

| Phase | Direct calls | Boundary after/between calls |
|---|---:|---|
| repository._generation_entry | 1 | authority.lock SQL/identity guard, receipt/head/input/parent SQL |
| _generation_owner_binding → assert_owner_review_generation_bundle → _linked | 1 | paid/goal/accounts/privacy SQL, then final_sources callback |
| final_sources → selected/image/selected rechecks → recheck_owner_review_input_receipts → _linked | 1 | resolve_saved_input_catalogs SQL occurs BEFORE this _linked; subsequent retained capture is separate |
| capture_retained_sources dispatcher | 1 | pure exact-policy dispatch into owner capture |
| owner capture → _Context | 1 | transaction/connection checks, guard/goal/privacy/time SQL, first _owner_evidence original receipt loads |
| owner capture → _capture_creative_retained_sources → _Context | 1 | after owner evidence+guards/time SQL; then shared creative guard SQL |
| capture_selected_reporting_sources | 1 | current source/reporting graph SQL, two fresh proof reads and guards |
| _capture_creative_retained_source | 1 | guard/goal/privacy/time SQL, actual media row locks/commitment checks |
| creative_currentness → _creative_local_witness | 1 | AFTER actual media/guard SQL; followed by final _guard/time SQL before return |
| shared creative orchestration → _creative_local_witness comparison | 1 | AFTER currentness function returned through SQL; then shared guards and second owner evidence SQL |

Thus ten explicitly spelled full document reparses are identifiable along these
named success-path calls. This is NOT a measured ten-count or complete cost count.
The last two witness validations are not adjacent pure duplicates: currentness
performs fresh SQL/guards between them. The selected/image/selected final callback
also uses fresh original fact/SQL guards; do not merge those passes.

Each genuine V6 PlanVersion coherent validator joins selected retained proof,
creative input/proof/time bounds and empty-catalog proposals, then calls
validate_owner_review_document with complete original linked catalogs. That helper
recomputes exact linked-catalog order and evidence joins, then the active owner
validator. The owner validator reparses input/actions/proof and derives/binds
owner evidence; public strict copied-instance boundaries remain intentional.
Existing per-domain owner kernels already reduce repeated pure derivation inside
exact checked model invocations. No new measured benefit may be assigned to them.

_linked always reparses ticket and candidate. Its already-reviewed same-argument
fast path skips only the immediate duplicate active owner review after exact
ordered source/input/privacy equivalence; it falls back for differences. Its
first pure invocation and second post-receipt invocation are separated by SQL and
callbacks, so cross-call caching/reuse would violate the existing contract.

_owner_evidence calls load_retained_owner_input_evidence, canonical full-catalog
comparison and retained owner validation. It runs twice around the creative /
selected currentness work. The second load is an intentional fresh original-row
and source commitment check, not a redundant pure call. A historical linked-only
source set cannot be replaced by active current sources or a fabricated epoch.

## Proven adjacent candidate and decision

Only the top dispatcher model_validate → owner _Context model_validate pair in
this map has no intervening SQL or explicit extension callback in current source.
This candidate is already known from the earlier wrapper assessment. A future
private checked-document/context handoff could eliminate ONE local duplicate,
provided public capture and _Context still strictly validate on independent calls,
wrong-policy/error ordering and copied nested mutation checks remain, and nothing
crosses the first transaction/guard boundary. No implementation is proposed now:
there is no measured margin showing this small change would make acceptance
reliable, and the parent explicitly stopped small-fix/retry loops. Do not simply
add a public validated flag or trust an arbitrary passed PlanVersion instance.

There is no newly proven adjacent duplicate in the deeper currentness/witness
calls that can be removed without crossing SQL/guard boundaries. Serializer-only
work inside owner Proof remains eligible for source analysis, but public serializer
mode/include/exclude/subtype compatibility must remain and the existing frozen
kernels already addressed the concrete supported pair. No additional optimizer
is justified by the new fixed-cause record alone.

## Bounded next investigation and remaining qualification

Next action can be source-only: produce an exact pure predicate/serialization
inventory inside ONE intrinsic owner-model validation, marking original public
entry, exact-type checks, private projections, fallback and canonical byte tests.
Approve an optimization only if the same local invocation proves duplicate work
with no callback/SQL/alias escape; otherwise retain the present source and report
that sufficient reduction is not established. A pre-refresh prepared graph is a
larger separately reviewed ownership/error-phase design, not an implicit fallback.
No new profiling/reproduction/test execution is authorized by this note.

The two sales-progress final_timeout nodes from diagnostics01 are genuinely
unrun, disjoint from the29passing cases and failed PGdelay. Prepare their separate
manifest from the same diagnostic production freeze using unchanged serial two-node
runner4581826. SQLite then PostgreSQL only on exact first pass, unique paths,
original exit before XML, repeated source/floors/sole-run checks. No recollection,
body, mypy or heavy check while Q12 owns the slot. Root must authorize this separate
qualification; exclude the failed PGdelay and all29passing nodes. Prior original
V6delay two-pass evidence and diagnostics01's new SQLite pass remain distinct.
