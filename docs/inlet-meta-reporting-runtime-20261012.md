# Opt-In Meta Reporting Runtime — 2026-10-12

Baseline `bb79dbf3154d8943897d30088118877a3335e43c`; local branch
`codex/inlet-w1-followup`. The existing application is the module-level
`app.main.app`; no new application factory or deployment architecture was added.

## Runtime Boundary

`INLET_CUSTOMER_META_REPORTING_ENABLED` defaults false. The actual reporting route
now lazily composes the existing count service using existing Meta settings and
Vault interfaces. No credential provisioning, new grants or scope expansion is
introduced. Disabled reporting/Meta flags, missing app secret, or a missing/invalid
encryption key return fixed unavailable responses before transport construction.
The example configuration explicitly leaves the new switch false.

Transport construction is lazy, caller-owned, uses zero automatic retries and ignores
environment proxies. Only HTTPS GET requests to the fixed Meta v26 account metadata
and Insights paths are admitted. The bounded collector retains redirect refusal,
exact count profile, page/body/time limits and original authority/grant checks.
No write client or advertising mutation path is composed.

The production runtime supplies a side-effect-free local availability callback.
It is checked before reads/replays, around provider IO and at final persistence.
Confirmation and capture have final write-exit checks; disabling during final
authorization rolls back the selection/capture rather than reporting a durable
success. Invalidation remains available with reporting disabled or config absent.
Explicit fixture runtime injection retains its prior behavior for compatibility.

Counts remain provider-reported website purchases. Explicit zero and missing data
remain distinct; money and ROAS remain unsupported and effective attribution remains
unknown. No changes to document versions, spending authority or public website.

## Assembled Qualification

72 unique exact cases passed: 12 component, 30 SQLite and 30 PostgreSQL.
Full Ruff, configured no-path mypy (1,534 files), exact collection, diff and seven
JavaScript syntax checks passed (11 static commands). Forty unaffected passes were
retained from attempt 02 across the independently checked sole addition of the
native-provider-auth test file. Attempt 03 added two SQLite and nine PostgreSQL
passes; attempt 04 ran only the remaining 21 PostgreSQL cases. No completed case
was rerun in the resource recovery.

Attempt 03's positive-count PostgreSQL browser case was interrupted at memory
headroom 507,117,568 bytes, below the 536,870,912-byte floor. Original exit -15,
runner exit 241, incomplete XML, source integrity and clean teardown remain recorded.
Recovery verified five earlier relocation manifests and retained source hashes,
then removed only 64,916 regenerable bytecode files (914,203,317 logical bytes)
from memory-backed `/tmp`; one file without a retained source was preserved.
No unique evidence, source, active process or database was deleted. Recorded headroom
rose to 1,271,828,480 bytes. Independent review admitted a fresh exact remaining-case
manifest with unchanged source, runner and resource floors. All remaining cases
then completed in bounded isolated processes.

Final results and twelve browser/API artifact sets are in
`/workspace/inlet-evidence/20261012/meta-runtime-attempt04/`; original interruption
records remain in attempt 03. Cleanup provenance and reviewer records are in
`/workspace/inlet-evidence/20261012/meta-runtime-recovery/`. Final evidence closure
and local commit binding are recorded alongside the completion freeze.

The new Chromium journeys use actual `app.main.app`, middleware, routes and static
Reporting/Planning assets over local TLS. Browser actions log in, verify disabled
reporting, review an available import, explicitly select the event, capture, follow
the handoff, explicitly apply the capture, save inputs and generate a plan. Same-session
API reads then verify current/history/export document equality and recomputed digests
for positive, zero and missing counts on both databases. Provider HTTP uses fixture
transport; there was no live provider read. Startup/deployment readiness is not
claimed: the test server disables lifespan startup.

Planning is explicitly configured with the existing canonical private-v4 constructor
inside the fixture, without replacing its implementation or authority checks. A
separate actual-app capability assertion proves the unchanged production-default v3
planner does not advertise selected reporting. This package therefore does not
qualify production-default capture-to-Planning activation. It qualifies the assembled
flow under that explicit fixture configuration.

The original authoring lint diagnostics are described in preparation notes. Formal
attempt 01 stopped on a new browser-test diagnostic fallback's SIM105 lint violation;
its source/result/log and unrun phases remain preserved. The fallback was changed to
`contextlib.suppress`; independent review also tightened final confirmation gating
and exact final-boundary tests before the next frozen qualification attempt. No
production validation was relaxed and no failure was retried unchanged.

## Dependency-Ready Work And Remaining Holds

A separately reviewed explicit composition interface for canonical selected planning
can build on these boundaries while preserving the default v3 policy and private
v4–v6 gates. Google selected-reporting production composition remains separate.
TikTok still needs qualification of its exact report metric/dimension/data-level
combination. Custom events/pixel identity, monetary values, effective attribution
and deleted-object completeness remain distinct unsupported areas.

Owner retention/artifact-sharing decisions, six human quality judgments, Q13
independent provider verification and historical R01–R03 uncertainty remain open.
No push, PR, hosted CI, merge, deployment, live activation, real credential operation,
provider/model call, advertising write or spend occurred. This is local fixture
qualification; it does not establish a purchasable live release.
