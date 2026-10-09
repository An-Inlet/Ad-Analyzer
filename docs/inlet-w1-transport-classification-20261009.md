# W1 Retained Transport Classification

Base `d85db66`; tests-only package. Eight pure MockHTTP test functions in four
mixed modules were missing explicit retained-engine classification. Their imported
helper modules already carry that classification, but pytest markers do not
propagate through Python imports. The frozen planning-only run therefore denied
these 29 cases at the intentional advertising boundary before testing the engine.

Only per-function `retained_execution` and `usefixtures("retained_execution_engine")`
decorators are added. Existing test-scoped fixture restores capabilities after each
case and rejects mixing with `planning_boundary`. No module-wide marker, global
seed change, application change, provider call or advertising authority is added.
AST comparison proved function bodies, parameters, existing decorators and every
other statement unchanged.

Reviewed functions:
- Google completion evidence: original capture bytes (2), nonexact success (6).
- Google execution completion: ambiguous wire capture (4).
- Google total publication: exact total-budget HTTP readback (6).
- TikTok linked publication: disabled linked graph (1), readback conflicts (6),
  unknown/expired reconciliation (1), malformed sanitized response (3).

All use synthetic contexts and `httpx.MockTransport`; assertions retain exact
payload/readback, ambiguity, expiry, no replay/retry and redaction contracts.
Other current durable/customer cases in these mixed modules remain unclassified
and unrepaired by this package. The TikTok real-transport rejection is unchanged.

Qualification: eight explicit function selectors plus the entire unchanged
`test_planning_provider_transport_boundary.py` and
`test_planning_execution_boundary.py` in the same pytest process:
**115 passed, zero failures/errors/skips, 3.637s JUnit**. These comprise 29 targeted
retained cases and 86 current boundary cases; the latter prove default denial
before I/O or authority changes after fixture teardown. Exact command, selectors,
log, XML and exit0 are in
`/workspace/inlet-evidence/20261009/w1-transport-classification/`.

Whole `ruff check .`, bare `mypy` (1127 source files) and `git diff --check`
passed. An initial invocation used an absent tool path and exited127; the corrected
venv invocation above completed successfully. Independent review precedes integration.
Frozen W1 remains failed; these focused results do not qualify Full or release.
