# Q16 October UI Chronology — 9 October 2026

Isolated branch `codex/inlet-q16-browser-chronology`, base `a368e22`.
Uses the reviewed additive October fixture `9b43f9e` without modifying it.
Only the explicitly invoked dated browser test and its private driver change;
no production source, global clock, TTL, validation, advertising authority,
shared fixture, W1 checkout/database, or live provider is changed.

## Actual Browser Contract

The existing four November-generation cases are retained. Four additional cases
cross SQLite/PostgreSQL with progress/privacy using October generation. The
actual production page/controller submits a decision and a customer application
report through real HTTPS APIs, exact server action/document digests and current
CAS. There is no API event seed. Both records are read back as immutable history;
the application report remains `customer_report_only`, not provider verification.

The current UI accepts application timestamps only to the minute. To avoid
reporting an application before this plan existed, the test naturally waits for
the next representable minute after actual generation, at most 60 seconds. It
checks the actual server document is still current and has the original digest
before submitting. The reported time must be at or after generation and no later
than the actual browser clock. No form-validity bypass, backdating, regeneration,
or evidence-deadline extension occurs. The outer test-only browser timeout is
150 seconds instead of 90 to allow the additional natural wait plus the existing
journey. Production deadlines are unchanged.

The actual empty November 3 import advances progress to zero; a real later order
and refund then produce $25 and $20. Fresh ordinary sessions are issued at dated
stages, with actual old-session 401 assertions. The same saved V1, digest, goal
and exact event payloads persist. Each reopened plan explicitly reads customer
history using the real UI button. Sales progress still says manual application
is not assessed and attribution is unavailable; it never changes a task to a
verified completed state or claims the sale was caused by the report. Missing
advertising reporting remains explicit; no additional native read occurs.

In the separate privacy branch, both genuine UI records exist before erasure.
After actual privacy erasure and explicit refresh, the plan, sales progress and
customer history are empty. The already-computed actual held response is drained
on a clone, its original Response is preserved, and the controller gets a
following task to reject the stale epoch before empty-DOM assertions. This is
client-side nonresurrection, not revocation of all already-computed server bytes.

## Evidence And Limits

Evidence root: `/workspace/inlet-evidence/20261009/q16-browser-chronology/`.
Each case keeps actual `original-artifact.json`, `fixture-ids.json`,
`browser-result.json` (including both October event payloads) and
`progress-responses.json`. The generated document is synthetic, unscored and
not expert approved. No screenshot or image-understanding claim is made. The
existing actual uploaded synthetic asset remains a textual media/SHA reference.
No comprehensive Q16, live integration, causal attribution or plan-quality pass
is implied.

Initial October-only run: one SQLite failure in 52.983 seconds (`first.log/xml`).
Both actual UI records saved, but after reopening the plan the driver incorrectly
expected history to load automatically. Corrected only the driver to explicitly
click Read Customer Decisions And Reports, preserving the product's explicit
read behavior. No surviving process was restarted after the environment
reconnected; the terminal result was inspected first.

Final command (with the existing nonaggregate disposable PostgreSQL fixture
environment):

```sh
/workspace/inlet-venv/bin/pytest -q tests/q16_browser_acceptance.py \
  --basetemp=/workspace/inlet-evidence/20261009/q16-browser-chronology/final-artifacts \
  --junitxml=/workspace/inlet-evidence/20261009/q16-browser-chronology/final.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
node --check tests/javascript/q16_browser.mjs
git diff --check
```

Final qualification: **8 passed, 0 skipped, 202.012 seconds** (`final.log/xml`):
original November4 plus new October4, with no overlap added to that count.
Whole Ruff passed; bare mypy passed all 1123 files; Node syntax and diff checks
passed. Natural minute waits account for most of the additional wall time.
Actual SQLite example timestamps: decision `2026-10-09T01:06:00.115925Z`,
report recorded `2026-10-09T01:06:00.292621Z`, application
`2026-10-09T01:06:00Z`. Full per-case source generation and event timestamps are
in the retained artifact/result JSONs. Final success includes both PostgreSQL
October journeys and both preserved November modes.
