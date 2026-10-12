# TikTok Uncapped Evidence Options — 2026-10-12

Engineering evidence gap, not an owner decision. Parser79f15fc5 remains unchanged;
no live calls, credentials or report tasks created. Targeted official reads only;
search returned unrelated results and the official Postman page exposed no useful
endpoint contract. No third-party assertion is used as a completeness guarantee.

## What The Available Sources Establish

The [official SDK reporting API](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/ReportingApi.md)
exposes asynchronous report task creation via POST and task status via GET. It does
not state a truncation-free result guarantee in the inspected description. The
[task body](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/TaskCreateBody.md)
provides report type, dimensions, metrics, advertiser scope, filtering, dates, service
type and output format. These establish candidate interfaces, not supported combinations,
completed-file integrity, unlimited coverage or live advertiser availability.

The [official ad filtering model](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/FilteringAdGet.md)
includes campaign IDs, campaign origins and primary status, defaulting to excluding
deleted objects. This makes a bounded all-status ad enumeration worth investigating;
it does not prove that every historical ad contributing to the report is enumerable.
The [ad API](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/AdApi.md)
is the endpoint reference to check alongside that model. These mutable main-branch
SDK documents were read on2026-10-12, not version-pinned live API qualification.

## Option A: Owned Native-Ad Inventory

Current `app/collectors/tiktok_native_inventory.py` reads campaign/adgroup diagnostics,
not a complete all-status ad-ID universe. Its explicit all-campaign-family and
historical-obligation completeness flags are false; it cannot be reused as uncapped
proof. Existing imported SQL ad rows are also not complete native inventory evidence.

Smallest proposed read-only extension: an owned, original-session/connection-generation/
privacy-bound GET ad enumeration, restricted to the same explicit regular campaign
partition and origin as the report, explicit documented all-status filtering, full
stable pagination and unique ad IDs. Retain query, request IDs, complete page totals,
acquisition interval and inventory digest without names/raw bodies. Establish a
conservative upper bound below the cap only if documentation proves this inventory
contains every ad counted by the report cap for the queried historical period.
A low current count alone is insufficient; concurrent creation/deletion, historical
visibility and snapshot consistency need a documented reconciliation/fence.

Exact official question: For v1.3 BASIC/AUCTION/AUCTION_CAMPAIGN regular campaign/day
complete_payment reporting with campaign_ids and STATUS_ALL, does the synchronous
20,000-ad limit apply to all ad IDs in those filtered campaigns before date filtering?
Can ad/get with the same campaign/origin scope and primary_status=STATUS_ALL enumerate
EVERY contributing ID, including deleted/archived/historical ads? What documented
snapshot or reconciliation guarantee makes a fully paged count below20,000 a valid
upper bound throughout report acquisition? Identify exact fields, excluded families,
maximum page counts and deleted-record retention. Without those guarantees, reject.

## Option B: Bounded Asynchronous Reporting

Potentially avoids a separate inventory, if official completion semantics explicitly
remove the synchronous cap for the exact query. Creating a report task is POST state
creation, although it is an analytics export rather than an advertising mutation;
no live task operation is authorized or attempted here. Offline contract work needs
no new owner decision. Later live integration remains under existing access gates.

Smallest proposed contract: same owned query/profile plus immutable task-ID binding,
bounded status polling, documented terminal-success semantics, exact output manifest
or integrity/row-count proof, and bounded safe download/parsing of every result part.
Pin allowed download origin, reject redirects/credential forwarding, retain file digests
and request IDs, preserve missing-versus-zero and unknown attribution. Do not assume
HTTP200 or task SUCCESS proves a complete file; require the documented guarantee.

Exact official question: Does report/task/create followed by report/task/check support
v1.3 BASIC/AUCTION/AUCTION_CAMPAIGN, campaign_id+stat_time_day, complete_payment,
regular campaigns, explicit campaign/status filters and account-local closed dates,
without the synchronous20,000-ad truncation? What are its own maximum data/file/part
limits, partial-success signals, task expiry, file format/schema, row-count/integrity
manifest and documented terminal/download completeness guarantees?

Recommendation: resolve asynchronous completion semantics first because it may avoid
inventory/report race proof. Keep inventory as a bounded alternative only if its
historical superset and stability guarantee are explicit. Neither path is currently
justified. Do not weaken parser79f15fc5, turn header absence into proof, or implement
supported durable capture before independent contract and fixture qualification.
