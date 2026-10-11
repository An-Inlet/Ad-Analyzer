# Q06 repeated-owner request qualification

Test-only child of `634b55a`; no production, browser or shared fixture edits.
`tests/test_google_owner_repeated_hypotheses_api.py` qualifies the existing
whole-request uniqueness rule for `(account_id, owner_selection_id)` using
`configured_owner_review` and its real API-acquired original-session receipts.

Two independently reconciled alternatives each total the actual confirmed
1,000,000,000-micro ceiling. Same requested daily amounts (5M/5M) and different
amounts (4M/5M) both receive the existing duplicate-owner refusal. This tests the
implemented whole-request rule; independent alternatives are not inherently
economically conflicting, and no daily-to-period calculation is inferred.

Before the first request, the fresh replica installs a narrow original-once
wrapper around the production validation handler. Public output is exactly HTTP
422 with `{"detail":"invalid request parameters"}`. The wrapper retains only
the error location/type/message in memory: `body.inputs`, `value_error`,
`Value error, duplicate budget owner intent`. It retains no error input/context
or request payload. Exact planning/head/request/dependency rows and original
catalog/selection/input-link rows remain unchanged; financial/execution counts
remain zero; both independent MockHTTP acquisition call lists remain unchanged.
The original session comparison exposes only a boolean on failure.

## Qualification and evidence

Evidence root: `/workspace/inlet-evidence/20261011/owner-repeated-hypotheses`.
Manifest `d13cccddd312a58472f17c5be2ad70acd24a04b54fd8d301334d0a1e2324a6f3`
and runner `bcadd61e33aa6c98a454de2b4939954fb32fdc3f5b7c1b359771843a5024fbbb`
were independently reviewed before separate parent authorizations for each phase.

- `python .../run_qualification.py sqlite`: exit 0, two passed, pytest 8.45s.
- `python .../run_qualification.py postgres`: exit 0, two passed, pytest 22.34s.
- Exactly four distinct cases; no failures, skips, retries or repeated cases.
- Whole `/workspace/inlet-venv/bin/ruff check .`: passed.
- Configured `/workspace/inlet-venv/bin/mypy --cache-dir /tmp/inlet-repeated-owner-mypy`
  with no source paths: passed, 1,485 source files.
- Whitespace checks produced no diagnostics. Test source remained unchanged
  through static checks and both executions: SHA256
  `7cf21bea620074d4ea8db16c6676b127fd4a10903d03c043b9c0bac0b48de7bc`.

`manifest.json` retains exact commands/node IDs and disposable local PostgreSQL
fixture configuration; each phase uses `-x`, its own fresh basetemp/cache/JUnit/log,
sanitized environment and no profiler. Runner checks source/head/floors/sole test
slot and refuses preexisting output paths. PostgreSQL uses per-test isolated
schemas, without database reset. Separate authorization files bind the immutable
manifest hash. `summary.json` hashes the retained logs, XML, commands, authorizations
and draft runner evidence; SHA256
`07efe15df1390e6ce0382a3bb6ddf63db6f780d9cf6d4e8e9f7cc632c69dfb9a`.

The first collection was count-only because configured and explicit quiet options
combined; a second collection enumerated the exact four nodes. Neither executed
test bodies. Initial runner drafts remain retained; preflight review corrected
benign JUnit-child handling, early subprocess-outcome persistence, per-phase
authorization and fresh cache/path checks before any execution. No test failure
was discarded and no production behavior changed.

This is request-admission evidence only. It does not qualify generation, edits,
replay, browser presentation, distinct opaque options resolving to one native
owner, actionable native settings, period-spend compatibility, performance margin
or any historical authority-expiry incident. Existing Q06 native-setting and
human-usefulness limitations remain.
