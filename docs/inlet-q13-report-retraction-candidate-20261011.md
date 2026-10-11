# Q13 V6 Report/Retraction — Unqualified Test Candidate

Base bcc362a; contract33d832e. One new test module exercises actual original-session
V6 create/generate/report/replay, milestone edit/successor generation and historical
report withdrawal through existing APIs. No production/default/retention changes.

Source and immutable execution manifest were independently reviewed before the
parent authorized SQLite once. PostgreSQL requires separate authorization and was
not authorized or run. Source bytes remain those pinned in the execution manifest.

## Stopped Qualification

`tests/test_owner_review_report_retraction_api.py::test_v6_report_and_historical_retraction[sqlite]`
failed: second actual POST `/generate` returned HTTP409 with the exact fixed detail
`planning_authority_expired`, at the expected-success assertion (line146). Original
pytest exit1, one failure, zero passes; pytest33.51s. The runner stopped and retained
log/XML/result/resources. PostgreSQL remains unrun. No retry or instrumentation.

First actual generation, initial report, report replay/receipt lookup, changed-key
refusal and input edit completed their assertions before this failure. Historical
retraction, its replay/negative checks and final exports were not reached. This is
not Q13 acceptance or qualification of the entire report lifecycle. The uninstrumented
HTTP outcome does not identify an internal phase, fact age, cause or remedy and
cannot close prior reliability incidents. Root integration is held pending changed
runtime qualification; this local commit freezes an unqualified test candidate only.

## Static And Preparation Evidence

Whole Ruff passes (`ruff01.log`, final `ruff02.log`); configured no-path mypy final
passes1490sourcefiles (`mypy02.log`); exact collection contains SQLite/PostgreSQL only;
`git diff --check` passed. First mypy exit1 found only the test's timestamp expression
inferred as object. `typing.cast(str, ...)` repairs typing without runtime changes;
collection identity unchanged. A concurrent resource sample fell below the512MiB
memory reserve. The attempted targeted stop found no owned PID because mypy had
already terminated naturally; no signal was delivered. The resource record retains
an empty interrupted-PID list. Warm-cache final mypy used an explicit reserve watcher
and completed successfully. No pytest-body failure occurred during preparation.

Evidence: `/workspace/inlet-evidence/20261011/q13-owner-report-retraction/`.
Immutable manifest SHA256:
`e05c0ed3b69c6dfe8da24e0e734bf152ca680b50f0dc9dca456773c31d9cd870`.
Runner SHA256:
`bcadd61e33aa6c98a454de2b4939954fb32fdc3f5b7c1b359771843a5024fbbb`.
Failure summary (`sqlite01-summary.json`) SHA256:
`955d6dfbf08ff878fede8e0c7dc3274c86afa49bf175906764b3e8f6d36d3b46`.
The summary records source hashes and evidence hashes/lengths, including original
failed static output, exact XML and phase authorization. Prior cohorts untouched.
