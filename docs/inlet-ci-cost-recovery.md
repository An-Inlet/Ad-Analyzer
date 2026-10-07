# Inlet CI Cost And Recovery Package

Recovery: 2026-10-07. Owner resumed Inlet only after reporting a $10 monthly
Actions budget; the budget itself is not independently verified. Full-scope Inlet
remains the MVP. No website work, capacity purchase, deployment, merge, credentials,
live provider calls or advertising spend is authorized. A confirmed renewed usage
limit requires stopping all project work again.

Preserved application head: a1adc737c101fb760f828fa915e6c228c944abcf.
Recovery worktree: codex/inlet-ci-cost-reliability, based on that exact head.
The source checkout was clean; no other worktree changes were discarded.
Git ls-remote verified main ea3591c5086fbf2cee8038bf9208ac7f0050de75 and
remote codex/inlet-mvp-next d897d1d70953dca13234a2456b5190d542f95a75.
Main and local AGENTS.md, automation policy and validation workflows were read.
The interrupted October 6 validations remain interrupted, not successful evidence.

## Availability And Cancellation Evidence

Git transport works. The shell GitHub Actions API read returned Forbidden. The
connected GitHub read tool succeeded and returned zero in-progress, queued and
waiting runs in three repository-scoped status queries. No demonstrably superseded
active run was found, so no cancellation was performed. Completed failure evidence
is preserved. No new hosted workflow was dispatched and no budget API was available.

## Identified Duplication

The automation regression invokes Full twice, each containing the complete pytest
suite. It runs inside the ordinary suite and is selected again by the later Focused
gate. On a fully successful validation this creates five complete-suite invocations:
one outer plus two nested in each of two wrapper executions. The nested environment
flag limits further recursion, but does not remove this repeated execution.

CI has no concurrency cancellation or job timeout. Python pip caching is already
present; npm package caching is absent. Pull requests to both main and dependent
Inlet branches run the expensive workflow. Push to main is a distinct post-merge
artifact, not automatically redundant PR evidence. Operations Code Validation is
small and path-scoped; the production audit is separately gated. Do not disable
production controls or claim skipped scheduled jobs consumed runner minutes.

## Implementation And Evidence Plan

1. Replace recursive Full-suite execution with bounded Bash/PowerShell orchestration
   regression tests: exact gate order, failure propagation, disposable-target safety,
   and repeated invocation. Preserve actual PostgreSQL reset/migration repeat tests.
   Run the complete behavioral suite once in required aggregate validation.
2. Add safe per-workflow/per-PR-or-ref concurrency cancellation, explicit timeouts
   and npm caching. Keep unrelated branches, manual evidence and production jobs
   separate. Preserve the required Validation context and final aggregate coverage.
3. Provide fast local/focused feedback before the expensive aggregate; document all
   changed gates and ensure a focused-only result cannot masquerade as release proof.
4. Run bounded local orchestration/workflow tests, Ruff/mypy and the known product
   failure fixtures before one assembled Full. Batch any authorized push only after
   a locally validated candidate; no repeated hosted known-failing candidates.
5. Measure actual command counts and elapsed time. Five-to-one suite execution is a
   structural target, not yet measured runner-minute savings. Compare available job
   durations without rerunning the old expensive baseline merely to benchmark it.

Next: implement the orchestration replacement and workflow controls on this isolated
branch. No implementation, new test pass or revised aggregate result is claimed by
this recovery note.

## Implemented Package And Measured Evidence

Only tests, test diagnostics, workflow controls and documentation changed; validation
scripts and application behavior are unchanged. The recursive wrapper and its two
wrapper-specific meta-tests were replaced by 32 parametrized real-script orchestration
cases (Bash and PowerShell). Every one of the 15 commands has an injected failure
case asserting exact status 37 and no subsequent command. Success runs the script
twice with an identical command trace, one complete-suite command per invocation,
all downstream commands retained, and no inherited PYTEST_ADDOPTS, recursion skip
flag or unrelated DATABASE_URL. Only leaf commands are substituted; the Bash
PostgreSQL URL guard executes real Python. Actual database repeat/reset integration
regressions remain and passed against a dedicated disposable PostgreSQL database.

The Validation job name, PR/main/manual triggers, full suite, PostgreSQL, migrations,
read-only, security, privacy, account-isolation and whitespace checks are preserved.
Ruff/mypy now run before the aggregate, with a bounded orchestration preflight.
There are no paths filters, draft skips or reduced required-success contexts.
The operations validation workflow retains its original triggers. Both validation
workflows cancel only stale runs in the same workflow and PR/ref group; manual
runs use their unique run ID and are preserved. Production workflows are untouched.

Existing pip caching remains; npm caching uses browser/auth/package-lock.json.
Operations lint gains pip caching. CI has a 120-minute job limit, 90-minute aggregate
limit and 5-minute bounded preflight; the small operations validation has 10 minutes.
Timeout/cancellation is not success. Aggregate JUnit now feeds the existing bounded
failure artifact collector directly, retaining historical nested-report support and
external-symlink/size protections. Full raw test reports are not uploaded.

Before: five complete-suite executions per successful Full/CI path. After: one
real complete suite; orchestration substitutes leaf tools in its own bounded sandbox.
All downstream gates still execute, including intentional overlap of selected
security/isolation tests. No production skip flag or test-selection switch was added.

Historical hosted measurement (different artifact, not an A/B benchmark): CI run
37438378995, commit b04cab6a7dc5221a04693c5fb9fc7ac6154f103e, Validation job
112185728275. GitHub job timestamps show 144.6 runner minutes (08:46:36–11:11:12 UTC
on October 6); aggregate pytest 84.82 minutes, final Focused gate 57.18 minutes. Removing
four of five suite invocations is an 80% structural reduction in those invocations;
it is not a measured 80% saving of total billed minutes. Actual hosted before/after
savings remain pending one deliberately qualified candidate run.

Local results before commit:
- Automation foundation + orchestration + diagnostics, actual disposable PostgreSQL:
  60 passed, 22 PowerShell-unavailable skips, 30.55s; /tmp/inlet-ci-cost-focused.log.
- Final bounded orchestration/diagnostics after adding aggregate artifact support:
  27 passed, 16 PowerShell-unavailable skips, 6.27s;
  /tmp/inlet-ci-cost-final-bounded.log.
- Whole Ruff and mypy (705 files) passed; whitespace check passed.
- An initial database-create call preceded container readiness and returned connection
  refused. The database was successfully created before integration cases executed;
  this was setup evidence, not a passing validation command.

No hosted run/push or application change in this package. The interrupted full MVP
candidate still needs its known-failure composition and one real complete local Full
before the single deliberate hosted qualification. Full-scope MVP remains required.

The unchanged real Focused shell gate also passed: **37 passed, 6 PowerShell skips,
29 deselected, 27.52s**, `/tmp/inlet-ci-cost-real-focused-gate.log`. It no longer
launches nested Full suites. This is local elapsed time, not hosted billing evidence.

## Independent Review And PowerShell Closure — October 7

An independent agent reviewed exact155dad29 read-only: no actionable coverage,
failure-propagation, concurrency or cache regression found. Its bounded rerun was
27 passed/16 unavailable-PowerShell skips; those skips were not treated as approval
of PowerShell behavior. No source repairs were requested by review.

Installed the official Microsoft Debian13 PowerShell7.6.6 package in the isolated
/workspace/inlet-powershell prefix. Package metadata came from
https://packages.microsoft.com/debian/13/prod/dists/trixie/main/binary-amd64/Packages.gz;
verified SHA256 efae8744e1e552c07ffd7d56782c71813c25d456f8edfb1cabb4f3bb2bfdc248.
Microsoft installation/support guidance:
https://learn.microsoft.com/en-us/powershell/scripting/install/install-debian.
GitHub's public release API returned403; the official Microsoft package endpoint
succeeded. No third-party build, package credential or hosted runner was used.

Initial launch hit the sandbox's read-only home cache (22 failures/61 passes in
32.77s). A local /workspace/inlet-tools/pwsh launcher sets XDG_CACHE_HOME,
XDG_CONFIG_HOME and XDG_DATA_HOME to writable /workspace/inlet-powershell-state
subdirectories, then execs the official binary. HOME and repository source are
unchanged. This launcher is environment setup, not a test stub or altered script.

Final command with PATH=/workspace/inlet-tools:/workspace/inlet-venv/bin:$PATH and
explicit disposable PostgreSQL configuration:
`python -m pytest tests/test_validation_orchestration.py
 tests/test_validation_diagnostics.py tests/test_automation_foundation.py`:
**83 passed, zero skips,41.60s**; /tmp/inlet-ci-powershell-closure-fixed.log.
All22 previously skipped PowerShell cases now executed successfully. This closes
this package's shell verification gap; it does not qualify the entire product.

Actual browser preflight also passed both synthetic H.264 and AAC blob decodes with
Chromium151.0.7922.173, /tmp/inlet-browser-preflight.log. No application code changed.
