# Current Reported Rule Source Six: Proposed Fixture Interface

Docs-only proposal on 91702b7 (reviewed current18 ca52cea integrated). No tests,
provider calls or implementation in this package. Original identities were read
from `/workspace/inlet-evidence/20261009/w1-failure-classification/failed-nodes.json`.
They establish six source cases and fourteen configured API failures, separately.
No new closure credit is claimed.

## First Package: Six Current Source Assertions

All three functions in `tests/test_reported_rule_source.py` remain current:

| Function | Both database cases | Preserved behavior |
| --- | --- | --- |
| test_actual_owned_reports_read_then_revocation_denies | 2 | Actual owned read, signed delta -250000, four completions, causal lift unavailable; unchanged request/post/held exposure counts; persisted original session revocation denies reread |
| test_final_authorization_wait_cannot_extend_report_lifetime | 2 | Original authorization callback runs twice; existing test advances clock beyond exact selection expiry after second check; current reader rejects with reported_rule_current_evidence_unavailable |
| test_final_rule_guard_rejects_changed_commerce_source | 2 | Genuine positive current read followed by original nonemitting decision and actual CommerceStore revision increment; current final guard rejects candidate source changed |

The shared source setup currently calls `ready_reported_rule`, whose old acquisition
origin executes an advertising operation under the current guard. The bodies are
read/authority tests, not retired execution contracts. No retained marker applies.

Reuse exactly the reviewed `tests/reported_rule_current_fixture.py` interfaces:

- Import `reported_rule_original: RetainedReportedOriginalIds` as a pytest fixture.
- Import file-backed/isolated `reported_original_fixture.customer_engine`, retaining
  the explicit `test_customer_identity.customer_engine as base_customer_engine`.
- Replace each setup call with `ready_current_reported_rule(db, configuration,
  tmp_path, monkeypatch, original=reported_rule_original, engine=customer_engine)`.
- Preserve every original statement after that call, parameter decorator and
  assertion. No new callback, clock mechanism, producer dispatch or shared helper
  change. The existing deliberate final-authorization delay is test behavior and
  remains exactly where it is; do not replace it with a different expiry test.

This source already validates the same owned genuine original receipt, account,
request and daily45m state before current MockHTTP GETs. Actual current report
acquisition and commerce publication produce the four observations; no ready
reports/runtime cross the pinned process. Its reviewed capture-timestamp adapter
stays unchanged. The original source expectation remains UNBOUND: all protected
provider tables/mandate actions and physical schema are identical at teardown.
The current tests' session revocation and commerce revision change are outside
that financial graph and must remain actual persisted changes, not simulated
exceptions. Existing statement-level and finalizer assertions both must pass.

## Proposed Bounded Qualification After Approval

1. One positive source/read/revocation function on SQLite and PostgreSQL.
2. Entire source module, six exact original identities, with raw log/XML.
3. Existing current18 dependencies and worker modules as bounded shared-source
   compatibility (19 cases including unchanged pure registry), plus86 default
   boundaries. Report these separately from six repaired frozen failures; do not
   sum overlapping positive probes or rerun historical batches.
4. AST proof of identical original post-setup bodies/assertions/decorators; whole
   Ruff, bare mypy using /tmp cache, and diff check. Preserve every failed attempt.

No production edits, new source helper or new historical manifest is proposed.
Stop and report genuine incompatibility rather than expand source permissions.

## Separate Investigation: Configured API Fourteen

`tests/test_configured_reported_rule_api.py` contains four functions, but only
three have original failed identities:

| Function | Failed identities | Actual source-read classification |
| --- | --- | --- |
| test_actual_configured_reported_candidate | 2 | Mixed: actual enqueue/tick/GET suggestion is a current read; final POST result review expects obsolete200 |
| test_actual_configured_reported_automatic_start | 10 (five changes × bothDB) | Original capabilities/Start/worker mutation and unknown/no-replay/session/capsule/source semantics depend on historical forward execution |
| test_configured_revoked_session_does_not_shadow_current_session | 2 | Original two successful Starts and subsequent worker original-session nonadoption require historical forward execution |
| test_configured_master_disable_constructs_no_native_or_policy_factory | 0 | Current disable/factory nonconstruction assertion; preserve untouched, not new failure credit |

Concrete current routing prevents simply marking this mixed module retained:
`customer_candidates.review` has deny_advertising_mutation plus final write guard;
`customer_session_automation.capabilities` returns unavailable, empty policies and
mandates; Start is guarded. `reported_automation.configured_session_automation`
yields None and its worker returns an empty dictionary before factory construction
under the current write boundary. A generic409 cannot replace these original
historical session/unknown/hold assertions.

The configured fixture itself goes beyond current18: configured_candidates_customer
creates a genuine consented mandate, original review/approval/run/advance; then
creates customer reported comparison through API, rolling import and four report
observations, registered candidate policy/manifest, automatic policies and original
customer login. Current18 provides source and actual read evidence, NOT a ready
configured customer runtime or equivalent API authentication/registry wiring.

Before any API implementation, freeze a separate split: preserve exact original
historical assertions at the literal PIN only after verifying functions exist there
and their node mapping; separately retain the candidate enqueue/tick/GET current
behavior with genuine owned source/configuration and current session, followed by
exact guarded review denial and zero new financial effects. Current capabilities,
Start denial and no factory/worker construction need explicit owned current API
counterparts. Successful current reads must precede adverse credit; empty runtime
or early generic denial is not equivalent candidate-read coverage. Original
revoked-session nonadoption remains historical proof and cannot be claimed from
current early prevention alone.

This document does not authorize an API producer, new manifest batch, or remove
any old assertion. Exact configured source/identity/registry fields, historical
node availability, retained/current per-function mappings, protected row deltas
and causal response details remain to be frozen in that next proposal. Implement
source6 first; API14 remains investigation, not an approved or qualified repair.
