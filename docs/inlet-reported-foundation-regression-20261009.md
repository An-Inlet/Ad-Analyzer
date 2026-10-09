# Current Reported Feedback Foundation Regression

Branch `codex/inlet-reported-foundation`, base `c7bd45d`. Implements the first16 interface approved at proposal `5aa0150`; no subsequent acquisition/runtime/browser package is included. Test-only changes; no production guards, collectors, policies, expiry limits or global fixture changes.

## Genuine Original, Current Consumers

The closed `reported_original_seed_driver.py` runs the exact source PIN `2155ff3e3ab00cd62057dd86cb49d45359d4f49f` in a separate interpreter. It calls untouched historical `ready(..., 'meta_ads', campaign=True)` and actual preparation/approval/run/claim/execute services for one MockHTTP Meta50m→45m reduction. The measured original server count is exactly1 and the receipt is verified-target-state. It reproduces the original source/cohort/session setup and stops before any reported job. The original fixture's now-issued60day session is unchanged (PIN `tests/reported_feedback_fixture.py` lines75–85); this is not a production lifetime or new extension.

Only bounded scalar IDs/count cross. The current `PreparedReportedRead` reloads and verifies owned user/session/account/campaign/source/mandate/run/attempt/receipt/reservation lineage, asserts no jobs/capsules/comparisons/slots, then constructs a current runtime and invokes actual current `request_comparison`. No old runtime, ORM object, mock server, numeric report or authority payload crosses. The two former server.posts assertions now check the actual historical measured count; no fictitious prior post is put into a current server.

The14 service and2 customer API cases retain current idempotency/progress, original session/source/event/environment drift, objective supersession/no fallback, unsupported policy, actual login/discovery/request/history/CSRF/session fences. Each of the five adapted functions is explicitly `planning_boundary`; no retained capability fixture is active. Existing unavailable API/shell tests still run unchanged. SQLite uses a file-backed current schema established before replica construction, preserving actual replica/producer shared state; original global identity fixture is untouched.

Before and finally after each current consumer, every persisted `provider_*` table plus `mandate_actions` is compared in primary-key order, including the original immutable effect and financial reservation. Exactly one original attempt/response/receipt/reservation exists; no new financial/effect row or mutation is allowed. Advertising write capability remains false. Current runtime has no native executor; its identity provider is the existing offline fixture. The original POST count is a measured historical counter, whereas the current no-new-effect assertion is persisted-graph evidence, not a fabricated transport counter.

Parent/child PostgreSQL paths validate the disposable URL, require loopback host/no URL query, exact owned UUID schema, and parent engine URL equality. The child checks every existing table except Alembic version is empty before producing. It does not create/drop/migrate/reset tables. Parent checks unchanged table set. Output is limited to4096bytes before JSON parsing and exact bounded scalar DTO validation. SQLite file and PostgreSQL UUID schemas are isolated; no aggregate database is touched.

## Evidence And Exact Commands

Evidence directory: `/workspace/inlet-evidence/20261009/reported-foundation/`. Logs/XML, producer source provenance/IDs/logs, and evidence-local final/qualified fixture directories are retained. `matched-failure-nodes.json` matches all16 exact original failure identities and XML ordinals/traceback hashes; `collection.log` confirms14+2. Counts below overlap and must not be added as distinct coverage.

Commands run from this worktree using `/workspace/inlet-venv/bin/`. PostgreSQL runs set `AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci` and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`.

- Before edits: `pytest -q 'tests/test_reported_feedback_service.py::test_actual_receipt_admits_owned_idempotent_job[sqlite]' 'tests/test_reported_feedback_customer_api.py::test_actual_owned_action_discovery_request_history_and_session_fence[sqlite]' --junitxml=…/baseline.xml` — both failed at retired execution guard,5.447s; `baseline.log/xml` retained.
- First repaired same pair —2passed17.195s (`first.log/xml`). Subsequent typed result/fixture hardening is qualified below.
- Exact collection: `pytest --collect-only -q tests/test_reported_feedback_service.py tests/test_reported_feedback_customer_api.py::test_actual_owned_action_discovery_request_history_and_session_fence` —16.
- `pytest -q tests/test_reported_feedback_service.py tests/test_reported_feedback_customer_api.py tests/test_reported_feedback_contracts.py tests/test_advertising_capabilities.py --basetemp=…/qualified-tmp --junitxml=…/qualified.xml` —27passed, zero skips/failures/errors,182.348s. Includes exact16 original failures and11 unchanged compatibility cases.
- Following reviewer-requested URL/output/fresh-schema hardening: `pytest -q tests/test_reported_feedback_service.py::test_actual_receipt_admits_owned_idempotent_job tests/test_reported_feedback_customer_api.py::test_actual_owned_action_discovery_request_history_and_session_fence --basetemp=…/final-tmp --junitxml=…/final.xml` —4passed, zero skips/failures/errors,28.539s (`final.log/xml`).
- Whole `ruff check .`, bare `mypy`, `git diff --check` —pass; mypy1138source files. Final logs `ruff-final.log`, `mypy-final.log`, `diff-final.log`. Initial local import/fixture-alias lint issues were corrected before qualification; no product failure claimed.

## Remaining Scope

This repairs current read/admission consumers, not automatic advertising execution. Acquisition+retry28, composition/archive10, configured journey with genuine PlanningConsent, and later browser families still require their separately reviewed seams. No full-suite/Full, live provider verification, production release or broader quality claim.
