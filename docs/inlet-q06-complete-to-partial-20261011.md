# Q06 Complete-To-Fresh-Partial Browser Recovery

Qualified test-only implementation on root `fdc4d3e`, following the reviewed
`docs/design/q06-complete-to-partial-recovery-v1.md`. Exactly the two new recovery nodes passed as recorded below.
Existing TLS01 failure and TLS02 four-case qualification remain unchanged.

## Scope

Three existing fixtures accept an optional `OwnerCatalogResponseControl`; defaults,
return tuples and static partial behavior are preserved. The controller changes only
copied mock campaign-budget rows for shared budget2, once, from referenceCount2 to3.
Independent budget4 and original payloads remain unchanged. The actual response
counter is bounded and locked. Combining static partial with the controller refuses.
The existing original-session check now compares credentials through a Boolean-only
constant-time check, avoiding assertion operand disclosure.

The new `complete_to_partial` variant adds exactly SQLite and PostgreSQL nodes.
It creates/exports genuine V1, removes the historical editor entry, acquires fresh
complete targets and includes a genuinely ready unsaved review. An original-session,
same-origin/CSRF, empty-body fixture checkpoint switches only future native responses.
Fresh partial acquisition/discovery then invalidates that ready choice. Replacement
acknowledgment and a complete alternative isolate the exact owner-readiness refusal.
The driver asserts no input POST on blocked Save; immediately before the one later
explicit-removal POST the harness verifies the entire switch-time planning snapshot
and financial counts are unchanged. No application route or authority behavior changes.

The final response validates actual complete/partial TargetCatalogV2 documents,
original shared owner with two observed members and referenceCount2→3, complete
campaign metadata, explicit unavailable discovery, and immutable historical V1 JSON
and digest. The original and subsequent catalog/discovery/document/export artifacts
are retained separately from fixed payload-free route diagnostics. No hidden
readiness/intent repair, downstream proof editing, clock changes or second generation.

## Preparation Evidence

Evidence directory: `/workspace/inlet-evidence/20261011/owner-complete-to-partial/`.
`ruff01.log` passed. `mypy01.log` preserved six test typing diagnostics: local
Request/string name reuse and lack of union narrowing for Google native settings.
Renaming the checkpoint local and adding an explicit GoogleSettingsV1 assertion
resolved them. Final `ruff02.log`, `mypy02.log` (1486 files), JavaScript syntax and
`git diff --check` pass. No production files changed.

Authorized collect-only `collect01.log` selected exactly two nodes (four old nodes
deselected), exit0 in2.97s. No bodies executed. Planned order:

1. `tests/test_owner_review_planning_browser.py::test_actual_owner_review_planning_browser[sqlite-complete_to_partial]`
2. `tests/test_owner_review_planning_browser.py::test_actual_owner_review_planning_browser[postgres-complete_to_partial]`

## Authorized Recovery01 Outcome

Independent source/applicability review closed before execution. Parent amendment
`5737ecd` explicitly authorized one sequential two-node run: PostgreSQL only after
SQLite exit0/exact single-pass XML and repeated source/resource/sole-test/fresh-path
checks. The separately recorded authorization binds immutable manifest
`5cef7a9f54bacd16ef63b68bba687facc1b1394db33e4153b93c0ae9afb55e22`
and runner `4581826db919ba5e68593a8672c64dc60d5c94e46ed248d8c30c3540489fd7f4`.
All1778 source hashes matched before and after. No retries or old-case reruns.

Both exact cases passed, zero failures/errors/skips/unrun: SQLite testcase28.204s,
suite30.092s, process32.415s; PostgreSQL testcase39.241s, suite41.011s,
process43.261s. The intended native refcount2→3 and fresh ready→unready transition,
owner-specific no-POST refusal, switch-time exact planning-state equality, single
explicit-removal revision, original session lifetime, zero financial effects and
immutable original V1 were asserted against actual local TLS/API/DB paths.

`recovery01-artifact-copies.json` binds20 durable copies (ten per database), including
four actual catalog/discovery snapshots per case, original and historical document/
export envelopes, artifact hashes and fixed route observations. Strict PlanVersion
and TargetCatalogV2 parsing, full original/export/historical document equality and
all document digests were verified. All36 observed routes completed successfully
(2xx), no truncation, both shutdowns complete. Initial read-only inspection used an
overly narrow status==200 assertion and stopped on legitimate create201 after the
SQLite copies; `artifact-inspection01.txt` preserves this inspection error. The
corrected inspection verifies existing copies and accepts successful2xx; no tests,
source or original artifacts were changed or rerun. Root separately corrected a
manifest-inspection key lookup before execution; no test/source change resulted.

Final static evidence predates the run on identical five source files: whole Ruff,
configured no-path mypy1486, JS syntax and diff checks passed. Only this outcome
ledger changed afterward. The run proves bounded synthetic original-session browser
recovery, not native-edit compatibility, a spending bound, incident closure,
performance reliability or the separate human usefulness gates.
