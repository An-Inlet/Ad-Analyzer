# Original-Session Google Reporting Resolver — 2026-10-11

Basec47e5ce; branch codex/inlet-selected-owned-context in reused
/workspace/inlet-selected-catalog. Frozen interface5574f28:
docs/design/selected-owned-context-interface-v1.md.

New implementation app/google_connections/selected_owned_context.py exposes
OwnedGoogleReportingContext with catalog_request/catalog_context/revalidate_catalog
and selected_context/revalidate_selected. Captures original session/identity, uses
workspace-first independent SQL snapshots, current owner/paid/sync gates, owned
source/privacy/generation/currency/timezone/grant/login checks. Selected reads also
validate actual current immutable selection and full aggregate/current manifest.
No transaction spans Vault decrypt or OAuth provider I/O. Actual injected
GoogleHTTPRead v24 and nonempty developer token required; no duck-type qualification.
Expiry begins before OAuth and is bounded by original session, operation60s and
entire capture60s; UTC clock resampled after authorization/locks. No token cache,
provider writes, default factory, customer routes or schema changes.

Verification on final source:
- pytest tests/test_google_selected_owned_context.py, actual SQLite and scoped
  disposable PostgreSQL: 34 passed, zero skips,33.42s.
- Whole repository Ruff check: pass.
- Whole mypy (scratch cache): pass,1297 source files.
- git diff --check: pass.

Tests build actual synthetic customer/Google connection, encrypted Vault grant,
GoogleHTTPRead MockTransport OAuth and two-phase aggregate import,0091 immutable
selection, catalog and selected reader. No manufactured reporting completion.
Coverage includes original-session/identity/role changes, grant/login/generation/
units/pause/expiry changes during OAuth, full manifest correction outside requested
dates, selection/privacy/current-pointer changes, paid/foreign denial, delayed
identity authorization and nonextendable original capture deadline.

Durable evidence /workspace/inlet-evidence/20261011/google-selected-owned-context/:
both-db-expanded.xml/.log, whole-ruff-final.log, whole-mypy-final.log and diff-check.log.
Initial failures preserved: detached expired ORM fixture session; then missing SQLite
foreign-key pragma rejected by actual0091 trigger. Fixture fixed with loaded original
session and enabled FK enforcement, no runtime bypass. Intermediate debug predicates
were removed. First corrected bothDB run24pass also retained.

DB fixture used localhost55432/inlet_oct07_next_integration_ci with random schemas;
no reset/default-schema changes. Final available workspace1360MiB/scratch5847MiB;
resource reserves maintained. No push/hosted/Full/live calls or broad baseline.

Remaining: customer confirmation/invalidation/final commit service, capture paging
orchestration, actual September/August range provenance and live v24 capability are
separate. Context is not finalization authority. Existing owner must be rechecked
inside storage commit transaction. Required developer-token limitation retained.
No Q01/Q02/live/purchasable qualification claim follows from these tests.
