# Operational Maturity Evaluation And Remaining Bridge

This package adds generic pure policy evaluation and a server dependency boundary.
It does not install a policy, independently reconcile Shopify, establish effective
action time or update a recommendation. Production is disabled: both `policy_for`
and `producer_for` return `None`.

## Frozen Interface

`OperationalMaturityPolicy` is immutable and versioned. Every numeric threshold is
required; there are no numeric production defaults. Identity includes metric digest,
currency and time zone. It requires independent full-window assurance; incremental
terminal imports cannot be allowed by a permissive configuration.

`IndependentReconciliationEvidence` is a bounded server facts port, with an explicit
`contract_test` or `live` environment, exact owned source/goal/privacy scope, closed
local window, per-day complete values and counts, completion digests, observation
times, freshness and correction state. A genuine independent full-window producer
is still missing. These facts are not accepted from any customer API. Marking a value
`live` in memory is not evidence that a qualified producer exists; production wiring
must register only a reviewed server implementation.

`evaluate_operational_maturity(policy, evidence, current_context)` is pure and shared
between fixture and future genuine producers. It revalidates the immutable inputs,
checks environment and exact scope, complete calendar-day coverage, ordered distinct
completions, minimum age and spacing, correction state, source freshness, sampled
revision envelope and exact entry-count stability. The full envelope prevents many
small adjacent changes from evading the revision bound. Missing/suppressed days are
not zero. Current incremental collector input always returns insufficient regardless
of policy. Results bind policy, evidence and current-context digests.

`evaluate_registered_maturity` resolves server-only policy and producer dependencies.
Absent registration fails closed without calling a producer. A fixture producer cannot
qualify a live context. Future production collection must reauthorize and fence the
current goal/source/privacy generation through collection and return; this package
has no database adapter that satisfies that obligation.

`operational_as_of` means only that the named policy predicates hold for the supplied
server facts at evaluation time. Result environment remains explicit. Authoritative
finality and action attribution remain unavailable; recommendation update is null and
spending authority none. Test thresholds are synthetic boundary fixtures, not proposed
customer policy values.

## Proposed Next Interfaces (Not Implemented Here)

1. **Owned assessment v3 bridge.** Resolve current owner session, confirmed goal,
   source generation/privacy epoch, immutable original execution receipt and latest
   non-superseded receipt evidence under the shared workspace fence. Independently
   resolve the server producer and versioned approved policy. Collect exact before
   and after local-day windows. Require qualified authoritative action interval
   provenance for delivery-linked claims, disjoint comparable windows on either side
   of that interval, identical metric/currency/calendar semantics and policy-qualified
   observations for both windows. Recheck current evidence after any source IO.
   Otherwise return explicit insufficient reasons; never manufacture an effective
   time from dispatch or configuration readback. An available comparison remains
   descriptive association, not causal lift.
2. **Bounded feedback input.** Persist a versioned server-owned assessment digest,
   policy version, exact evidence lineage, environment and explanation codes with
   an idempotent original-action key. Only a current live assessment may contribute
   to a live bounded recommendation. Reject contract-test/insufficient/retracted
   inputs. Direction and amount remain constrained by a separately approved decision
   policy; none of this raises the spending mandate, bypasses review or emits writes.
3. **Retraction/invalidation.** Compose the candidate package's transactional
   `app/optimization_candidates/invalidation.py` hooks for commerce revision,
   workspace privacy changes and newer original-attempt receipts. A feedback record
   must retain dependency identifiers/digests so invalidation can remove its learned
   contribution and recompute/explain affected recommendations idempotently. Do not
   delete financial reservations, settlement history or immutable provider receipts.
   Exact persisted schema and invalidation API must be agreed with the candidate
   owner before implementing dependent changes or reserving a migration.

The v3 bridge, qualified timing producer, genuine independent reconciliation source,
feedback consumer and retraction-aware recomputation remain missing production code.
Policy intent/parameter approval and provider qualification are separate gates, not
substitutes for implementing those components. Existing owned v2 remains insufficient.
