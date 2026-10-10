# Corrected W1 Validation — 10 October 2026

## Current Result

All 1,330 original failing identities now have passing targeted successor evidence:
1,172 direct cases and 158 preserved historical cases with current-policy coverage.
This is not an aggregate pass. The corrected, unfiltered aggregate is running on
frozen commit `9d7aa2e1193ec627b33088764210f94e49cf504d`.

The canonical collection succeeded with 7,094 parent cases, including 19 separately
identified historical wrappers. Their 407 children are reported separately and
must not be added to the parent total. The original failed aggregate and its
`6a3b0f1` source remain unchanged; its XML hash was verified again.

## Integrated Final Packages

| Package | Integrated commit | Relevant evidence |
| --- | --- | --- |
| Fresh customer planning | `0305253` | Current browser journey passes SQLite/PostgreSQL; original two-case pilot separately preserved |
| Configured reported API | `44943c7` | Current reads, session ownership and write prevention; original 14 cases separately preserved |
| Two-brand planning and closure | `fbcbd81` | Both current database journeys, precise privacy changes, protected financial history and original two-case pilot |
| Archive privacy | `328ec85` | Both current database privacy journeys, independent financial-source validation and original two cases |

Each package has its own delivery ledger and retained failed-attempt evidence.
The closed historical registry, coverage map, collection paths and exact literal
partition expectations are synchronized at 19 batches / 407 children.

## Frozen Preflight

All required local preflight commands completed with exit zero:

| Check | Result |
| --- | --- |
| Existing npm graph and authentication build | Graph verified; rebuilt bundle byte-identical |
| Browser/media probe | Actual decoding passed |
| Ruff / mypy / full branch diff | Passed; mypy checked 1,278 files |
| PostgreSQL safety | 3 passed |
| Upgrade / downgrade / upgrade migrations | Passed on a separate owned database |
| Orchestration and diagnostics | 43 passed |
| Read-only boundary | 75 passed |
| Security | 99 passed |
| Privacy | 14 passed |
| Focused isolation | 43 passed |

These gates overlap and their counts are not additive. No preflight gate skipped.
PowerShell 7.6.6 is available through `/workspace/inlet-tools/pwsh`.

Preserved preflight corrections: one trailing blank line in an older document
required the successor from `14e625b` to `9d7aa2e`; the local launcher was corrected
to accept the media probe's exact environment key and create its scratch parent
before pytest fixtures. Failed outputs remain retained. The latter changes did not
modify product or test code. Successful database/static gates were not duplicated
when the launcher resumed its remaining steps.

## Running Aggregate And Evidence Retention

The aggregate started at 19:43:12 UTC. No marker exclusions, new skip policy or
stop-on-first-failure option was used. It has its own dedicated database; migration
and small-gate databases are separate. The original aggregate database is untouched.

Durable evidence directory:
`/workspace/inlet-evidence/20261010/w1-corrected-9d7aa2e/`.
It contains the frozen source record, canonical collection, exact commands, every
preflight result, start/PID records, raw aggregate log and periodic resource samples.
The JUnit and terminal result will be written there when pytest exits.

Supplemental test files use the unique scratch directory
`/tmp/inlet-corrected-9d7aa2e-aggregate`. A terminal watcher will inventory every
member, create a bounded lossless archive, stream-verify contents and metadata, then
copy and hash-verify it into durable evidence. Restart loss or an unverified archive
prevents a qualified pass. Preflight supplemental artifacts are already archived
and verified. Existing unique evidence is not deleted.

The controller preserves 1 GiB durable and 2 GiB scratch reserves. A resource stop
is an interruption, not a passing test result. Inactive ignored caches were moved
intact, with recovery manifests; the active checkout and original artifacts were
excluded. No aggregate restart or duplicate is authorized by this status document.

## Remaining Gates

First reconcile the terminal aggregate against its exact collection and historical
child manifests, verify skips and supplemental retention, and report actual timing.
A local pass would not establish hosted CI capacity: CI still has its 90-minute
pytest and 120-minute job limits. Node 24 locally differs from CI Node 22, and
existing offline dependencies were reused rather than freshly installed.

Pushes and hosted retries remain held. No merge, deployment, live provider/model
call, credential change, purchase or advertising mutation occurred. Q01–Q16 remain
partial and the six human usefulness gates are unmet. Read-only Google/TikTok
selected-event proposals are saved separately for review; they are not implemented
and do not change this frozen candidate or qualify launch readiness.
