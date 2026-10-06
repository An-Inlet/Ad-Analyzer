# B17 Production Learning Readiness

Baseline: `1c82e03`. B17 remains partial. Audit acceptance: “Add measured action-outcome feedback. Comparable mature windows update bounded recommendations with an explanation.” Owner decisions and live qualification cannot substitute for the missing implementation below.

| Requirement | Implemented evidence | Remaining production code |
| --- | --- | --- |
| Owned measurement | Terminal Shopify imports publish retained aggregate manifests with source generation, privacy epoch, revision, source window and day coverage (`commerce/evidence.py`, `commerce/sync.py`). | Independent reconciliation producer capable of establishing complete coverage beyond incremental `updated_at` pages; qualification rules must distinguish these sources. |
| Descriptive comparisons | `outcomes/descriptive.py` compares exact Decimal store totals, current confirmed goal and source, complete equal local-day windows; prior publication can show observed stability. | No maturity, action attribution or recommendation authority follows from this comparison. |
| Retained revision evidence | `outcomes/reconciliation.py` reads up to 16 terminal publications and 400 requested local days, rechecks owned manifests and completion digests, reports per-day observed value/count changes and coverage changes. | These incremental observations do not establish independent rescans or authoritative finality. Truncation is explicit. Missing/suppressed observations cannot become stable zero. |
| Effective action time | Receipt contract can represent an authoritative interval. Current actual activation adapters report timing unavailable. Configuration readback is factual configuration, not delivery onset. | Qualified provider timing producer, original-attempt binding and conservative interval validation. Until then delivery-linked assessments remain insufficient. |
| Operational maturity | Existing owned v2 assessment is deliberately `insufficient`, with null differences and `maturity_policy_unavailable`. | Parameterized policy registry, evaluator and source producer; no production policy values are installed. |
| Owned action comparison | Pure evaluator handles synthetic comparables. Owned receipt/measurement isolation exists. | Explicit v3 bridge must combine qualified timing, policy evidence and comparable complete windows. Never relabel v2/descriptive results as mature. |
| Bounded feedback | Existing learning ranks human approval/rejection history; it is not measured action-outcome learning. | Persisted versioned feedback consumer, bounded recommendation update and explanation, no execution or spending authority. |
| Corrections | Source generations/privacy epochs and retained publication revisions are available. | Retraction/invalidation lineage from changed or erased evidence through assessment and recommendation; avoid leaving learned output after its evidence becomes invalid. |

## Collector Contract And Limits

Internal read-only `collect_owned_reconciliations` returns `inlet.owned-reconciliation-observations.v1`. It requires a current confirmed goal revision and latest owned publication, acquires workspace/source fences and calls fresh authorization before and after work. No endpoint, scheduler, migration, policy installation, provider call or database commit is added. PostgreSQL queries have a transaction-local two-second statement timeout. The sample is bounded before manifest loading; serialized output is bounded at 512 KiB.

Every observation identifies the actual terminal completion and source window. Assurance is `terminal_updated_at_import`; independent reconciliation and maturity are always unqualified. Completion digests deduplicate observations; publication count is never a maturity threshold. Same generation/privacy epoch is mandatory. Unreadable historical observations are counted without returning their data. Last-change discovery lag measures when a retained publication first observed a changed complete day relative to that local day's end; it is **not** a provider mutation time, finality proof or proposed maturity delay. Coverage state transitions are separate from complete-day value/count revisions. Even a truncated sample showing unchanged days is only sampled stability.

Shopify refunds are assigned to `refund.processedAt` in `commerce/ledger.py`, not silently reassigned to the original sale day. A return occurring later can legitimately affect a later day. Calibration must measure delayed arrival/backfills/revisions of the dated facts actually retained; a generic returns-window delay is not an evidence-based maturity rule.

## Next Shared Interface: Disabled Policy Evaluation

Implement immutable `OperationalMaturityPolicy` with version/digest, exact metric definition, currency/time-zone semantics, allowed reconciliation assurance, bounded configurable minimum age, observation spacing/count, tolerated revision rules and maximum source staleness. No values are preselected or inherited from existing 30/90-day defaults. Registry lookup returns `None` by default. Policy fields are server-owned; a browser cannot supply qualification evidence.

A pure `evaluate_operational_maturity(policy_or_none, collected_evidence)` returns versioned qualified/insufficient reasons and exact supporting completion digests. It must reject missing policy, truncated/unreadable coverage, generation/privacy mismatch, unsupported assurance, future/open windows and unmet configured predicates. Qualification means operational sufficiency under the named policy, never authoritative finality. Offline tests may use explicitly synthetic policy values to verify boundaries without enabling a production policy. This registry/evaluator can be implemented independently of owner parameter selection; the v3 receipt bridge and feedback/retraction wiring remain subsequent code packages.

## Narrow Owner Decision Still Needed

Recommended policy intent: permit **explicitly labeled operational maturity**, with future correction/retraction support; do not promise authoritative finality that current sources do not provide. Keep production qualification disabled until a documented calibration establishes defensible values for each supported source/metric/time basis. No numeric age or stability count is recommended yet: current retained incremental import samples cannot estimate independent completeness or delivery onset reliably.

Owner selection of that intent does not complete the missing producer, policy evaluator, v3 bridge or feedback consumer. Ask for calibrated parameter approval only with actual coverage/revision evidence and sensitivity results, clearly identifying insufficient sample sizes. Delivery-linked launch outcomes also need qualified timing evidence; a separate configuration comparison may remain descriptive. No policy can raise the customer's overall spending mandate or authorize new campaigns/creative.

## Subsequent Offline Evaluator Package

`app/outcomes/maturity.py` now implements the immutable parameterized policy, disabled
registry/producer lookup, generic pure evaluator and server dependency boundary
proposed above. No numeric production values or genuine independent reconciliation
producer are installed. Its typed facts port supports future server producers without
changing the mathematical checks; fixture/live environment mismatch fails closed.
See `b17-operational-maturity-interface.md` for the frozen interface and proposed v3,
feedback and retraction interfaces. The missing independent source/timing producers,
v3 assessment bridge and feedback/retraction consumer remain implementation work.

## Subsequent Read-Only V3 Bridge

`app/outcomes/owned_v3.py` now implements a reusable read-only owned bridge with
short-lived snapshot sessions released before producer IO and a fresh fenced
recheck afterward. Actual inputs remain insufficient; only explicit fixture timing
and qualified synthetic reconciliation can demonstrate association arithmetic.
V2/history remain unchanged. Persisted v3 dependency lineage, strict customer
projection and feedback/contribution/retraction storage are still unimplemented;
see `b17-v3-feedback-contract.md` for the proposal awaiting schema reservation.

## Subsequent Disabled Feedback Persistence

The proposed storage is now implemented offline in `app/outcome_feedback` and
`app/outcomes/feedback.py`, with migration0064, owned multi-publication lineage,
strict export serialization, idempotent contribution CAS, deterministic active-set
recomputation and transactional retraction of derived numeric data and candidate
caches. Raw mutation triggers fence workspace ownership and advance the export privacy
counter. See `b17-v3-feedback-contract.md` for bounds and concurrency semantics.
This supersedes earlier statements that feedback storage is unimplemented; it does
not enable production policies or qualify existing sources. Genuine independent
reconciliation, authoritative action timing, calibrated policy values and a customer
v3 projection remain outstanding. Current default actual assessments cannot produce
eligible feedback. B17 acceptance is therefore still incomplete.
