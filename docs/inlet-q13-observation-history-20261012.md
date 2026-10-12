# Q13 Observation History Display Checkpoint

The history renderer now accepts the reserved field-observation variant separately
from customer decisions, reports and retractions. It renders matching/conflicting/
unavailable comparisons, typed values, evidence intervals/provenance and limitations
without inventing actor, implementation time, supersession or causal effect. Values
and URLs remain text only. Entire mixed pages are validated before display; malformed
or foreign data clears the view. Historical evidence is checked against event time,
not today's clock, with strict calendar validation and microsecond ordering.

The browser cannot authenticate providers, recompute normalized-facts digests, prove
original-action binding or establish current ownership. Those remain server duties.
Legacy missing-value comparisons may retain evidence but remain unavailable. Current
actions still cannot yield a genuine multi-field partial comparison. No writer,
producer, API, event schema or default composition behavior changed; Q13 remains
incomplete. See the [display boundary](design/q13-observation-history-view-20261012.md).

## Exact Verification

Packet `/workspace/inlet-evidence/20261012/q13-renderer02`, manifest SHA-256
`9cd6c6fbbfe4c6e6a7039fdbe7594e7e032ccbdb8f1c8467ef675f244951ecdc`.
Whole Ruff, configured mypy (1,560 files), exact collection and diff checks passed.
Two selected runtime tests passed without skips: actual Chromium document/comparison/
mixed-history DOM and application asset-route compatibility. Runner process durations
were 5.262855s and 5.174330s; XML testcase durations were 1.443s and 0.593s respectively.
Source integrity verified; no interruption, escalation or surviving process members.

The browser fixture uses comparator-produced synthetic matches/conflicts/missing
values alongside separate customer reports/retraction, plus URL/country values and
adversarial mutations. It covers strict microsecond/offset/calendar chronology,
closed nested shapes/window bounds, cross-scope/account/source/union/authority/status
refusals, sequence/cursor guards, unavailable reasons and safe literal rendering.
This is a local display fixture, not authenticated observation API/database or live
provider verification. Existing report/document/comparison assertions remain present.

Attempt01 passed Ruff then stopped at mypy on a fixture variable-name collision.
Collection, diff and both runtime nodes were unrun. Its logs/original exit/disposition
remain preserved. Renamed the synthetic report tuple; application bytes did not
change for attempt02. Results are not combined across attempts.

Local branch `codex/inlet-w1-followup`; no push/PR/deployment/provider/spending action.
V6 remains default-off, explicitly selectable and unqualified; incident
INLET-REL-20261012-01 remains open. Next independent planning package is Q10's explicit
constraint interpretation contract, preserving existing policy behavior. Full Q13
still requires qualified field semantics, observation admission/writer, retained
evidence/erasure and API/database acceptance joins.
