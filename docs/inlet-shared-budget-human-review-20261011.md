# Shared-Budget Review — Human Decision Packet

**Decision requested:** nominate the owner or an advertising/ecommerce expert to
review this local synthetic case and record a separate pass/fail, reason and
required correction for each of the six gates below. Recommended scope: assess
the existing investigation-only customer flow. Do not interpret it as a qualified
native budget recommendation or release approval. No human verdict is recorded.

## What The Customer Entered

The actual PostgreSQL browser journey uses a November 2026 Shopify merchandise
net-sales goal of $12,000 and an unchanged $1,000 November budget ceiling, USD,
America/New_York and balanced aggressiveness. The customer supplies an independent
alternative with $100 allocated and $900 unallocated. Those are period allocations.

Two observed campaigns, **Mug Campaign 1** and **Mug Campaign 2**, share an observed
$10-per-day setting. The customer enters a $5-per-day hypothesis for review. These
daily amounts are separate from the $100/$900 period allocation. Inlet neither
converts them into a period spending guarantee nor applies any advertising change.
The saved disposition is `investigate_only`, application is `unavailable`, and
period-spending compatibility is `not_assessed`.

## Read The Actual Evidence

| Stage | Actual local artifact | What it demonstrates |
| --- | --- | --- |
| Original complete membership | [Catalog](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-complete_catalog.json) · [Discovery](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-complete_discovery.json) | The shared owner has two observed members and declares two members. |
| Generated plan version 1 | [Document](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-document.json) · [Export](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-export.json) | One retained owner review covers both campaigns and preserves the customer hypothesis and product/image basis. |
| Fresh incomplete membership | [Catalog](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-partial_catalog.json) · [Discovery](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-partial_discovery.json) | The same owner still has two observed members but now declares three. Discovery is unavailable even though campaign metadata remains complete. |
| After explicit removal | [Historical version 1](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-historical.json) · [Historical export](/workspace/inlet-evidence/20261011/owner-complete-to-partial/recovery01-02-historical_export.json) | The original document and digest are unchanged. Its freshness envelope may change truthfully. |

The browser first explicitly includes a newly discovered, ready review, then reads
the changed membership. Saving is blocked with an owner-specific reselection/removal
message and no input POST or planning-state change. Explicit removal then permits
one save with an empty owner-review list. **Input revision 2 is not generated plan
version 2:** only plan version 1 exists. The revised-input submission and stored
counts are verified in the browser/API test; no separate revised-input JSON
artifact was captured, and none is implied by the historical links above.

## Record Six Separate Judgments

Use pass/fail plus a concrete reason and correction. Pending is not a pass. These
judgments supplement, rather than replace, the provider-alone and combined-platform
reviews in the [main review packet](inlet-creative-review-packet-20261011.md).

| Human gate | Question for this flow | Verdict, reason and required correction |
| --- | --- | --- |
| Scope, facts and semantics | Can the customer identify both affected campaigns and distinguish complete membership from missing membership without inferring an unseen campaign? | Pending human review. |
| Campaign-specific usefulness | Does the review give a useful, understandable next step or a defensible reason to defer? | Pending human review. |
| Budget and alternatives | Are the daily hypothesis, period allocation and unchanged total ceiling clearly distinct, without implying a safe native edit? | Pending human review. |
| Rationale and uncertainty | Is it clear why incomplete membership blocks the review and what fresh evidence is needed? | Pending human review. |
| Creative feasibility | Do the retained product/image statements and production prerequisites remain feasible and honest, without implying visual assessment, usage rights or approved claims? | Pending human review. |
| Honest lifecycle labels | Can the customer distinguish an unsaved review, revised inputs, an immutable old plan and an applied advertising change? | Pending human review. |

## Mechanical Evidence And Remaining Limits

[Recovery qualification](inlet-q06-complete-to-partial-20261011.md) records the two
passing SQLite/PostgreSQL browser cases. Twenty copied artifacts, both strict
catalogs and original/export/historical document digests were independently
verified. The earlier [four browser journeys](inlet-owner-planning-browser-20261011.md),
[duplicate-request checks](inlet-q06-repeated-owner-qualification-20261011.md) and
[renderer repair](inlet-owner-creative-renderer-repair-20261011.md) are separate
cohorts. Their original failures and corrections remain preserved.

This is private V6 behavior with synthetic provider responses. Default V3 is
unchanged. Native-edit validity, daily-to-period spending qualification, expert
usefulness and live-provider readiness are not established. Original reliability
incidents R01/R02/R03 remain separate and open; passing these journeys does not
explain them or establish a timing margin. All remote, hosted-check, merge,
deployment, credential, live-account and spending holds remain.
