# Google owner retained review — slice 1

Based on reviewed design `dee53c4`. This package adds the historical pure review
validator and a private immutable linked-input evidence loader. It does not register
V6, change PlanVersion, enable generation, or add customer routes/UI.

`validate_retained_google_budget_owner_review` uses the existing exact historical
linked-source kernel and shares action/proof comparison with active validation.
Active validation still requires the complete original input account/source set.
Empty owner tuples do not invent a privacy epoch or source. Ordinary selectors
still require their original linked catalogs.

`load_retained_owner_input_evidence` validates the saved input, complete receipt
links and original actor/session/authentication scalar commitments before returning
ordered CatalogEvidence and SourceFence values. The existing public retained
receipt validator still returns None. No mutable ORM row or Session crosses the
new port. Caller-owned historical authorization and final acceptance remain
required; this helper performs SQL reads, without provider IO or current paid/TTL
lookup. Absence of those lookups is source-reviewed, not a new wall-clock-expiry
qualification.

The loader requires a clean, active, nonnested original Session and underlying
Connection root. It checks those identities before and after delegated reads and
before return. Clean-state checks are not sticky flush detection: an already
completed flush is outside this claim.

## Qualification

Evidence is retained in
`/workspace/inlet-evidence/20261011/google-owner-retained/`.

- `sqlite01`: eight new pure cases and ten actual SQLite cases, 18 passed,
  10 PostgreSQL cases deselected, 28.41s. Actual fixtures obtain source catalogs and save
  inputs through the private configured API with MockHTTP sources and normal clocks.
- `pg02`: the disjoint ten actual PostgreSQL cases, 10 passed in 78.70s,
  18 other cases deselected.
- `active03`: unchanged active owner-review regression file, 29 passed in 1.95s.

Coverage includes historical linked subsets versus full active source coverage,
unsafe copied primitives and proof substitutions, empty/no-link inputs, an
unselected owned account, original receipt scalar tampering, missing links, dirty
resident rows, foreign input identity, Session root replacement, underlying
Connection root replacement, and Connection nesting. Read/fault operations leave
planning and financial row snapshots and native call counts unchanged. Test setup
is separate from the no-effects measurement.

The deliberate Connection-root fault emits SQLAlchemy's `transaction already
deassociated from connection` warning on cleanup. It is retained, not suppressed.
No tests are repeated merely to remove this expected warning. There is no natural
expiry, provider inventory freshness, V6 generation, or live qualification claim.

Exact commands, final static outcomes, source hashes and JUnit counts are recorded
in `qualification.json`. No original failure evidence is removed.

Total disjoint coverage: eight new pure cases, twenty actual cases (ten per
database), and twenty-nine unchanged active pure regressions. No failures, errors
or skips; no SQLite duplication. Disposable PostgreSQL fixtures use isolated
per-test schemas on the dedicated local test database; no original database or
evidence was reset. Whole Ruff, configured no-path mypy, fresh-process imports of
both owner modules and git diff checks are required and retained in the manifest.

The first whole mypy run found two test-only typing errors: access through an
implicit imported private alias and intentional assignment to a frozen property.
The repair references the defining function directly and calls the same Pydantic
`__setattr__` operation explicitly. Production and fault behavior are unchanged;
no DB rerun was needed. Both initial and repaired static logs are retained.
Final whole Ruff passed; configured no-path mypy passed for 1460 source files.
