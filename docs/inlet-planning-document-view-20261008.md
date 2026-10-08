# Customer Plan Document Display Foundation

Display-only `plan-document.mjs` renders an immutable PlanVersion after matching the
selected workspace/plan and planning-only authority. Actions, exact provider references,
manual steps, rationale, limitations, independent scenarios, briefs, customer constraints
and evidence windows/coverage remain separate. Expired or source-changed documents are
labeled historical; no accepted/applied/provider-verified flag is inferred. The module
contains no network, storage, publication or decision controls. It uses textContent for
all provider/customer text and clears prior display before a mismatched response.

This is not yet a customer page or authenticated journey. The future controller must
check original session and selection across each operation, clear on session/selection
change, schedule expiry invalidation using the returned expiresAt, and fetch freshness
from the server. DOM rendering alone cannot prove current source or authorization.

Verification: one real Chromium DOM test passed in 2.58s, covering literal malicious-
looking product text, no injected elements, quality/freshness labels, exact expiry,
source-change history, foreign workspace rejection and clearing. The first dump-DOM
harness timed out despite loading; replaced with explicit browser result callback and
owned process-group cleanup. Ruff, prescribed mypy (1,032 source files), node syntax
and diff checks passed. No live provider/API/customer-flow qualification claimed.

Independent review repair: goal section now displays the exact confirmed goal revision,
net-sales target/currency, target and baseline windows/time zones and deadline separately
from the freeform milestone. Browser regression renders a changed $12,000 confirmed
target and verifies it cannot be hidden behind unchanged milestone text. Final browser
check passed (1 case, 2.52s), Ruff/mypy/node/diff passed. An intervening environment
reconnection lost the prior tool process handle; that attempt has no terminal claim.
Final log/JUnit are `/workspace/inlet-evidence/20261008/planning-document-view.*`.

Integrated at `2506f9f` on `codex/inlet-planning-mvp`: 11 document-view/comparison
checks passed in 2.72s, whole Ruff/mypy (1,040 files) passed. Integrated log/JUnit:
`/workspace/inlet-evidence/20261008/planning-view-integrated.*`. Display-only limitation
and remaining controller requirements above still apply.
