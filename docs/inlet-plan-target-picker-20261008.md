# Planning Target Picker Component

Branch `codex/inlet-plan-target-picker`, isolated from frozen root `95a9ec1`.
Implements `docs/design/planning-target-picker-ui.md` in
`app/portal/static/plan-target-picker.mjs`; no controller, HTML, server, or provider changes.

The component reuses the native-target renderer's catalog/scope/coverage validation,
shows original read intervals and expiry, and treats names/IDs as literal text.
Include is the default. Exclusion and fixed allocation are mutually exclusive.
Fixed amounts are explicitly customer hypotheses in the confirmed goal currency,
not native settings or spending permission. Exact decimal parsing uses BigInt and
returns safe integer micros within the existing 10^15 contract bound. No floating
multiplication/rounding, forecasts, provider writes, network requests, or retries.

`expiresAt` is the original catalog ISO string (controller uses `Date.parse`).
`readIntent` checks actual current expiry and its revocable handle; returned selectors
are freshly copied and contain only account ID, canonical key, and selection key.
Clear, rerender, and invalid render revoke prior handles. Invalid render clears DOM.
Detached stale controls do not call the change callback.

Stable DOM hooks: `select[data-role="target-choice"]` with `include`, `exclude`,
`fixed`; `input[data-role="target-amount"]`; enclosing
`fieldset[data-target-key="<canonical entity key>"]`.

Validation on final component source:

- `/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_plan_target_picker.py`:
  **1 real Chromium DOM test passed in 3.43s**. Exercises Google/Meta/TikTok schema
  fixtures, literal injection strings, fresh selector copies, exact one-micro and
  six-decimal amounts, invalid/negative/exponent/overbound inputs, explicit zero,
  aggregate ceiling, synthetic 100/101 list limits, default-clock expiry,
  clear/rerender/invalid-response revocation, stale callbacks, currency/ceiling
  rejection, and zero component network calls. Synthetic expanded catalogs test
  component limits only, not provider acquisition qualification.
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: **1065 source files passed**.
- `node --check app/portal/static/plan-target-picker.mjs` and
  `node --check tests/javascript/plan_target_picker_dom.mjs`: passed.
- `git diff --check`: passed.

Root owns authenticated controller integration, original session/scope epochs,
receipt timers, explicit reselection, cross-account ceiling reconciliation, and
customer create/edit payloads. This component test is not authenticated journey,
live-environment, or full-suite qualification.
