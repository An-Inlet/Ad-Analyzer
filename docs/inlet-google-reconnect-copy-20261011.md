# Google reconnect and disconnect explanation

Child of `7906bc0`; copy-only production repair. Google disconnect review,
its existing acknowledgment and result message now explain workspace-wide saved
plan, recorded decision and selected reporting evidence erasure. They distinguish
retained imported reporting/goals and unchanged running ads. The existing callback
selection page conditionally warns: if this account was previously connected,
reconnecting has the same derived-data erasure effect and requires fresh import,
selection and a new plan. No inferred counts or account-only deletion promise.

Changed production files: `app/portal/static/index.html`, `portal.mjs` and
`google-callback.html`. No other provider copy, new checkbox, API/request,
authorization, backend, retention or advertising behavior changed.

The existing Google browser journey now asserts this text at actual callback,
disconnect review, existing acknowledgment and post-disconnect result stages.
Its consent, current-role, selection and cancellation behavior remains intact.
No new test functions, database fixtures or lifecycle simulations were added.

Qualification uses the reviewed immutable manifest
`f6a7be5afedb28f756c482741d337dd15e5b85a35afec63dd1906e81f8fc86fe`
and runner `22287a1bf84fc1b90da3e198ea6e5d5b50898ca0742e84215762fc2df5cc47c0`:

- Existing `test_google_navigation_selection_cancel_retry_and_current_role[sqlite]`:
  one passed, 6.37s, exit 0.
- The PostgreSQL variant: one passed, 7.58s, exit 0.
- Exactly two distinct unskipped cases, each once, separate parent phase
  authorizations, fresh process/basetemp/cache/XML/log, no retries or profiling.
- `node --check app/portal/static/portal.mjs`, whole Ruff and whitespace checks
  passed. Final configured no-path mypy passed for 1,486 source files.

Evidence: `/workspace/inlet-evidence/20261011/google-reconnect-copy/summary.json`,
SHA256 `5315f4869f1949612dd018721a2f8ce693d3e4610301ab375aa4a8477135ed79`.
It retains source and evidence hashes, exact XML identities, original exit codes,
resources, manifest, runner and authorization records. PostgreSQL uses the existing
explicit local disposable test database with per-test schemas, without reset.

Initial Ruff E501 from a new assertion is retained in `ruff02.log`; only line
formatting changed before successful `ruff03`. Initial mypy began just before the
parent's concurrency hold and was already terminal when polled; no adverse test
effect was observed or inferred. Final mypy ran after slot release and includes
the completed assertion changes. No test failure was discarded.

This verifies warning presentation and existing connection controls, not the
separate accepted-plan/reconnect erasure journey. Frozen Q11 asks to retain V1 and
its decision after reconnect, whereas current same-account reconsent semantically
erases that graph. The conflict remains explicit. This repair neither weakens
privacy nor claims preserved-history reconnect qualification. The read-only
decision proposal remains at `/workspace/inlet-design/Q11-RECONNECT-LIFECYCLE-DECISION.md`.
