# Commerce 0053 Migration Producer — Frozen Single-Phase Interface

Approved bounded successor of `13fed34`; SQLite repair is separate `7db9053`.
This interface changes tests only. Social two-phase and all other profiles remain
out of scope. No current authority/privacy guard is patched.

Public test helper in `tests/retired_producer_fixture.py`:

```python
@dataclass(frozen=True)
class RetainedCommercePublicationIds:
    workspace_id: int
    store_id: str
    publication_id: str
    order_count: int
    publication_count: int
    evidence_state_count: int

def retained_commerce_publication_fixture(
    engine: Engine, artifacts: Path,
) -> RetainedCommercePublicationIds: ...
```

The helper is single-shot, not a context or persistent child. It requires an
explicit disposable PostgreSQL URL and exactly `inlet_publication_[a-f0-9]{32}`
as current schema. No SQLite branch, arbitrary revision/profile/callable or
schema creation/reset is exposed. Parent creates the UUID schema and executes
actual current 0047→0051→0053 Alembic upgrades. Parent closes its connections and
Sessions before invoking the child. Child and parent verify exact physical
Alembic revision set `{20261006_0051, 20261006_0053}` (the two
sibling heads both descend directly from0047), required commerce publication/evidence/order
and workspace tables, absent newer presence/planning tables, and an empty
commerce publication/evidence/order graph before seeding. The preexisting
`preserved` workspace may remain.

Use the existing verified local PIN
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f` and exact app/tests tree checks through
`retired_snapshot.extract`; no fetch/download. Add one closed driver mode
`commerce_publication_0053`; its schema prefix is allowed only for this mode.
All existing modes retain their existing allowlists. Child uses the pinned
`candidate_historical_schema.without_candidates` as the original pinned commerce
migration test did, then pinned `test_commerce_publications.complete` and its
actual CommerceSyncService with synthetic measurement input. No advertising
runtime is created. No current process monkeypatch escapes the child.

Child commits and closes its Session before writing JSON. Only the six exact
scalar fields cross: workspace_id strict positive int, store/publication IDs
nonempty bounded strings, three measured strict integer counts each exactly1.
Parent validates the exact field set/types and reads back the owned publication,
store and evidence state using fresh current SQL. Parent snapshots and compares
actual table names and Alembic revision before/after to detect any DDL change;
child performs no DDL. Existing subprocess 180-second/output bound applies.

The existing actual migration test preserves every downgrade/re-upgrade,
retained workspace/order and empty re-created publication/evidence assertion.
Qualification runs that PostgreSQL case plus existing shared producer cases on
both databases, then whole Ruff/bare mypy/diff. Failures remain evidence; no
schema or privacy fallback is added to force feasibility. This is current
migration qualification with a genuine historical producer, not current
execution enablement or a Full-suite result.
