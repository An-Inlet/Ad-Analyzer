# Inlet Customer Foundation Integration — October 7

This isolated branch combines reviewed local packages with the preserved validation
repairs. It is not the frozen `9450aa48` qualification tree, is not deployed, and
does not establish live provider qualification.

## Integrated Code

- `422bbe4`: configured planning/native observations, immutable reported-feedback
  revisions, conditional customer budget consent, Google/Meta execution and actual
  configured TLS customer journeys.
- `02b405cd`: goal progress, canonical workspace-before-goal locking, and original
  session/role/revision/source-context revalidation after interpretation and after
  its accounting commit. Denied delivery retains incurred usage without replay.
- `9450aa48`: prior historical migration fixture repairs and the diagnostic Meta
  connection race harness. The original failed run's worker cause remains unknown;
  the controlled delayed-start and removed-lock evidence remains in its ledger.

The two merges required only progress-ledger conflict resolution; both histories
were retained. No product or test behavior was changed to resolve a conflict.

## Checks Actually Run

On integration head `413922fa3f59bc4e72a812172c4ed1704dd9d45c`:

- Whole-repository Ruff passed; mypy passed for 770 source files; diff check passed.
- Nine-file interpretation/progress/budget/feedback/configured Google+Meta TLS
  cohort: **38 passed, 42 skipped, 83.31 seconds**. This invocation omitted the
  disposable-PostgreSQL flag: 40 PostgreSQL cases were not exercised, alongside
  two expected SQLite concurrency skips. Log: `inlet-next-integration-focused.log`.
- The same cohort restricted to PostgreSQL, with its explicit disposable flag:
  **40 passed, 40 deselected, 187.68 seconds**. Log:
  `inlet-next-integration-postgres.log`.
- Seven-file historical and new populated migration/revision cohort:
  **29 passed, 3 expected SQLite skips, 25 warnings, 108.83 seconds**.
  Log: `inlet-next-integration-migrations.log`.

All database checks used the separate `inlet_oct07_next_integration_ci` database.
The active frozen Full database and checkout were untouched. No additional Full,
hosted run, push, merge to main, deployment or live provider call was performed.

The contracts/catalog/provenance/TikTok packages being developed afterward are not
part of these results. They require their own integration and checks.

## Subsequent Origin Integration And Historical Fixtures

Head `92c472e` adds origin schema `59a1235` and catalog `2cc0bd1`. This is separate
from the earlier green integration above. Its first targeted cohort produced
**4 failed, 53 passed, 4 skipped in 133.67 seconds**: four historical fixtures
queried new ORM origin columns in genuine pre0080 databases.

The test-only repair reflects the real historical revision table and exposes only
readonly legacy/null origin discriminators. Explicit fixtures replace exact class
references in application modules, restore aliases including later imports, and
dispose only their own mapper. Production models, financial checks and physical
constraints are unchanged. Installation asserts that the new table/columns do not
exist; older schemas without any execution revision table never install it.

Retained intermediate evidence:

- Initial reflection omitted foreign-key target metadata: 3 failed, 1 passed;
  full foreign-key reflection corrected that fixture defect: 4 passed.
- Broader migration cohort: **1 failed, 75 passed, 7 skipped, 2 errors** in
  147.70 seconds. The failure was an overly broad helper invocation before the
  revision table existed. Explicit fixture installation fixes it. The two SQLite
  errors exposed a separate ORM foreign-key DDL metadata defect under investigation.
- Cleanup implementation initially omitted one pytest fixture parameter:
  1 failed, 7 passed. The parameter is now explicit.
- Final historical/isolation cohort: **8 passed, 26 warnings, 20.57 seconds**.
  It includes a late-import alias restoration regression and populated historical
  migration behavior. Whole Ruff, mypy782 and diff check passed.

The ORM cross-dialect defect and a final combined cohort remain outstanding here;
these eight passes do not relabel either failed aggregate as successful. Evidence
logs use the `inlet-next-integration-historical-*` and
`inlet-next-integration-migration-final` prefixes.

## Combined Repair Verification

Head `164d2c2e0f9b0fc883c43b755b842e4fbc2961f3` adds the reviewed historical
fixture repair, credential/configuration substrate `3821008`, and metadata repair
`68f89cb` (including `302f81e`). Independent review closed the historical alias
restoration concern. The metadata repair reproduces and fixes a real integrity
defect: PostgreSQL ORM table creation could suppress a deferred FK during subsequent
SQLite creation using the same metadata, allowing an origin-marked revision to
commit without its proof. The named DDL rule is now restored, and both ORM and
the unreleased migration's SQLite trigger require the physical FK. No deployed
database repair is claimed.

The expanded 27-file cohort passed **123 tests with 7 expected skips and 110
warnings in 171.39 seconds**, terminal exit 0. Historical fixtures run before
current-head provenance checks, exercising mapper restoration and dialect reuse.
This also covers populated migrations, configured credential contexts and actual
MockHTTP catalog admission. Whole Ruff, mypy789 and diff check passed.

Log: `inlet-next-integration-migration-repaired.log`. The previous failed aggregate
logs remain retained. No second Full or hosted qualification was launched. Actual
optimization API/UI and TikTok runtime/browser packages remain separate work until
their own integration; this result does not claim live functionality.

## Configured Optimization API Integration

Merged configured optimization backend `c418bc4`. Its explicit legacy origin
constructor defaults exposed a historical test mapper incompatibility (baseline
1 failed in 3.50s). The test-only reflected mapper now accepts only legacy/null
defaults, rejects marked authority, and preserves read-only origin properties.
The regression checks both constructor paths and late-import cleanup.

The eight-file historical/API/interpretation cohort passed **49 tests with 20
warnings in 116.37 seconds**, exit 0. Whole Ruff, mypy795 and diff check passed.
Log: `inlet-next-integration-optimization-api.log`. This is focused integration
evidence, not Full qualification or live verification. The separately reviewed
financial-period boundary followup remains pending integration.

## Configured Customer Journey Integration — Terminal Result

Code merge `c7c54f3c887d3297ae732a087d7650f3259a909a` integrates reviewed
optimization UI `e8ce58b`, financial-period repair `0d965b1`, and TikTok backend/HTTPS
`d02159a`. The settings merge preserves both additive configurations; append-only
ledger conflicts retain both histories. Subsequent changes through `e15c4c4` are docs.

The combined nine-file cohort passed **105 tests, zero skips, in 722.83 seconds**,
terminal exit0: financial-period pure/API, initial budget mandate API, configured
optimization API/UI/HTTPS, and Google/Meta/TikTok configured execution HTTPS.
SQLite and disposable PostgreSQL both ran. Actual customer sessions/pages/routes
and provider MockHTTP were used; no live provider qualification is claimed. Whole
Ruff, mypy809, optimization JavaScript syntax and baseline diff check passed.
Log: `inlet-next-integration-configured-final.log`; copied to durable executor
evidence with SHA256SUMS. No new Full or hosted attempt was launched.

The independent read-only TikTok browser review found no actionable issue. Root
reviewed the financial boundary and optimization UI changes. Original invalid
local midnights now reject rather than choose a fold or normalize a skipped date;
ordinary23/25-hour DST periods remain valid.

Separate frozen945 remains locally Full-qualified; its hosted run failed before
application tests. See [exact hosted evidence](inlet-hosted-qualification-20261007.md).
Diagnostic-only `d50947c` is separate and has8 focused passes plus real local151/154
decoding; no hosted fix is claimed. Next package is the
[configured v2 preview/review bridge](design/configured-v2-preview-review-bridge.md),
starting with shared pure interfaces. No migration is reserved yet.

## V2 Review Interfaces And Standalone Import Repair

Integrated `bea8f43` and `ba2e7dd` at `deaed5b4a56b60c5adbe3b9f9381aca92bd8ab2c`.
A narrow inherited import cycle was removed by extracting the identical UTC clock
into an import-neutral module; customer_runtime retains its original reexport and
dataclass defaults. Fresh subprocess regressions verify standalone contract imports.
The new frozen request/proof/native-match contracts preserve distinct consents and
mandates, one shared ledger, native preview bytes and explicit absence of authority.
Actual Meta MockHTTP codecs supply both sides of the semantic comparison.

Combined pure/preview/configured-optimization integration passed **63 tests, zero
skips, in 66.93 seconds**, exit0, including SQLite/PostgreSQL owned cases. Whole
Ruff, mypy814 and baseline diffcheck passed. Log: `inlet-v2-contract-integration.log`.
Root read review found no actionable issue. No routes, financial runtime registration
or schema was added by these commits.

Next isolated package reserves0081after0080 for owned immutable hash-only V2 proof
storage, populated migration and lifecycle/export validation. No dependent route/UI
implementation precedes its review. Hosted diagnostic and documentation research
remain separate; no additional paid run or Full was launched.

## V2 Proof Storage And Canonical Ownership Bindings

Integrated reviewed schema `af14eb8` and strengthening `41dd530` at code head
`00e937ec65334c21f670de55c55de0fb5f8d127e`. Additive0081 creates an immutable,
owned hash-only proof child; a composite unique index avoids rebuilding the populated
parent. Proof/link erasure cannot create a new parent review. Downgrade refuses to
discard retained proof. V1 bytes/routes and historical financial reconciliation
remain unchanged. Strict export is protected history, not eligibility.

Canonical insertion checks bind the two distinct consents to one ledger, the saved
planning intent/policy, execution review consent/full mandate, preview/profile/native
state and plan, reconstructed customer intent, full retained qualification envelope
and recomputed native semantic match. Negative tests recompute a valid outer hash
before testing contradictions. Current ownership/financial freshness still belongs
to the forthcoming runtime bridge; proof parsing is not spending authority.

The combined eight-file integration cohort passed **60 tests, 1 expected PostgreSQL
skip for a SQLite-only connection integrity case, 7 warnings, in 45.07 seconds**,
terminal exit0. Includes actual populated SQLite/PostgreSQL migrations, lifecycle,
strict exports,0080 metadata/DDL compatibility, initial-budget historical migration,
and fresh-process imports. Whole Ruff, mypy818 and baseline diff check passed.
Evidence: `inlet-v2-proof-integration.log`. Independent read review found no actionable
issue in the storage-only package; root additionally reviewed canonical inner bindings.

The next isolated package is the actual configured V2 API/runtime handoff. Its options
and prepare interfaces must be frozen before dependent UI work. No Full, live
qualification, new hosted run, main change or remote merge occurred in this package.

## V2 API Interface Freeze

Reviewed `bf29197` and integrated at `d15f104dbfe8df608a850865ceecd986be2e5668`.
The GET options and POST exact-review callable contracts are frozen before parallel
backend/frontend implementation. Options are bounded to50, explicitly show financial
qualification not checked and no spending authority, and expose fixed unavailable
reasons. POST retains only preview digest and chosen mandate ID/revision.

Current-root API/native/proof contract tests: **32 passed in1.45s**, exit0. Whole
Ruff, mypy820 and baseline diffcheck passed. Log: `inlet-v2-api-contract-integration.log`.
Actual V2 runtime/routes and UI remain work in progress; no actual handoff journey is
claimed by this pure contract result. The startup diagnostic separately awaits the
owner's one-time action; it has not been dispatched or duplicated by the executor.

## Completed Configured V2 Customer Handoff

Backend `063243c`, additional authority regressions `685e791`, and UI/TLS delivery
`4d9a928` are integrated at product head
`88f4ba50b879b3faab73603e8f0bb766efa4eebd` on `codex/inlet-next-integration`.
This completes the bounded Meta campaign-owned DAILY USD handoff through the
configured API and customer pages. It does not extend live provider qualification.

The customer reads existing separately consented execution limits, explicitly
selects a mandate, and requests an exact review. Both mandates must retain the same
ledger, account set, period, currency and total cap; execution limits cannot exceed
planning limits. Fresh native semantic and financial checks precede atomic
review/link/0081 proof persistence. V2 preview bytes remain non-authorizing.
The customer then opens the ordinary review and separately approves it. Existing
run/claim/dispatch/readback controls remain responsible for execution.

Original-session, source, goal, profile and proof checks guard forward operations.
Lost-response replay returns the same review; missing proof or erased preview cannot
recreate authority or fall back to V1/manual behavior. Retraction preserves retained
history and unknown-result financial holds and permits historical reconciliation.

Validation actually completed:

- Root backend/V1/storage integration at `01d238a`: **60 passed, 1 expected SQLite
  concurrency skip**, exit0. Actual PostgreSQL cases ran. Quiet progress and exit
  file determine counts; elapsed duration was not captured. Log:
  `inlet-v2-runtime-integration.log`.
- Author backend cohorts cover **26 distinct SQLite/PostgreSQL API cases**.
  The first10 and next8 overlap by2; a further10 cover source/goal drift during
  provider IO, altered digest, another original session and atomic final-guard
  rollback. A duplicate compatibility run was canceled, not counted as passing.
- UI author's composed cohort: **15 passed in84.63s**:3 frontend,4 configured
  V2 HTTPS,8 V1 planning/budget HTTPS. Its retained summary explicitly is not a
  raw stdout log. Initial two harness failures were corrected without weakening
  production behavior or assertions.
- Exact integrated product head `88f4ba5`: **7 passed in36.39s**, no skips, covering
  frontend and configured V2 HTTPS on both databases. Log:
  `inlet-v2-ui-integration.log`. The browser makes a fresh preview and explicit
  selection/handoff/approval; assertions verify exact amount/proof, distinct
  mandates on one ledger, zero attempts/reservations/provider writes at approval.
- Whole-repository Ruff, `mypy app tests` (**825 source files**), Node syntax for
  both affected product modules and diff check passed on the integrated head.
- Independent read-only authority review of exact `063243c` found no actionable
  finding; root also reviewed the UI and additional test changes. The reviewer
  did not claim an independent test run.

Evidence and terminal metadata are retained under the October7 executor evidence
directory with SHA256 checksums. The10:50 disconnect notice did not interrupt
execution: commands and original active test-session polling succeeded at10:51,
and both integration runs subsequently completed. No new Full, hosted dispatch,
remote push/merge, deployment or live advertising operation occurred.

## Next Package And External Status

The [rendered TikTok tables](design/tiktok-rendered-response-contract-20261007.md)
resolve the former owner-export documentation blocker. The standalone discovery
parser package is underway in isolation; publication eligibility remains separate,
especially the2026 Custom Identity transition. Existing v1 catalog/creative bytes
remain unchanged. Unconfirmed ID scalar shape is retained explicitly rather than
coerced into a qualified publication identifier. Candidate/session composition
proposal `08192aa` remains a future reviewed design, not implemented behavior.

The owner-run startup diagnostic still awaits the owner's action. Frozen Full
candidate `9450aa4` and draft PR130 are unchanged. This next integration branch is
local and has not replaced that candidate. No merge/deployment authority is inferred
from offline API or browser acceptance.


## TikTok Discovery Integration — 11:38 UTC Checkpoint

This checkpoint supersedes the older “Next Package” status above. Strict discovery
parsers `1b5cee8`, linked assessment `5547095`, bounded owned collector `17cb712`
and ownership regressions `22857ec` are integrated. Pure candidate configuration
`64c1b76` is also integrated; it does not enable candidate or automatic execution.
The collector permits only explicit contract-test MockTransport, rechecks the
original principal and owned grant around bounded HTTP, rejects ambiguous JSON,
and preserves null/absent events, deprecated events and incomplete pagination.
Assessment grants neither publishing eligibility nor spending authority.

Exact product head `dc75330283e674f70f3053f0bbcdb7f9c15ac881` passed **227 tests,
1 warning in849.04s**, exit0, covering parser/owned discovery/linked assessment,
candidate configuration, and existing configured TikTok API and full HTTPS
publication compatibility. The warning is an intentional wrong-type tamper fixture.
Ruff, mypy (837 source files) and diff checks passed. Log and terminal metadata:
`inlet-tiktok-discovery-integration.log` and
`tiktok-discovery-integration-terminal.json` in the executor evidence directory.

Customer discovery API `1fa2409` and HTTPS UI `25ad4f3` are now assembled at
`0c428a48fa340a5f437bc3ee89cf532df4495526`, tree
`2af2f936aa2a3b7181269a00b8729ef059dc89bc`. Root read review found no actionable
issue. Exact-root API/contracts/frontend/configured HTTPS acceptance completed: **35
passed in45.37s**, no skips, exit0, on SQLite and PostgreSQL. Evidence:
`inlet-tiktok-customer-integrated.log` and
`tiktok-customer-integrated-terminal.json`.
Whole Ruff and mypy (846 source files) passed. The initial Node invocation used
an incorrect nonexistent module path and failed; corrected invocations for
`app/portal/static/execution.mjs` and `tiktok-discovery.mjs` both passed, as did
diff checks. This correction changed no product code.

Executor availability was verified with successful shell/status/test-session calls
at11:09,11:23 and11:38 despite disconnect notifications. The original combined run
completed normally. No quota event, hosted retry, provider call or deployment was
observed or initiated. The separate candidate worker has a reproduced both-database
admission starvation defect under repair; it is not yet integrated. The owner-run
startup diagnostic remains pending. The new assembled qualification branch is
local and distinct from the preserved Full-qualified `9450aa48` artifact.


## Candidate API And Original-Session Worker Integration

Reviewed package `9580eb98c6adf348ffda3622f1beb44328c9c9ad` is integrated after
independent exact-head review closed with no remaining actionable finding. The
review discovered admission starvation before process bookkeeping; author reproduced
it on both databases, then added guarded60-second scheduling deferral preserving
leases, attempts and fences. Actual configured Google/Meta API selection, queued
reads and separate exact review use original-session private contexts; default source
registration remains absent, unqualified facts remain blocked and automatic
first-decision production remains unavailable. Manual and V2 review paths retain
their existing separate authority.

Root combined API/scoped-worker/scheduler/manual optimization/legacy preview review
cohort: **90 passed in158.94s**, exit0, both databases. The initial command named a
nonexistent test file and collected zero tests (exit4); the retained initial path-error
log is not a pass. Corrected test paths changed no product behavior. Whole Ruff,
`mypy app tests` (**852 files**) and diff check passed. Separate actual V2 handoff
compatibility passed **26 tests in205.74s**, no skips, on both databases before
the merge freeze. All author before-failure,
repair and configured compatibility logs are copied and hashed in the executor
October7 evidence directory.

The next UI package will add a server-computed decision digest and customer
selection/status/review controls on an isolated successor. It is excluded from the
upcoming immutable Full candidate. The owner authorized one assembled local Full;
no hosted retry or live action follows from that authorization.


## Assembled Full And Separately Tested Successors — 12:02 UTC

The assembled qualification branch is frozen at
`2476b87ac55b116d848f80f1286aae6551eeed7c`, tree
`6beebdd913d9fbaf06a7143d6bacb7e1a3daaf8f`. One actual
`bash scripts/validate.sh Full` started11:50:26 UTC using dedicated disposable
`inlet_oct07_assembled_r1_ci`. It remains running and **cannot pass as-is**:
its SQLite/PostgreSQL historical0074 metadata tests both failed. No new Full,
hosted retry or remote action has been started. Earlier9450aa48 qualification is
separate; neither ac26a67 nor this candidate inherits that result.

The two failures reproduced separately (2failed,20deselected,3.11s). Their fixture
removed0076 while leaving its newer0081 proof child/trigger installed. The test now
runs the real0081 downgrade before removing its historical parent, then restores
0081 after the old graph. No cascade shortcut, missing-table fallback, application
code or production migration changed. Repaired historical/current-proof/lifecycle
cohort: **39passed,1 Alembic configuration deprecation warning,54.65s**, bothDB.
Whole Ruff/mypy855/diff passed. This repair is a later successor, not a changed
qualification checkout or a retroactive Full pass.

Later customer UI package0daac163 merged at92c40b6: explicit named policy/consented
mandate selection, bounded read/status, blocked explanation, exact server-digest
review handoff and separate ordinary approval. Root independently reviewed it;
combined API/contracts/DOM/configuredHTTPS cohort **24passed76.65s**, no skips,
bothDB. Ruff/mypy855/Node2/diff passed. No auto mode, provider writes or fixture
evidence promoted to production.

Verified Google v25 schema review found conversionGoalCampaignConfigs has no
partial_failure request field. Source3318338, integrated8974e25, omits it only for
that collection in both validation and mutation. Six other request bodies and
persisted plan/request hashes remain unchanged. Strict complete daily/total
publication adapter cohort **41passed0.30s**; root wholeRuff/mypy855/diff passed.
An initial root test command referenced a nonexistent filename and collected0
(exit4); corrected paths passed without product changes. Author's pre-fix strict
wire test failed as expected. This is offline schema/HTTP verification, not a live
provider result, and is outside frozen2476.

Logs and terminal metadata for these packages are retained and SHA256-listed in
the executor evidence directory. At11:59:07 successful tools confirmed the original
Full wrapper/timeout/bash/pytest processes still alive after the11:58 disconnect
notification; checkout clean and unchanged. No quota indication was observed.


## Google Original Operation Evidence — Integrated Successor

Source2a520d0 is independently reviewed and integrated at
`c942e700546d2b26190f008d1029dce32a8095f5` (tree
`10aed380c31b7eb1ac61f904024cde369689681c`). Actual single-operation creation and
activation responses now retain exact owned original-request/run/step/fence,
operation and result commitments in the existing protected evidence table. A new
versioned document preserves old v1 and normalized response bytes. Existing receipt
GET consumes the evidence with fresh historical owner/session checks, including
closing workspaces, and explicitly unavailable financial finality. Unknown or
contradictory responses never create completion; no reservation is released.

Author's actual configured API/protocol/legacy/coordinator cohort passed154 with
one expected SQLite-only concurrency skip in167.25s; conflict rollback2passed5.95s.
Actual populated PostgreSQL v1/v2 dump/restore, immutable ownership and downgrade
refusal2passed68.81s (initial missing-tools invocation skipped2, subsequently rerun
with the existing tools). Root reviewed exact contracts, append transaction,
original-response/receipt binding, fresh authorization and strict export behavior;
no actionable finding remained. Root whole Ruff, mypy859, diff and fresh import
orders passed. Additional combined capture/contracts/Google+Meta+TikTok actual HTTPS
compatibility completed: **70passed614.92s**, zero skips, both databases, exit0.
Productc942e70 was unchanged throughout; terminal documentation head6c86d9c.
Exact log `inlet-google-completion-integrated.log` and terminal metadata
`google-completion-integrated-terminal.json` are retained with checksums. This successor remains outside
frozen2476 Full and has no live/financial qualification.


## Mandate Traceability And TikTok Contract Evidence

Integrated documentation-only source0a192f8 at49f98a5. The
[traceability review](design/mandate-requirement-traceability.md) maps the approved
spending mandate to current safeguards and identifies universal outside-writer
protection as a stronger implementation assumption, not an original promise. It
retains current accounting and admission guards, rejects unapproved recommendation-only
scope reductions, and proposes a nonauthorizing original-allocation/native-envelope
producer before conditional financial qualification. Complete audit text was unavailable
for this particular review; its source limitations are explicit. Relative links and
diff checks passed; no runtime tests are attributed to this documentation change.

The parent supplied complete rendered official TikTok endpoint-table evidence for
linked Push/Pull creation, readback, identity details and explicit advertiser special
capabilities. This resolves the exact-field research blocker. Implementation remains
offline and separately tested; the prior CUSTOMIZED_USER mock journey is historical
contract evidence, not proof of current native new-ad eligibility. No live account
access, publication, source qualification or spending authority follows from research.


## Original Google Allocation Observation And Startup Fixture Repair

Reviewed source2655940 integrated at7f10a42 adds an explicit owned CSRF-protected
POST for a saved Google total-budget creation run. It joins actual original
creation captures/receipts, reviewed native amount, separate retained reservation
and current owned native inventory. Both original lineage and customer/source
authority are rechecked after transport closure. Native matching is explicitly
nonfinancial: no upper bound, settlement, portfolio coverage or spending authority.

Root combined actual envelope API/contracts and existing multi-platform native
diagnostic/account API cohort: **171passed183.28s**, zero skips, both databases.
Whole Ruff/mypy863/diff passed. Source author's overlapping impacted cohort74passed
91.45s. Exact logs and terminal metadata are checksummed in the executor evidence
directory. Separate customer UI work uses the frozen interface; this backend
package is not a new Full or live qualification.

Frozen2476 Full reported a third failure at collected node2913: the managed
startup positive test's expected check-name set omitted the existing
planning_reporting_profile validation. Root reproduced1failed0.42s and corrected
only that expectation at749b85b. Startup/deployment/planning-profile cohort
**35passed1.90s**, Ruff/mypy/diff passed. Production startup guards are unchanged.
The earlier two historical0074 fixture failures retain their separate93e5275
repair. The frozen Full checkout remains unchanged and must finish before the
combined repair preflight and next immutable candidate.

Validation timing evidence now includes --durations=20 in new focused cohorts and
a passive30-second Full process/progress/cgroup sampler. No Full flags or coverage
were changed. Initial samples show four CPU quota cores, rising pytest RSS, large
file cache/reclaimable slab and later memory-limit reclamation events without OOM.
These are observations, not a concluded bottleneck. Full quiet progress permits
approximate group windows only; it cannot retrospectively provide precise per-test
durations. Further heavy cohorts are sequenced to avoid unnecessary contention.


## Owned Resumable Shopify Acquisition — Reviewed Integration

Source512df29 (b0eeeeb implementation plus2cdc759 atomicity and512df29 deadline
repairs) integrated at9860f13. The actual configured owner API creates a fixed
acquisition request; each leased worker step performs at most one bounded GraphQL
read. Migration0082 owns job/checkpoint/seen staging, invalidation and bounded cleanup.
Existing v2 publications remain unresolved/unqualified, with no snapshot, settlement
or directional claim. Dedicated cadence and expiry do not promise every store can
complete within the limits.

Independent review reproduced a genuine late-authorization publication leak in both
databases (publication2vs1 despite unavailable job). A real savepoint now contains
publication/revision/terminal staging changes and all final checks. Deadline is
resampled after the last potentially blocking authority check. Author's10 focused
ordinary/late-failure cases passed18.37s; independent final original-provider-denial
cases2passed5.31s. Review closed with no remaining actionable finding. Earlier failed
b0 evidence is retained, not relabeled as passing.

Root actual API/worker/new storage and historical0081 cohort: **47passed60.50s**,
zero skips, three existing Alembic path-separator warnings, both databases. Whole
Ruff/mypy877/diff passed. The only cherry-pick conflict was append-only progress
documentation; both histories were retained. Exact log and terminal metadata are
checksummed. This successor was not added to frozen2476 Full, and no live Shopify
call, remote action or deployment occurred.


## Customer Budget Observation — Integrated UI

Reviewed source1f87ccf integrated atda6c1fd adds an explicit saved-run Google
budget observation. It separates original/current native settings from the recorded
reservation, validates exact response/run/environment/freshness, and clears stale
workspace/run/session/logout/expiry results. No automatic native read or reservation
change occurs; unsupported runs return a clear unavailable result.

Root integrated new DOM/HTTPS plus existing Google/social execution UI cohort:
**45passed244.08s**, zero skips, both databases. Whole Ruff/mypy879, both Node
syntax checks and diff passed. Author's new3passed9.45s and all-three configured
creation/activation6passed123.53s remain overlapping package evidence. Only appended
progress documentation conflicted during cherry-pick; both histories were retained.
Logs and terminal metadata are checksummed. This remains outside frozen2476 Full.


## Frozen2476 Full — Terminal Failure And Combined Repairs

The original immutable Full finished2026-10-07T13:36:50.029749Z, exit1, after
6383.567407seconds overall. Head2476b87/tree6beebdd remained unchanged and clean.
Its primary4961-node suite: **4881passed,77skipped,3failed,157warnings**,6198.77s.
Exact failures:

- `tests/test_campaign_performance.py::test_actual_0074_immutable_metadata_and_owned_reference[sqlite]`
- `tests/test_campaign_performance.py::test_actual_0074_immutable_metadata_and_owned_reference[postgres]`
- `tests/test_managed_infrastructure_configuration.py::test_production_configuration_validation_accepts_safe_managed_postgresql`

Initial disposable reset and migration-to-head completed. The script stopped at
pytest failure, so its subsequent Ruff/mypy/diff, PostgreSQL/migration-cycle and
read-only/security/privacy/focused stages did **not** run on this frozen artifact.
Separate successor checks are not retroactive Full credit. Terminal metadata,
complete log, exit code and passive resource samples are checksummed; historical
pending records remain historical. No quota or lost-run explanation is asserted.

On clean successor19ff2fa, the campaign-performance, managed-startup and historical
0081 suites were run together: **42passed27.69s**, zero skips, one existing Alembic
path-separator warning. This includes all three failed node IDs plus nearby
behavior/migration checks. Repairs93e5275/749b85b therefore pass the combined
preflight alongside integrated0082. No new Full or hosted run was started. The
next immutable candidate must include only reviewed passing packages, and record
duration/JUnit instrumentation before launch without truncating coverage.

## Shopify Customer Acquisition — Integrated And Independently Checked

Source70780aa/13e6d09 integrated as1ec7757/4101773. The Measurement History page
now exposes explicit completed-local-day read requests, bounded recovery for the
original customer session, manual refresh/cancel, and a v2 publication reference
with unresolved-correction/unqualified-maturity limits. Existing v1 measurement
rendering remains separate. Source/runtime absence does not hide authorized
operational recovery; it does not grant source readiness or replay authority.

Independent source review checked owner/goal/store/original-session bindings,
20+probe bound, final authorization and async UI selection/cookie fencing. Root
ran new recovery contract/API/actual customer HTTPS suites on SQLite/PostgreSQL:
**9 passed16.40s**, zero skips. Real API→dedicated worker→publication uses provider
MockHTTP fixtures, not seeded acquisitions/publications or runtime getter overrides.
Ruff, repository-prescribed mypy (**886 source files**) and diff checks passed.
An exploratory `mypy .` command found duplicate script module names; required
no-argument `mypy` passed without modifying configuration. Author evidence42pass
and4post-fence browser checks is overlapping, not extra independent Full coverage.

Logs and terminal evidence are checksummed. This package remains outside failed
frozen2476 Full; no new Full, hosted retry, live calls or deployment occurred.
