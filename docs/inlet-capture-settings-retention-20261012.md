# Capture Request And Effective Settings Retention — 2026-10-12

Baseline `548c351`, branch `codex/inlet-w1-followup`, local-only package. Existing
Google capture stored attribution plus an opaque query-profile digest but did not
retain readable requested settings. The actual query sends no attribution overrides.
This package retains that fact through capture storage, saved provenance, plan history,
workspace export and customer review. It does not activate a social producer.

## Implemented Boundary

Finite `CaptureSettingsV1` binds exact platform/API/event/family/advertiser, producer,
query digest, count meaning, report support, money-unit state and requested settings.
Effective attribution stays unknown until a separate evidence contract exists.
Meta request flags cannot become effective attribution; unsupported/unverified social
combinations cannot claim supported observations, and unknown units cannot supply
money. Existing Google queries, selected-event confirmations and permissions are
unchanged; both conversions/all-conversions profiles are distinct.

New settings use request2/capture2, provenance2 and plan-version3. These are wire
formats, not changes to default policyV3 or privateV4–V6. Historical captures and
plans retain exact payloads/digests with absent settings omitted. New plans may
contain old/new typed provenance; every selected capture must be typed, at least
one settings-bearing capture requires plan3, and settings cannot hide under old tags.
Historical reprojection compares the retained record against its original capture.

Migration0093 replaces only the capture binding trigger/function. It preserves all
existing scalar ownership, byte, FK, immutable-row and raw-erasure/privacy fences;
frozen0091 is unchanged. It admits exact request1/capture1 without settings or
request2/capture2 with object settingsv1. No table/column/data rewrite. Downgrade
refuses any non-v1 capture before changing DDL; it never erases records to permit
rollback. Reader-first rollout and a reader-capable rollback floor are required.
No deployment or rollback to a full old image has been tested or authorized.

## Verification

134 exact cases passed:106 contract/component,14 SQLite and14 PostgreSQL. Full
Ruff, configured no-path mypy (1516 source files), exact collection, three JavaScript
syntax checks and diff check passed. No failures/errors/skips in qualified XML.
One heavy slot, subprocess cleanup and all resource floors were preserved.

Successful106 component+2 SQLite browser cases from attempt04 were carried forward.
Attempt05 reran the corrected failed migration case and the25 previously unrun
cases. Hash comparison proves the only source difference is that migration test's
expired ORM-reference correction;1824 other source files are identical. Independent
review approved this scope. No whole-suite rerun or unchanged failed retry.

Earlier runs stopped immediately and retain original source/log/XML/exit/unrun
records:01 Ruff test-probe placement/context style;02 mypy optional local reuse;
03 new synthetic fixture still using an old generic producer/query digest;04 test
accessing expired ORM attributes after session close. These were corrected test
setup issues; production guards were not weakened. The migration-trigger issue
was caught and fixed during source review before qualification.

Evidence: `/workspace/inlet-evidence/20261012/capture-settings-attempt05/`.
Final continuation manifest SHA256:
`3274f48427b53287cfe3138ac9b2872b747841e6d02c9d9731ae3d961af027f6`.
Completion freeze SHA256:
`4578c4cb3cfb2e8f917ba680da48080426254f98e70cf6568b0bb6461ee8513e`.
The freeze binds546 evidence files and1825 source files, including all five attempts,
pre-change fixtures, acquired request/capture/export artifacts, retained-plan artifacts
and prior DTO probes. Final independent evidence review CLOSED: all546 evidence/1825 source hashes,
134 exact identities, seven static results, four retained-plan artifacts, two
old-to-plan3 lineage sets and six capture/export/wire records verified. No local
commit blocker; no human, live, social capability or historical incident closure.

SQLite uses ORM-created schema plus explicit frozen migration functions. PostgreSQL
uses the actual Alembic chain in isolated disposable schemas, including0093.
The prior capture fixture is a genuine pre-change serialization of an existing pure
fixture, not a live/database capture. The prior plan2 fixture is an actual saved
SQLite API artifact from the preceding package. Their original bytes/digests remain
fixed. Old strict DTO probes establish format rejection, not full-image rollback.
Browser Meta variants are explicitly presentation-only adversarial DTOs, not qualified
Meta reports or evidence of an activated producer.

## Source Gaps And Holds

The parent's recovered primary-source evidence and exact candidate distinctions are
recorded in [the social semantics design](design/social-selected-event-semantics-v1.md).
This executor's additional retrieval remained inaccessible; no duplicate independent
retrieval or live verification is claimed.

- Meta [out-of-cycle changes](https://developers.facebook.com/documentation/ads-commerce/marketing-api/out-of-cycle-changes/occ-2025):
  `action_report_time`/`use_unified_attribution_setting` are ignored from2025-06-10;
  `7d_view`/`28d_view` return no data from2026-01-12. Requests are not effective settings.
- Meta [AdsActionStats](https://developers.facebook.com/docs/marketing-api/reference/ads-action-stats)
  and [Insights fields](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-account/insights):
  candidates are exact `offsite_conversion.fb_pixel_purchase` and `.fb_pixel_lead`
  in `actions`, with matching `action_values` only in identical window/breakdown
  context. Still missing: explicit v26.0 campaign/day field/window combination
  qualification, row-scoped effective settings and counting mode. `action_target_id`
  does not establish custom conversion ownership; no grouping/substitution or window sums.
- TikTok v1.3 [metrics](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443967255553&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language):
  website count `complete_payment` pairs with documented key `total_complete_payment_rate`.
  Monetary wire units, precision and scaling are unverified; no MoneyCell/revenue/ROAS.
  `purchase`, `total_purchase` and website payments are not interchangeable.
- TikTok v1.3 [dimensions](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443956638721&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language)
  and [synchronous reporting](https://business-api.tiktok.com/gateway/docs/index?doc_id=1738864778664961&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language):
  still missing exact metric/dimension/data-level combinations and campaign/day
  deleted-status filter qualification. `event_source_id` is not established at that
  grain. Actual account/ad-group windows and counting mode remain unknown; ordinary
  impression-time guidance alone does not qualify them.

No omission-as-zero rule is established for either social provider. Keep social
producers held until the exact source gaps are resolved and a bounded producer
contract is reviewed. Next package is that qualification, not activation based on
candidate names or guessed units.

Both owner retention and artifact-sharing decisions remain pending, as do six human
quality judgments. Q13 independent provider verification remains a gap; historical
R01–R03 causes remain incompletely explained. No public webpage change, push, PR,
hosted CI, merge, deployment, live provider/model call, credential operation,
advertising write or spend occurred. Planning remains manual-action-only.
