# Customer Budget Alternatives Editor — 2026-10-08

Local branch `codex/inlet-planning-scenario-editor` from frozen interface567cbdf.
Uses unchanged ScenarioIntent server DTOs and exact retained target selectors.
No advertising writes or native-budget recommendations.

Customers explicitly add up to8 named alternatives with up to100 target allocations
each and a reserve. Every alternative independently reconciles to the confirmed
ceiling using the existing shared exact decimal→BigInt micros parser. Choices are
copied, bounded, unique and tied to original catalog expiry/revocable handles.
Root checks fixed amounts remain unchanged in each alternative and excludes
prohibited targets. Scope/session/expiry clearing also clears alternatives.
Existing scenario revisions require fresh observation, rebuilding and explicit
replacement confirmation. Comparison-window edits remain refused.

Actual ChromiumDOM covers independent sums,1micro precision, rejected exponent/
overceiling/duplicate input,100/8 bounds, unchanged keys after deletion, copied
selectors, revocation/expiry/literal labels/no component IO. Actual localHTTPS
Google scenario journey onSQLite/PostgreSQL saves two alternatives, rejects fixed
allocation mismatch before request, generates, explicitly rebuilds a successor,
and verifies the original immutable document. Three-platform scenarioAPI coverage
is a separate package; this browser journey is Google only. Existing all3 target
and account-level browser journeys remain in the same focused cohort.

Initial component2passed. Integrated focused cohort12passed (10actualHTTPS +2DOM).
A final scenario-only rerun adds explicit excluded-target rejection before request.
Exact times/results and frozen reviewed head follow after terminal results.
No whole-suite, human-expert, live-provider or launch-readiness result inferred.
No claim of complete Q05/Q07, zero-alternative-removal browser coverage, comparative
window analysis or optimized allocations. Evidence under
`/workspace/inlet-evidence/20261008/planning-scenario-{component,browser,browser-negative}.{log,xml}`.

Final results: component2passed4.718s; integrated12passed90.305s; added excluded-target
negative scenario-only2passed14.599s,0skips. WholeRuff/mypy1066, Node syntax
and diffchecks pass. Frozenhead awaiting independent review.
