# W1 Next Retained-Engine Package — Classification Proposal

Original source review base `9ba3e68`; implementation base `d665feb`. Root approved
the per-function classification below. Arithmetic is corrected against the existing
`successor-coverage-244.json` exact-node ledger; qualification is recorded separately
in `docs/inlet-w1-retained-engine-package-20261009.md`. This is not a request to
restore product execution.

## Exact Baseline And Coverage Arithmetic

Original frozen W1 has1,247 failed nodes whose traced terminal path is
`tests/test_mandates.py::seed` → `app/mandates/service.py::approve` → the current
advertising-write denial. The reviewed account-diagnostics66 and native-assembly72
successor repairs directly cover138 of those nodes. The already integrated
`ae470f1` TikTok read fixture repair directly covers another72 shared-seed nodes:
**1,247 −138 −72 =1,037 shared-seed failures remain**. The first proposal omitted
that reviewed TikTok coverage;1,109 was therefore stale at its stated cutoff. Root's reviewed `20a44eb` transport
package covers29 different direct-sink failures; matching its seven marked function
families against the original failed identities finds zero shared-seed intersections.
It does not reduce1,037. The four shell/route failures are also outside this set.
Later concurrent packages must be credited only after exact identity intersections
and reviewed results; this proposal does not credit pending Meta/native/migration work.

Original evidence remains
`/workspace/inlet-evidence/20261009/w1-failure-classification/failed-nodes.json`,
source XML SHA256
`e3263f5e2bca0d484b4657d6672a32dfdc44539ee1cbed8257bf1a7187488037`.
All counts below are exact original failed identities, including backend and other
parameter values. Do not substitute module collected counts for failure closure.

## Recommended Bounded Package: 23 Functions, 147 Original Failures

These six modules contain only the listed test functions, and every body was read.
Use explicit per-function classification anyway; do not put markers on helpers or
modules. The bodies themselves operate retained publication/activation/optimization
state machines, financial reservations or original-request evidence. Their reads
and ownership negatives are subordinate to those same retained engine contracts,
not the current planning catalog/customer account API.

| File | Exact test function | Frozen failed nodes | Body-level contract retained |
| --- | --- | ---: | --- |
| `test_publication_core.py` | `test_exact_separate_review_and_server_compiler` |2|Separate publication approval, dispatch refusal before approval, exact compiler and idempotent preparation.|
| same | `test_paused_dag_one_reservation_and_distinct_activation_review` |2|Four fixture creation steps, one reservation and separate activation review; resources stay paused.|
| same | `test_timeout_after_effect_reconciles_without_duplicate_creation` |2|Unknown publication outcome and readback without duplicate resource creation.|
| same | `test_crash_before_emission_requires_authoritative_no_effect` |2|Claim/reconciliation fence and no replay without quiescence proof.|
| same | `test_cancel_releases_only_before_dispatch` |4|Historical cancellation preserves a post-dispatch financial hold.|
| same | `test_current_authority_checked_before_each_step` |12|Generation, owner, billing, mandate, kill and high-water drift stop the next fixture write.|
| same | `test_concurrent_claims_one_attempt` |1|PostgreSQL concurrent historical claim preserves one reservation/attempt; original SQLite intrinsic skip remains.|
| same | `test_transport_substitution_and_foreign_receipts_rejected` |2|Exact offline transport and receipt workspace/fence checks.|
| same | `test_receipt_cannot_predate_attempt_or_come_from_future` |4|Historical receipt freshness rejects before insert.|
| same | `test_original_request_archived_and_partial_no_effect_keeps_full_reservation` |2|Original request receipt retained; partial no-effect/cancel never clears unresolved hold.|
| `test_google_action_plans.py` | `test_claim_apply_readback_retains_future_exposure` |8|Budget/pause/resume/negative-keyword fixture execution, exact review, unknown/readback and retained future exposure; unconditional live boundary remains asserted.|
| same | `test_current_state_generation_and_unmatched_outcome_fail_closed` |2|Unsupported/current-state/reconnect mismatch prevents or fails historical action reconciliation.|
| `test_google_request_terminal.py` | `test_exact_batch_all_or_nothing` |24|Two actual MockHTTP executed originals; typed closure set, lineage/time/session negatives; closure cannot substitute financial transition proof and never releases holds.|
| `test_google_replacement_source.py` | `test_composition_prepare_and_transfer` |30|Actual original captures plus explicitly synthetic contract-only transition source; repeat preparation, approval/run and financial hold transfer, or exact rejection on drift.|
| same | `test_unknown_ancestor_never_calls_financial_source` |2|Unknown original stops repeat preparation before synthetic financial source; hold stays held.|
| `test_social_activation_journeys.py` | `test_full_persisted_social_activation_reuses_original_reservation` |4|Actual MockHTTP Meta/TikTok creation+activation after separate approval; one original reservation, no replay, scoped outcome receipt.|
| same | `test_unknown_social_activation_retains_attempt_then_reconciles_without_replay` |4|Unknown actual activation leaves one attempt/hold; later readback verifies without another POST.|
| same | `test_post_claim_graph_or_authority_drift_prevents_activation` |16|Creative/media/cancel/disconnect/generation drift after claim causes zero activation writes and retains hold.|
| `test_exposure_qualification.py` | `test_exact_reservation_is_counted_once_only_for_activation` |2|Retained creation claim's reservation excluded exactly once from activation accounting.|
| same | `test_unknown_evidence_never_becomes_zero_exposure` |8|Unknown financial model/bounds/completeness/regressed spend remains unqualified, never zero.|
| same | `test_lineage_and_freshness_fail_closed` |10|Retained financial proof foreign/duplicate/currency/plan/post-read expiry checks.|
| same | `test_profile_lifetime_limits_downstream_dispatch_eligibility` |2|Financial profile lifetime bounds historical dispatch; no expiry extension.|
| same | `test_unresolved_prior_period_holds_are_preserved_in_portfolio` |2|Prior-period financial hold remains counted; wrong reservation cannot be used for activation.|
| **Total** | **23 functions** | **147** | **No pass claim yet.** |

The expected unchanged module collection is148 cases:147 original failures and the
one existing SQLite PostgreSQL-only concurrency skip. This is source/original-run
accounting, not a newly executed cohort. Successful future qualification would
cover at most those147 original failures, leaving890 shared-seed failures before
other independently reviewed packages; it cannot automatically clear other callers.

## Minimal Proposed Fixture Interface

Only on each named function add existing `@pytest.mark.retained_execution` and
`@pytest.mark.usefixtures("retained_execution_engine")`. Existing fixture in
`tests/conftest.py` requires that marker, rejects `planning_boundary` combination,
and monkeypatches only the explicit deployment-capability pair for that test's
lifetime. Do not change it, make it autouse, mark shared helpers, or add a global
runtime toggle. Existing fixtures must still produce genuine approved mandates,
separate execution consent and full scope/review/claim state. No fabricated grants,
row shortcuts, disabled auth checks or parameter/assertion edits.

Each selected fixture helper remains unmarked: imported users do not inherit the
classification. This is essential for current customers/readers that share those
helpers. Preserve actual current-provider ownership, session, privacy where present,
unknown-response, no-replay, hold/fence and live-boundary assertions verbatim. All
provider traffic stays in existing fixtures/MockHTTP; no external calls.

Proposed qualification after approval: run these six complete modules on existing
isolated SQLite/PostgreSQL fixture schemas, together with unchanged
`test_planning_provider_transport_boundary.py` and
`test_planning_execution_boundary.py` in the same pytest process. Those boundary
functions must remain unmarked/default-deny. Run whole Ruff, bare mypy and diff
check. Preserve all failed attempts and stop to report contradictory current vs
historical fixture requirements rather than adding another bypass. No Full,
aggregate DB, hosted action, migration or workflow change.

## Large Families Deliberately Excluded From This Package

`test_optimization_runtime_substrate.py::test_owned_credentials_context_and_cleanup`
(32 failed nodes) directly tests current vault credentials, session revocation,
source generation, billing and post-IO expiry; its retained setup is not enough to
classify the body as a write-engine test. Other functions in that module are pure
configuration/no-network/vault checks, currently passing. Keep them default.

All eight `test_candidate_selection.py` bodies were read: actual native read queue
and export, V1 byte compatibility, logout/role/privacy/catalog/expiry changes,
workspace-lock waits, atomic insert failure, exact owner selection and insert-time
expiry. These29 failures are a read-only candidate subsystem with historical
mandate prerequisites; they need a separate authentic-record/current-reader design,
not this blanket retained-engine marker. No source-only conversion is assumed.

`test_optimization_candidates`, `test_candidate_review_bridge`, customer runtime
API modules, TikTok owned discovery, restore/privacy/export and campaign-media
families remain unclassified here unless reviewed separately. Their module/import
names are not proof that all their bodies are retired. This package does not overlap
initial_start's Meta8/native-planning10 work or failure_review's migration work.
