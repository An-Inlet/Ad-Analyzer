# W1 Three Further Migration Fixture Repairs

Base d665feb; interfaces e8568a4 and budget-only alternate21f4770 approved before
implementation. Tests only; current production migrations, privacy, capability
boundary and frozen W1 source/database unchanged. Social and restore remain
separate proposals, not implemented here.

Each closed producer takes an existing owned PostgreSQL schema and artifacts
path. Parent verifies exact prefix/revision set, empty target graph, actual old
revision column shape and absent later tables. Child independently verifies
schema/revision/empty target and pinned imported source. Actual pinned producers
commit and close Sessions before returning strict bounded scalar DTOs. Parent
compares table names/revision set unchanged and current SQL-owned rows against
returned values. No child DDL, arbitrary module/callable, policy flag or fallback.

- Budget: actual parent0078→0079; earlier authentic745acee source creates the
  preparation through its actual customer HTTP route. GET-only mock requests and
  zero posts are checked. Current valid/foreign serializer checks, immutable
  UPDATE/DELETE refusal and populated0078 downgrade refusal remain. SQLite still
  uses its original current first_customer and HTTP201 assertions unchanged.
- Candidate: original2155ff3 fixture→enqueue→process completes with one actual
  result/job and zero mock writes. Current0062→0060 deletes only derived tables;
  complete mandate ID set survives;0062 re-upgrade creates empty jobs.
- Replacement: original2155ff3 prepared→transfer executes exactly one original
  MockHTTP write and produces genuine predecessor/successor/run lineage. Current
  empty0058→0057→0058 roundtrip and populated downgrade refusal remain, with the
  same exact replacement ID set afterward.

The original2155 budget probe failed after SQLite passed: pinned initial privacy
cleanup queried absent0085 initial_rule_candidate_dependencies at real0079.
Result1pass/1fail12.479s, preserved in budget.log/xml and budget-artifacts. No
bypass was added. Root approved literal745acee533638f6f937339110944454cd8ce2a83,
exact app/tests/scripts hashes and unchanged contemporaneous mapper. Original
budget fixture/test bytes match2155; extraction/source-marker changes apply only
to the closed budget mode. Existing2155 modes/extractor remain unchanged. The
approved document's 'six-scalar' typo was corrected to the actual seven fields.

Individual terminal probes:

- Earlier budget:2passed0skips17.612s (SQLite and PostgreSQL).
- Candidate:1passed0skips10.103s (PostgreSQL).
- Replacement:1passed0skips11.014s (PostgreSQL).

Evidence `/workspace/inlet-evidence/20261009/w1-next-migrations/` contains each
named .log/.xml and retained artifact subtree with extracted source, producer
logs and actual scalar outputs. Initial Ruff formatting findings were corrected;
whole Ruff, bare mypy1131 and diff checks passed on final source. Final combined
qualification is appended after terminal completion. No Full result is inferred.

Final combined terminal qualification: **9 passed, 0 failures/errors/skips,
77.578 seconds**, with explicit disposable PostgreSQL enabled:

```text
pytest -q tests/test_budget_mandate_migration.py \
  tests/test_candidate_migration.py tests/test_replacement_migration.py \
  tests/test_commerce_publication_migration.py \
  tests/test_retired_producer_current_lifecycle.py \
  tests/test_retained_initial_rule_lifecycle.py
```

`final.log/xml` plus `final-artifacts/` retain the results. Current SQLite budget,
actual three PostgreSQL migration cases, commerce compatibility and existing
review/initial lifecycle bothDB cases all pass. Independent review required before
integration. These are three targeted frozen-failure repairs; all other W1
failures remain classified separately, not made green by this result.
