# Initial Rule Ordinary Fixture Operating Probe

Frozen clean source: `3136b70b35bee928c1fe72646fce4fbfae856a1d`, isolated `/workspace/inlet-initial-objective-factoring`. No production code/configuration/deadline edits. PostgreSQL disposable per-test schemas; root Full and other worktrees untouched.

## Scope and supported declaration

Three actual configured API Start → configured runtime → worker → offline HTTP-provider executions pass with the existing explicit test fixture native observation lifetime30s and initial preview maximum60s. The effective preview deadline is capped by the native source. This proves this offline functional path under the sampled load, **not robust ordinary-profile support or production latency qualification**. No registered production evidence source/profile exists by default, customer session automation defaults disabled, and profile settings default absent. No real provider or network latency is represented by the mocked HTTP transport. Review dwell and dispatch delay consume the same evidence lifetime.

|Sample|Worker elapsed s|Start TTL remaining s|Admission exit remaining s|Claim exit remaining s|POST remaining s|
|---|---:|---:|---:|---:|---:|
|1|23.371570|26.361933|13.207922|6.616140|0.559985|
|2|20.268366|26.255546|14.988|8.764|3.505206|
|3|20.295792|25.968076|14.942|9.026|3.780772|

Worker median20.295792s, range20.268366–23.371570s. Each sample persisted one original attempt/response/receipt, verified_target_state, and retained its exposure hold. Raw JSON contains exact preview and native ages, UTC timestamps, perf_counter phase times and SQL counts. SQL instrumentation overhead is included and unquantified. Concurrent root Full remained active; repeat load averages recorded in provenance. Counts are not timing claims.

## Real dispatch delay

After actual Start, a31-second real wall-clock delay was injected immediately before worker.advance, without modifying any authority clock. Initial positive assertion failed diagnostically at409 original_session_ended (expiry), before admission/claim/provider POST. An explicit adverse assertion rerun passed in43.29s: TTL−7.015190s at rejection; zero admissions/attempts/responses/receipts, no execution steps or exposure reservations. The positive diagnostic failure is preserved, not counted as a passed test. No retry or replay was attempted.

## Timeout distinctions and uncertainty

The native read5-second per-request timeout,20-second whole-read deadline and30-second observation lifetime are required values supplied by the existing contract fixture (`tests/test_planning_reporting_configuration.py`), not production numeric defaults. `app/collectors/meta_budget.py` bounds each read by remaining collection time and rechecks current original session/source/goal after IO. They do not describe worker execution timeout.

`worker.advance` has no30-second execution timeout. `Settings.worker_timeout_seconds` defaults900 and feeds deployment process policy; it grants no authority lifetime. Execution transport (`app/executors/optimization_http.py`) independently configures HTTP timeout12s and a30-second streamed-response bound. Neither extends source authority. Final post-IO authority/document/time checks remain immediately before durable emitting state in `app/publication/optimization.py::execute_claim`.

A failure before emission is denial. Once provider emission is attempted, exceptions become unknown response and failed readback becomes unknown receipt; retained original attempt/exposure and read-only reconciliation apply. The ordinary samples did not exercise provider uncertainty; existing focused unknown-path tests are separate evidence. A slow real provider, queue delay, customer review dwell or contention may exhaust the very small observed margin. No robust lower bound or production supported envelope can be inferred.

## Reproducibility

Raw `initial-ordinary-{phases,repeat2,repeat3,delay31,delay31-audited}.json/.log` are retained under `/workspace/inlet-evidence/20261007`, with the original probe record. `initial-ordinary-provenance.json` pins head, source/test script SHA256, subprocess status, actual delay and sampled host load. Saved scripts: `inlet_ordinary_phases.py`, `test_initial_ordinary_profile.py`, `inlet_ordinary_audited.py`, `test_initial_ordinary_delayed.py`. Scripts are out-of-tree copies/instrumentation; positive test copy only removes the120-second fixture override. Audited adverse copy replaces successful-worker assertion with explicit expiry/zeroeffect assertions. Tests run with existing isolated PostgreSQL test fixtures. First sample preceded the output-path/delay instrumentation options; its phase collector semantics are otherwise unchanged.
