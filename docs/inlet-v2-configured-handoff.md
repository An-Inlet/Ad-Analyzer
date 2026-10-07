# Configured V2 Preview Execution Handoff

The owned preview API now offers separately consented optimization mandates and prepares an ordinary exact optimization review. The customer supplies only the expected preview digest and execution mandate ID/revision. Options are bounded to 50, with explicit truncation, and do not claim financial eligibility.

The original planning consent and the separate marked 0080 execution consent must retain the same ledger, goal, period, currency, account set and overall limit. Execution caps cannot enlarge the planning caps. Fresh configured native inventory, independent qualification and financial exposure readers remain mandatory. A native observation is never converted into qualified state.

Preparation uses the actual request-local optimization assembly. After external reads, the transactional writer rereads the original session, preview and both policies, then atomically stores the protected review origin, owned link and canonical 0081 proof. Proof expiry is bounded by preview, qualification, exposure and original session expiry. The preview carries its native/calibration expiry bound. Explicit configuration coherence prevents a review being prepared with a different planning configuration from its later approval guard.

Ordinary approval and dispatch use strict preview-version guards. Missing V2 proof cannot fall back to V1 or manual authority. Lost-response retries return the original proof/review; erasure cannot recreate authority. Historical reconciliation still uses the original attempt and retained reservation after proof erasure and never replays an uncertain mutation.

## Offline Acceptance Fixture

`tests.v2_execution_fixture.ready(engine, configuration, path, monkeypatch, replicas)` returns `(alice, planning_root, execution_base, target_query, preview_json, server, controls, planning_mandate_json)`. It uses the ordinary configured dependencies, actual imported/calibrated planning path, API-created planning consent and V2 preview. Consumers create the separate execution consent through the ordinary API. Financial evidence is explicitly a server contract scenario and HTTP uses the low-level MockTransport seam; no runtime getter override or seeded execution review, attempt, hold or receipt is used.

The fixture shares actual mocked native state across the read-only planning collector and qualified execution adapter. Authentication form fields are excluded from mock persisted campaign settings. `controls['callback']` can inject an independent database change at actual provider IO.

## Checked At Backend Freeze

- Ten SQLite/PostgreSQL cases passed in 99.30s: exact review/replay/approval/mutation/readback, uncertain outcome without replay, proof/preview erasure, and erasure after actual committed claim.
- Eight cases passed in 66.02s: verified flow again plus changed overall cap, changed native budget and original-session revocation during fresh provider reads. These overlap the prior ten by two cases; 16 distinct parametrized cases were checked.
- Whole Ruff and mypy (827 files) passed. No Full, remote or live-provider actions.

This is offline configured acceptance, not live qualification. Actual browser composition and broader compatibility/drift coverage are subsequent checks, not claimed by this checkpoint.
