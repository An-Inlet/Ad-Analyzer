# Inlet B15–B20 Working Acceptance Matrix

> Historical checkpoint / scoped evidence record. For current implementation, focused
> tests, exact-artifact aggregate validation and live qualification, start with the
> [current acceptance matrix](inlet-current-acceptance.md). Requirements and historical
> test/CI results below are preserved; old missing-feature claims are not current status.

Checkpoint: 2026-10-06. Documentation base: PR94, commit
`5f9a0d0d4d1d016135c54d3360b16e0800b6f6b6`. **None of B15–B20 is complete.**
The draft branches below are separate candidates, not functionality already combined
in this checkout, merged to main, deployed, or available for purchase.

The exact acceptance criteria below were retained from the original audit read through
ChatGPT Library by the integrating agent. No original-file materialization is claimed:
its bytes are unavailable to this executor. The detailed rows are an engineering
decomposition of those criteria, not additional verbatim audit text. The original
audit remains authoritative; later owner instructions make the public webpage
owner-managed and separate. Do not infer acceptance from package numbers or fixtures.

| Package | Retained Audit Acceptance Criterion | Audit Dependencies |
| --- | --- | --- |
| B15 | Implement Google reviewed campaign publication. Partial resource failures reconcile without duplicate launches. | B08, B14 |
| B16 | Implement Meta and TikTok actions and reviewed publication. Each declared campaign type passes its complete journey. | B07, B10, B11, B14 |
| B17 | Add measured action-outcome feedback. Comparable mature windows update bounded recommendations with an explanation. | B05, B09, B12, B16 |
| B18 | Reuse public page v2; build Inlet onboarding, navigation, activity and support. Customers finish core tasks without operator setup. | B03, B06, B13, B14; public page subsequently owner-managed |
| B19 | Qualify SaaS operations. Correct readiness, protected admin boundary, exact-artifact CI, alerts and successful restore drill. | B02, B04, B13 |
| B20 | Run unrelated pilot businesses through all launch workflows. Include revoked access, stale data, retries and closure. | B09, B12, B15, B16, B17, B18, B19 |

**Evidence vocabulary:** “implemented” means inspected committed code; “tested” means
an identified test or recorded run at its named head. Reported package test counts
below were not rerun for this documentation change. “Code” denotes unfinished
implementation that can proceed offline. “Qualification” denotes intended-environment
or provider evidence that code/tests cannot substitute for. “Decision” denotes an
unresolved product, commercial, privacy, or live-operation approval. All provider
responses in cited new tests are fixtures or MockTransport responses.

## Evidence Register

| Evidence | Exact candidate and inspected sources | Recorded validation and limits |
| --- | --- | --- |
| E94: combined customer foundation | [PR94](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/94), documentation head `5f9a0d0d4d1d016135c54d3360b16e0800b6f6b6`; code head `b3035a8e2df2d86fa38b91d5d717b76d71056aa5`; `docs/inlet-audit-status.md` | Combined focused 214 passed, 8 SQLite concurrency skips, PostgreSQL counterparts ran. This is the foundation baseline, not B15–B20 completion. |
| E95: browser-origin Shopify API journey | [PR95](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/95), `54587ecf6219ee1b587b906aae2a8cdf8a79eeba`; `tests/test_customer_browser_api_journey.py`, `tests/javascript/customer_portal_api_browser.mjs` | 44 passed, 6 SQLite concurrency skips. Chromium uses HTTPS, real cookies, FastAPI and SQLite/PostgreSQL; actual Shopify clients parse mocked HTTP and import the baseline. Shopify authorize/callback/list/disconnect and billing checkout/webhook are called by test JavaScript API helpers. This does **not** prove customer-visible consent/navigation or checkout clicks. |
| E97: dependency readiness | [PR97](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/97), `8392a880565f6039e5de8dd79afb91af0b56329d`; `tests/test_dependency_readiness.py` | 23 focused passed, including guarded disposable PostgreSQL. Fresh read-only SELECT 1, NullPool, independent 2s connection/1s statement timeouts and cleanup. Reachability only; no schema, capacity, DNS wall-clock or production health claim. |
| E98: publication coordinator | [PR98](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/98), `bc3aadc9636c7028c03c2563c4e1f63559212dac`; `docs/inlet-publication-core.md`, `app/publication`, `tests/test_publication_core.py` | 102 focused passed, 2 SQLite concurrency skips; PostgreSQL cases and migration 0040 roundtrip passed. Exact local fixture compiler/transport only. Production factory disabled. Activation approval is recorded; activation is not executed. |
| E99: rendered campaign review | [PR99](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/99), `292ac8d4cfa2d52b15d76d1dc8edce78b61f0c95`; `docs/inlet-campaign-review-ui.md`, `tests/test_campaign_review_ui.py` | 53 focused passed, 1 SQLite concurrency skip. Real HTTPS Chromium/API/DB on SQLite and PostgreSQL: exact revision approval, edit invalidation, stale approval, role revocation, literal text and private image success/failure. Existing drafts are fixtures; no create/upload/publication journey. |
| E100: native logical restore | [PR100](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/100), `4b3f535e760644e6002ea28776208f39a84b7560`; `docs/inlet-restore-drill.md`, `scripts/inlet_restore_drill.py`, `tests/test_inlet_restore_drill.py` | 19 focused passed, 5 Alembic warnings. Native PostgreSQL 16.15 restored 82 tables/44 rows/two synthetic tenants; schema/data/ACL/sequence comparisons and failure cleanup. Generated disposable schema, same local role, no real backup or production topology. |
| E101: Meta lock order | [PR101](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/101), `88353406e089bfb309bee2c5a247e29dc6f031d3`; `docs/inlet-meta-review-lock-order.md` | 69 focused passed, 3 SQLite lock skips; PostgreSQL barriers reproduce then repair review versus disconnect/reauthorization deadlocks. No actual actions/publication. |
| E102: CRM lifecycle repairs | [PR102](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/102), `2508a7586e27fdd22d79c0e870fadb3e2d962e53`; `docs/inlet-crm-renewal.md` | 193 focused passed, 15 SQLite concurrency skips. Preserves quota after stale lifecycle responses, binds renewal client, handles unknown Omnisend statuses/JSON retry delay and brand-wide quota. PostgreSQL counterparts ran; not a complete retained-enrichment/customer UI journey. |
| E103: private GCS adapter | [PR103](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/103), `d4c78c52513a1c18ce141d35e9402c0249ab1a32`; `docs/inlet-private-media-storage.md`, `tests/test_gcs_media_storage.py` | 76 focused passed, 1 SQLite lock skip. Actual SDK with mocked HTTP verifies private bucket metadata, generation preconditions/pinned reads, exact size/SHA, races and unknown outcomes. Disabled default; no live cloud calls, deletion lifecycle or orphan cleanup. |
| E104: visible Shopify consent journey | [PR104](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/104), `fa70d8b5aa7d3f14c08a83cc622ba53409279591`; `docs/inlet-shopify-consent-ui.md`, `tests/test_shopify_consent_browser.py` | 37 focused passed, 6 SQLite concurrency skips; real portal controls and HTTPS Chromium GET callback bridge on SQLite/PostgreSQL. Cancel, Back/retry, stale return, session change, successful workspace return and query-history cleanup pass. Consent network is intercepted and provider HTTP mocked. Disconnect UI/live qualification remain open. |
| E107: delayed-write authorization | [PR107](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/107), `a6de6e962274a035537430266f700288b24e5efd`; `docs/inlet-progress.md` | Combined 108 passed, 9 SQLite concurrency skips; final focused 12 passed, 2 SQLite lock skips. Rechecks current customer authorization after upload/lock/provider waits and expiry; local revocation fenced through commit. Remote revocation remains a point-in-time check. |
| E108: concrete Google publication compiler/HTTP | [PR108](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/108), `e4c1392fa1302569ed286c1e5bf27ed1db4b36ab`; `docs/inlet-provider-publication.md`, `app/executors/google_publication.py` | 27 focused MockTransport tests passed: actual v25 paused Search graph serialization, validate-only, one-shot mutation, exact semantic readback, uncertainty/conflict/no-replay. Runtime unavailable. Provider qualification reads, durable provider approval/coordinator, UI, production authority, activation and settlement remain code. |
| E109: supplied video validation | [PR109](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/109), `e12f11baa447d69d111f897f582ddafb34e3c95e`; `docs/inlet-video-validation.md` | 58 focused passed, 1 SQLite lock skip; real synthetic FFmpeg 7.1.5 MP4/H.264 with optional AAC, full bounded decoding and exact offline TikTok approval. No OS-sandbox claim. The reviewed integration candidate serializes upload authorization, validation and persistence in a worker thread. Video playback/upload UI, production isolation/load and provider acceptance remain open. |

Full/hosted CI is a separate gate. This matrix does not assert terminal CI success
for these candidates; validate the final integration artifact, checkout SHA and tree
before updating release evidence. Summing independent test counts is not an
end-to-end or combined-regression result.

## B15 — Google Reviewed Publication

| Working criterion | Current evidence | Remaining code | Qualification / decision |
| --- | --- | --- | --- |
| Exact approved draft compiles to the supported Google campaign graph with explicit tracking, bidding, budget, targeting and destination behavior | B14 immutable supplied-content review; E99 renders current digest. E108 adds separate typed provider documents and a deterministic Google Search paused-graph compiler. | Persist the separately qualified provider review/approval and integrate its coordinator/UI; verify account/currency/timezone, conversion goal/action/target mappings; prove rendered review-to-request equivalence end to end. | Qualify current Google API fields and selected Search capability. Customer approves exact new campaign and creative. Existing review/simulation approval is not live authority. |
| Execute bounded provider requests and verify owned paused resources | E98 binds scope, native generation, request digest/fence and dependency receipts. E108 implements actual Google v25 HTTP serialization, validate-only, single mutation and semantic readback under MockTransport. | Integrate concrete transport with durable provider approval/coordinator and qualified production mandate authority; finish capability/identity qualification reads. Default factory remains unavailable. | Approved project/client/developer access and test account; actual paused-resource readback and native budget semantics. No spend authorized by this assignment. |
| Partial creation, uncertainty and concurrent workers do not duplicate launches or lose exposure | E98 retains one reservation across partial success/unknown outcomes; immutable receipts and PostgreSQL duplicate-claim regression. E108 reconciles acknowledged IDs with exact semantic readback; unknown unacknowledged timeouts cannot be resent. | Connect real adapter receipts to durable coordinator/background dispatch/recovery; qualify authoritative no-effect evidence rather than broadening retry eligibility. A timed-out create or empty eventual list cannot imply no effect. | Qualify provider reconciliation/idempotency limits and interruption recovery on an approved account. |
| Activation requires separate approval and safe accounting | E98 records a separate exact paused-graph activation approval; reservation remains held. | Actual typed activation plan, refreshed authority/readback, mature spend reconciliation, bounded settlement and partial-resource handling. | Explicit activation/spending approval; validated provider exposure and reporting-delay policy. Paused resources alone do not prove zero future exposure. |

The earlier adapter-port proposal is partly implemented by E108: separate provider
review/plan/request/receipt schemas and a narrow concrete Google compiler/HTTP adapter
now exist. Its shared ports are recorded in `docs/inlet-provider-publication.md`.
Google supports the explicit manual-CPC/nonshared daily-budget Search profile;
additional variants require typed extensions. These documents and transport are not
production authority. Freeze further shared variants centrally before Meta/TikTok work.

## B16 — Meta And TikTok Actions And Publication

| Working criterion | Current evidence | Remaining code | Qualification / decision |
| --- | --- | --- | --- |
| Optimize supported existing campaigns within the fixed mandate | B07 reservation/fence framework and provider import/lifecycle foundations exist. They do not constitute concrete Meta/TikTok action execution. | Provider-specific budget-owner/status actions, exact current-state preconditions, request serialization, readback, cumulative exposure and uncertainty handling. | Verify supported budget configurations, conversions and provider spending semantics. Aggressiveness never enlarges the total limit. |
| Compile and review supported Meta static-image and TikTok supplied-video campaigns | B14 strict supplied-content schemas; E99 static-media display and approval; E109 adds bounded MP4/H.264 validation/offline approval, and E103 adds private GCS storage. E101 repairs Meta lifecycle/review lock order. | Exact provider identity/pixel/event/bidding/attribution/placement/schedule models and compilers; native uploads, video playback/upload UI, media lifecycle deletion, and review every semantic field. Upload-thread integration is implemented in the reviewed candidate. | Qualify provider permissions, identity/media rights and supported campaign types. No generated/new creative publication without customer review. |
| Create paused graphs, reconcile partial effects and activate only after separate review | E98 offers a fixture-only common coordinator, not provider transports. | Concrete Meta and TikTok create/action/readback/reconcile/activation adapters integrated through the frozen shared authority and receipt contracts. | Approved sandbox/test-advertiser journeys and separately authorized activation. Until then factories and live writes stay unavailable. |

## B17 — Measured Feedback And Explanations

| Working criterion | Current evidence | Remaining code | Qualification / decision |
| --- | --- | --- | --- |
| Compare mature, complete, comparable before/after windows for an exact executed action | Existing `app/learning/report.py` compares completed weeks of analysis/review activity. Legacy unified-outcome tests reject immature cohorts and currency mismatches. Shopify canonical measurements and goal baselines also exist. These are reusable components, not an Inlet action-effect result. | Bind immutable execution receipts, goal/mandate revisions and native account generation to corrected measurement snapshots; require matching currency, metric definition, attribution/value horizon, timezone and coverage; invalidate/recompute when corrections or confounders change comparability. | Qualify conversion delay/maturity and comparable-window policy per provider. Do not claim causal lift from an uncontrolled before/after comparison. |
| Explain observed change, uncertainty and withheld conclusions to the customer | Legacy weekly-learning reports offer bounded activity suggestions, with tests in `test_weekly_learning_report.py`; approval acceptance is not advertising effectiveness. | Customer-scoped outcome API/UI with reproducible evidence references, missing/immature/confounded reasons, absolute/relative changes and minimum-evidence rules. | Owner review of customer-facing claims and success criteria when not settled by the audit. |
| Use evidence for bounded future recommendations without bypassing authority | Legacy decision learning only breaks otherwise equal ranking ties and does not change approvals or advertising state. | Connect qualified Inlet outcomes to versioned recommendation policy; test insufficient evidence, contradictory updates, tenant isolation and unchanged spending/review gates. | Validate policy inputs, including draft 5/10/20 aggressiveness. Feedback cannot create new spend authority or auto-publish creative. |

No new B17 contract or schema is frozen by this document. Define a shared immutable
outcome-evidence interface only after provider execution receipts and measurement
maturity inputs are stable. Do not assign dependent implementations to guessed fields.

## B18 — Usable Customer Application

| Working criterion | Current evidence | Remaining code | Qualification / decision |
| --- | --- | --- | --- |
| Customer signs in, creates a workspace and recovers safely from interrupted requests | E94 includes disabled-default Google sign-in, server sessions, owner membership, durable provisioning/goal retries. E95 uses actual sign-in buttons/session cookies and checks a second customer's denial. | Integrate remaining core-task screens and explicit actionable error states; preserve logout, role changes and stale-response guards across all screens. | Configure/qualify hosted identity, approved domain/CSP popup behavior and unrelated customer devices. |
| Customer connects the supported tools they already use and selects owned accounts | Scoped APIs/imports exist; E95 verifies Shopify APIs/imported baseline. E104 now verifies actual Shopify portal controls, consent navigation/GET bridge, cancel/Back/retry/session changes and workspace return using mocked provider boundaries. E102 repairs CRM lifecycle safety. | Shopify disconnect/deletion UI; complete account selection/reconnect/status controls for advertising and optional customer-data providers; integrate repaired lifecycle errors into actionable UI. | Approved apps/callbacks/grants and actual provider consent/renewal/revocation. A fixture browser API call does not prove a usable consent screen. |
| Customer describes a milestone, edits/confirms a goal, budgets, reviews a plan and follows progress | Existing portal saves/reviews/confirms structured monthly Shopify goals and displays simulated mandates. It explicitly says confirmation does not authorize spend. | Complete supported milestone interpretation/manual fallback, cumulative-window editing, mandate creation/editing/pause/revoke, execution review/activity/outcome screens and progress updates. | Confirm any unsettled goal/policy semantics; qualify actual underlying imports. Do not imply simulated mandates execute ads. |
| Customer creates/edits supplied campaign content and approves the exact plan | E99 renders saved drafts, edits a bounded subset and invalidates approval; E107 rechecks delayed-write authorization. E103 private storage and E109 bounded video validation are separate tested candidates. | Draft creation, media selection/upload/video playback, full supported audience/schedule editing and preview-to-provider-plan mapping; finish B15/B16 dispatch controls. The reviewed candidate integrates serial upload authorization/service in a worker thread. | Media/provider placement qualification and customer approval. An offline content preview is not a provider placement preview. |
| Customer purchases/manages a subscription and can export, close and obtain help | Billing test transport, entitlements and management preparation exist; E95 verifies fixture checkout/webhook APIs. Shopify privacy/export foundations cover narrower data boundaries. | Real customer-visible checkout return/recovery/management journey; unified customer export and closure orchestration across grants, sessions, billing, jobs, facts, checkpoints and media; activity/support paths. | Commercial price/currency/limits/cancellation choices, privacy/retention policy and live checkout/webhook qualification. Existing measurement export is not full account export/closure. |

E104 supersedes the earlier uncommitted Shopify UI status. Its actual portal navigation
is now verified offline, including cancellation and session changes; external consent
and token/metadata responses remain mocked. E95 remains useful API/import/erasure
evidence, not a substitute for E104's visible controls. Neither proves live consent.
The public webpage is owner-managed and separate; these application gaps cannot be
closed by an illustrative demo or email early-access button.

## B19 — Operational Readiness

| Working criterion | Current evidence | Remaining code / operational preparation | Qualification / decision |
| --- | --- | --- | --- |
| Health accurately distinguishes live process from a usable dependency | E97 returns not-ready on invalid configuration or failed fresh SELECT 1; connection/resource cleanup and safe errors tested. | Schema/version compatibility checks as needed; readiness must reflect the actual artifact's dependencies without promising universal timeout bounds. | Intended-environment database reachability, pooling/capacity and failure/rollout behavior. |
| Customer access cannot enter protected administrative/operator surfaces | Existing customer identity/session/role boundaries are separate from legacy operator API/dashboard authentication; repository security and IAP tests cover narrower boundaries. | Inventory every operator/admin route and worker trigger in the assembled release; add final-artifact customer-versus-admin negative tests and verify no development bypass leaks into customer deployment. | Intended-environment identity/IAP/IAM and network enforcement; operator access ownership and incident controls. Separate code paths alone do not prove the deployed boundary. |
| Release the exact tested artifact with safe migrations and rollback | Existing validation/deployment scripts and migration tests; E94 combined subset, E98 migration 0040 roundtrip. | Assemble all selected branches, resolve migration ancestry, run required Full/security/privacy/isolation gates against exact final head/artifact; update deployment/runbooks and rollback/reconciliation procedure. | Human review, merge and release approval; intended-environment secret/IAM/network/configuration checks. A green predecessor branch is not final-artifact evidence. |
| Backup restoration preserves data, constraints and ownership | E100 native restore verifies generated schema/data/ACL/index/sequence fingerprints, membership/provider ownership and cleanup. | Adapt approved drill to actual backup/key/media inventory; implement/test post-snapshot deletion/consent/session/grant reconciliation before restored workers serve or execute. | Real backup/PITR/offsite integrity, multi-role ownership, encryption-key/media recovery, RPO/RTO and intended-environment recovery drill. Same-role disposable restore does not prove these. |
| Operators can detect and safely contain failures | Existing runbook covers kill switches, stopping workers, uncertain mutation non-retry and audit preservation. Durable job/retry foundations exist. | Complete application/provider/job/billing/storage alert signals, actionable sanitized diagnostics, incident/support procedures and recovery exercises. | Deploy and test monitoring/alert routing and operator ownership; authorize any provider intervention separately. |

## B20 — Unrelated Pilot Businesses

| Working criterion | Current evidence | Remaining code / offline acceptance | Qualification / decision |
| --- | --- | --- | --- |
| Unrelated businesses complete the entire core workflow without crossing ownership | E95 and E99 test real browser/API/database slices with synthetic tenants; E100 preserves two synthetic tenants on restore. No complete pilot exists. | Assemble unrelated two-customer journeys through supported setup choices, goal/mandate, purchase, imported evidence, campaign review, paused creation, approved activation, outcome, disconnect/export/closure. Exercise actual application controls; identify each substituted provider boundary. | Recruit/approve unrelated Shopify pilot businesses and qualify their supported providers/data. Synthetic tenants are not real pilots. |
| Interruptions, delayed results and failures remain safe across the whole system | Isolated suites cover sessions, duplicate provisioning, delayed billing, stale approvals, scope and fixture publication uncertainty. | Combined crash/retry/reconnect/revocation/partial-publication/provider-delay scenarios against the final integrated release candidate, plus budget and privacy invariants. | Authorized real-environment pilot failure/recovery evidence and support coverage. Do not authorize ad spend merely to finish a test. |
| Product can be purchased and operated with accurate claims | No production purchase, live advertising operation or complete customer/pilot acceptance is claimed. | Close B15–B19 code gaps, acceptance evidence and unresolved review findings; keep application/public claims synchronized with available behavior. | Approved pricing/terms/privacy, provider permissions, operational release and explicit pilot spending mandates. Real success criteria must be reviewed, not inferred from PR count. |

## Dependency Order And Next Evidence

1. Stabilize B14 media/review and shared production publication interfaces. Integrate
   the actual Google compiler/HTTP/readback with qualified review/coordinator; Meta/TikTok depend on their exact
   operation schemas and media prerequisites. Shared fixture success does not finish them.
2. Add real activation/reconciliation/settlement under separately qualified authority;
   continue customer source/setup and core-task UI in independent packages.
3. Define B17 comparable outcome evidence from stable receipts and corrected measurement
   windows, then API/UI/feedback tests. Preserve legacy learning functionality.
4. Integrate final branches and migrations; run exact-artifact validation, operational
   preparation and full offline unrelated-customer journeys before live qualification.
5. Seek concrete owner choices only for unsettled commercial/privacy/product policy or
   authorized operations. Missing implementations above are engineering work, not
   reasons to stop for credentials. No merge, deployment, grants or spend is authorized.
