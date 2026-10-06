# Integrated Inlet Candidate Acceptance

This is the current implementation view of `codex/inlet-mvp-next`; draft PR130 is
tracking frozen `a4fcd3a35d585d11def78261382234e081fb8f6b` (migration 0071).
Local Full and normal hosted run 37443239927 are running; session automation 0072
and its UI remain outside that frozen candidate. Main remains `ea3591c`. Nothing has been merged,
deployed, purchased or qualified against live provider accounts. An offline test
pass is not evidence of a purchasable service or complete live acceptance.

| Package | Implemented and tested offline | Remaining acceptance |
| --- | --- | --- |
| B01 | Positive conversions (100 clicks, 10 conversions, $100 spend) do not produce no-conversions finding; true zero preserved | Preserve through final assembled Full/CI |
| B02 | Identity, scoped roles, revocable sessions, authorization race coverage | Execution facade now binds fresh original-session guards after commits/IO; intended IdP/live qualification remains |
| B03 | Idempotent provisioning, owner membership, customer signup | Deployed signup/recovery |
| B04 | Owned imports/jobs, connection generations, workspace-first closure locks; scheduler self-deadlock repaired | Final assembled isolation and unrelated live accounts |
| B05 | Net Shopify merchandise sales, local windows, refunds, 13-month retention, terminal publications and privacy invalidation | Deployed historical coverage/completeness reconciliation |
| B06 | Editable goals, versioned confirmation and immutable baseline reviews | Qualified connected baseline and intended-environment customer journey |
| B07 | Simulation plus separate production consent/ledger; exact review, held exposure, activation, settlement and atomic repeat-reservation transfer | Consented account-set pinning and mixed-currency hold rejection tested; actual native exposure sources and draft aggressiveness validation remain |
| B08 | Google connection, import, refresh/disconnect and customer UI | Live permissions, callbacks and history reconciliation |
| B09 | Actual Google optimization adapter and durable shared optimization coordinator integrated | Owned candidate queue/selection and exact Google original-response evidence integrated; candidate-to-review is implemented; original-session automatic orchestration, separate admissions and actual customer controls are implemented offline; native financial/transition producers remain unqualified |
| B10 | Meta reporting, customer connection UI, retained-account ownership and concrete adapters | No-DSA named configuration, customer creation and separate activation integrated; live supported-profile qualification remains |
| B11 | TikTok import/connection UI, actual creation and activation adapters/journeys | Named video/cover configuration, customer creation and separate activation integrated; native catalog parser and live advertiser/history qualification remain |
| B12 | Klaviyo, HubSpot, Omnisend transport, pacing, guarded customer OAuth/selection/disconnect | Live permissions/data-purpose qualification; no persistent gateway enrichment implied |
| B13 | Checkout/return/management, webhook reconciliation and entitlements | Scoped production adapter/webhooks, offer qualification, enforced production paid-work gate and GET-only historical receipt recovery implemented; commercial decisions, intended-environment purchase/cancel and external closure remain |
| B14 | Exact supplied-media review, private storage and bounded real decode | Hosted preflight now passed on e512529; complete hosted suite and intended storage/provider media setup remain |
| B15 | Actual Google durable paused creation, distinct activation and authoritative settlement protocol | Customer intent facade/named catalog integrated; concrete native exposure/terminal-reporting sources and live qualification remain |
| B16 | Actual Meta/TikTok durable creation/activation with original-attempt reconciliation | Social producer, no-DSA exact confirmation, original-confirmer guards and customer creation/activation integrated; native provider capability proof remains |
| B17 | Owned terminal commerce history, privacy-cascading receipt-linked assessment and Measurement History | Owned reconciliation observations, disabled parameterized maturity evaluator, v3 association bridge and retractable bounded feedback implemented; owned independent Shopify acquisition/publication and canonical association-feedback consumer are implemented; authenticated directional evaluator/adapter is implemented with contract fixtures; genuine delivery timing, qualified maturity/count facts, calibration and automatic first-action policy remain unavailable, so B17 is incomplete |
| B18 | Signup, source connections, goals, billing, media, activity, recovery and local closure reconciliation | Google/social creation and optimization UI integrated; both approval-context findings repaired and independently source-reviewed. Production assembly, default export gate and external closure/disposition remain |
| B19 | Readiness/schema checks, route/model registry, operator attention including terminal source rejection, native restore drill | Populated financial/social restore and composed export/closure verified offline; green final Full/CI and intended-environment alerts/recovery/retention remain |
| B20 | Cross-provider service/browser/isolation suites; two-brand composed fixture integrated | Integrate complete offline pilot matrix; unrelated live pilots and end-to-end purchasing/operations |

## Current Critical Path

1. Verify the assembled accounting, closure, activation, strict export and durable
   optimization changes with the integrated Google customer execution journey.
2. Validate the integrated session orchestration and directional consumers; complete
   usable read-only account diagnostics independently of unavailable execution mandates.
   An exact customer-reviewed first action exists; automatic initial direction does not.
3. Resolve the concrete [provider evidence/product decision](design/provider-guarantee-product-decision.md).
   The strict financial contract is not demonstrated for arbitrary outside-writer accounts.
   Preserve it unless the owner explicitly selects a separately specified launch scope;
   do not add empty financial interfaces or treat access as a missing guarantee.
4. Supply qualified measurement maturity/effective-time evidence before claiming
   action comparisons. Current persisted assessments honestly remain insufficient.
5. After the applicable policy/assembly work or explicit scope decision, freeze the
   assembled candidate; run Full and normal authorized PR CI, resolve
   actual failures, and complete the explicit offline pilot matrix. Then present
   concrete configuration/commercial/release and unrelated live-pilot gates.

No aggressiveness percentage increases the overall spending mandate. New campaign
creation and activation require their separate exact approvals. Local closure
reports admission fencing and observed local records; physical worker termination,
external ad shutdown, billing cancellation and data disposition are separate.
Export is disabled by default pending uniform writer/deployment qualification.
The public webpage remains separately owner-managed.

## GitHub Diagnostic Boundary

The exact shell workflow dispatch remains paused. Read-only diagnosis found the
execution environment proxy rejects the HTTPS tunnel to `api.github.com` with
`403 Forbidden` before GitHub responds. Connected GitHub Actions reads and ordinary
authorized pushes/PR creation succeed. No plan quota exhaustion is established;
no credentials, network settings or restrictions were bypassed. A verified actual
plan/usage limit still triggers the owner's all-project stop instruction.

## Verification Discipline

Exact commands, results and logs are in `docs/inlet-progress.md`. No final Full or
hosted success is claimed for this evolving successor. Individual focused passes
must not be added together as if they were one full suite. Focused integration checks cover owned exports, session callbacks and optimization;
these do not substitute for the final assembled Full.

## Predecessor Check Disposition

| Frozen predecessor | Local Full terminal result | Hosted terminal result | Disposition |
| --- | --- | --- | --- |
| PR112 `f698dea` | Failed:1578 passed,38 skipped,1 nested failure; Shopify initial-session readiness race | Run37410847813 failed:1581 passed,32 skipped,4 failures; FFmpeg decoder cases plus nestedFull | Superseded failed candidate; decoder and deterministic browser repairs incorporated into130 |
| PR118 `216fda2` | Failed:1597 passed,38 skipped,1 nested failure; billing initial-session readiness race | Run37410393272 failed:1597 passed,32 skipped,7 failures; decoder/upload cases, nestedFull and Chromium page-target discovery | Superseded failed candidate; repairs incorporated into130 |
| PR130 `0cf6706` | Passed (exit0):1813 passed,46 skipped in initial suite; all subsequent gates including final nested Full passed | Run37412515307 failed:1816 passed,40 skipped,3 failures; browser playback and nested validation | Frozen predecessor; successor includes retained Meta ownership repair, commerce publications, bounded export, coordinator/social creation, operator attention and codec-qualified browser repair |

No predecessor has both successful local and hosted final qualification. Earlier successful foundation runs remain
historical evidence only and are not substituted for final integrated acceptance.

## Successor Focused Evidence

At `915fbcc`, the combined exports, TikTok browser, route/model registry, provider attention, social coordinator and diagnostic suite passed **127 tests with one SQLite-only lock-contention skip**. Whole mypy (402 files) and Ruff passed. PR146 playback repair was integrated at `28089c7`; the actual customer portal, campaign review and billing browser suite completed successfully (16 tests). These checks do not establish a successful Full or hosted CI for the successor. No live qualification occurred.

Frozen PR130 local Full completed with exit0; final account-isolation/automation gate passed38 tests with6 PowerShell-unavailable skips. Exact log:/tmp/inlet-mvp-candidate-full.log. Hosted PR146 preflight run37415266510 failed before dependency/test execution: both Google Chrome154.0.8037.57 and Chromium154.0.8037.0 returned browser_no_result. This is not a quota failure. The later e512529 normal PR130 run37421671069 passed the actual H.264/AAC preflight; its complete pytest/remaining gates were still running at this checkpoint.

## Post-Freeze Review Repairs

The successor contains a proved post-credential-context authorization repair for
creation, activation and optimization (PR169). Root regression suite20passed;
Ruff/mypy474 passed. Both c602a1b Full and e512529 hosted CI predate this repair.
They remain useful exact-artifact verification but cannot qualify the newer tree.

Google native inventory is integrated and explicitly unqualified; the absence of
a proved preventive writer-control mechanism and the monetary-basis decision are
documented in `docs/design/google-native-exposure-qualification.md`. TikTok's
missing authoritative list response schemas remain a concrete parser blocker,
recorded in `docs/design/tiktok-catalog-response-evidence.md`. No invented provider
fields or spending guarantees fill these gaps.

## Latest Assembled Integration

`ca404a9` joins migration 0058 (replacement audit) and 0059 (social configuration
review) at 0060. Combined regression checks passed 54 tests with one SQLite-only
concurrency skip; Ruff and configured mypy (484 files) passed. This is not Full.
The repeat protocol has no qualified native source and does not enable live
execution. It retains predecessor obligations, rejects late ancestor-receipt
drift and prevents a canceled unattempted successor from locally releasing
inherited exposure.

Frozen c602a1b Full terminated with exit 1: 2511 passed, 58 skipped and four
failures (nested Full, two Shopify probes and TikTok logger fixture). Two stale Shopify barrier probes and logger contamination were
reproduced and repaired in the newer tree. The third native-import barrier failure
has not reproduced independently; diagnostics and guaranteed cleanup were added
without changing deadlines or blocking assertions. Combined affected modules
passed 50 tests with six SQLite-only skips. The replacement assembled Full is
running on exact `8efe196`, not yet qualified.


## Prior Frozen Validation And Newer Focused Packages

Frozen `8efe19668d4920df6607ddd60140ab8ab0779049` has tree
`11252fdbc785c270b49a1340dff95506d7391405`. Local Full log is
`/tmp/inlet-oct06-candidate2-full.log`; local Full finished with exit 0.
Normal PR130 run `37427571832` failed on the Meta startup race and nested wrapper.
Actual hosted checkout `80e432a072d4970fd4fe50c23b1a913257e99250` has the same
frozen tree. The repaired successor requires its own terminal validation.

Preceding hosted `e512529` failed: 2426 passed, 51 skipped, five failures. Its
nested report included CRM HubSpot/PostgreSQL and Meta/PostgreSQL browser failures
whose exact assertions were lost to the old diagnostic bound. Both passed the
hosted outer suite and an unchanged local Chrome 154 reproduction (eight ordered
browser cases); their hosted-only cause remains unresolved. The new candidate
retains bounded nested failure and skip evidence through normal CI artifacts.

Newer integration packages are outside that frozen validation: PR174 adds owned
named optimization discovery, mandate/topology consent and exact initial/repeat
customer APIs (combined root checks: 49 passed); PR175 surfaces terminal provider
rejections without raw error data or retries (combined root checks: 35 passed).
The existing-campaign UI is integrated after 39 combined API/browser/route tests
passed on SQLite and PostgreSQL (PR176). The social execution consumer is integrated after 27 combined API/browser/route
checks passed on both databases (PR177). Production runtime factories remain disabled. Their focused
passes are not a replacement for a final assembled Full and hosted pass.


## Remaining Engineering Is Not An Access Request

The earlier review at `1c82e03` identified gaps since partly implemented. Current
integration includes production billing scope and offer qualification, mandatory
production paid-work enforcement, original-bound GET-only receipt recovery, owned
candidate preparation/selection, native diagnostics and exact successful Google
original-response evidence, operational maturity evaluation and retractable feedback.
These focused packages do not qualify the live product.

Candidate-to-review orchestration, independent commerce publication/authority
assembly and scoped association-feedback consumption are now integrated and tested.
Mandate-derived automatic execution remains under implementation in separate 0072;
directional feedback production remains unavailable. Genuine delivery-time evidence, calibrated
maturity/action policy and native financial/transition bounds remain unavailable or
unqualified. Provider limitations are explicit in the spending-source matrix;
credentials cannot supply absent preventive-writer or reporting-finality guarantees.
Unknown original requests remain unknown. Diagnostic acquisition and captured
configuration completion alone never authorize replacement, release or spending.

The repeat ancestry32→33 defect and both social approval-context findings are fixed,
regression-tested and independently source-reviewed. The production billing bypass
is likewise repaired and source-reviewed. These reviews did not independently run
the reported tests. Original exact frozen hosted validation failed two tests from
the Meta Retry harness race; PR199 repairs its deterministic cause. Final assembled
Full/hosted qualification remains pending and earlier failures remain recorded.

The frozen 8efe196 local Full subsequently finished with exit 0 (primary suite:
2639 passed, 59 skipped; all later gates completed). Its hosted run remains failed.
The successor joins billing, feedback, captured Google completion, candidate review
and default-disabled runtime observations at migration 0071. Root combined migration,
native restore and registry checks passed: 13 passed, 1 expected SQLite skip.
Neither these focused checks nor the older successful local Full validate the
successor's entire assembled tree; a new frozen Full and normal hosted CI are required.


## Integrated After a4fcd3a

Integration9c76ff8 includes session backend/UI and authenticated epochs (0072), the
0073 schema join, exact Google transition composition, and the owned directional
consumer. Root focused checks: session66 passed/1 expected skip, supporting composition
46 passed, migration/restore8 passed/1 expected skip, complete disposable schema
roundtrip passed, directional42 passed. These are separate suites, not an assembled
Full result. Both frozen a4fcd3a validation runs remain pending at this update.

The provider matrix is a proposal, not a release-scope change. Recommendation-only
launch would leave autonomous action, publication and qualified learning acceptance
incomplete. No production source or policy is installed by passing synthetic tests.
