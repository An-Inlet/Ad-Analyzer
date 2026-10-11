# Selected Fresh-Read Query Shape — Read-Only Inventory

Status: source inventory only, after the [cost assessment](../inlet-creative-save-cost-assessment-20261011.md).
No implementation, tests, extra observer run, cache or removal of a fresh pass.
Inspected current source underlying clean `330030d`; Q05 multi-account acceptance
qualification remains a separate lane. Counts below distinguish observed totals
from statically derived call multiplicities; no SQL statements or parameters recorded.

## Observed Totals Are Not Yet Per-Helper SQL Attribution

The approved single-case probe measured 692 SQL calls in **each**
`recheck_selected_paired_sources` invocation, and 697 in complete v5 retained witness
capture. Generation calls selected recheck, image recheck, selected recheck, then
retained witness capture. Each 692-call stage is a large composed fresh validation,
not a single SQL snapshot and not 692 campaign rows. The source uses bulk campaign,
fact and daily-metric reads; this evidence does not establish a per-day N+1 defect.

The existing stage observer does not isolate each storage helper. Therefore a precise
numeric decomposition summing to 692/697 cannot honestly be presented as measured.
The following call graph gives exact explicit invocation multiplicities for the
successful one-Google-account / chosen capture / present raw-traffic graph path.
Additional catalog, commerce, authority, goal, privacy and database-clock work remains
in the enclosing totals.

## One 692-Call Paired Recheck

`selected_paired_local.recheck_selected_paired_sources`:

1. `load_paired_traffic` → `check_selected_start`, then one public
   `load_raw_range_traffic` for the chosen account. This independently loads one
   selected graph and one traffic graph before comparing the actual whole graph.
2. `selected_plan_local.recheck_selected_sources` → `check_selected_start`, retained
   saved catalogs, then `capture_selected_proof`.
3. `capture_selected_proof` calls `check_selected_start` before/after its account
   loop. Each account calls `capture_selected_reporting_pin` once.
4. That pin helper does **two independent `proof()` reads**, with guards/private source
   comparisons between and around them. Each proof calls `_reporting`, `_head`, and
   private `_read_selected_traffic_pass`. Each private pass loads selected once,
   followed by traffic. Previous reviewed reuse eliminated a duplicate selected load
   *inside* that one private pass, not either fresh proof.
5. Back in `recheck_selected_sources`, another selected graph is loaded and compared
   with the original complete capture. Commerce, expiry, paid/authority checks follow.
6. Outer paired recheck finishes its own authority, paid, transaction and expiry checks.

Thus this explicit reporting subtree has: four `check_selected_start` invocations;
four selected graph reads (one public traffic read + two inner proofs + final selected
graph comparison); three traffic-body reads; two `_reporting` legacy/current proof
reads. Saved catalog internals may add other source validation; this is not a complete
statement-counter formula.

## One 697-Call V5 Witness Capture

`creative_retained_sources.capture_creative_retained_sources` guards its context, then
calls `selected_plan_witnesses.capture_selected_reporting_sources` and the creative
retained-source collector, with final original-context/goal/privacy/expiry guards.

The selected witness collector invokes `current_proof()` **twice**, separated by
commerce witness construction. Each current proof calls the per-account pin helper,
and each pin helper independently reads `proof()` twice. For one chosen account this
is four `_reporting` calls plus four fresh joint selected/traffic reads. Creative
metadata/currentness and commerce are additional parts of 697; do not label the
entire witness stage as selected-only SQL. The outer double reads, inner double reads,
and selected-image-selected ordering are intentional race-detection boundaries.

## Concrete Repeated Ownership Work Inside Those Reads

`campaign_performance.selected_storage.read_selected_capture` explicitly:

- locks scope;
- reads the immutable historical graph and its native campaign/selection/completion
  bindings in bounded bulk queries;
- calls `read_selection`, which locks scope again, reads head/selection, and calls
  `current_scope` once;
- calls `_aggregate`. `_aggregate` calls `current_scope` itself, then `read_current`
  whose before/after authorization callback calls `current_scope` twice more.

Therefore one selected capture read invokes `current_scope` **four times**. These
are fresh invocations, not ORM cache promises. `current_scope` itself performs seven
explicit successful-path database operations in the inspected Google branch:

1. workspace FOR UPDATE (`lock_scope`);
2. account FOR UPDATE (`lock_scope`);
3. refreshed workspace read;
4. workspace lock inside `validate_advertising_scope`;
5. owned active account/integration join with row locks;
6. exact native source FOR UPDATE;
7. scalar workspace privacy revision read.

Separately `_traffic_for_selected` reads current presence, exact range receipt and
its dependencies; default `read_range_receipt(require_current=True)` invokes
`_aggregate`, causing three more `current_scope` invocations. Traffic also independently
compares the full daily metric manifest against the presence facts. These checks are
not optional because a selected pin alone does not establish raw traffic provenance.

Static consequence for the explicit subtree above: paired recheck has
`4 selected reads × 4 + 3 traffic reads × 3 = 25` current-scope invocations, each with
seven explicit operations (175 operations attributable by source shape). The selected
part of witness capture has `4 × 4 + 4 × 3 = 28` such invocations (196 operations by
source shape). This is a falsifiable static expectation, **not an observed allocation**
of the 692/697 totals. Callback/helper behavior and the complete runtime path must be
measured before optimization claims.

Full metric manifests are also repeatedly traversed within these composed paths:
`_reporting` calls `read_current` (which reads a manifest) and independently `manifest`;
selected `_aggregate` reads another through `read_current`; range `_aggregate` reads
another; traffic reads one for exact present-cell comparison. A single inner joint
proof therefore reaches five explicit manifests. Fourteen manifest invocations are
visible in the paired reporting subtree and twenty in the selected witness subtree.
They are bounded bulk reads, not one query per metric row. No recommendation is made
to replace their distinct observations with one cross-pass snapshot.

## Narrow Next Investigation, Conditional On Acceptance Evidence

If Q05 exposes actionable capacity/latency cost, the next diagnostic contract should
measure fixed helper envelopes (`current_scope`, `_aggregate`, `read_selected_capture`,
`read_range_receipt`, `_reporting`, `manifest`) with invocation counts and exclusive SQL
counts. Patch actual imported aliases, keep parent span identities, and never emit SQL
text, native IDs, arguments or credentials. This requires separate approval; no such
probe has run here.

The smallest candidate worth **evaluating**, not implementing now, is redundant owned
row acquisition **inside one `current_scope` invocation**. It currently reacquires
workspace/account through both lock_scope and validate_advertising_scope. Any fused
read design must preserve workspace-first lock strength/order, owned active integration,
source generation/native currency/timezone, privacy, and negative behavior. A joined
query is not automatically equivalent: lock ordering and same-transaction mutation
hooks must be proven. Do not remove before/after callbacks, independent `_aggregate`
checks, guards, or later fresh proof reads merely because they reach the same rows.

Even an eventual private same-invocation factoring must not create caller-supplied
"already authorized" tokens, retained SQL caches or cross-account/current-generation
reuse. Public helpers retain complete validation. Root should choose a slice only
after the actual Q05 outcome and measured helper attribution; original409 remains
unresolved and no owner policy change is needed for this read-only investigation.
