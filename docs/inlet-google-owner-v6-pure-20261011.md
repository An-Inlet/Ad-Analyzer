# Genuine owner-review pure composition — slice 2

Base `3007e90`, implementing only slice 2 of the reviewed genuine V6 design.
No runtime capability registry, service, repository, current/history dispatch,
customer route, browser or default-policy activation changed. V1–V5 still reject
nonnull owner hypotheses, including explicit empty tuples, in their old entrypoints.

## Pure boundary

`OwnerReviewPlanComposer.compose` accepts the original GenerationTicket,
CreativePairedEvidenceV1, canonical V6 policy, and aware generation time. It does
not retag V5 evidence or strip inputs. The shared private composition body validates
canonical policy/ticket/evidence and exact creative presence independently. Old
SelectedPlanComposer compose/_compose and CreativePlanComposer wrappers still
reject owner-review composition, including a V6 ticket with absent owner inputs.

PlanVersion adds omitted-None `google_budget_owner_review` and
`google_budget_input_catalogs`. Genuine V6 requires both, explicit owner input and
all existing selected/traffic/creative proofs. Other pairs cannot adopt them. The
complete ordered input-linked catalogs cover every fixed/scenario allocation and
uniquely resolved exclusion, not only owner accounts. Full AccountRef and exact
TargetRef/evidence/source joins are checked. Extra unrelated account catalogs are
not retained; full selected proof sources still cover unselected owned accounts.
Original receipt authenticity remains a later SQL integration obligation.

Owner investigations follow ordinary diagnostics and precede creative production.
There is one investigation per full account/owner, with no NativeBudget, proposed
field or application authority. Daily hypotheses and observed amounts do not prove
period ceilings, valid provider edits, pause or zero spend. Existing global creative
capacity and full 1MiB document size remain unchanged. V6 serialization revalidates
complete document joins; its size check serializes validated child values without
recursing through the root checked serializer. Old valid serialization bytes remain
unchanged. Pure V6 recognition is not service capability registration.

## Qualification and preserved failures

Evidence: `/workspace/inlet-evidence/20261011/google-owner-v6-pure/qualification.json`.
All cases are synthetic pure packets; no database/provider/browser execution.

- `pure01`: 4 Google/zero/empty/no-link positives passed; the first Meta case
  failed because the new fixture copied Google's 3-minute expiry into a Meta
  5-minute catalog reference. The fixture now obtains the complete envelope from
  its actual projected catalog. Both fixtures had workspace 1; workspace mismatch
  was a disproved inspection hypothesis, not the defect.
- `pure02`: excluded those 4 passed cases. First Meta case exposed the real shared
  raw-scanner defect: required timestamp recursion rejected optional
  MetaSettingsV1.starts_at=None. Preserved failure; no fixture restamping.
- The reviewed narrow repair recognizes only the exact complete MetaSettingsV1
  field shape and discriminator. Its starts_at/ends_at may be None; nonnull values
  remain strict aware timestamps in both scanners. Required catalog/report clocks
  and spoofed or partial settings shapes remain strict. No global None exception.
- `pure03`: 15 strict schedule tests and 4 mixed Meta/TikTok scenario/exclusion
  cases passed. The fixed-allocation fixture then failed because its scenario
  omitted that fixed target. The corrected fixture preserves the same zero fixed
  allocation in the scenario, as the unchanged input contract requires.
- `pure04`: all remaining 34 new cases passed, with the earlier 8 document cases
  excluded. Thus 57 distinct new cases passed across these attempts. Google4 ran
  before the Meta-only scanner repair; subsequent changes do not alter their
  non-Meta path. This is disjoint qualification, not a single clean run claim.
- `compat05`: 177 passed in 15.85s. This includes 4 additional new cases (aware
  schedule, retained mixed-Meta scenario/exclusion, and full old-output goldens),
  plus unchanged V4 paired composition, V5 composition, Q08 composition/document,
  active input/owner checks, all old generation refusals and nested byte goldens.
  Exact node IDs and per-file counts are in the manifest/XML. No broad retry.

Full V4, V5 Meta and V5 TikTok JSON/digest/descriptor goldens were captured from
immutable predecessor `b7f71639afa8a04ce8dd7f864e98539396b75cdf`, then compared on
this branch. Existing nested Python/JSON golden tests also passed. The byte-limit
regression checks the exact serialized boundary with an injected smaller bound;
production MAX_DOCUMENT_BYTES stays 1,048,576. It is not a maximal-size performance
benchmark or a five-second authority-window qualification.

The first configured mypy run reported five typing errors: raw parser values were
annotated as strings instead of objects and a test referenced an implicit constant
reexport. Annotation-only helper widening and a defining-module constant import
preserve runtime operations; no repeated pytest was needed. Initial logs remain.
Final whole Ruff and configured no-path mypy passed (1467 source files), as did
fresh-process document/composer/ports imports and diff checks.

Total distinct successful cases: 61 new + 173 unchanged = 234. Three initial test
failures and initial mypy findings remain explicitly unresolved only as historical
attempt records; their identified causes are fixed and covered. Earlier unrelated
R01/R02 generation conflicts are not diagnosed or resolved by this pure package.
No performance, economic qualification, SQL authority, full Q06 quality, expert,
customer-browser or live acceptance claim is made.
