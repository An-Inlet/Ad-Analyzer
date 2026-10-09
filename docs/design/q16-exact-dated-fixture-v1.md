# Exact Q16 Dated Fixture V1

This is an explicitly invoked October 2026 acceptance experiment, not a permanent default regression or full Q16 qualification. Its fixed November 3/4 dates are unchanged. Run `tests/q16_exact_acceptance.py` by path only while the real clock is October 2026; the fixture rejects other dates rather than skipping or silently moving the case. No dependent browser fixture is qualified by this package.

## Shared Test Interface

`tests.q16_fixture.prepare_q16_case(engine, config, replicas, patch, artifacts, *, branch, native_calls) -> Q16Ids` prepares an independent `progress` or `privacy` workspace. `Q16Ids` is a frozen scalar dataclass containing workspace, goal/revision/confirmation, store, account, media/SHA, plan/version/digest and create/generate request keys. No principal, runtime or fabricated document crosses the seam. The caller owns replica clients, patch lifetime, engine and private artifact directory.

`import_progress_stage(engine, config, ids, *, stage) -> datetime` invokes the actual Shopify measurement importer for `later_day` or `refund_correction`. It does not issue sessions, alter API time or reconcile billing. The caller explicitly performs those ordinary stage operations using the reviewed `issue_at` and `paid(..., initial=False)` helpers from `q16_clock_feasibility_probe`.

The initial provider metadata is USD/America_New_York from the actual connection service. Its first measurement import contains a fixed September 15, 2026 12:00 -04:00 $8,000 merchandise agreement. Actual October goal HTTP creation, preview and confirmation preserve this September baseline and the November $12,000 target, $1,000 budget and balanced aggressiveness. Reporting is September with August comparison. Native Google reads use MockHTTP and return an actual campaign and child ad group; no reported metrics or selected-event presence are fabricated. Default planning honestly preserves `current_reporting_unavailable` for both requested windows.

The $25 mug and lack of testimonials/approved health claims are customer-supplied facts. `tests/fixtures/q16/synthetic-mug.png` is a deterministic, author-created 128×128 green mug illustration on white. Its pixels were inspected. Actual media upload produces a workspace-owned object and SHA; actual media download verifies the bytes. The plan input currently cites its ID/SHA in product-offer text: this is **not** a typed asset dependency, vision ingestion, real brand/product photograph or proof that the generator consumes pixels.

## Clock Map

- Initial Shopify connection/import and goal HTTP confirmation: actual October UTC wall time. September baseline is fixed explicitly; no relative agreement timestamp.
- Session issuance for each synthetic stage: only the customer API module's imported time reference is replaced during actual login, and fixture token verification receives coherent synthetic claims. Global `time.time`, access guards, identity refresh, database time and final monotonic five-second ceiling remain unchanged. Sessions retain ordinary TTL; no expiry-row edits.
- Plan API: existing `utc_now` factory seam supplies November 3 05:05Z, November 4 05:05Z and the later correction time. No authority guard is replaced.
- Paid state: actual checkout initially, then signed receive/reconcile with coherent fixture provider time at each stage. This is service-level billing qualification, not future-clock billing HTTP/browser qualification.
- Native catalog: original read-time expiry remains untouched; historical progress/read does not refresh native data or need a new native receipt.
- Later order: created November 3 15:05Z. Same-order refund processed November 3 17:05Z arrives at November 4 05:05Z plus configured sync cadence plus one minute. The actual importer replaces the same order's facts with sale plus signed return. No manufactured daily totals.

Initial progress covers November 1 04:00Z through November 3 05:00Z (two New York days across DST), amount $0. Next stage extends exactly one closed day to November 4 05:00Z, amount $25. Refund correction preserves that prefix and gives $20. Original session expires before the next-day progress read; an ordinary fresh login restores access. Reads retain exact V1 document/digest/goal, counts of versions, inputs, request receipts, events, goal confirmations/previews/revisions and commerce snapshots. Manual application stays not assessed and attribution unavailable; there are zero execution attempts and no additional native calls.

## Privacy Branch And Remaining Acceptance

A separate exact-basis workspace generates V1, successfully exports its artifact and serializes its current lifecycle version section. Actual semantic privacy invalidation deletes the graph. Original plan read/progress/artifact/version, create/generate receipt lookup and old-ID generation reject without native calls or resurrection; all six lifecycle plan sections are empty.

This proves scoped section serialization and old-ID endpoint behavior, **not** a streamed workspace archive, delivery-revocation race, browser late-response behavior or full Q16. A previously downloaded artifact cannot be remotely revoked. An intentional fresh create with complete client-retained inputs is a new submission, not old-ID resurrection; this fixture does not invent permanent request-key tombstones or prohibit that separate operation.

Next dependency-ordered package: independent review of these exact IDs/operations; then dated actual browser progress/correction plus separate archive snapshot/delivery privacy proof using the same fixture. Preserve fixed Q01–Q16 and six expert gates. No optimization quality, live provider, production latency or full acceptance claim follows from these synthetic tests.


## Approved October Generation Mode

`prepare_q16_case(..., generation_stage="october")` is additive; omitted/default `"nov3"` retains the original path and `Q16Ids` fields. Actual October goal confirmation is followed by real-time paid/media/native preparation and API plan generation. Each October API clock callback uses fresh real UTC time, not a captured operation timestamp; the original ordinary October session stays in use. No November watermark is imported during preparation.

`import_progress_stage(..., stage="initial_day")` additionally imports a real empty page at fixed November 3 05:05Z. Caller-owned paid reconciliation, fresh login and API clock switching remain explicit. The later/refund stages are unchanged. This lets a truthful October decision/manual report be recorded after actual generation, then retained through the exact November progress stages. The report is customer-only and supplies no provider verification or spending authority. See [approved chronology](q16-october-plan-chronology-proposal.md).
