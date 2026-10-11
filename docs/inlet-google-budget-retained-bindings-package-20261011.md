# Retained Google Budget Input Binding

Adds `validate_retained_google_daily_budget_input_bindings` in the existing
standalone binding module. Active admission still requires the exact full input
source set. Both wrappers use the same catalog chronology and owner/scenario/child
kernel, without changing input accounts or manufacturing missing source fences.

Historical validation requires exactly the linked catalog/source account subset,
full retained AccountRefs, unanimous original privacy, and original admission-time
validity. It has no current clock, session or TTL lookup. Empty/no-links history
requires no ordinary selected targets and returns no owner evidence or invented
epoch. SQL link authentication and original opaque selection commitment checking
remain mandatory in the separately implemented caller. No API/input fields or
consumer activation are included here.

## Local Evidence

Evidence remains at `/workspace/inlet-evidence/20261011/google-budget-input-bindings/`.
Source reviewed before test execution; the sole pure-test slot was explicitly
released by the parent. No database/browser/provider calls.

- `history-01`: 11 passed, 1 fixture failure. The second-account projected fixture
  added nonexistent composite `account_id`; removed that extra field, retaining
  account identity on actual native/metadata/reference nodes. Failure preserved.
- `history-02`: 51 passed, zero failures/errors/skips, 1.325 seconds: 12 historical
  cases plus all 39 active admission regressions. Includes genuinely distinct
  linked accounts with differing retained epochs, original historical-time
  positive, no-links empty/no-target boundary, copied primitives and changed
  resolved binding refusal.
- Whole Ruff passed; configured no-path mypy passed 1440 source files.
- `git diff --check` passed. No broad baseline rerun.

No claim of current source authorization, daily-to-period spending qualification,
provider mutation authority or live verification is made.

## Root Integration

Author `a60f5dc` independently CLOSED and integrated as `7e8b00f`. Root whole
Ruff and configured no-path mypy passed over1,448 files; diff check passed.
No repeated pytest at integration. This includes active original binding `ed594ad`
and scalar commitment `afde942`; their separate results remain in their ledgers.
Atomic input/read/history consumers are source work in an isolated lane and are
not activated by this package. Generation of owner hypotheses remains unavailable.
