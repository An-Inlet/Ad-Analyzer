# Qualified Reporting Consumer And Planner Boundary

Predecessors reviewed: presencecontracts e5d9dae, pure summarya4a395c, finalized
storagedb4325a, pureMetaparsera99aaed. Meta0090 producer owns Meta/model/lifecycle/
campaign_performance.service.publish_meta files independently. This consumer lane
must not edit those producer-owned files or introduce newmigrations.

Own new `app/campaign_performance/presence_report.py`, necessary planning evidence/
composer/retained-source code and focusedtests. Define `CampaignPerformanceV3` with
schema `inlet.owned-campaign-performance.v3` and
`read_current_with_presence(db, workspace_id, actor, account_id, campaign_id,
expected_completion_id, authorize)` matching existing read_current parameters.
ReturnV3 only from actual valid sidecar graph; genuinely absent sidecar returns
unchangedV1/V2. Corrupt/present-but-incomplete graph is controlledunavailable, never
fallback. Legacy read_current and existing publicroutes remain unchanged.

The trusted constructor reuses actualowned legacyread, actualcompletion/account/
campaign mapping and sameSession read_presence completegraphvalidation. Bind exact
header/legacycompletion/manifest/source/generation/privacy/window/currency/event and
campaignnativeidentity. Preserve original-session callback/finalauthority and noIO/
commit underdatabase reads. Avoid O(campaigns*facts) repeatedcompletegraph reads;
any cache is explicit one-operation/transaction-scoped, never auth/session-global.

V3 carries exact legacy facts separately from typed presence metadata and bounded
campaign-specific presence/summary. Choose/document concrete newDTO fields without
changing V1/V2 serialization. Typedvalidation revalidates nestedunsafecopies and
recomputes summary flags from presentfacts; a client-provided aggregate/zero flag is
never accepted. Whole headerfactdigest is validated by actualSQLreader, not claimed
proven by a campaign-only subset. A complete legacyrowcount alone never proves
selected metric presence. Keep per-document/collection byte/count bounds and report
capacity failures rather than truncating facts into falsecompleteness.

Use the reviewed summarize_presence semantics: returnedrowpresence vs absentcalendar
days; empty/missing/partial/generic data never complete-windowselectedzero. Count and
value independent, exactDecimal/integer arithmetic, explicit selected event required.
Attribution remainsunknown, no crossplatform comparison/causalclaim. V3 may report a
positive observedpartialsum with explicit scope; no fabricated completeCPA/ROAS.

Planner: add V3 as a new PerformanceEvidence document variant, preserve olddocument
roundtrips/digests exactly (no newdefaultfields on legacy models/PlanVersion). New
productionpolicy/generator constants become `inlet.descriptive-review.v2` and
`inlet.descriptive-planning.v2`; old tickets/readers/persisted versions remainlegacy.
Only newpolicy uses V3 reader; policy/schema mismatch fails before persistence.
Update actual evidencecollection AND final reporting/gap rechecks together; actual
currentpresence absence orgraphmutation duringgeneration must prevent stale save.
No mocked composer, finalsource proof or clientprovidedreport shortcut.

New policy retains one local reporting witness per account with SAMEevidencekey
`local:reporting:{account_id}` but kind `local_reporting_v2`. Its newdomain digest
binds existing completelegacyreportingstate plus actualcanonical presenceheader/
completefacts OR explicitabsence. No newdefaultcolumns or oldv1digest changes.
Currentcapture/recheck chooses witness version from storedpolicy, preserving oldv1
historicalgraphs. Newpolicy absence is pinned too. Exact dependency count/key checks
remain, noextra/missing rows accepted; read remainsDB-only for viewers. Missing,
corrupt, changed/deleted sidecar or changedcurrentpointer invalidates newadvice.

Composer: 100click/10selected/$100 cannot produce no-conversion advice. A truly
present0 for every requested campaign/day may produce a specificlocatable tracking/
landing-page investigation, labeled observedselectedevent/window and unknown
attribution. Missing/partial0 remains investigationforunavailableevidence, never a
whole-windowzero. Noforcedpause/budgettransfer, forecasting orspendingauthority.
Existing positivelegacybehavior and correctlegacyzero uncertainty preserved.

Qualification: actualownedSQL/store_presence→newreader→actualcustomerplanservice/API
positive/zero/missing/partial cases, no client-createdpassingbundle. TwoDB legacy
roundtrip/golden/sourceabsence+corruptgraph/change races/foreignscope/revocation/
viewerDB-only/oldversionhistory checks. Before0090merge these prove consumer path
only. Root will add actualMetaimport→planintegration after bothlanes reviewed; no
fullQ01/Q02/Q09 or live claim from sidecarfixtures. Q01Google selected-eventproducer
and Q09TikTok explicitselected/window producer remain unresolved protocol packages.
