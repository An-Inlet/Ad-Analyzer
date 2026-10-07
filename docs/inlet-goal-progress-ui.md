# Customer Goal Sales Progress UI

The workspace page selects the current saved goal revision and requests its owned
sales-progress projection. Available amounts remain signed (including refunds and
true zero). Unavailable and not-started responses show no sales amount. The view
retains the original target, closed-day coverage and time zone, source watermark,
as-of time, and explicit non-achievement/non-attribution/no-spending labels.

A local edit clears the projection until save or reload. A separate request epoch
binds responses to the goal revision and workspace; the original session-cookie
context is checked before and after reading. Refresh clears prior numeric output
before requesting current information. Errors cannot retain an earlier amount.

First UI checkpoint: portal/render checks 12 passed in 7.49 seconds. Additional
late-progress-response after local edit plus pure contracts: 2 passed in 6.89 seconds.
Ruff and mypy for the new Python runner passed; Node syntax and git whitespace checks
passed. Tests preserve genuine zero/negative amounts, unavailable nulls and mismatch
rejection. The existing mocked portal fixture now explicitly supplies an unavailable
progress response instead of expecting the removed static unavailable paragraph.

Backend e7fa9be is integrated. Actual HTTPS Chromium → assembled FastAPI →
SQLite/PostgreSQL acceptance passed (2 tests in 7.54 seconds). The fixture confirms
a real goal and imports normalized Shopify sales/refunds through CommerceSyncService;
only identity and provider boundaries use test fixtures. The browser reads the actual
owned progress route, preserves negative refunds, refreshes an importing source to
unavailable, restores current progress, clears unsaved edits, and discards actual
held responses after workspace changes and logout. Snapshot counts remain unchanged.
No browser fetch or goal-progress service substitution is used.

Final portal/render regressions: 12 passed in 6.86 seconds. Whole-repository Ruff
passed; mypy over app and the two new Python runners passed (441 files). Separate
focused runner mypy, Node syntax, and git whitespace checks passed. PostgreSQL used
an isolated schema in the disposable test database, without resetting that database.
Unavailable coverage metadata does not render a measured-day count.

It adds no provider calls, data retention, achievement inference, advertising
attribution or spending authority. No Full, remote CI, deployment or demo artifact.
