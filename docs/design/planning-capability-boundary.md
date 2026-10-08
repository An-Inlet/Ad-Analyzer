# Planning MVP Capability Boundary

Shared interface frozen before dependent implementation: app.advertising_capabilities
exports advertising_writes_enabled() -> Literal[False] and
require_advertising_write() -> NoReturn, raising AdvertisingWritesDisabled with HTTP409
and fixed detail advertising_writes_disabled_in_planning_mvp. No environment flag,
customer approval, manifest, injected runtime or stored mandate enables mutation.
This artifact is planning-only; retained execution code is post-launch, not a second
production mode. No live operation or deployment is authorized by this change.

Call the guard through the module at execution admission/claim/dispatch entrypoints,
before durable financial changes or any external resolution. Final provider sinks
also guard all mutation-family requests, including validateOnly, uploads and status
updates. A denial must not be swallowed and stored as an uncertain emitted attempt.
Already retained obligations remain readable and must not be released by this policy.

Do not block all POST: Google googleAds:search/searchStream and connection OAuth
maintenance are reads/connection operations. Provider sink enforcement uses known
semantic read endpoints, rejects unknown paths/method overrides, and retains existing
path/context checks. No global HTTP monkeypatch. Mock transports receive the same
production denial by default; there is no mock-based production bypass.

Read-only planning catalog moves to an owned planning API without removing identity,
tenant/account/connection ownership, source freshness or billing checks. UI capability
is false; remove active publication/activation/automatic controls. Plan decisions
record only planning decisions, not execution approvals. Preserve historical views.

Tests: unpatched default-denial API/worker/direct-adapter probes with zero emissions
and zero new claims/holds, plus actual planning API/browser reads. Existing historical
execution tests may explicitly opt into a test-only monkeypatch of this boundary to
retain engine regression coverage; no suite-wide autouse bypass, production override,
or claims that patched tests validate MVP deployment. Existing source snapshots remain
unchanged. This interface alone is NOT complete P01 enforcement; integrations and
independent review must finish before acceptance.
