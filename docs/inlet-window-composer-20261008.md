# Pure Requested-Window Composer — 2026-10-08

Base `4fc2b94`; branch `codex/inlet-window-composer`.
Interface: `docs/design/planning-window-runtime-packages-v1.md`, package A.

New `WindowPlanComposer.compose(ticket, evidence, policy, generated_at)` accepts the
genuine server ticket, validates canonical v3 configuration and the complete new
bundle with `assert_ticket`, and derives inputs/actor/version/parent directly from
that ticket. No ticket or old bundle is fabricated. It is not wired into production;
the existing composer still rejects v3 and the service default remains unchanged.

Primary action assessment uses only requested primary summaries. Comparison appears
as separately labeled observations or exact known gap; larger original report totals
never substitute for requested values. Text retains requested dates, source time zone,
currency, selected event, metric coverage, present/calendar-day counts and original
queried dates. Integer/Decimal formatting uses fixed Context(prec=50), with no rates,
percentages, forecasts, cross-platform aggregation or causal/spending authority.

All successful references remain in the plan, including comparison and excluded
campaign evidence. Lossless deterministic gap grouping uses account + exact UTC
window + reason, listing every native ID and splitting only at whole-ID boundaries.
Each fragment repeats its full context; inverse identities must equal the original
set. Catalog gaps are explicitly collection-time outcomes, not current provider
absence. Their original non-reporting explanation is also retained.

The new policy keeps independently versioned manual/scenario/creative construction,
reusing only existing narrow `targets`, `location`, platform names and error type.
It preserves fixed allocations, independent customer hypotheses, ceiling reconciliation,
exclusions, constraints, creative capacity and product-fact/hypothesis distinction.
Old composer bodies and models are untouched. This code duplication deliberately
avoids an unreviewed legacy refactor or transforming new evidence into an old bundle.

Full reference count, grouped limitations, action count, field text and final existing
PlanVersion validation enforce capacity. Failure returns no partial PlanVersion;
this pure package has no persistence to modify. A valid400-slot bundle may exceed
public reference capacity after native/customer/policy/commerce references are added;
that is explicitly refused, not truncated.

## Qualification

Final focused compatibility cohort: **110 passed in 10.53s**. Whole Ruff passed;
bare configured mypy passed **1,099 source files**; diff check passed.

New tests include genuine ticket/parent derivation and invalid/expired inputs;
positive/selected-zero/missing; primary0 versus comparison10; requested observations
from a56day original with much larger totals; successful-primary/comparison-gap;
full evidence retention; fixed/scenario/constraint/exclusion/creative/zero-budget
behavior; hostile Decimal context; collection-time gap wording; deterministic whole-ID
splitting; distinct account groups with identical native IDs; actual40campaign Google
and TikTok comparison plans; actual80campaign two-account plan; actual90long-ID
campaign plan; genuine101action rejection; field2000/+1 and total limitation overflow;
and valid400successful-window evidence plus context/catalog reference refusal.

The400-reference test builds a consistent synthetic whole400fact source header and
campaign subsets; it proves pure contract/capacity behavior, not database/source
ownership. Representative Google/TikTok cases use actual native catalog projection
contracts and explicit absence gaps; they are not actual owned API or provider tests.

```text
/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_window_composer.py tests/test_planning_composer.py tests/test_window_evidence_contract.py tests/test_requested_window_projection.py --junitxml=/workspace/inlet-evidence/20261008/window-composer/pure.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Raw evidence: `/workspace/inlet-evidence/20261008/window-composer/pure.log` and
`pure.xml`. The cohort includes old composer behavior and canonical policy/refusal
assertions; no legacy fixtures/golden outputs were modified. No DB/API, default
activation, provider IO, native write, Full, live or recommendation-quality claim.
Next dependency is reviewed owned adapter/final rechecker, followed by separately
frozen service dispatch and actual import-to-customer-API acceptance.
