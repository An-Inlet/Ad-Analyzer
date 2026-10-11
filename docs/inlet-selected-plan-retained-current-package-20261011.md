# Current selected plan retained proof — 2026-10-11

Base: `7c1de6b`. Internal current-capture port only; no v4 registration,
retained-source dispatch, historical validation, new persistence or provider IO.

`app/planning_documents/selected_plan_retained.py` exports:

```python
capture_selected_reporting_pin(
    db: Session,
    principal: CustomerPrincipal,
    account: AccountRef,
    privacy: int,
    selector: SelectedCaptureSelectorV1 | None,
    now: datetime,
) -> SelectedRetainedAccountProofV1
```

Caller owns the original transaction and externally refreshed original identity,
including its final freshness check before accepting/persisting the returned proof.
This port performs local READ_ROLES guards, preserving viewer current-read access;
it does not call the owner-only source-fence resolver. It rejects a changed/nested
transaction, pending ORM changes, wrong privacy, expired original session and
foreign selectors. It derives the fence from actual qualified `_reporting` and
loads the exact selected graph through `load_selected_plan_graph` only when a
selector is explicitly supplied. None never means latest.

The proof retains the atomic current selection head even for explicit absence of
a capture. Qualified reporting, head and chosen graph are recomputed after the
first complete read. Private source rows (including private grant/login binding)
are compared transiently and never returned, logged, hashed or persisted. Final
local authorization/privacy/session checks follow all SQL. Caller must still run
its original externally refreshed identity fact's final age check; this function
cannot manufacture that fact from a customer principal.

## Evidence

Durable evidence: `/workspace/inlet-evidence/20261011/selected-plan-retained`.

- `sqlite01`: seven SQLite cases passed, seven PG cases deselected, 8.28s.
- `both02`: sixteen cases passed, zero skips, 36.08s. Actual customer login,
  Google OAuth/vault and MockHTTP selected capture fixture; no seeded captures.
  Viewer selected/explicit-absence positives plus mid-read privacy, selection-head,
  private-login, original-session, membership and campaign-metadata mutations.
  Mutation transactions roll back after denial; production storage guards remain.
- `static02/ruff.log`: whole Ruff passed. Initial whole mypy reported four test
  annotation/import-export errors (preserved); corrected annotations/import.
  `static02/mypy-final.log`: whole mypy passed, 1333 source files.
- `static02/ruff-final.log`, `diff-final.log`: final checks.

Bounded invocation used `pytest tests/test_selected_plan_retained.py`, unique
scratch basetemp, durable JUnit and `--durations=20`; PG used the existing disposable
local test database with per-test unique schemas. No database reset, Full suite,
external provider traffic or deployment. Workspace/scratch remained above reserves.

The fixture also constructs a closed native catalog for the shared reader helper;
this port never consumes it and makes no new native catalog qualification claim.
Historical proof validation is a separate root-owned module. Full collector/final
persistence composition and original external identity-age acceptance are not
claimed by these internal-port tests.
