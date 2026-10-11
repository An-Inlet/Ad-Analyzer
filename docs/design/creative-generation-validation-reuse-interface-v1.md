# Creative Generation Validation Reuse — Proposed Internal Interface

Status: design only, awaiting review. No implementation or policy changes.
Base: reviewed service 2c61bcf; parent integrated head4100fe5. No tests run for
this proposal. Scope is offline performance, not relaxing an authority deadline.

## Measured Evidence And Limits

Parent final06 stopped on PostgreSQL Google/one-image generation with
`planning_authority_expired`: six cases passed and 21 remained unrun. Isolated
same-case timing07 passed with maximum IdentityFact age2.724s. Two-image timing08
passed with maximum age2.759s; its longest interval ended at repository final
acceptance, with2,627 SQL calls,0.560s SQL and2.467s CPU. Full journey had16,277 SQL
calls taking5.608s. These measurements establish substantial repeated work; they
DO NOT prove the cause of the earlier expiry. Preserve failed evidence and the
five-second gate. No retries, synthetic clock, refreshed fact under SQL or larger
limit are proposed.

## Concrete Redundancy

`selected_plan_retained.capture_selected_reporting_pin.proof()` loads a complete
selected capture graph, then calls `selected_traffic_reader.load_raw_range_traffic`,
which loads that same graph again to validate the supplied pin. The outer retained
function deliberately executes proof twice, with guards and private source checks.
Those independent fresh passes must remain.

`selected_paired_local.recheck_selected_paired_sources` separately loads traffic,
then reconstructs the selected proof with those double passes, then reloads the
selected graph. The service invokes this whole boundary before and after the image
SQL check. Retained witness capture then performs two additional complete proof
captures. A selected account therefore currently incurs approximately20 complete
selected graph reads and10 traffic reads in final generation. This count is a
source-level estimate, not a measured assertion about every branch.

Every paired assert_ticket also revalidates copied nested models and recreates
window projections. Some pure work can be prepared once, but only with a separate
strict internal trust boundary; frozen Pydantic objects alone are insufficient.

## First Slice: Same-Pass Selected/Traffic Read

Implement only the following bounded read fusion first; retain all outer fresh
passes, image ordering, guards, witness captures and public signatures.

Internal module-private value `_SelectedTrafficPass` contains:

- Exact immutable AccountRef, SourceFence and explicit capture ID.
- Strictly validated SelectedPlanCaptureV1 and its SelectedPlanPinV1.
- RawRangeTrafficGraphV1 or KnownTrafficGap, with full existing current receipt,
  completion, presence/profile, full manifest, native campaign map and current
  DailyMetric equality checks. No absence downgrade on corrupt present evidence.
- Private Session, root SessionTransaction, Connection and root connection
  transaction identities used during construction. No serialized authority token,
  credential, deadline, provenance claim or returned currentness guarantee.

Factory signature (internal, no public consumer input graph):

    _read_selected_traffic_pass(
        db: Session, *, account: AccountRef,
        expected_source: SourceFence, capture_id: str,
    ) -> _SelectedTrafficPass

The factory loads/strictly validates the selected graph itself, then calls a private
traffic-body helper with that exact local graph and derived pin. It does not call
arbitrary authorizer/provider callbacks between the two reads. The traffic body
keeps every current ownership/source/privacy/receipt/manifest/fact check except the
redundant second load of the same selected capture. Check clean root transaction
identities before/after and reject flush, nested transaction, commit, rollback,
connection replacement, ORM changes or reentry. There is no reusable constructor
accepting a caller-created graph, public cache lookup or serialization API.

Initially consume this factory only inside each retained `proof()` pass. The first
and second `proof()` each construct a NEW pass from fresh SQL; compare full existing
proof equality and private grant/source data exactly as today. Never carry the
factory value from first pass to second, across the image check, from collection to
persistence, or into retained witness construction. Its graph fields are used only
to derive that invocation's proof. The existing public traffic loader keeps its
standalone behavior/signature; implement its common private traffic-body factoring
without allowing external callers to bypass the independent selected graph load.

This removes eight nested selected graph reconstructions per selected account from
the estimated20, while preserving the other12 and every outer fresh comparison.
Traffic reads and all broad late checks are deliberately unchanged. Measure whether
this reduction provides useful CPU/SQL headroom before expanding the scope.

File ownership for this first slice: selected_traffic_reader.py private factoring;
selected_plan_retained.py proof-local factory consumption; optionally a new private
module to avoid import cycles; new focused tests/ledger. No service, authority,
public DTO, historical reader, capability, API, policy or migration changes.

## Optional Second Slice — Requires Separate Approval And Measurement

Only if the first slice leaves measured pure CPU dominant, propose an operation-local
prepared validator for immutable input graphs. Its constructor must revalidate the
entire copied ticket/bundle/candidate and exact policy, recompute all projections,
and create a private defensive snapshot before external identity refresh. SQL pass
results still come from fresh actual rows. Any local fast path must require exact
private object identity plus immutable content commitments and transaction scope;
it must not trust a model_copy instance or caller-supplied hash. No public
assert_ticket/model_validate behavior changes. This proposal does NOT approve that
second implementation or removal of repository candidate/proof checks.

## Required Regression And Measurement Evidence

- Actual original selected capture/range HTTP fixture on both SQLite and PostgreSQL;
  resulting selected proof, traffic pin, complete maps and gap reasons identical to
  the existing path. Include actual explicit zero, absent cells and unqualified
  old raw provenance. Do not manufacture current authority with a pure graph.
- Count exact selected-loader calls: each retained proof's two fresh passes use
  one selected load apiece, while traffic still runs once per pass. Assert actual
  fresh SQL row reads, not just wrapper call counts.
- Mutate selected receipt/fact/map, current aggregate metrics, selection pointer,
  source generation/private grant, or traffic sidecar between the two passes; each
  existing rejection remains. Mutation between selected and traffic inside one
  pass must be caught by second fresh pass before acceptance. Test unknown/corrupt
  present sidecar never becomes an absence gap.
- Transaction/session replacement, nested transaction, flush, dirty state and
  original owner/session/privacy changes still reject. No provider or blob IO under
  SQL; unauthorized/paid errors retain their current statuses.
- Tampered copied-model inputs still fail strict validation; ordinary current
  missing-media and late image/source changes preserve zero version/head/dependency/
  receipt effects in actual generation.
- Keep real5s expiry and post-flush expiry negative tests; inject a deliberate delay
  beyond the current limit and require failure, not cache reuse or restamping.
- Repeat the same bounded instrumented Google one/two-image cases with stage times,
  statement counts and maximum fact age. Prefer structural load-count reduction
  and measured headroom over brittle absolute CI speed assertions. Run final normal
  actual API qualification without timing monkeypatches before claiming a fix.

## Remaining Uncertainty

A fast isolated run cannot establish that this repair eliminates final06's cause.
If normal qualification still expires, capture the failing stage and resource/
lock evidence rather than widening authority or adding retry. Larger maximum
account/window graphs may need a separately reviewed bounded admission/capacity
policy; this proposal does not silently lower supported capacity or claim a5s
execution guarantee for every possible32MiB bundle.
