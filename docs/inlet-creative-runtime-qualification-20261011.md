# Private V5 Runtime Qualification — 2026-10-11

Normal qualification passed after service `4100fe5` and performance slice `e478b4b`.
Earlier failed attempts and the unresolved timeout cause remain recorded. The default customer
service remains V3. V5 requires the exact canonical server policy and an explicit
private media store. No live provider, advertising write, hosted CI, push, merge or
deployment is part of this work.

The new tests use actual HTTP media upload, input save, generation, history,
export, correction and privacy lifecycle routes. Native provider responses and
identity are local fixtures; generated documents, proofs, dependencies and receipts
are produced by the real service. Google positive evidence includes 100 clicks,
10 selected conversions and $100 spend. Social output retains unsupported selected
reporting and production-required creative status.

## Retained attempts

Evidence directory: `/workspace/inlet-evidence/20261011/creative-runtime-api/`.

- `probe01`: incorrect copy working directory; collection exited 4 with no tests.
- `probe02`: genuine Google generation succeeded, but a coverage-label assertion
  failed. Corrected the assertion to check the numeric selected count without
  assuming the wrong coverage label.
- `probe03`: five SQLite positive journeys passed before final service freeze.
- `probe04`: six SQLite negative/lifecycle probes passed before final freeze.
- `probe05`: two SQLite unexpected-callback probes passed before final freeze.
- `final06`: six passed, one failed, then stopped; remaining 21 cases did not run.
  PostgreSQL Google one-image generation returned `planning_authority_expired`.
  The five-second identity freshness limit correctly rejected acceptance. The
  cause of this individual delay has not been established.
- `timing07`: the isolated failed PostgreSQL case passed with instrumentation;
  maximum identity age was 2.724 seconds. This is diagnostic evidence, not proof
  that the earlier failure was repaired.
- `timing08`: PostgreSQL Google two-image journey passed; maximum identity age was
  2.759 seconds. That interval performed 2,627 SQL calls (0.560 seconds SQL wall
  time, 2.467 seconds process CPU). Instrumentation preserves the real clocks and
  authority checks and logs no SQL text or parameters.
- `remaining09`: nine passed, then the PostgreSQL input-race test blocked on its
  own preparation transaction. The hook also ran inside catalog resolution, before
  preparation committed. Root canceled only that blocked test UPDATE; pytest
  recorded one failure and stopped. This was a test fault-injection defect, not
  evidence of a production lock failure. Remaining ten cases did not execute.
- `negative10`: reruns eight strengthened negative cases on both databases. The
  input-race hook now mutates only during the second resolution call, after the
  preparation transaction commits. Exact error and injection markers are required.
  One passed, one reporting-error assertion failed: its actual bounded reason is
  `current campaign reporting evidence unavailable`. Corrected that expected
  reason; the unexpected result and log remain retained.
- `negative-lifecycle11`: 18 strengthened negative/lifecycle cases on both
  databases passed, zero failures/errors/skips. Whole Ruff and configured mypy
  (1,407 files) passed. Exact elapsed time is retained in the JUnit artifact.

Whole Ruff and configured no-path mypy passed (1,407 files) before `final06`.
These checks do not constitute a new exhaustive qualification of the entire
successor branch. The frozen predecessor qualification and all artifacts remain
unchanged.

## Review and next work

Independent review found a P2 evidence gap in negative tests accepting any 409.
Require explicit injection markers and the intended error, especially a populated
flush marker plus `generation evidence expired`, so an unrelated authority timeout
cannot qualify the rollback boundary. The repair passed all 18 negative/lifecycle cases on both databases; independent
source review closed the P2.

A narrow transaction-local validation reuse design was approved at `02dce3f` from the
measured repeated graph reads. It must preserve ownership, lock ordering, clean
transaction checks, independent fresh passes, original observations and deadlines,
copied-model validation and the five-second identity limit. No performance repair
or cause resolution is claimed yet. Common Basis V5 artifact implementation waits
for this runtime fixture to be reviewed and frozen. Human expert usefulness,
browser, live integration and release gates remain unmet.

The three runtime test files are frozen for reuse. Their scenarios have passed
across the recorded runs, but the initial whole-cohort authority expiry remains an
open performance investigation. A final normal 28-case cohort is required after
the separately reviewed performance slice; diagnostic passes do not erase failures.

## Integrated Normal Qualification

After reviewed performance commit `e478b4b`, `final12.xml` passed all 28 actual
API/lifecycle cases on SQLite and PostgreSQL in 319.863 seconds, with zero failures,
errors or skips. No timing plugin or clock replacement was loaded. Whole Ruff
passed and configured no-path mypy passed 1,408 files. This supersedes the pending
normal-cohort gate above; it does not erase `final06` or establish its root cause.
Bounded comparative timing and a deliberate real-clock authority-expiry test remain
separate checks.

`timing13` passed both PostgreSQL one/two-image journeys after integration. Combined
SQL calls were 29,471 versus 32,531 across the earlier two diagnostics. The maximum
identity interval used 2,217 calls versus 2,627, but its age was 3.693 seconds versus
2.759 seconds previously (SQL wall time 1.033s, process CPU 2.999s). Thus structural
query reduction is verified; elapsed-time improvement is not. No retry or expanded
optimization is justified from this measurement alone. The original timeout cause
remains unproven. `runtime-qualification.json` retains attempt counts and XML hashes.

The real-clock expiry regression is integrated at `db4a220` and independently
review-closed. SQLite passed in 15.774s and PostgreSQL in 20.758s: after genuine
retained capture, one six-second delay triggers the original five-second guard
and leaves no generation writes. See the [expiry package](inlet-creative-authority-delay-package-20261011.md).
