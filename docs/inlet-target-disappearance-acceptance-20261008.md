# Target Disappearance And Explicit Reselection Acceptance

Base: `390851c`. Branch: `codex/inlet-target-disappearance-acceptance`.
Scope: one new offline customer API test module; no production, portal, controller,
shared fixture, capability, schema, or policy changes.

## Verified Behavior

`tests/test_planning_target_disappearance.py` runs the same scenario for Google,
Meta, and TikTok on SQLite and disposable PostgreSQL. Existing owned source and
goal fixtures supply setup only. MockHTTP returns original inventory, then empty
campaign/child inventory, then a replacement campaign with a different native ID
and the exact original display name. Child parent IDs follow the replacement.
Real native collectors, V2 metadata binding, receipt persistence, customer routes,
input resolution, generation/composition, current/history reads, and export run.
There is no constructed evidence bundle or patched authority/composer/receipt.

The customer saves the original exact selector. A fresh empty catalog observes
its disappearance; this does not retroactively invalidate the unexpired original
as-of receipt. Generation still uses that original receipt without native rereads
and preserves its native ID and selector. A fresh same-name replacement has new
canonical and snapshot selection keys. Current saved output remains unchanged.
Both cross-pairings of old/new canonical and selection keys return HTTP 409 and
leave plan/input/version/receipt-link counts unchanged. An explicit customer edit
selecting the new exact handle creates revision/version two with the new native
ID. Version one and its export digest remain unchanged. The graph contains one
plan, two inputs, two versions, two receipt links, and zero execution attempts.

## Checks And Evidence

Final command (approved disposable PostgreSQL environment supplied):

```text
pytest -o addopts='' -q tests/test_planning_target_disappearance.py \
  --junitxml=/workspace/inlet-evidence/20261008/target-disappearance/results.xml
ruff check .
mypy
git diff --check
```

Final pytest: **6 passed, 0 skipped, 31.48 seconds**. Whole Ruff passed; mypy passed
for 1,086 source files; diff whitespace check passed. A preceding six-case run
passed before strengthening explicit native-ID/current-document/graph assertions;
these overlapping runs are not additive coverage. Initial Ruff identified three
long lines, then formatting corrected them before final qualification.

Raw final log and JUnit: `/workspace/inlet-evidence/20261008/target-disappearance/pytest.log`
and `/workspace/inlet-evidence/20261008/target-disappearance/results.xml`.

## Remaining Limits

This is partial Q14 evidence, not closure of the frozen case. It does not test
unknown-parent topology, simultaneous duplicate display names, unsupported manual
verification, or the customer browser disappearance/reselection interaction. The
existing actual HTTPS helper does not expose dynamic native inventory controls;
this package uses actual customer APIs with offline MockHTTP, not a browser claim.
A retained receipt is original timestamped evidence, never live-provider truth.
No live providers, ad writes, aggregate suite, remote actions, or deployment ran.
