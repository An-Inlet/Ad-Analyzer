# Prepared Browser Startup Diagnostic

The dedicated remote branch `codex/inlet-ci-startup-mode` points to
[`c0f2c073b45ca053c81cb1244de1ff1cb18df2a6`](https://github.com/Konner-An-Inlet/Ad-Analyzer/commit/c0f2c073b45ca053c81cb1244de1ff1cb18df2a6).
Main, PR130 and its Full-qualified candidate9450aa4 are unchanged. No PR was opened
for this diagnostic branch. A read-only Actions query after publication returned
zero runs for this branch; no diagnostic has been dispatched.

## Locally Verified Candidate

The existing registered `CI` workflow has an explicit manual mode. Exact
`browser-startup` mode skips the entire Validation job and selects only the startup
diagnostic. Ordinary push/PR and default `full` behavior are preserved. Unknown or
empty explicit manual modes select no job. GitHub expression string comparison is
case-insensitive; the supported choice is the lowercase value shown below.

The job has a **five-minute timeout** and its diagnostic step a **two-minute timeout**.
It uses an exact pinned checkout action and script commit
`c845ccaf30c71d0b707b73cc93a99023111720ba`. No package install, database, application
suite, FFmpeg generation, artifact upload or provider request is included. Logs are
the only diagnostic output. The command observes startup using invalid empty clips
and always labels codec qualification `not_attempted`. It cannot select a qualified
browser or relax the normal CI codec gate. Queue time and charges are not measured
until a run occurs.

Local results: 14 startup diagnostic tests passed, 11 routing cases passed and 16
PowerShell orchestration cases passed after correcting PATH. The earlier 33pass/
16skip invocation is retained as a PATH setup mistake, not unavailable tooling.
Whole Ruff, configured mypy707, standalone script mypy and diffcheck passed.

## Exact Owner Action

From your own authorized GitHub CLI, run this **once**, specifying the mode:

```bash
gh workflow run ci.yml \
  --repo Konner-An-Inlet/Ad-Analyzer \
  --ref codex/inlet-ci-startup-mode \
  -f mode=browser-startup
```

This uses the already registered workflow on the dedicated branch; no main merge
or new workflow registration is needed. Do not omit the mode: the default is Full.
After submission, share the run URL so its startup facts can be inspected before
any subsequent qualification attempt.

The executor has no callable connector for a new workflow dispatch. Exposed rerun
actions would rerun an existing workflow and are not a substitute. The historical
shell dispatch route failed at the network proxy with403 before a GitHub response;
it has not been retried or bypassed. This access limitation is why owner execution
is needed, not a claim of quota exhaustion or missing project authorization.

The hosted startup cause remains unproven. Matching local Chrome passes under the
recorded restrictions; the prior artifact contains no additional startup evidence.
See the [exact failed-run evidence](inlet-hosted-qualification-20261007.md).
