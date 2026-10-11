# Private V5 Runtime Qualification — 2026-10-11

Qualification is in progress against service commit `4100fe5`. The default customer
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
