# Inlet Audit Acceptance Status — 2026-10-06

All evidence below is offline. Main remains the audited ea3591c; drafts are not
merged, deployed, live-qualified or a purchasable release. A green isolated test
suite is not completion of the audit's full customer/provider journey.

| Package | Current Acceptance Status | Remaining Critical Work |
| --- | --- | --- |
| B01 | Conversion defect fixed and reviewed | Live campaign-type qualification remains separate |
| B02 | Scoped identity and shared revocable sessions implemented/tested | Google browser sign-in implemented offline; live identity setup/qualification |
| B03 | Atomic idempotent workspace/owner provisioning implemented/tested | Complete browser onboarding qualification |
| B04 | Explicit import/job ownership implemented/tested | Each new provider path must maintain the same boundary |
| B05 | Shopify canonical sales/refund/history contract implemented/tested | Customer OAuth routes and concurrent session fencing implemented/tested; live reconciliation |
| B06 | Editable versioned goals and usage controls implemented/tested | Manual/mock interpretation remains intentional; no live model claims |
| B07 | Durable mandate/reservation/action safety implemented/tested | Complete qualified provider execution and accounting journeys |
| B08 | Google HTTP connection/backfill/lifecycle code and tests | Browser setup, grant-level revocation orchestration, live qualification |
| B09 | Bounded Google action/precondition/reconciliation preparation | Actual qualified live action adapter journey; no approved spend |
| B10 | Meta child metric model/fixtures implemented | Actual child performance ingestion and complete lifecycle qualification |
| B11 | TikTok HTTP import/history/lifecycle and scheduler wiring implemented/tested | Business renewal/revoke contract, conversion qualification and live journey |
| B12 | Klaviyo/HubSpot HTTP and conservative field projections implemented/tested | Durable pacing and verified Omnisend HTTP adapter implemented/tested; renewal, canonical identity mapping/retention consumer |
| B13 | Test Stripe HTTP, webhooks, entitlements, management and safe recovery implemented/tested | Commercial configuration, complete browser journey and live qualification; legacy unknown keys fail closed |
| B14 | Typed immutable offline review and bounded image validation implemented/tested | Video validation, production media storage, rendered review and preview/publication equivalence |
| B15 | Not implemented | Google reviewed publication and partial-failure recovery after B14 |
| B16 | Not implemented | Meta/TikTok actions and reviewed publication after shared contracts |
| B17 | Not implemented | Mature comparable outcome evidence and bounded feedback |
| B18 | Portal plus actual HTTPS browser/API/database lifecycle tests pass | Actual browser/API/DB signup, goal and billing fixture journey passes; complete source setup, mandate editing, activity/support, export/closure |
| B19 | Operational foundation exists; readiness HTTP status repair implemented/tested | Dependency readiness, exact-artifact checks, monitoring, backup/restore and release qualification |
| B20 | Offline two-workspace fixtures cover specific cases | Unrelated real pilot businesses through complete launch workflows |

## Immediate Critical Path

1. Finish exact-head Full/CI on repaired integrated checkout; keep migration and
   populated roundtrip evidence tied to that checkout.
2. Extend actual application/browser/database journeys to the customer Shopify
   connection routes, including interruption, replay and session rotation.
3. Add paced CRM renewal while retaining verified account binding. Omnisend's
   first-party identity contract is resolved; canonical enrichment/retention remains.
4. Complete B14 shared review/media contracts before B15/B16 publication adapters;
   then measured outcomes, operational qualification and pilots.

Latest bounded rereview at integrated8ae5ab7 closed TikTok outbox, portal retry and
Klaviyo nullable-channel findings. Full/CI remained separate. Browser full-suite
harness received a bounded20→60second timeout adjustment without removing assertions;
its final-head validation must not be credited to an earlier head.

The /ready repair makes invalid startup configuration return HTTP503 and no-store,
while /health remains liveness. It does not introduce a database connectivity probe
or prove live availability; B19 is not complete.

## Combined Customer Foundation Candidate

Branch `codex/inlet-release-foundation` combines PR87–93 with the frozen PR86
foundation. Migration0039 joins media/review0037 and CRM pacing0038. Populated
0036→head→0036→head tests preserve existing ownership, goals and Meta generation;
new feature tables are removed/recreated as expected in the disposable database.

At code head `b3035a8e2df2d86fa38b91d5d717b76d71056aa5`, the combined focused
suite passed **214 tests, 8 intentional SQLite concurrency skips**, with PostgreSQL
counterparts executed. Twenty warnings are existing Alembic configuration
deprecations. Ruff and mypy (287 files) passed. Full and hosted CI must still be
run on the final candidate; these focused results do not replace them.
