# B17 Maturity And Action-Time Decision Bundle

Prepared against `c602a1b`. This worksheet records **unresolved owner choices**;
implementation approval of this document is not approval of a maturity policy.
No values below are enabled, defaulted or inferred from elapsed time.

## Decision 1: What “Mature” Means

**Recommended direction: operational, as-of maturity.** A result qualifies only
under an explicitly approved versioned policy, after complete independent source
reconciliations, required observed stability and correction handling. Future
corrections remain possible and reopen qualification. This is achievable from
retained Shopify facts plus additional producer logic, subject to retention limits.

Alternative: authoritative finalization. The retained Shopify producer does not
have a source guarantee that no future refunds/corrections will occur. Requiring
that guarantee means maturity remains unavailable. Store-total sales processing
facts cannot supply it, regardless of how many days have elapsed.

The owner should select one direction. Choosing operational maturity still requires
the numeric and correction choices below; it does not itself make data mature.

## Decision 2: Operational Policy Inputs (All Unset)

| Required Choice | Owner Input / Evidence Needed | Consequence |
|---|---|---|
| Minimum lag after the final local observation day | Unset. Use target stores' refund/correction practices and an agreed business tolerance | Does not qualify alone; must also pass all reconciliation checks |
| Number of distinct complete reconciliations | Unset. A replayed publication never counts as another observation | Determines how many retained terminal imports are needed |
| Minimum separation and total span of those reconciliations | Unset. Choose with the actual import cadence and observed corrections | Prevents repeated near-identical reads from masquerading as independent maturity |
| Stability tolerance | Unset. Decide exact daily value/count stability or a documented bounded tolerance | A threshold must be explicit in unit/currency and cannot aggregate away offsetting daily corrections |
| Correction/reset policy | Unset. Recommend qualification is reopened on relevant corrections, missing coverage, privacy/generation change or unsupported basis | Prior saved as-of evidence is not current qualified evidence |
| Source freshness at evaluation | Unset for maturity policy. Existing descriptive endpoint's 24-hour gate is not silently adopted as approval | Old complete imports do not establish current knowledge |
| Calendar/window and minimum evidence policy | Unset beyond existing equal-local-day descriptive checks | Required before translating descriptive observations into recommendations |

Use the same policy version/digest for both comparison windows. Do not borrow the
legacy unified GA4/CRM cohort default of 90 days. Do not assume a 7- or 30-day value.
A policy whose horizon or required observations exceed retained history must return
insufficient; it must not authorize retaining data past the existing privacy policy.

## Decision 3: What Action-Time Evidence Is Required

Keep **delivery-linked** timing for launch action claims. Configuration-state
comparisons may remain separately named descriptive reports, not substitutes for
measured advertising outcomes. There is no request here to approve weaker action
claims, and no current state receipt proves delivery onset or cessation.

Current evidence can prove dispatch time and exact status/configuration at a readback
instant. The current adapters do not prove authoritative delivery intervals. Neither
an ENABLED readback, a successful mutation acknowledgement nor a Shopify sale date
may be promoted to a delivery timestamp. A future producer needs documented provider
semantics and owned resource lineage before filling that interval. If unavailable,
B17 action comparison remains insufficient even if commerce maturity is qualified.

## Proposed Producer Contracts (Design Only)

`OperationalMaturityEvidenceV1`:

- Workspace, owned store/connection, generation, privacy epoch, goal revision and
  exact metric-definition/currency/time-zone digests.
- Approved immutable policy ID/digest and all required parameters; no client proof.
- Half-open local windows and exact UTC boundaries, evaluated-as-of, terminal
  source watermark and current source revision.
- Ordered distinct retained publication IDs/digests and completion lineage, each
  independently owned/valid/current for its source epoch, with exact covered-day
  sets, zero/missing/suppressed state and observed correction comparisons.
- Qualification `operational_as_of | insufficient`, fixed reasons and a bounded
  mature-through date only if every approved policy condition holds. Never finality.
- Read-time invalidation for erasure, disconnect/rebind, retention, current source
  change or relevant correction; no reconstruction from an old saved payload.

`ActionTimingEvidenceV1`:

- Owned original attempt/request, current latest receipt sequence/digest, reviewed
  target set, account/connection generation and action purpose.
- Semantics `delivery | configuration_effect` (never interchangeable), source
  contract/API version, exact authoritative evidence digest and observed-as-of.
- A bounded effective interval and the provider's documented reason it bounds the
  chosen event. No interval is inferred from dispatch/receipt observation alone.
- `available | unavailable | conflict`, supersession lineage and fixed reasons.
  Paused creation cannot qualify activation; mixed or conflicting target evidence
  prevents a graph-wide timing claim. Unknown latest evidence invalidates older
  success for current qualification.

Neither contract is installed or enabled by this document. No new table/migration
is reserved. Any persistence proposal must specify all publication/receipt ownership
foreign keys, privacy cascades, retention and a strict export serializer first.

## Completion Gate

Even qualified maturity plus action timing does not imply causal lift. Comparable
windows must retain source/basis/calendar checks and confounder limitations. A
separate approved bounded recommendation policy must explain what changes and why;
no automatic spend-limit increase follows. Until these producers and policies are
implemented and verified, B17 remains partial. Current descriptive UI must continue
to say **As-Of Descriptive · Maturity Unqualified · Action Attribution Unavailable**.
