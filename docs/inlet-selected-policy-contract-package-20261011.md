# Standalone Selected Policy Contract — 2026-10-11

Base `06098a292d36ff9fc62058cc1a0a7b653ca38946`; implements the approved
[interface](design/selected-policy-contract-interface-v1.md).

Only new production module: `app/planning_documents/selected_policy_contract.py`.
It exposes the frozen `SelectedPolicyContractV1`, exact pair recognition,
`assert_selected_ticket_policy`, and `assert_selected_composition_policy`.
Canonical v4 requires no creative input; reserved v5 requires creative input.
Both descriptors identify the unchanged `local_reporting_v3` witness family.
Recognition confers no authority and performs no input/creative proof validation.

Strict primitive validation precedes descriptor equality. Full canonical policy
comparison and digest binding reject mixed, unknown or altered policies. Model
revalidation rejects unsafe copied instances. Policy construction imports ports
locally; TYPE_CHECKING annotations avoid a document import cycle.

No consumer, serialized existing document, capability registry, default v3 policy,
SQL, API, persistence or runtime changed. V5 remains unregistered. Genuine v5 still
requires separately reviewed creative proof and end-to-end persistence/lifecycle
integration; this module does not retag documents or manufacture tickets.

Evidence: `/workspace/inlet-evidence/20261011/selected-policy-contract/`.

- Focused pure tests:26passed, zero skips,2.389seconds (`pure.xml`).
- Both fresh-process document/contract import orders passed.
- Whole Ruff final check passed; initial import-order lint failure retained.
- Configured no-path mypy passed:1,381 source files.
- Diff whitespace check passed.

No PostgreSQL, external calls, remote push, hosted checks, merge or deployment.
