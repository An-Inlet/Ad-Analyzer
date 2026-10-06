# Meta Lifecycle and Campaign Review Lock Order

P1 repair based on PR94 `5f9a0d0`. No provider calls, changes to grants, advertising
writes, migrations, merge, or deployment are part of verification.

Campaign review acquires the workspace, mandate/goal, advertising account and
integration locks before reading the current Meta connection generation. Native
Meta disconnect previously acquired Meta first, then updated the integration;
reauthorization acquired pending grant and Meta before upserting the account.
Controlled PostgreSQL barriers reproduced `DeadlockDetected` for both operations
against the complete `campaign_review.service.binding` path. The baseline log is
`/tmp/inlet-meta-review-baseline.log`; the retained regression contains the fixture
and deterministic barriers. Existing dashboard membership and customer principal
checks preceding these services are reads and introduce no row-lock inversion.

Native Meta lifecycle now takes the same workspace `FOR NO KEY UPDATE` fence before
locking a pending grant or connection. Native campaign and direct child imports do
the same; scheduled imports skip a busy workspace rather than waiting. This fence
serializes review and lifecycle transactions without blocking foreign-key KEY SHARE
locks. Suspended workspaces can still disconnect, and imports keep their existing
ownership/status checks. Approval revision, generation and revoked-scope checks are
unchanged. Post-repair regressions verify generation changes and disconnect still
invalidate the prior connection binding.

The tests use a disposable PostgreSQL schema and fake provider, not live Meta. SQLite
cannot verify this lock-order behavior and explicitly skips the two barrier cases.

Verification: focused SQLite/PostgreSQL suite
`pytest -q tests/test_meta_review_locks.py tests/test_meta_connection.py tests/test_meta_detail.py tests/test_campaign_review.py`
passed: 69 passed, 3 SQLite-only lock-test skips (72 collected), including both new
PostgreSQL barriers and populated migration regression. `ruff check .`, repository
configured `mypy` (289 source files), and `git diff --check` passed. An exploratory
`mypy .` invocation was not the repository command and fails module discovery because
it includes the scripts directory twice; configured `mypy` is the required check.
Full and hosted CI remain pending; no live behavior has been verified.
