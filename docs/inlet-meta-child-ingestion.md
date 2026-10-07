# Resumable Meta Child Performance

Baseline: PR94 `5f9a0d0d4d1d016135c54d3360b16e0800b6f6b6`; includes isolated
Meta lock-order repair PR101. Previously, Meta child models and fixture collector
existed but the scheduler never called them. Customer detail returned metadata and
account-wide comparisons without per-ad or per-ad-set performance.

With the existing `AD_ANALYZER_META_DETAIL_ENABLED` opt-in, campaign inventory and
campaign insights are staged first. The scheduler then advances one child page per
normal `MetaSyncService.page` call: ads, ad-set insights, ad insights. Every HTTP
request uses the existing fixed Graph host, read-only GET, 12-second timeout and
2 MB response bound. `META_SYNC_PAGES` bounds page calls per selected workspace/tick.
Checkpoint commits survive session/worker restarts. The final transaction publishes
campaign, ad-set, and ad daily rows together and deletes staging; earlier snapshots
remain visible on partial results or failed publication. The normal disabled mode
retains the established campaign-only behavior.

Migration0041 (parent0039) creates an owned generation/window checkpoint and minimal
normalized JSON pages. Composite foreign keys bind its workspace/native connection,
canonical advertising account and integration. Under the workspace/native locks,
every page rechecks the generation, owner, window and active integration. Reconnect,
disconnect, stale generations, invalid cursors and unrecoverable capacity/parent
errors clear staging. Transient errors retain the last acknowledged cursor and
persist retry backoff. Canonical revocation rejects import and clears staging when
the worker next examines the connection. Native deletion cascades on PostgreSQL;
service cleanup also deletes pages explicitly for SQLite fixtures.

Bounds: at most100 pages per child phase,300 pages total,30,000 normalized rows and
16 MB normalized payload per window; per-phase cursor history is bounded100. These
are explicit fail-closed capacity limits, not permission to silently truncate data.
Capacity/invalid-snapshot errors are visible through connection error_code and the
customer detail import_status. No raw response, credential, or provider next URL is
persisted. Historical rows whose current owned parent/creative inventory cannot be
validated fail closed and keep the preceding complete snapshot; this is not a claim
that deleted/historical creative attribution has been solved.

Customer detail paginates current ads and ad sets (100 each) and returns each entity's
window impressions, clicks, spend micros, exact decimal conversion string and
conversion-value micros. Missing metrics remain null. Currency and selected conversion
event semantics follow the existing native account/event normalizer. Campaign spend
remains the account total; overlapping grains are never added together. Spend agreement
is tested per campaign/day and ad-set/day, not only at account total. Comparisons are
explicitly informational: common coverage/eligibility is not independently established,
and modeled or delayed provider differences do not reject publication. Current creative
metadata is not historical creative attribution.

## Primary Contract Evidence

Read the official Meta Python Business SDK at commit
[`efd8423a2e595ea8d4c04eb824ce113f2f1d68cd`](https://github.com/facebook/facebook-python-business-sdk/tree/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd):

- [AdAccount.get_insights](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adaccount.py): read GET insights, level, fields, time_increment string and time_range map.
- [AdsInsights](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adsinsights.py): account/campaign/adset/ad levels and requested identifiers/performance fields.
- [Ad](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/ad.py): account, campaign, ad-set, creative and current metadata fields.
- [Cursor](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/api.py): only continue when paging.next and paging.cursors.after are present. Inlet reconstructs its fixed URL rather than following next.

The developer portal Insights page returned429 during inspection. SDK schema evidence
and actual mocked HTTP request tests do not constitute live Graph-version qualification,
real account grants, provider review, or production acceptance. No live calls occurred.

## Verification Ledger

Tests exercise the real scheduler, request builder, bounded HTTP decoder, durable
checkpoint and transaction publisher with offline HTTP responses. They cover restart
at every page, all three paginated phases, last-page failure, cursor cycles, foreign
account/parent rejection, existing snapshot preservation, persisted retry, generation/
revocation/disconnect cleanup, separate-customer facts, composite PostgreSQL constraints,
and populated0041 downgrade/reupgrade. Customer API tests cover scoped per-child metrics
and revoked access. Parent/day mismatch tests deliberately accept discrepant provider
facts while refusing a false account-wide reconciliation claim.

Focused final results and PR are recorded after validation. Full/hosted CI and live
qualification are separate gates; B10 is not claimed complete from this package alone.

Final focused validation: `pytest -ra tests/test_meta_detail_scheduler.py
 tests/test_meta_detail.py tests/test_meta_connection.py tests/test_meta_review_locks.py
 tests/test_inlet_integrated_migrations.py` — **55 passed, 3 skipped** (the SQLite
migration/lock variants), 27.44 seconds. Disposable PostgreSQL variants ran. Full
repository Ruff, configured mypy (291 source files), and whitespace diff checks passed.
Exact command output: `/tmp/inlet-meta-child-final-verified.log`. Full not started;
hosted CI will run on the draft PR. No live provider qualification or B10 completion claim.
