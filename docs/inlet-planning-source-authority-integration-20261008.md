# Planning Sources And Authority Integration — 2026-10-08

Reviewed adapter `c9b0dd6` and authority/interfaces `29ae12f` integrated at `5ba2aca`.
Actual all-platform native, owned reporting and Shopify readers supply typed evidence.
Reporting-window gaps retain exact completion/window/native/document pins and undergo
final manifest revalidation. Detached customer principals are replaced by freshly locked
rows before exact identity/session comparison. Public requests accept intent/selectors,
not complete client artifacts. Service and authenticated customer journey remain pending.

Assembled source/gap/authority/composer/comparison/storage cohort: 125 passed in 86.14s,
one existing Alembic warning. Whole Ruff and prescribed mypy passed (1,039 files).
Evidence: `/workspace/inlet-evidence/20261008/planning-source-authority-integrated.log`
and `.xml`. No Full, remote, hosted, live service or deployment activity.

Subsequent integration inspection found an additional unresolved ordering issue: existing
reader bind_authority paths call the identity provider while holding database locks.
This test cohort does not qualify the no-I/O-under-locks requirement. A narrow repair
is authorized in the isolated adapter lane: refresh identity before each planning read
context, use DB-only authority under locks and finalize after waits; retain existing
nonplanning wrapper semantics. Additional ordering/expiry regressions and independent
review are required before this source package is qualified for the full service.
