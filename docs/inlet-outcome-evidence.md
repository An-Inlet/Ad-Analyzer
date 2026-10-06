# B17 First Consumer Module

`app/outcomes` evaluates immutable aggregate inputs without database queries,
provider calls, scheduling, persistence or spending authority. This is the first
B17 module, not completion and not a replacement for production receipts.

`contracts.py` defines frozen nested consumer values. `evaluator.py` revalidates
inputs, computes a deterministic content digest, and rejects mismatched scopes,
unknown generations, differing metric/currency/attribution/time bases, incomplete
coverage/maturity, stale sources, conflicting receipts and overlapping actions.
It preserves local calendar boundaries through DST, reports unequal calendar-month
lengths, distinguishes missing from zero and omits relative changes for zero or
negative baselines. Cross-owner or invalidated-privacy values are redacted.
Corrections/supersession change the input digest; no previous evidence is rewritten.
Even comparable fixtures are labeled `synthetic_comparable`, with
`interpretation=observational_only`, null causal lift and no spending authority.

Production receipt normalization is explicitly absent. `ReceiptInput` cannot
claim a verified production effect. It is not an extension to the scheduler's
transport protocol. That owner will supply committed shared types separately.

`project_commerce_snapshot` copies existing `CommerceSnapshot` and `CommerceStore`
values already read in the caller's authorized consistent transaction. It preserves
saved revision/window/currency/time zone and canonical Shopify merchandise metric,
ignores arbitrary result fields, and redacts unavailable privacy values. Existing
snapshot completeness does not prove historical page lineage or refund maturity:
projection emits `historical_manifest_unavailable`, unknown source generation,
empty day coverage, no maturity policy and unknown correction finality. These are
visible insufficiency reasons rather than fabricated production qualification.

No endpoint exposes this module yet. Future callers must verify current membership,
owned historical references and privacy state before consumption. No indefinitely
retained aggregate copy is introduced. See `docs/design/outcome-evidence-proposal.md`
and `docs/design/historical-measurement-manifest.md` for missing producer/receipt
ports and acceptance requirements. No migration is needed for this pure package.
