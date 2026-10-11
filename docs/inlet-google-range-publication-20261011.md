# Owned Google Range Publication — 2026-10-11

## Implemented Scope

`app/google_connections/range_publication.py` consumes the injected, exact v24
`GoogleAggregateRangeHTTP` reader. The new customer router is
`app/api/customer_reporting_range.py`, with POST
`/api/customer/v1/workspaces/{workspace_id}/reporting/google/aggregate-range`.
The intent contains only the owned account ID, request ID and inclusive local dates.
Application router registration remains the integration owner's separate change.
No default live runtime is installed.

The original customer session is retained across independent SQL snapshots and
mocked provider I/O. Before and after acquisition, the publisher compares the
complete connection snapshot, encrypted grant/login pin, privacy, units and current
completion. Pending staged imports or changed scheduling state fail closed.
Only actual returned campaign/day rows replace the requested range. Other dates,
accounts and all ordinary import scheduling fields remain unchanged.

Actual aggregate publication, its current pointer, one scoped successful
`google_customer_range_read` JobRun and the immutable 0092 receipt commit together.
The final receipt is reread against the full aggregate manifest, followed by the
original-session guard and deadline check. Same-body current receipt replay performs
no HTTP; a concurrent winner is reused before publication. Foreign/conflicting or
stale receipts fail without a new read. No analysis/execution outbox is enqueued.
Generic aggregate conversions are not customer-selected conversion observations.

Only the exact concrete range HTTP class receives the existing aggregate descriptor;
duck types and subclasses do not acquire publication provenance. DAILY/social
publication and financial authority are unchanged.

## Dependencies And Evidence

This branch includes reviewed range HTTP d022715, receipt DTO a72c3ed, storage
8f570b4 plus cf5b30f, and original-session/SQLite transaction boundary 5637567.
The SQLite explicit BEGIN repair is inherited, not a separate local workaround.

Durable logs/XML: `/workspace/inlet-evidence/20261011/google-range-publication/`.
Initial failures were fixture URL concatenation without a slash; that failed log
is retained. The corrected first SQLite run passed 9 cases, and the expanded
SQLite gate passed 14. Final combined and static outcomes are recorded below.

Tests exercise real customer API authentication, actual encrypted vault/OAuth
mock requests, the 61-day August–September America/New_York range, exact receipt
replay, foreign/CSRF rejection, pending-import rejection, original-session and
post-final-HTTP races, transaction rollback before and after the receipt savepoint,
and a concurrent same-request winner. All HTTP is injected MockTransport.

## Remaining Boundaries

Live v24/provider compatibility, access approval and real provider qualification
are not established by fixtures. The required developer token compatibility limit
is unchanged. Parent integration owns router registration and downstream planning
consumer work. Ordinary subsequent imports legitimately make this range stale;
there is no background customer session or scheduler pause. This package grants
no advertising spend or write authority.

## Final Checks

- Focused actual API (both SQLite/PostgreSQL), raw range HTTP and receipt storage:
  **95 passed, zero skipped, 58.11 seconds** (`focused-final.xml` / `.log`).
- Whole configured Ruff: passed (`ruff-final.log`).
- Whole configured mypy: passed, **1,318 source files** (`mypy-final.log`).
- `git diff --check`: passed. No broad baseline or Full run.
- An attempted `mypy .` invocation encountered the repository's duplicate script
  module discovery; the repository-configured `mypy` invocation above passed.

## Review Repair: Global Request-ID Collision

An independent P2 review found that different workspaces can reach publication
before a global receipt-ID collision becomes visible. Exact receipt primary-key
uniqueness errors now roll back the entire outer publication transaction and return
sanitized409, without reading or exposing a foreign winner. Other database integrity
errors are not translated. Actual duplicate-header tests on both databases verify
unchanged metrics, jobs, completion pointer, receipt count and source sync time.
The repaired API cohort passed **35 cases, zero skips, 103.32 seconds**; whole Ruff,
configured mypy (1,318 files) and diff check passed. Durable `collision-*` evidence
is retained alongside the original95-case package evidence.
