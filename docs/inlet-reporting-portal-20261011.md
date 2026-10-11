# Customer Reporting Page — 2026-10-11

## Implemented

`/app/reporting` is a public static shell backed exclusively by authenticated
customer APIs. Your Workspace links to it. It loads owned Google account choices,
reads current event selection, requires explicit invalidation before range refresh,
acquires a closed local-day aggregate range, discovers named event/family options
without a default, confirms the exact selection CAS, and captures the same range.
An invalidated selection retains its ID/digest for subsequent confirmation.

Unknown range/capture responses keep immutable request bodies and IDs in page
memory. Explicit retry uses the same request; successful retained receipts are
rendered only after server success and a current-session check. Known unavailable
responses are not shown as unknown successes. Reload abandons the in-memory retry
reference; no permanent browser deduplication or storage is claimed.

Server labels are rendered with textContent; no raw HTML, OAuth tokens, browser
persistent storage, arbitrary provider URLs or new live factory. Session/account
changes clear prior receipts and stale response state. Dates remain server-validated
in the account time zone. Generic conversions and selected-event facts remain
separate. The capture-ID receipt is a partial planning handoff, not a completed
planning product flow or authority to change advertising.

Root owns customer API registration in main.py. This package registers only its
static shell and explicit public-shell route-policy entry.

## Actual Browser Evidence

The local HTTPS browser uses actual login, CSRF, owned account listing, range,
selection and capture API/SQL paths. Only Google HTTP uses injected MockTransport;
transport loss is simulated after real server responses. No fake frontend API.
The browser verifies August1–September30, explicit conversions-family selection,
unsafe-looking labels remaining text, lost range and capture responses replayed
with stable IDs, exact DB receipt identity, explicit invalidation deleting old
capture data, a new range/reconfirmation with retained CAS, disabled runtime, and
session replacement clearing previous-owner results.

Evidence is retained under
`/workspace/inlet-evidence/20261011/google-range-publication/portal-*`.
Initial fixture failures are retained: the selected ownership mock returned extra
unrequested fields, and a post-invalidation assertion wrongly expected erased
captures to survive. The fixture now returns exact queried fields and verifies the
actual capture at a pre-invalidation DB checkpoint, then verifies erasure. Both
browsers passed the next cohort; its remaining failure was the new shell's missing
route-policy inventory entry, now added without changing authentication policy.

## Limits

No live Google approval or v24 compatibility qualification. No publication,
advertising changes, financial authority, background reads or public website edits.
No default reporting runtime. No automatic downstream plan creation; the selected
input V4 consumer remains an independently integrated package.

## Final Checks

- Actual local TLS reporting browsers on SQLite and PostgreSQL, route boundaries,
  and focused existing portal checks: **21 passed, 1 unrelated legacy browser case
  deselected, 29.32 seconds** (`portal-final.xml` / `.log`). No reporting case skipped.
- Whole Ruff passed; configured mypy passed **1,319 files**.
- Both new JavaScript modules passed `node --check`; `git diff --check` passed.
- No Full, hosted checks, push, merge, deployment or live provider calls.

## Original-Session Display Fence Repair

Independent review identified a same-owner session replacement gap between UI
operations: replacing operation cookies could adopt a new browser session while
retaining the prior session's displayed selection, range or pending body. The page
now retains a separate display-origin cookie fence. Ordinary work rejects a changed
fence and clears all owned state before any request; explicit Refresh Session is
required to establish a new display origin. Trailing session awaits are followed
immediately by synchronous checks before state/options/confirmation/invalidation
rendering, as well as receipt rendering and preflight action dispatch.

The actual browser journey now signs into the same owner again between operations
without a focus event and proves no old capture intent is issued. After explicit
refresh, a microtask cookie rotation following the trailing session response proves
old choice data cannot render. Both SQLite/PostgreSQL browsers passed **2 cases,
zero skips, 23.46 seconds** (`portal-origin-repair.xml` / `.log`). Whole Ruff and
configured mypy (1,319 files), JavaScript syntax and diff checks passed.
