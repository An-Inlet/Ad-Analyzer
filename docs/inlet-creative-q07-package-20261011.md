# Q07 allocation currency and confirmed ceiling — qualification ledger

This package adds an allocation-only currency guard and actual private V5 Q07
acceptance tests. It does not activate private V5 as the default or authorize any
provider mutation, FX conversion or spending. Frozen Q07 expert-quality acceptance
remains separate from these deterministic API checks.

## Concrete defect and repair

A real owned Meta EUR catalog selector included in the normal three-account USD
goal input was accepted with HTTP201. The actual native currency and persisted
owned account both read EUR; amounts still totaled1000, selectors came from the
real target-catalog endpoint and no scope/staleness failure was substituted.
`creative-q07/sqlite-02.xml` preserves that failing regression (4.29s call).

`allocation_currency.check_allocations` revalidates inputs and actual catalogs,
rejects ambiguous duplicate full target tuples and binds exact TargetRef/account
before comparing every fixed/scenario allocation currency, including zero, to the
confirmed goal currency. Mismatch returns the fixed422 detail:
`Planning allocations must use the confirmed goal currency.`

Input resolution invokes the shared guard after ordinary exact selector resolution.
Repository generation invokes it using actual collected catalogs after completed
request replay and exact proposed-target validation, before writes. Historical
reads/exports and completed replay remain unchanged. Foreign-currency inspection,
unallocated accounts and exclusions remain allowed; no blanket account ban exists.
No schema, immutable DTO, deadline, authority, policy registration or clock changed.

The historical saved-input regression scopes only the new input guard to a no-op
for one real input save, explicitly emulating the pre-fix admitted state. It restores
the guard before genuine generation, which returns422 with unchanged retained rows
and zero financial effects. No positive document or proof is seeded.

## Fixture and retained attempts

Q05 gains only keyword-only `meta_currency: Literal["USD", "EUR"] = "USD"`, set
at initial owned Meta bootstrap and matching native MockHTTP account response before
acquisition. Default USD and source123/vault identity remain unchanged. Normal Q05
both-database preservation is included in final qualification.

Evidence root: `/workspace/inlet-evidence/20261011/creative-q07`.

- SQLite01: original second-Meta proposal failed the workspace connection uniqueness
  constraint before acquisition (3.86s call). Constraint preserved; no currency
  conclusion. Revised seam uses the original bootstrap, never mutates a receipt.
- SQLite02: real wrong201 described above, retained before production repair.
- SQLite03: two repaired API cases passed: allocation/fixed/zero/create/edit refusal,
  unchanged exact plan/request rows and financial counts, stale selector409,
  unallocated/exclusion/replay positives, and historical admitted-input generation
  refusal (5.00s and9.11s calls).
- SQLite04: actual assertive/confirmed-ceiling case plus four pure helper checks
  passed. Actual API case25.09s; pure duplicate/exact-target/unsafe-copy/valid-zero
  checks passed. Scoped mypy initially found a test Any-return annotation mismatch;
  corrected with explicit dict conversion, not a product change.

## Arithmetic and goal evidence

Actual create rejects over1000, negative integer, unsupported allocation currency
field and attempted client ceiling/aggressiveness overrides without plan-row changes.
The separate actual EUR account test proves currency rejection beyond schema-extra
field refusal. Goal update/preview/confirm sets assertive while retaining1000;
an allocation-plus-reserve total of1100 still fails, and genuine generated document remains1000/assertive.

A real1100 goal revision cannot be adopted before confirmation, whether input uses
the old or new revision. Actual confirmation permits a new input revision with
independently reconciled1100 scenarios. Stale input CAS fails. Genuine version2
retains1100; version1's1000 document digest/history/export remain exact. Original
product/image/reporting windows and Google-only selected observation are preserved.
No native calls occur during replay/history/export, and financial graph counts stay
zero. Generation may perform fixture read-only catalog acquisition.

Final `both-05.xml`: exactly20 passed, zero failures/errors/skips,199.120s.
Collected20 comprised six actual Q07 cases, four pure helper cases (overlapping
SQLite04), two unchanged Q05 preservation cases, six existing three-platform
repository stable-history cases and two existing cross-plan replay receipt cases.
The approved20 run had already started when a narrower14 suggestion arrived;
root explicitly retained the running20 without restart. No broader suite ran.
Whole Ruff passed; configured no-path mypy passed1422 source files; diff check passed.

Eight actual version1/version2 document/export artifacts (SQLite and PostgreSQL)
are retained under
`/workspace/inlet-evidence/20261011/creative-q07/artifacts/`.
[Manifest](/workspace/inlet-evidence/20261011/creative-q07/artifacts/manifest.json)
records exact file hashes and PlanVersion document commitments. Author verified
strict parsing and each exported document/digest against its paired document.
Artifacts show1000/assertive followed by1100 only after actual new confirmation;
old artifact packets were not overwritten.
The unrelated original browser both-02 generic409 remains unexplained; this repair
and its passing cases do not diagnose that earlier event.
