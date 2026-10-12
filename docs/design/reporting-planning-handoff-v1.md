# Reporting Capture Handoff v1

Local package after c4224ce; Q01/Q02 customer workflow join. No new API, schema,
provider calls, default-policy change, retention change or publication authority.

## Shared Interface

Reporting emits only `/app/planning#inlet-capture-v1=<workspace>:<account>:<capture>`.
Workspace/account are canonical positive safe decimal integers; capture is exactly
32 lowercase hex characters. One exact fragment, at most 128 characters; duplicate,
extra, encoded and malformed values are rejected. No tokens, labels, dates or facts.
Planning consumes and removes the fragment immediately using replaceState. It is an
untrusted in-memory navigation hint, never evidence, permission or currentness.

The initial cookie state binds the hint. Successful session/workspace reads must
identify its workspace with owner membership. The customer must choose that exact
workspace and prepare a new plan. Any other workspace, session refresh/replacement,
saved-plan selection, cancellation or edit revokes the hint. Capability and current
account reads must support selected reporting and the hinted Google account.
Application requires a new-plan editor, an explicitly checked matching account,
a blank capture field and an explicit Apply Capture click with fresh session and
capability checks. No automatic workspace/account/goal/period selection, overwrite,
save or generation. Display account and exact capture as literal text. A successful
application consumes the hint. Existing server input validation remains authoritative
for expired, deleted, foreign or otherwise stale captures.

## Acceptance

- Actual TLS Reporting capture completion navigates to Planning; fragment is removed;
  no account/goal/period/capture/save is automatically selected.
- Explicit apply preserves other customer inputs and creates the exact selected
  capture input through real APIs; generate/read/export retains selected 10 count,
  100 clicks and no false zero-conversion guidance. SQLite and PostgreSQL.
- Malformed/duplicate/foreign hints, unsupported capability, unchecked account,
  existing field/edit, stale handles and session/workspace change fail closed.
- Existing manual Capture ID entry and default V3 remain available/unchanged.
- No live providers, advertising execution or spending; fixture IO only.

## Q01–Q16 Reconciliation At c4224ce

All cases retain pending human quality judgments; this table records mechanical
coverage and gaps, not aggregate qualification or live verification.

| Case | Integrated evidence / remaining gap |
| --- | --- |
| Q01 | Positive Google selected count 10 / 100 clicks tested; manual capture-ID join selected here. |
| Q02 | Explicit zero differs from missing; same customer handoff gap. |
| Q03 | Meta-only actual catalog/image creative tested; selected attribution and native-budget qualification missing. |
| Q04 | TikTok-only storyboard without owned video tested; attribution/native-budget qualification missing. |
| Q05 | Independent three-platform allocations/creative cap tested; no cross-platform unique conversions claimed. |
| Q06 | Shared Google owner/affected-set investigation and partial recovery tested; daily-setting to period-ceiling recommendation unqualified. |
| Q07 | Over-ceiling, negative/currency and confirmed goal revision guards tested; aggression cannot raise ceiling. |
| Q08 | Zero-budget owned empty catalog and creative preparation tested; no paid allocation/forecast. |
| Q09 | Safe Google partial/social unsupported baseline; historical matrix 2 pass/1 fail/1 unrun and separate PG probe preserved. Social producer/attribution comparability missing. |
| Q10 | Typed exclusions/fixed budget/one image/product constraints tested; arbitrary freeform constraints conservatively defer creative. |
| Q11 | Corrected selected count retains V1 and V2 lineage; fresh-consent erasure tested. Preserved-history reconnect awaits retention decision. |
| Q12 | Integrated actual V6 edit/CAS/replay/second generation/obsolete decisions: SQLite sequential and PostgreSQL concurrent qualified. |
| Q13 | Integrated report/retraction across V1/V2 and historical replay/export qualified both databases. Independent provider field-observation producer missing. |
| Q14 | Three-platform disappearance/reselection and duplicate Google-owner labels tested; unknown parent topology remains explicit gap. |
| Q15 | Session/ownership/post-IO/deadline and literal-text JSON export tested. c4224ce adds four Session/Connection proof-scope cases; no CSV claim. |
| Q16 | Dated sales progress 0→25→20, chronology and erasure/archive tested; human quality and retention decisions separate. |

R01–R03 original incidents remain incompletely explained. Successor passing cohorts
do not retrospectively explain them. Artifact-sharing and retention owner decisions
remain pending and outside this package.
