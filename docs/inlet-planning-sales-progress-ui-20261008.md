# Plan-Bound Sales Progress UI — 2026-10-08

Branch: `codex/inlet-planning-progress-ui`, based on frozen interface `133993d`.

Implemented a display-only `plan-progress.mjs` renderer and an explicit **Read Sales Progress** control in the existing planning page. The renderer binds the response to the displayed immutable document, version, digest and complete confirmed goal, independently of editable input revisions. It keeps the two backend goal-digest domains distinct. Available amounts use only the server-computed canonical signed decimal string and BigInt, including values beyond JavaScript's safe integer range. The original target, closed-day prefix, coverage extent, source watermark and as-of time remain visible. Missing/changed-goal results never invent zero or substitute a new goal.

The controller uses the existing no-store, original-cookie, epoch and trailing-session checks. It captures the displayed document before IO and checks that the exact document, plan, workspace, version and digest remain displayed immediately before rendering. Clearing a document, navigation, session invalidation or errors also clears sales. Historical/expired documents can request this independent observation without altering plan eligibility or manual history.

Validation at this checkpoint:

- `pytest -q tests/test_planning_progress_view.py`: 1 actual Chromium DOM test passed. Covers exact unsafe positive and negative amounts, zero, sub-unit negative values, malformed/noncanonical/beyond-int64 strings, safe-number disagreement, foreign scope/version/digest/goal, authority contradictions, changed-goal unavailable, matched unavailable/not-started, literal text and clear-on-rejection. Pure renderer performs no IO.
- `ruff check .`: passed.
- Repository CI command `mypy`: passed, 1086 source files. Earlier `mypy app` also passed (613 files); exploratory `mypy .` failed duplicate module discovery for the existing restore script, so the configured CI invocation was used.
- JavaScript syntax checks for renderer/controller and `git diff --check`: passed.

This checkpoint does **not** qualify the actual progress API or authenticated controller/browser journey. Backend implementation is a separate lane. After reviewed integration, exercise actual generated-plan sales reads, a real Shopify ledger correction followed by an explicit reread, immutable artifact/manual-history separation, historical/changed-goal responses, and original-session/late-response rejection. No schema, backend, provider, or advertising execution code changed. No live requests, deployment or Full run.
