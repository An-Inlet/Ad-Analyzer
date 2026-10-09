# Current Campaign Approval Lock Regression Qualification

Base `254b67a`. The PostgreSQL approval wait test now obtains its genuine approved
source from the already reviewed `retained_campaign_binding` producer, then reloads
that binding using current code. All current login, membership, draft creation,
ASGI route call, PostgreSQL workspace lock, concurrent revocation and final
unapproved-row assertions remain. Every original assert AST is identical. The
other upload-race function is unchanged; no shared producer/helper changes.

Full module: **12 passed, two existing SQLite lock-interleaving skips, zero
failures/errors, 64.584 seconds**. Two original PostgreSQL failures are newly
covered; ten upload-race passes overlap previous results. Whole Ruff passed after
an initial import-format finding (preserved); bare mypy passed, 1162 files;
diff check passed. Formatting changed no test behavior.

Evidence: `/workspace/inlet-evidence/20261009/review-lock2/` includes raw initial
and final Ruff output, mypy, qualified log/XML and assertion-preservation JSON.
This current test is marked planning boundary, uses no retained execution override,
and proves the request actually reaches the contested database lock before
revocation. No production code or aggregate run changed.
