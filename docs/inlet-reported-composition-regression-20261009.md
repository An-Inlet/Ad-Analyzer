# Current Reported Composition And Archive Regression

Branch `codex/inlet-reported-composition`, approved proposal `6981672`, reviewed acquisition `123cf9b`. Repairs only composition8 and operational archive2. No production changes, baseline routing/consent substitution, execution capability exemption, TTL extension or aggregate run.

## Current Reads Over Genuine History

All10 now use the reviewed genuine pinned original effect plus actual current request/acquisition adapter. Original shared acquisition/journey/baseline fixtures remain untouched. No case invokes PreviewRow preparation or execution consent; later baseline/PlanningConsent families remain separate. Original comparison, correction, source/session drift, causal/delivery unavailable, no-spending-authority, repeated reports, counts and numeric dependency assertions remain current.

The two unknown-receipt cases still perform an actual `MetaOptimizationTransport.read_back` with MockTransport GET→ReadTimeout, then actual current `optimization.record_receipt`. The test registers its exact current observation time before the GET and asserts exactly one GET. It does not substitute a constructed unknown receipt for the real transport result.

The sole optional `ExpectedUnknownReadback` is off by default. It requires a one-shot explicit aware UTC timestamp; absent/double/non-UTC expectations fail. The final checker independently constructs expected unknown content from the persisted original request and registered time, checks the persisted scalar timestamp, validates the entire body/digest/current normalized projection/chain, and permits exactly one sequence2 same-attempt receipt superseding the original. Only the original run/step state may change from verified_target_state to unknown. Every other protected field/table compares exactly, including original receipt/request/response/fence and held reservation. Candidate/feedback derivatives are empty before the real readback and after, preventing invalidation from hiding prior documents. Original measured historical POST count remains1; no fake prior mock post is introduced.

Normal composition, original-session revocation, archive, foundation and acquisition keep strict complete financial/effect-graph equality. The timestamp helper's pure regressions cover unarmed access, repeated arm and naive/nonzero-offset timestamps; they do not claim provider behavior.

Archive uses a module-local fixture seeding the **actual export_engine**, with fresh current sessions and unchanged real lifecycle begin/claim/build/unpack/check. Existing separate exporter session, complete archive/comparison inclusion, session redaction and original-session numeric-dependency rejection remain. The original two scoped lifecycle DB-clock seams remain unchanged for the offline future closed-after-window; no global/auth clock or lifetime is changed. The archive is built by the existing implementation, not a custom serializer or fabricated file/manifest. This is service/archive acceptance, not a browser or new endpoint claim.

## Evidence And Commands

Evidence directory `/workspace/inlet-evidence/20261009/reported-composition/` contains raw logs/XML, exact failed-ID matches and evidence-local isolated producer artifacts. Disk preflight3.7GiB free; no active/original aggregate source or database touched. Source extraction cleanup, if subsequently authorized, is separately inventoried and does not remove logs/IDs/XML/DBs. Counts overlap and are not additive coverage.

All commands use `/workspace/inlet-venv/bin/` from this worktree. BothDB cases set `AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci` and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true` with isolated UUID schemas.

- Before edits: `pytest -q 'tests/test_reported_feedback_composition.py::test_real_reports_compare_without_claiming_causality_and_idempotent_receipt[sqlite]' 'tests/test_reported_feedback_exports.py::test_actual_comparison_archive_rechecks_original_session_without_slot[sqlite]' --junitxml=…/baseline.xml` —2failed at the retired guard,3.843s; original logs retained.
- First repaired SQLite nominal +latest_unknown_receipt +archive cases:3passed29.630s (`first.log/xml`). Final qualification below includes the subsequent explicit scalar observed_at check.
- `pytest --collect-only -q tests/test_reported_feedback_composition.py tests/test_reported_feedback_exports.py` —exact10 (8+2), `collection.log`.
- `pytest -q tests/test_reported_feedback_composition.py tests/test_reported_feedback_exports.py tests/test_reported_original_expectation.py tests/test_reported_feedback_service.py::test_actual_receipt_admits_owned_idempotent_job tests/test_reported_feedback_acquisition.py::test_fixed_windows_preserve_rolling_coverage_and_repeat_spacing tests/test_reported_feedback_customer_api.py::test_unavailable_api_is_owned_and_accepts_no_proof tests/test_reported_feedback_customer_api.py::test_reported_comparison_shell_is_csp_protected --basetemp=…/qualified-tmp --junitxml=…/qualified.xml` —20passed, zero skips/failures/errors,128.622s. Includes exact10 original failures,3 new pure expectation checks and7 overlapping strict-default/current-boundary cases.
- Whole `ruff check .`, bare `mypy` (1140source files), `git diff --check`:pass. No production issue discovered or expectation rewritten.
- `matched-failure-nodes.json` maps exactly the10 original failed identities with original XML ordinals/traceback hashes to current successful nodes.

No Full/full-suite pass, live provider activity, deployment, advertising writes under current capabilities or comprehensive quality claim. Remaining configured/baseline families need their separately reviewed current PlanningConsent/historical route split.
