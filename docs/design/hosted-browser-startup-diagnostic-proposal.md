# Hosted Browser Startup Investigation And Minimal Diagnostic Proposal

Status: proposal only. No workflow is installed, pushed or dispatched. No paid run
is authorized by this document. Exact failed candidate9450aa4 remains unchanged.
Diagnostic implementation d50947c is not a proven hosted repair.

## Evidence Matrix

Failed run37602978286/job112731582938 used Ubuntu24.04.5 image20261004.327.1.
Chrome154.0.8037.97 and Chromium154.0.8037.0 remained alive through the 12-second
probe, without any loopback GET or JavaScript diagnostic. Dependency installation
and pytest never started. No quota evidence appears in the preserved log.

| Hypothesis | Falsifiable check and result | What remains unknown |
| --- | --- | --- |
| Missing H.264/AAC codecs | Hosted never requested clips. Matching Chrome154 actually decodes both locally. | Exact hosted Chromium snapshot capabilities remain untested; cannot explain absence of page requests from codecs alone. |
| DBus error causes startup failure | Matching Chrome emits the exact same unknown-address DBus error during successful decode. | Other runner-specific desktop/process initialization may differ. |
| Missing native dependencies | `ldd /opt/google/chrome/chrome` has no missing libraries in matching Ubuntu24.04.5 container; actual binary runs. | Runner's full library and kernel/image policy state not reproduced. |
| External network or proxy needed for startup | External container network disconnected; child already filters proxy environment; matching Chrome still decodes both. | Hosted loopback navigation must be observed directly. |
| Loopback harness readiness | d509 self-check succeeds; first actual GET0.259s, page target exact, decode completes0.462s in constrained local run. | Hosted self-check/DevTools phase absent from old log. |
| CPU/shared-memory or account permissions | Unprivileged UID65534, fresh writable HOME, two-CPU quota and64MiB shared memory pass. | Hosted transient scheduling, kernel/AppArmor policy and full cold image differ; this is not exact hardware reproduction. |
| Browser flags necessarily prevent launch | Existing flags pass matching Chrome, including resolver restriction. No security/codec flag was removed. | A runner-specific interaction is still possible; speculative flag changes unsupported. |

New local observations are in `/tmp/inlet-codec-constrained-offline.log` and
`/tmp/inlet-codec-startup-detail.log`. The latter used a temporary diagnostic copy
that exposes bounded stderr on successful startup; no product/preflight code was
changed. It showed loopback ready, DevTools ready, one exact page target, and both
real clips loaded at readyState4/width64. This does not qualify hosted CI.

## Smallest Next Hosted Diagnostic — Requires Separate Authorization

One manually dispatched job, ubuntu-latest, hard timeout five minutes, contents
read only. No push/PR trigger, matrix, retry, services, PostgreSQL, dependency
installation, npm, application imports, Full, or provider calls. Checkout a frozen
reviewed commit containing d509 diagnostics using the existing pinned checkout
revision; do not checkout an arbitrary user-supplied ref. Never print environment,
credentials, arbitrary target URLs or raw DevTools bodies.

Two steps only:

1. Checkout exact reviewed diagnostics revision. Record bounded OS/kernel/browser
   versions and available CPU/shared-memory sizes. Do not install packages or
   inspect secret-bearing process environments.
2. Run a stdlib-only **startup diagnostic**, once per distinct existing Chrome and
   Chromium binary, using the existing `probe` function and temporary profiles.
   Feed empty synthetic clip bodies, deliberately, to remove FFmpeg/package setup
   as a prerequisite. A returned media-error result establishes page startup only;
   it NEVER selects or qualifies a browser. If no result arrives, d509 emits
   bounded loopback/startup/target/phase evidence and cleans up its process group.
   Print explicit `codec_qualification: not_attempted`. Do not write GITHUB_ENV or
   alter the normal validation workflow's real two-clip codec gate.

Expected budget: two existing 12-second probes plus bounded cleanup, version calls
and checkout, with five-minute job enforcement. No arbitrary timeout extension and
no automatic rerun. Existing job logs suffice; no artifact-upload step is needed.

Interpretation:
- Self-check false: investigate local HTTP fixture/socket readiness before browsers.
- Self-check true, DevTools absent: browser bootstrap/pre-navigation stall.
- DevTools ready but expected page target absent: launch/navigation handoff issue.
- Expected target present but no HTTP GET: local browser networking/navigation stall.
- Media-error results arrive: browser/page bootstrap works for this diagnostic;
  actual codec qualification remains a separate unchanged requirement.

Only after those facts identify a repair should any normal paid validation run be
proposed. The current evidence does not justify declaring d509 a fix, disabling
sandbox controls beyond existing test flags, bypassing network restrictions,
relaxing decode assertions or raising launch deadlines.

Parent subsequently downloaded and verified the hosted artifact archive. It
contains only `summary.txt`: `No nested JUnit report was produced.` Preserved
paths are `/workspace/inlet-evidence/20261007/inlet-hosted-37602978286.zip` and
`hosted-artifact-summary.txt`. It supplies no additional browser startup facts.

Local environment cleanup: the temporary matching container is stopped and its
original bridge network restored. Docker's zero-CPU update did not clear its
NanoCPUs setting; it retains the explicit two-CPU test cap while stopped. The
attempted period/quota reset was rejected as conflicting. No daemon configuration
or container replacement workaround was attempted; future reuse must account for
that retained cap. No customer data or credentials were involved.

## Concrete Locally Frozen Preparation

Implementation commit `c845ccaf30c71d0b707b73cc93a99023111720ba` contains
`scripts/diagnose_browser_startup.py`. Run only with
`python3 -m scripts.diagnose_browser_startup` from its checkout root. It attempts
at most one installed binary from each Chrome/Chromium family, deduplicates exact
binary paths, and invokes d509's bounded probe without modifying its launch bounds.
No installs, application imports, database or GitHub environment export occur.
Exit0 means collection finished for an existing browser, not startup or codec
qualification. Browser failure remains explicit structured evidence; absence of
any installed browser exits2. Every record says
`codec_qualification: not_attempted`, even if a mocked result reports loaded data.

The reviewable YAML artifact is
[hosted-startup.workflow-example.yml](hosted-startup.workflow-example.yml).
It pins both checkout action and the implementation commit above. It is deliberately
outside `.github/workflows`; **nothing has been registered or dispatched**.

A new `workflow_dispatch` workflow must first exist on GitHub's default branch;
simply placing it on this local/remote feature branch does not make it dispatchable.
Registration, publication and the paid diagnostic run require separate explicit
authorization. An alternative is a separately reviewed manual-only diagnostic mode
in the already registered CI workflow, with fail-closed conditions excluding all
ordinary dependency/test/Full jobs. That alternative has not been implemented or
authorized and must never silently turn into an automatic Full retry.

Fourteen focused tests pass, including sanitized failure facts, child cleanup,
missing-browser no-install behavior, no selected-browser export, alias deduplication,
no qualification from media errors/loadeddata/no-result, and no fallback/retry after
launch failure. Ruff, explicit-package-bases mypy (four files), and diff checks pass.
Actual local CLI returns expected `MEDIA_ELEMENT_ERROR: Format error` for both empty
clips, establishing page startup only while keeping qualification not_attempted.
Logs: `/tmp/inlet-startup-cli-final-tests.log` and `/tmp/inlet-startup-cli-real.log`.

## Existing Registered CI Alternative — Locally Prepared, Not Dispatched

The isolated successor now edits the existing `.github/workflows/ci.yml` locally:
`workflow_dispatch.inputs.mode` is a required choice, default `full`, with only
`full` and `browser-startup` offered. Push/PR triggers and the validation job's
steps/services stay unchanged. Job-level conditions select validation for ordinary
events or manual Full; manual browser-startup selects only the five-minute diagnostic
job, whose two steps pin checkout and c845 implementation. No Postgres service,
installation, test suite, artifact upload, or Full belongs to that diagnostic job.
Empty/unknown manual modes select neither job, never fall back to Full. GitHub
expression comparisons ignore string case, so case variants of the two documented
values are semantic aliases; the UI offers lowercase and an approved dispatch must
explicitly use `browser-startup`. No fallback treats any other value as Full.

Official GitHub docs confirm the workflow must exist on the default branch and
that an already run workflow can be dispatched against another branch/tag;
[workflow dispatch documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).
The API takes a branch/tag ref and configured inputs;
[workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).
This reuses the existing registered CI file instead of registering a new workflow.
It still requires separately authorized publication of the exact branch and an
available permitted dispatch mechanism. No previously denied shell dispatch route
may be retried or bypassed. If no permitted mechanism is available, the owner must
perform the exact reviewed dispatch; preparation is not authorization to run it.

Focused routing/CLI/existing orchestration checks:33 passed,16 skipped because
PowerShell is unavailable in this environment. Final expanded case-aware routing
cohort:11 passed. Ruff, targeted mypy and diff checks passed. Logs are
`/tmp/inlet-ci-startup-mode-tests.log` and
`/tmp/inlet-ci-startup-mode-final-tests.log`. This local preparation did not change
945 or launch any hosted job. Hosted startup cause remains unresolved.
