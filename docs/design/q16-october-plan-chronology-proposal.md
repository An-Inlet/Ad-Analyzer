# Approved Additive Q16 October Plan Chronology

Root approved this additive interface after reviewing `7259317`. The test helper now implements it; no production behavior changes. Existing callers retain the November default.

## Reason

The November-generated dated archive case can create a genuine decision, but its November manual report is rejected with HTTP 422 by `AssertionIntent.coherent_assertion`, which independently checks actual wall time. This is correct validation for the real clock; no guard patch or pre-plan/backdated report is appropriate. The unchanged frozen Q16 inputs require initial **progress** as of November 3, not plan generation on that date.

## Exact Additive Interface

Add optional keyword `generation_stage: Literal["nov3", "october"] = "nov3"` to `prepare_q16_case`. Preserve `Q16Ids` fields and the current default path exactly. For `october`:

1. Perform the same real Shopify NY first September import and actual October goal HTTP create/preview/confirmation.
2. Sample a fresh real `datetime.now(UTC)` **after** confirmation as `generation_at`. Use actual paid checkout/reconcile at that time, actual owned media upload, actual native reads, and actual plan create/generate through the existing API service-clock seam using **fresh real `datetime.now(UTC)` on every callback**. Retain the original ordinary October login; do not issue a future session. Do not import November watermarks yet or force an early reimport inside the configured sync cadence.
3. Caller GETs the genuine document and current digests, submits an actual decision and manual report using the just-generated `generated_at` timestamp. It is on/after plan generation and no later than real wall time or the fresh real service recorded-at clock. The report remains unverified. No fabricated event/validation bypass.

Extend `import_progress_stage` with the additive literal `initial_day`, returning November 3 05:05Z and importing a real empty Shopify page that advances the watermark while preserving September facts. Existing `later_day` and `refund_correction` branches stay identical. As before, the caller separately performs paid reconciliation (`initial=False`), fresh ordinary session issuance at the stage time, and the existing plan API clock seam. This avoids hidden session/billing operations inside the importer helper.

The caller then reads initial progress $0 on November 3 and later $25/$20 on November 4, while retaining the October V1 and its genuine decision/report. Native evidence may now be expired, which historical progress already supports; no native reread, deadline extension, regeneration or implicit head replacement. Record exact old/current freshness honestly. The archived event graph now has two genuinely recorded events before erasure.

## Qualification Before Dependent Reuse

Root approved the interface before implementation. Browser consumption waits for the qualified helper freeze; its default November path remains unchanged. Focused both-database proof must verify actual October generation follows the successful HTTP confirmation and persisted preview timestamp (the confirmation row has no timestamp), both event endpoints succeed with real nonfuture timestamps, V1/digest/goal/events remain unchanged through November progress, old October session expires before fresh login, native calls stop after generation, and both events serialize in the real archive then disappear after semantic erasure. Preserve complete original common-case windows/amounts and prior dated limitations.

This is an ordering change to a new explicit fixture mode, not a production clock seam or a change to fixed Q16 dates. The existing November-mode 422 probe remains evidence of the rejected clock combination, not a product defect.

Implementation note: holding the actual October setup timestamp constant for the entire API operation was rejected by freshness validation because later native observations were newer. Fresh real-time callbacks match production and preserve all boundaries; no clock rollback or tolerance change. `Q16Ids` remains unchanged.
