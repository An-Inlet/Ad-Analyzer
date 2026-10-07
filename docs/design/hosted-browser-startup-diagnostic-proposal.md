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
