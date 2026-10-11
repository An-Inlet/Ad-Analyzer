# Owner Linked Same-Call Validation Proposal

Status: source-only, implementation and execution not authorized. Based on `606d38b`
and parent-supplied final07 measurements. No provider, tests, imports or probe executed.

## Concrete Duplicate And Limits

The ordinary owner-binding phase took .566632 seconds with zero SQL in final07. Entry
was .216883 and actual bindings .005185; these three sibling spans total .788700 but
do not identify the saving available from any nested call. Final07 pre-CAS passed at
4.9628 seconds and post-flush failed at5.19766. No claim that this proposal would have
prevented either this failure or the earlier ones.

Actual call tree:

    repository._generation_owner_binding
      assert_owner_review_generation_bundle
        bundle.assert_ticket(ticket)
        _linked(ticket, candidate, actual_catalogs)
          GenerationTicket.model_validate(ticket)
          PlanVersion.model_validate(candidate)
            validate_owner_review_document
              linked_owner_input_catalogs(candidate.inputs, candidate.catalogs)
              validate_google_budget_owner_review(candidate inputs/actions/proof,
                  candidate catalogs, selected-proof fences, evidence privacy)
          exact policy/ticket/input-digest checks
          linked_owner_input_catalogs(ticket.inputs, actual_catalogs)
          exact full canonical catalog equality
          validate_google_budget_owner_review(ticket inputs, candidate actions/proof,
              selected actual catalogs, ticket sources, ticket privacy)

Thus the final validator can repeat an immediately preceding validator, but it is NOT
unconditionally redundant: ticket inputs are currently joined only by digest and ticket
sources/privacy are distinct arguments. No omission is safe without complete argument
proof. `bundle.assert_ticket` and full ticket/candidate model validation stay unchanged.

## Smallest Proposed Change

Own only `owner_review_generation.py`, a new focused test file and ledger. Keep `_linked`
public-to-module signature unchanged; no new parameter, flag, prepared artifact or
cache. Immediately before its final owner-review call, prove same arguments using the
freshly validated local `ticket` and `candidate`:

1. Full canonical `ticket.inputs.model_dump_json()` equals validated candidate inputs;
   not merely digest equality. If unequal, retain the current validator call.
2. Actual linked catalogs have already been proven byte-for-byte equal to complete
   ordered candidate `google_budget_input_catalogs` by the existing check. Keep it.
3. Candidate actions and owner proof are the identical freshly validated local objects
   supplied to the PlanVersion's owner validator. No reassignment, callback or SQL
   occurs between candidate validation and this decision.
4. Ticket privacy equals the strict integer privacy passed by PlanVersion:
   `candidate.evidence[0].privacy_revision`.
5. Complete ticket source fences equal the complete candidate selected-proof fence
   set in canonical serialized content, matched by unique full account identity.
   Validate cardinality/uniqueness before matching. Do not use only account IDs,
   hashes, timestamps or SourceFence object equality. Ordering differences alone
   must not cause new refusal: if canonical sorted matching is not readily proven,
   simply fall back to the existing full validation.

Only when all five proofs hold may `_linked` return `actual` without the second
`validate_google_budget_owner_review`. Otherwise execute the original validator with
all original arguments. This is a conservative fast path, not a stronger acceptance
gate: it introduces no new refusal or replacement error, and never relies on equality
of unsafe copied models before full validation. No equality branch suppresses errors
from the existing mandatory calls. Full canonical comparisons are themselves pure
and add cost; measurement must include them.

A private ordinary predicate may implement the five comparisons, taking the already
validated locals only, but it cannot be exposed as reusable validation authority.
No argument claiming `validated=True`. No proof object escapes `_linked` invocation.
Actual helper naming and source diff need review before implementation.

## SQL Boundary And Entry Preservation

`recheck_owner_review_input_receipts` also calls `_linked` after SQL receipt resolution.
It must still resolve receipts and enter a NEW `_linked` invocation with fresh complete
ticket/candidate validation. Any reuse is confined to that invocation's immediately
preceding PlanVersion validation; never the earlier generation call or receipt read.
Current full resolved-catalog comparison, source/currentness/TTL checks and original
exception translation remain. If parent prefers a generation-only first slice, do not
add a bypass flag: retain original `_linked` for receipt recheck and separately review
how to avoid duplicating its algorithm. The preferred minimal change applies the same
argument-proof rule independently to each full fresh invocation.

No PlanVersion/public validator change, no data copied before identity refresh, no
callback alias/prepared packet, no validation moved across I/O. Historical entries,
service fact acquisition, all selected/image/retained passes, CAS, flush and final five
second guards stay unchanged. The existing ValueError→fixed409 scope is unchanged;
unexpected SQL/callback errors are not caught by the predicate.

## Required Focused Acceptance

- Spy on the actual validator aliases: valid genuine V6 complete/empty review performs
  one owner-review validation through mandatory PlanVersion per `_linked`, whereas
  baseline performs two. Ticket/candidate model validators remain mandatory. The test
  must not replace their validation with success stubs.
- Compare returned catalogs and complete candidate canonical bytes with baseline;
  V5/wrong pair still rejected and unsafe copied nested bool/bytes/time/proof fails.
- Change ticket source, privacy, input or original catalog independently: either the
  mandatory existing join rejects, or the proof does not hold and the full validator
  runs with unchanged refusal. Include same-instant/different-offset serialization and
  differently ordered valid source sets; conservative fallback must preserve semantics.
- Two separate receipt/current invocations each perform fresh validation; mutate a
  source/catalog between them and prove refusal, no cross-pass reuse. Preserve original
  missing receipt and unexpected callback/SQL error normalization behavior.
- Actual bounded save rollback and real six-second guard checks remain; select exact
  nodes after source review. No full repeated API cohort or diagnostic retry implied.
- Any later timing observation records canonical-comparison overhead and nested versus
  sibling spans honestly. A lower validator count is not an incident closure or a
  reliable latency guarantee. If savings are negligible, report that outcome.

This is routine same-call pure work reuse with a concrete source equivalence obligation.
It does not require changing the owner's authority model. Parent/reviewer must approve
the exact proof and the after-SQL per-invocation treatment before implementation.
