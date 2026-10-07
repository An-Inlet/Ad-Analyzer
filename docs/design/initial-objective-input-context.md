# Private Initial Objective Input Context

Frozen before implementation, 2026-10-07. Source-only successor to144786f.

`calibration._read_current_objective(...) -> _CurrentObjectiveInputs` performs every
existing `current_objective` check and returns:

- `report: CampaignPerformanceV1 | CampaignPerformanceV2`: the exact owned current
  report validated with the original-session authority callback and source locks.
- `goal: Goal`: the freshly owned, revision-checked ORM goal row locked by this same
  transaction; this is not a transferable permission or serialized value.
- `goal_definition_digest: str`: the existing domain-separated fingerprint of the
  exact stored confirmed goal definition, without reconstructing normalized bytes.

Public `current_objective(...) -> None` invokes the private reader and discards the
context. `_CalibrationInputs` adds `current_objective: _CurrentObjectiveInputs`;
its existing full dependency/document reconstruction and final expiry checks remain.

Only `preview.inputs`, immediately consuming that private calibration result within
one DB-only transaction, reuses the current report and goal. It compares the selected
observation's completion ID to the validated current report, checks the goal revision
again, and RETAINS `goals.assessment` with newly sampled effective time. Assessment
is time-dependent (source freshness and rolling retention); an earlier successful
assessment cannot replace this later guard. No freshness formula is copied or cached.
The consumer uses the original goal-definition digest, then retains final original
session authorization and freshly sampled report/observation expiry.

The full second `inputs` pass after preview mandate validation stays unchanged.
The context is never accepted as an input to an authority API, stored on a session,
passed through external IO, or retained across commit/rollback, requests or workers.
This package owns calibration.py, preview.py, tests and documentation only.

Regression boundaries: mismatched selected completion; native source/current report
or goal revision changes at the post-mandate boundary; historical-input erasure;
original-session revocation; elapsed preview expiry; late goal assessment changing
from confirmed to unavailable. Public standalone readers continue to revalidate.
Measure actual PostgreSQL SQL counts and elapsed after implementation; query reduction
alone does not establish latency or ordinary30-second operation qualification.
