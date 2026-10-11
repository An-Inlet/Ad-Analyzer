# V6 Slice Three: Retained Currentness And History Boundary

Design only from rootbc2c56b and reviewed integration contractdee53c4. No registry,
service, API or UI implementation/activation. Pure V6 documents/composer must freeze
first. This refines the existing contract with actual signatures and file ownership.

## Existing Concrete Boundaries

`creative_retained_sources.capture_creative_retained_sources(db, *, principal,
document, now) -> tuple[RetainedSourceWitness,...]` and
`recheck_creative_retained_sources(db, *, principal, document, dependencies:
Sequence[PlanDependencyRow], now) -> None` are exact V5 wrappers. Their `_Context`
checks genuine policy pair, clean Session and Connection root identities, fresh
DB clock, original actor/READ_ROLES, goal and privacy before/after delegated work.
Capture returns all local reporting witnesses, commerce and creative; recheck
validates the complete immutable dependency set and compares current witnesses.

`creative_currentness.capture_creative_retained_source` and
`creative_history.creative_local_witness` also explicitly reject non-V5 today.
These are real subordinate gates; merely changing the top dispatcher cannot make
V6 work. `selected_plan_history.validate_selected_plan_history(db, document)` loads
exact stored version and complete bounded dependencies, validates selected pins,
traffic history and creative dependency. `repository.version` invokes it whenever
selected proof exists. Lifecycle/export calls this same history boundary; V6 cannot
bypass it through an alternative read path.

`catalog_receipts.validate_retained_input_receipts(db, inputs) -> None` already
validates original rows and owner opaque commitments via
`google_budget_input_receipts`. It currently returns no evidence. The reviewed
new `load_retained_owner_input_evidence(db, inputs)` therefore requires an actual
refactor, not a caller inventing catalogs/sources or a fake historical principal.

## Frozen Proposed Ports And Responsibility Split

**Retained lane** owns new `google_budget_owner_retained.py`, narrow extraction in
creative_retained_sources/creative_currentness/creative_history, the two top-level
retained_sources dispatch branches and new focused tests. Exact public new ports:

```
capture_owner_review_retained_sources(
    db: Session, *, principal: CustomerPrincipal,
    document: PlanVersion, now: datetime,
) -> tuple[RetainedSourceWitness, ...]
recheck_owner_review_retained_sources(
    db: Session, *, principal: CustomerPrincipal, document: PlanVersion,
    dependencies: Sequence[PlanDependencyRow], now: datetime,
) -> None
validate_owner_review_plan_history(db: Session, document: PlanVersion) -> None
```

Keep old V5 wrapper signatures and policy refusals. Extract private shared bodies
behind independently exact canonical V5/V6 wrappers; do not pass a fake V5 document
or a caller-selected bypass flag. Shared primitive creative witness construction
may accept the already frozen canonical selected-policy descriptor requiring
creative, with full exact document validation and owner semantics checked by V6
wrapper. No future-version permissive `>=5` predicate. Revalidate copied models.

**Receipt/history lane** (may be same author sequentially) owns catalog_receipts
internal validated-pair extraction and selected_plan_history's exact V6 dispatch.
Return frozen `RetainedOwnerInputEvidence(catalogs:tuple[CatalogEvidence,...],
sources:tuple[SourceFence,...])`, max20 each, no ORM/session/scalars. Before returning,
validate unchanged original input row, complete link graph, original actor, exact
receipt payload/selection membership and original owner selection commitment from
retained session/authenticated scalars. Keep public validator behavior unchanged.
No current session, epoch or receipt TTL invented for history.

**Integration lane** owns service.py/repository.save_generation, generation_ports,
policy_capabilities, server constructor/factory/API capabilities and actual API
fixtures. It consumes these ports after both retained and pure packages freeze.
No independent change to defaults or registry by retained lane. `repository.version`
can keep its existing selected-history entry point if that exact dispatcher owns
V6; avoid double-recursive history calls. Use local imports to preserve current
retained_sources/selected-history cycles. Authors agree shared file ownership before
parallel work, never both edit selected_plan_history or catalog_receipts.

## Current, Save And Historical Semantics

Current V6 capture: validate exact V6 document and owner proof, enter shared clean
context; guard; load original authenticated receipt evidence; compare complete
canonical catalog tuple and retained owner proof; obtain full reporting/commerce/
creative witnesses through shared current bodies; repeat original owner evidence
comparison and context checks after delegation; final fresh DB-time/authority guard.
Original owner catalogs remain original receipt observations; current reporting
checks do not relabel them as a fresh provider absence claim. The integration lane
separately performs current original-session `_load`/TTL/source checks for save.
Current viewing retains READ_ROLES and existing paid behavior, not paid-write gates.

V6 recheck validates whole dependency set first, then invokes V6 capture and compares
all witnesses with exactly the existing timestamp semantics. No owner-only subset,
new dependency kind, cached result, removed selected/image/selected pass or widened
five-second authority. Keep bound MAX_EVIDENCE+MAX_ACCOUNTS+2 and one overflow row.

Historical dispatcher validates stored row and *all* existing dependencies/pins first,
then original receipt/link/opaque commitment and `validate_retained_google_budget_owner_review`
against the exact retained catalogs/sources. It must not call its own outer history
dispatch recursively. No media byte I/O, provider read, current source/session/paid/
privacy epoch/TTL comparison. Later nonempty catalogs, metadata removal or source
reconnect cannot rewrite immutable history; missing/corrupt original retained proof
fails. Existing privacy erasure still removes access/data through lifecycle rules.

At top capture dispatcher preserve existing409→source_integrity_unavailable and
ValueError/ShopifyError→proof_unavailable mappings, while401/402/403 propagate.
Do not broadly catch unexpected DB/clock/provider exceptions in new low-level code.
Match existing recheck mapping deliberately; exact interface review should resolve
any new status rather than silently broadening exception handling.

## Focused Qualification Selection

New actual SQL fixtures must use genuine V6 documents once pure freeze supplies
them, never retag V5. Select existing tests as patterns, not full-suite reruns:
`test_creative_retained_proof.py`, `test_creative_currentness.py`,
`test_creative_retained_dispatch.py`, `test_creative_history_sql.py`, plus owner
input-history tests. Cover nonempty, explicit empty, unrelated included account,
cross-account ordinary scenario catalogs, missing/extra dependency, missing input
link, changed opaque receipt commitment, full catalog mismatch, raw SQL mutation
between delegated calls, swapped Session/Connection roots, dirty/flush/reentry,
post-clock expiry, viewer current read, expired-but-intact history, media removal,
semantic erasure and unchanged V5 output. Error normalization/auth statuses checked.

Only after these ports close: integration lane actual API create→generate→current→
history→export/correction/replay with original session and zero execution effects.
UI remains held until that API freeze. Performance census, if separately authorized
on this new coherent milestone, is observational only and cannot alter these gates.
