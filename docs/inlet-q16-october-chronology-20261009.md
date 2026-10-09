# Q16 Natural October Chronology Qualification

Branch `codex/inlet-q16-october-chronology`, isolated worktree `/workspace/inlet-q16-october-chronology`, base `7259317`. Root approved the additive interface before implementation. No production code, auth validator, global time, TTL, default policy, W1 source/database or external provider changed.

## Frozen Shared Interface

`tests.q16_fixture.prepare_q16_case(..., generation_stage: Literal["nov3", "october"] = "nov3")` preserves the existing default and unchanged `Q16Ids`. October mode uses the original real session; actual goal HTTP confirmation precedes fresh real-time paid/media/native preparation and plan generation. The existing API callback samples fresh real UTC on every invocation. The generated timestamp is checked against the real clock and existing goal preview timestamp; the matching confirmation row is checked without inventing a confirmation timestamp.

`import_progress_stage(..., stage="initial_day")` adds an actual empty import at November 3 05:05Z. Existing later/refund operations remain unchanged. Caller explicitly reconciles paid state, issues a fresh ordinary session and changes the existing API clock seam. See [approved contract](design/q16-october-plan-chronology-proposal.md).

## Actual Evidence

The new October parameter of `tests/q16_archive_acceptance.py`:

- Creates a genuine decision and unverified manual-application assertion after actual October V1 generation. Uses exact server digests/CAS, reports the actual generated timestamp, and receives two successful events. Archived assertion has `verification=customer_report_only`, `spending_authority=none`, and advertising writes disabled.
- Advances fixed November stages, proving $0→$25→$20 with closed-day counts2→3→3; expired October/previous-day sessions reject before fresh ordinary logins. Goal/V1/document digest and both event documents remain unchanged; version/input/request/event/goal/snapshot counts do not change across reads. Progress explicitly remains manual-application not assessed and attribution unavailable. Native calls stop after generation.
- Builds/delivers an actual complete archive containing both events. The existing after-real-build erasure hook rejects delivery and closes the file; a fresh complete archive has no plan graph or old plan ID. Genuine paid billing rows and foreign populated configuration remain untouched; revoked-session download rejects.

The old November parameter still proves its future manual-report timestamp rejects422 and only a genuine decision exists. The original exact dated API four cases are unchanged. No full Q16, expert quality, browser, live or optimized-recommendation claim.

## Checks

Final single compatibility invocation: **8 passed, zero skipped, 61.276 seconds** across SQLite/PostgreSQL. This comprises old exact API4, old November archive2 and new October archive2; do not add prior overlapping runs. Raw `qualified.log/xml` and per-case before/after manifests, plan/event payloads and three progress projections are retained under `/workspace/inlet-evidence/20261009/q16-october/qualified-artifacts/`.

```
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
/workspace/inlet-venv/bin/pytest -q tests/q16_exact_acceptance.py tests/q16_archive_acceptance.py \
  --basetemp=/workspace/inlet-evidence/20261009/q16-october/qualified-artifacts \
  --junitxml=/workspace/inlet-evidence/20261009/q16-october/qualified.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Whole Ruff and bare mypy1,122 passed (`ruff.log`, `mypy.log`); diffcheck passed. No Full rerun. Initial probe failure (`first.log/xml`) correctly rejected a captured fixed actual-time API clock because subsequently gathered native evidence was newer; fixed by fresh real callbacks, matching production. Initial mypy caught a test assumption that GoalConfirmation had created_at; corrected to actual preview timestamp + matching confirmation row. The confirmation HTTP success happens before generation, but its model has no own timestamp. Both new cases then passed (`second.log/xml`) before the final eight-case run. These are fixture corrections, not production defects or relaxed validation.

Next: independent review of this qualified helper/API chronology before the browser lane consumes the new mode. Existing dated October validity restriction remains explicit and outside default test collection.
