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

## Independent Review: Identity IO Boundary Repaired

The original bind_authority reused provider.check_active under SQL authorization
locks, contradicting the promised no-provider-IO boundary. Replaced locally with
PlanningReadContexts + loaded original snapshot: refresh before opening SQL, exact
current owner/session/identity checks under locks using5s identity fact, final guard
on context exit. Resolver deadline now sampled after final guard AND SQL close.
No global authorization helper changed. Original authenticated_at/expiry remain pinned.

Actual engine transaction instrumentation asserts identity-provider callbacks have
no active SQL transaction; provider revocation is observed under subsequent locks;
expiry during SQL-context close denies scope return. Full original tests retained.
Final review run40passed onSQLite/PostgreSQL,0skips32.80s; wholeRuff/mypy1297 and
diffcheckpass. Evidence review-final-both-db.xml/.log, review-final-ruff.log,
review-final-mypy.log. Earlier review-both-db log preserves4 test-only missing type
import failures (36passed), repaired before final run. No tests deselected in final.

## Trusted Preparation-To-Resolver Grant Pin

Added backward-compatible keyword expected_grant=(encrypted ciphertext, private
login customer ID or null). Trusted callers capture it during initial preparation;
resolver compares before its first snapshot instead of adopting a changed grant.
No plaintext getter/public DTO/repr or customer service edits. Finalization still
must compare the same original pin under its own SQL lock; root owns that late-race
fix. Same-source proof remains separately bound to exact request scope.

Final pin suite46passed0skips onSQLite/scopedPostgreSQL,63.73s. WholeRuff and mypy1297
pass; diffcheckpass. Durable pin-both-db.xml/.log, pin-ruff.log, pin-mypy.log and
pin-diff.log retain evidence. Pre-first-snapshot grant and login mutations deny with
zero OAuth calls; unchanged pin succeeds. Prior40case regression coverage retained.
Final observed workspace1259MiB/scratch5847MiB available, reserves preserved.
