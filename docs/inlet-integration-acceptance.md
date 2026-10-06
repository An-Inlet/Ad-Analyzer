# Customer Foundation Integration Acceptance

> Historical checkpoint / scoped evidence record. For current implementation, focused
> tests, exact-artifact aggregate validation and live qualification, start with the
> [current acceptance matrix](inlet-current-acceptance.md). Requirements and historical
> test/CI results below are preserved; old missing-feature claims are not current status.

This isolated integration branch combines draft PRs 79–85, including their repaired
predecessors, without merging main or enabling providers. It is based on PR83 and
retains branch ancestry for review. Parallel migrations0032 and0034→0035 converge
through explicit no-op merge0036. No history was rewritten to pretend the original
parallel branches were sequential.

## Verified So Far

- Integrated subset before latest scheduler/portal retry updates:144 passed,
  one SQLite-only row-lock skip with explicit disposable PostgreSQL.
- Integrated Ruff/mypy passed (270 files including the assembled journey).
- Latest scheduler, portal retry, CRM and migration subset:78 passed.
- Assembled real application/database journey:2 passed (SQLite/PostgreSQL),
  covering session/workspace, Google connection selection, goal review/confirmation,
  signed billing webhook plus dispatcher, entitlement changes, disconnect and logout.
  Shopify baseline installation remains an explicit fixture-only boundary.
- Populated PostgreSQL0031→head→0031→head:2 tests passed. Existing workspace,
  goal/revision, job, failed analysis and pending outbox data survived. New retry
  defaults and backoff columns were checked. Goal receipts intentionally disappear
  on downgrade and are empty after re-upgrade.

These checks are not final-head Full/CI acceptance. Latest review fixes are included and targeted tests passed; Full/CI remain pending.
The standalone browser still requires an existing verified session; customer
Shopify setup and closure flows remain implementation work. Provider methods are
exercised through deterministic fixtures/HTTP mocks, never live credentials.

## Pending Review Repairs

- Portal definitive422 correction and preserving uncertain create attempts while
  editing a different goal: integrated PR81 e97d600.
- TikTok outbox analysis must bind SourceConnection rather than Google connection:
  integrated PR83 ad4e9f2.
- Klaviyo explicitly nullable subscription channels: integrated follow-up c2e09c1; valid null means unknown, not unsubscribed.
- Actual customer API journey passed offline; customer Shopify onboarding routes
  remain in progress on a separate branch.

## Launch Boundary

No hosted identity setup, provider permission review, live token renewal/revocation,
real purchasing, spend or campaign publication was exercised. B14–B20 and the
remaining documented provider/customer implementation gaps are not complete.
