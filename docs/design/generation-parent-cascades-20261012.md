# Generation Parent Cascade Contracts — 2026-10-12

Completed locally after failed-finalizer commit `0eb03bf1`, on
`codex/inlet-w1-followup`. Tests and source mapping only; full current-source reads
remain unchanged. This is bounded cascade evidence within the existing 52-model
inventory, not all-writer closure or permission for shortened reconstruction.
The release inventory remains **57 passes / 1 unresolved** and
INLET-REL-20261012-01 remains open.

## Executed Contracts

Four tests passed: two cases on both SQLite and PostgreSQL.

The range case obtains actual offline MockHTTP range/selection/capture publication,
then directly deletes its original JobRun or aggregate completion. It checks the
receipt cascade, advancing privacy revision, current-reader 409 refusal and rollback
restoration. Completion deletion removes the exact related child sets; unrelated
history remains by count. Seven table families are checked: range receipt, aggregate
completion/current head, selected capture/fact, reporting semantics/metric presence.
This is not complete coverage of every transitive table or byte-for-byte verification
of unrelated retained history. Range-reader equality is verified after rollback.
Account deletion is refused by a foreign key; rollback preserves counts and privacy.
A committed completion deletion also refuses the original current read.

The catalog case uses actual catalog DDL and a seeded owned planning graph, not a
native catalog observation. Linked receipt deletion and retained input deletion are
refused by exact FK errors. Unlinked receipt deletion cascades its selections without
advancing privacy, proving that a privacy revision cannot stand in for catalog query
membership. Rollback restores counts. The normal workspace-locked semantic-erasure
helper removes receipts, links, selections, inputs and versions atomically: rollback
restores counts/privacy, and committed erasure persists removal. PostgreSQL uses real
migration-built schemas; SQLite replaces catalog tables using migration0088 DDL and
checks foreign keys. No completion-update immutability claim is made from metadata.

These direct parent DML tests qualify database behavior, not customer deletion APIs.
They do not establish concurrent cascade blocking against prepared generation.

## Checks And Preserved Evidence

`/workspace/inlet-evidence/20261012/parent-cascades04/qualified-summary.json` binds
four passing tests, four passing final static commands, exact XML identities and
1912 verified source hashes. Ruff, mypy (1595 files), collection and diff check pass.
Manifest: `440db81ac6376d46e3a75afa0e65e2d4c5a6f8fbfef5b7fb6047e94498990ba0`.
No skipped cases, resource interruptions or surviving child processes.

Earlier attempts remain preserved and confer no runtime acceptance:

- 01: Ruff passed; mypy rejected reuse of one exception variable across HTTP and
  integrity errors. Runtime and subsequent checks unrun; separate names fixed it.
- 02: statics passed; first SQLite case failed the overly broad assertion that deleting
  one completion removes all completion-related workspace rows. Remaining cases unrun.
  The corrected oracle computes exact target membership and retains unrelated history.
- 03: Ruff passed; mypy rejected accessing completion_id on an insufficiently narrowed
  union of row classes. Remaining checks unrun. Explicit table-column lookup fixed it.
- 04: all final checks and all four runtime cases passed. No production code changed.

## Writer Map And Remaining Package

Source tracing beyond direct model references remains mandatory. Low-level catalog
and ordered plan erasure helpers obtain their workspace contract from callers; their
individual DELETE statements have no universal mutation epoch. Restore verification's
completion DELETE is rolled-back privileged maintenance, not customer writer evidence.

Shopify identity helpers are another indirect family: `bind_store` takes the workspace
lock before `preserve` and alias insertion; `apply_order` locks the store through the
workspace gate before `prepare_source`. `CommerceSyncService.page` takes workspace,
native connection and store locks before reconciliation. Privacy-event handling
locks discovered workspace owners in order, advances semantic privacy for erasure,
then checks that newly discovered owners are within the locked set before identity
writes. Disconnect advances workspace privacy before preserving identity/removing facts.
Normal disconnect revokes the retained CommerceStore and deletes measurement children;
it does not delete that store or its aliases. Actual store deletion cascades aliases,
and workspace deletion cascades privacy identities; those are separate open contracts.
`remember` and `finish_reconciliation` are not independently gated helpers. The owner
recheck is not a global domain-insertion fence against every later ownership change.

The marker query includes domains mapped to other stores in the workspace through a
NOT-IN predicate. A store-local identity snapshot cannot prove its membership. Next:
qualify cross-store alias/marker insertion, removal and generic parent cascades with
workspace concurrency on both databases; trace remaining helper callers and physical
SQLite transaction boundaries. Do not infer a complete revision/gate from these source
walks or use them to shorten source reconstruction. Final authorization callbacks and
response/commit-boundary work remain in the earlier inventory's closure queue.

No push, PR, external/live operation, hosted CI, merge, deployment or advertising
write/spend. Pending HTTP-admission changes remain separate and release-unqualified.
