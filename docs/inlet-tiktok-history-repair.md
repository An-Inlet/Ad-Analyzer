# TikTok Deleted-Object History Repair

Branch: `codex/inlet-tiktok-history`, based on PR #75 head
`01aa869b7df73bcdf1dca5fc25391a43f0af4efc`. Offline only; no provider calls.

A successful refresh formerly omitted deleted inventory and report rows using
provider defaults, then replaced the account/window metrics with the incomplete
result. Historical spend could consequently become zero while the connection
reported success.

All inventory requests now explicitly include `filtering.primary_status=STATUS_ALL`.
Each BASIC report requests its matching `campaign_status`, `adgroup_status` or
`ad_status` with `IN` and the string-encoded JSON value `["STATUS_ALL"]`. The existing
HTTP layer JSON-encodes the enclosing filtering list exactly once. Both filters
persist across pagination. Deleted parent inventory follows the same tenant-scoped
validation and normalization as active inventory. Atomic publication and parent
validation remain unchanged; malformed or orphan facts still fail without replacing
published metrics.

## Evidence And Limits

Primary SDK inspected at `tiktok/tiktok-business-api-sdk` commit
`f809c396520df2d7b201a9ccc5378d822b728ed3`:

- [FilteringAdgroupGet](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/FilteringAdgroupGet.md)
  and FilteringAdGet expose `primary_status`, defaulting to `STATUS_NOT_DELETE`.
  FilteringCampaignGet also exposes `primary_status`.
- [ReportingApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/ReportingApi.md)
  defines a filtering list; the matching
  [OpenAPI schema](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/yml_files/report_integrated_get.yml)
  requires `field_name`, `filter_type`, string `filter_value`, and permits `IN`.
- The review cites [Basic Report Supported Dimensions](https://business-api.tiktok.com/portal/docs/basic-reports-supported-dimensions/v1.3)
  (document 1751443956638721) for the status enum semantics. This environment's web
  extraction returned no body; a direct public-document fetch was blocked (403).
  Therefore status-specific enum applicability is implemented from the review,
  but is **not independently qualified against a readable current portal body**.
  Confirm this detail before live enablement. No mocked test constitutes live
  provider verification.

`tests/test_tiktok_deleted_history.py` uses the actual HTTP adapter with MockTransport
and database publication. First import records spend; second import simulates
campaign/adgroup/ad/all deletion and returns empty rows unless the exact filters
are present. Every phase takes two pages. Tests assert all three grains retain
12,340,000 micros and another workspace retains its independent 100,000,000 micros.

Against the unchanged PR #75 wire adapter: four SQLite regression failures,
including all-deleted history becoming zero. With the repair: **49 tests passed**
across the deleted-history, HTTP-runtime, and source suites, using SQLite and
explicit disposable PostgreSQL. Ruff, mypy (251 files), and diff checks passed.
Full validation and hosted CI remain pending at this commit.
