# Selected Summary Preparation — 2026-10-11

Added pure `summarize_selected_capture`: validates the entire immutable graph and
exact current dependency DTOs before slicing dates, keeps count/value presence and
missing calendar days independent, sums with explicit Decimal precision, and permits
full-window zero only for supported evidence present on every requested closed day.
The summary retains the whole capture digest; an out-of-slice malformed/corrected
source cannot disappear behind a requested slice. No aggregate conversion fallback.

Independent review closed with no P1/P2 in this pure arithmetic/DTO scope. This is
preparation for the future owned plan reader, not actual customer-plan activation.
Caller DTO equality does not prove authorization, current storage or provider support.

Checks: `pytest tests/test_selected_summary.py tests/test_selected_raw_observations.py
 tests/test_selected_reporting_contracts.py tests/test_reporting_presence_summary.py
 -ra`:156passed,0skips,0.88s (13new summary cases). Ruff repository pass; mypy app/tests
1278files pass after correcting a test-helper dict annotation. Initial typing errors
retained at `/workspace/inlet-evidence/20261011/selected-summary/mypy-initial.log`;
focusedJUnit/log and final checker logs are alongside. Diff check passed before commit.
No database, provider I/O, default factory or public API changed. No full aggregate
rerun, push, hosted run, merge, deployment, live call or advertising mutation.

Durable selected storage proceeds independently against the reviewed interface in
an isolated branch. The next injected Google read port is documented in
[its interface](design/google-selected-read-interface-v1.md); runtime/provider
qualification and customer selection remain separate prerequisites.
