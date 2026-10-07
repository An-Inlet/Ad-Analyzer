# Configured Planning And Reporting Runtime

The ordinary customer API and Meta worker now share an explicit pinned profile.
No profile is installed by default, and this read assembly does not qualify spending.
The earlier [native read checkpoint](inlet-planning-native-budget-read.md) documents
the collector boundary; [contract proposal](design/planning-reporting-runtime-contract.md)
describes the policy inputs.

## Deployment And Callable Interfaces

Both `AD_ANALYZER_PLANNING_REPORTING_PROFILE_PATH` and
`AD_ANALYZER_PLANNING_REPORTING_PROFILE_DIGEST` are required to install a profile.
The latter is `PlanningReportingProfileV1.digest()` of the strict parsed document,
not a hash of whitespace in the file. Missing both disables this assembly. A partial
pair, invalid profile or digest mismatch fails readiness and returns a sanitized
configuration error. Load once per configured path/digest, retain immutable policy,
and restart processes when installing a different profile; file contents do not
silently hot-reload. API and scheduler deployments must pin the same profile.

`configured_bundle(sessions, configuration)` returns the profile, initial runtime
and reported runtime bound to the supplied session factory. Each owned native reader
captures only the original customer's authority, then closes private transactions
before HTTP. There is no global customer or implicit background engine. The FastAPI
getters use their request's database bind; `run_meta_tick(engine)` uses its engine.
A direct reported getter without a database returns unavailable.

All initial/window/feedback numeric policy parameters and native-read resource limits
are explicit profile inputs. Optional feedback is an explicit null, not an omitted
section. The fixture values are not product recommendations or empirical policy
qualification. Native budget read coverage is currently Meta USD only. Other launch
platforms and supported currencies remain implementation work.

## V2 Preview And Versioned Baseline Ports

`PreviewIntentV2` stores the server-resolved objective, calibration/observation IDs,
environment/profile/current goal commitment, opaque `native_option_id` and exact
mandate ID/revision. Public v2 selection is only `{option_id}`. It does not construct
a qualified `TargetChoice` or accept a browser-provided native proof.

`preview_v2_service.prepare_preview` performs fresh real native GET discovery and
nominal consent/cap/quantum checks, repeats original-session/current reporting/goal
checks, and writes an immutable v2 preview. Full native observation and profile are
committed in the document digest. The qualified `native_state_digest` column stays
null. Both native reads and the row use the existing
`inlet.initial-preview-goal.v1(definition)` commitment, so strict binding can prove
the relationship. Existing qualified optimizer and v1 hashes are unchanged.

`bind_preview_row(row)` and `preview_mandate_reference(row, document)` are pure
strict bindings, not fresh authorization. `preview.read_preview` returns the strict
version union with original actor/session, source, goal, calibration, report,
mandate and expiry checks. Initial exports use the same binder. The qualified
review bridge explicitly rejects v2 before accessing any v1 native-state field.

Reported-feedback version-aware consumption is a separate dependency, frozen in
consumer commit930feaca after0078. Integrate it before claiming a v2 adjusted-preview
journey; this package's tests stop at the actual v2 baseline and its strict export.
No altered v1 handoff, financial qualification or automatic advertising mutation is
introduced.

## Actual Worker Reachability

`run_meta_tick` previously selected only due rolling imports/open native windows.
A due fixed report on fresh rolling coverage could therefore never reach the page
service until the rolling interval elapsed. With an installed profile, a bounded
correlated job predicate now also considers due pending/waiting or acquiring work.
It matches workspace/account/integration/source generation, environment and exact
window policy/family, and requires an unexpired obligation. Existing connection
backoff, per-tick connection/page bounds, workspace/session locks and lease checks
still apply. Missing configuration does not query the operational job table.
Rolling coverage/cadence remains separate and is preserved across fixed reports.

## Local Evidence And Remaining Scope

`tests/planning_runtime_fixture.py:configured_journey` exercises real customer
comparison requests, actual `run_meta_tick(engine)`, repeated fixed HTTP reports,
owned captures, calibration, encrypted-vault native GETs and a v2 USD45→46 preview.
It installs a fixture profile and replaces only low-level HTTP/clock seams, with
ordinary runtime getters. Existing DB/identity test harness supplies the isolated
backend and fake identity service. The source historical action comes from the
existing actual mocked optimization journey; no new write occurs during planning.

SQLite and PostgreSQL cases verify that fresh rolling coverage does not hide due
fixed work, rolling timestamps stay intact, changed session/generation/profile and
expiry deny current use, and the strict export/qualified bridge behave as declared.
The fixture is reusable by the dependent feedback/browser acceptance package.

This is offline code and mocked-provider verification. No live profile was installed,
provider account contacted, advertising spend changed, branch remotely pushed or
Full validation run by this package. Qualified live exposure/replacement/finality,
automatic execution and complete customer acceptance remain separate unfinished
work; the missing deployment profile alone does not explain those gaps.
