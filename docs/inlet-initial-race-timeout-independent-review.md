# Independent Initial Start Race And Timeout Review

Read-only review of frozen author commit `3e6537dd04d677354a05775dfacd39163575c19d`
in `/workspace/inlet-initial-start-binding`, including the underlying Start path.
This documentation successor starts from independent acceptance `086c426`; it does
not copy author application/test changes or alter the active qualification artifact.
Line references below identify inspected code, not a claim of current remote state.

## Concurrent Start Review — Closed, No P1/P2 Findings

At `3e6537d`, `tests/test_initial_concurrent_start.py:47–52` runs the actual catalog
then synchronizes each thread's first read at a barrier. Both callers have passed
initial absence checking and committed before these reads. Lines59–66 use separate
PostgreSQL sessions and the actual `service.start`; lines67–77 assert the same run
ID, one run/link/candidate/opportunity, no attempt and no provider POST. SQLite is
explicitly skipped at lines34–35 because its locking is not this acceptance proof.

The corresponding [Start implementation](../app/initial_planning/start_service.py),
lines162–180, releases the local transaction before provider reads, reacquires
current authority and mandate, then checks `existing_start` again before insertion.
[Candidate authorization](../app/optimization_candidates/service.py), lines135–139,
calls `lock_customer_mutation`; the second check therefore occurs under renewed
customer/workspace authority. Lines233–241 bound the eventual Start expiry by the
earliest dependency, named policy, mandate, preview and selection expiry.

The author reported the PostgreSQL race passing in10.79seconds plus Ruff/mypy938/
diff checks. This independent review inspected the frozen test and code; it did
not rerun the race or claim independent timing. The race proves convergence for
simultaneous identical original Starts, not arbitrary cross-session consent
changes. Separate acceptance `086c426` covers competing workers after Start,
revoked mandate, exhausted budget, configured maintenance and0085 refusal.

## Time Limits Are Different Boundaries

| Source and inspected lines | Value/behavior | What is not established |
| --- | --- | --- |
| [Fixture profile](../tests/test_planning_reporting_configuration.py):19–34 | Explicit native HTTP5s, total acquisition20s, observation TTL30s | These are contract-test values, not shipped production defaults |
| [Settings](../app/settings.py):216–220 and [policy contract](../app/planning_reporting/contracts.py):14–29 | Production profile path/digest defaultNone; timeout/TTL policy fields require explicit values | No automatically selected30s production observation lifetime |
| [Meta native collector](../app/collectors/meta_budget.py):65–79,103–111,224–231 | Monotonic deadline checks, HTTP timeout capped by remaining budget, final observation expiry check | Checks occur at control points; they are not an independent thread/process cancellation at exactly20s |
| [Optimization HTTP](../app/executors/optimization_http.py):116–140 | HTTPX timeout12 and30s elapsed streaming guard checked on yielded chunks, plus2MB response bound |12s is the HTTP phase/inactivity configuration, not an overall call upper bound. The30s check cannot asynchronously interrupt a blocked request/context callback; no whole-journey30s SLA follows |
| [Owned catalog](../app/production_runtime/optimization_catalog.py):104–119 |60s monotonic guard checked by `check()` around context/read work, also respecting context expiry | Not a hard wall-clock cancellation mechanism for every nested call or the two catalog passes in Start |
| [Operational settings](../app/settings.py):564–577 | Configured web60s, worker900s, scheduler300s, shutdown30s | Merely reading these settings does not prove live platform enforcement, cancellation behavior, or source-evidence validity for those durations |

No deadline is extended because a worker's outer runtime setting is longer. The
positive initial fixture explicitly supplies120second observation/preview lifetimes
before evidence production. It proves the configured path under those values. The
ordinary contract-test30second profile's expiry tests prove denial on stale evidence;
they do not prove a successful complete path within30seconds at production latency.
This corrects earlier shorthand referring to an “ordinary30second default.”

## Expiry And Uncertain Emission Safety

[Optimization execution](../app/publication/optimization.py), lines978–1026, performs
fresh state/provider validation, reacquires locked authority after blocking IO,
rechecks forward provenance and evidence lifetime, then durably marks the step
`emitting` before calling `apply_once`. Apply exceptions become an unknown response;
readback exceptions become an unknown receipt. These evidence checks prevent stale
proof from granting a new action; they cannot promise a provider call already sent
will be canceled by an outer timeout.

The existing initial unknown-response test in `tests/test_initial_rule_start.py`
(mode unknown at the reviewed author tree) records one original attempt/fence,
Stops, erases the candidate and reconciles the original native target. It asserts
one POST and a still-held reservation. This is mocked-provider evidence of no
replay/hold retention, not real-provider settlement, request cancellation or charge
finality. Losing the worker after durable emission must remain uncertain rather
than automatically reclaiming a provider claim; this review changes no such guard.

## Remaining Qualification And Validation

Representative successful latency, scheduler dispatch delay, chosen production
TTL/profile values, transport failures at each actual deployment boundary and live
outer-timeout enforcement remain unqualified. A longer positive fixture must not
be presented as qualification of the shorter profile. No numerical production
policy/default, timeout, authority or spending guard was changed by this review.

Validation for this docs-only package: source inspection, relative links where the
file exists in this branch, and `git diff --check`. The concurrent-Start test is
referenced at author commit3e6537d and is intentionally not copied into this earlier
acceptance branch. No new runtime tests, Full/hosted retry, provider calls or active
initial/rule branch edits.
