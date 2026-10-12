# TikTok Website Purchase Count Producer — Proposed Bounded Contract

Baseline a2b8ca5175240dbb546c328a0de178d37868ec4e. Design only, outside the
clean product checkout. Parent official-source research is recorded in
`docs/inlet-tiktok-count-source-update-20261012.md`; this executor did not independently
retrieve it. Documented composition establishes a fixture target, not live availability.

## Scope And Query

Add a distinct `tiktok.website-payment-count.campaign-day.v1` profile and
`tiktok.v1.3.campaign-day.website-payment-count.v1` producer. Preserve the existing
unverified `tiktok.website-payment.campaign-day.v1` profile and every historical byte.
Exact selected event `complete_payment`, family `event_count`, advertiser-owned scope;
no pixel/custom-event ownership, unique customers, monetary value, ROAS or causal claim.
Requested attribution overrides absent; effective windows/report-time/counting mode
remain unknown under the existing attribution DTO. Separately describe the documented
ordinary impression-attributed account-local date basis, never purchase-occurrence time.

Fixed GET `/open_api/v1.3/report/integrated/get/`, API v1.3, `advertiser_id`,
`service_type=AUCTION`, `report_type=BASIC`, `data_level=AUCTION_CAMPAIGN`, dimensions
`campaign_id,stat_time_day`, metric `complete_payment`, `query_lifetime=false`.
One inclusive, closed account-local interval of at most 30 days. First implementation
uses one immutable nonempty owned campaign partition, at most 100 campaign IDs, with
`campaign_ids` IN and JSON-array-string filter_value; no adaptive partitioning/retry.
Include `campaign_status=STATUS_ALL` through the documented filtering representation;
exact filter wire syntax must be checked against the supplied source before coding.
Retain TT_ADS_PLATFORM origin limitation explicitly. Scope excludes Promote, Branded
Mission, iOS14-dedicated, Shop Product/LIVE GMV Max; query completion cannot prove
account-wide coverage. Do not classify unknown campaign kinds as regular from omission.

Pin page_size=100, pages starting 1, maximum 100 pages; limits below provider maximum
are intentional local bounds. Freeze all scope fields across pages. No CHUNK,
implicit all-account report, total_metrics inference, redirects or returned URL follow.
Query descriptor/digest includes all defaults, exclusions, filters and omission rules.

## Shared Pure Boundary Before Acquisition

Proposed frozen `TikTokCountQueryV1`: capture/request digest, exact owned scope and
selection, immutable native-to-local campaign mapping, timezone, closed dates, fixed
query descriptor. Construct only from validated input; no authority is conferred.

Proposed frozen `TikTokCountPageV1`: query/request digest, page/page_size/total_number/
total_page, bounded request_id, allowlisted truncation-header evidence (including
explicit absence), acquisition timestamps, normalized returned campaign/day cells.
Raw body, token, arbitrary headers and provider error text are never retained.
Strict JSON duplicate-key rejection; exact dimensions and local midnight date grammar;
owned campaign and requested range checks; finite nonnegative bounded decimal counts.
Explicit numeric zero is present; omitted metric/row or dash stays missing. Null,
malformed, negative, nonfinite, excess precision and ambiguous duplicate rows refuse.
Money is always unsupported. Other purchase keys never substitute.

Proposed frozen `TikTokCountCollectionV1`: query plus ordered pages and facts, with
exact contiguous pagination, stable totals/page size/scope, unique campaign/day rows,
matching returned-row total_number, bounded bytes/facts/pages and matching request IDs.
A repeated request ID is not assumed invalid without source evidence. Empty report
needs a documented consistent empty page_info shape; unknown empty shapes refuse.
No truncation signal may yield a completed collection. Unknown throttle-header values
fail closed; header absence alone does not prove a campaign lies below the synchronous
20,000-ad cap. If the available response cannot establish uncapped completeness for
this bounded query, collection must remain unavailable rather than inventing proof.
No date splitting, pagination or enable_total_metrics is treated as a cap workaround.

## Persistence Boundary To Resolve Before A Durable Producer

Existing SelectedCaptureV1 v1/v2 stores only page_count and facts, not per-page request
IDs/header evidence. Do not hide proof in a query digest, add mutable side data, or
silently change v2 serialization. First implement/test the pure query/page/collection
boundary, then independently review the exact additive retained-proof/version plan.
The retained proof must be committed by the capture digest, survive strict storage,
export and historical readers, and be erased with its owned capture. Preserve all
legacy bytes/digests and reject unsupported newer schemas at old reader floors.
No table/migration or new schema number is authorized by this design alone; choose
the smallest explicit existing JSON-boundary extension after examining all consumers.
This engineering contract review is not a new owner approval request.

Only after that boundary is fixed, implement injected HTTP plus owned acquisition:
original customer/session, paid entitlement, workspace/account/connection generation,
privacy revision, selected-event and exact aggregate completion guards before/after
IO and immediately before atomic commit. Source grant and campaign mapping must remain
unchanged; no SQL transaction held across network IO. Bounded monotonic and aware
wall-clock deadlines, response/body limits, sanitized failures, caller-owned transport
and every response closed. No real credentials, network factory, customer route or
runtime activation in the first producer package. Default planning v3 and private v6
remain unchanged. Existing v4/v5 TikTok unsupported fixtures remain truthful until the
actual retained producer path is qualified.

## Acceptance Sequence

1. Pure exact-profile/query/page/collection tests: positive/zero/missing/dash,
   malformed/duplicate/foreign/date/shape refusals, stable complete pages, changed or
   absent totals, gaps/repeats/oversize, throttle/cap ambiguity, unavailable scope and
   byte/deadline bounds. Preserve old unverified profile fixtures.
2. Review durable version/reader-floor contract; then storage/export/history and
   corruption/erasure tests on SQLite before PostgreSQL. Never expose partial capture.
3. Injected transport and owned acquisition tests for successful pages, original
   session replacement/revocation, connection/grant/selection/aggregate/privacy changes,
   late failures and atomic rollback. No generic fallback.
4. A separate runtime/customer composition package may follow proven producer closure.

Use one heavy slot, existing disk/memory floors, exact frozen selection, stop first
unexpected failure, preserve original exits/log/XML/unrun nodes, whole Ruff and
configured mypy before code commits, independent review. No hosted CI, push, merge,
deploy, live activation/provider/model/credentials, advertising changes or spend.
Both owner decisions, human quality judgments and other recorded live gates remain.

## Independent Review Closure

`/root/failure_review`: CLOSED for the pure boundary only, not durable producer
eligibility. Implementation must model uncapped completeness as an explicit validated
proof state with documented provenance: never a caller `uncapped=True`, campaign-count
or day-row inference, or absent-header inference. Without source-established proof,
positive fixtures qualify parsing only; completed collection remains unavailable.
Compare total_number to raw unique provider rows before any missing-fact expansion;
synthesized missing cells never count as returned rows. Request IDs bind page/query
without cross-page uniqueness assumptions. Do not promote CaptureSettings support or
new supported capability until the durable proof/reader-floor contract is reviewed.
