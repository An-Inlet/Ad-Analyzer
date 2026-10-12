# Q13 Fixture Observation Entry Contract

From ac4b62ab: the assembled app already reads immutable budget observations and
receipts, but has no customer acquisition entry point. Close only that offline gap.

- POST `/{plan_id}/budget-observations` accepts expected version/event sequence,
  exact document/action digests and request key. Workspace/plan come from the path;
  no account, evidence, query, URL, profile, provider timestamp or callable is accepted.
- Default mode is disabled. Explicit injected_fixture mode, exact configured V6,
  and an installed in-process immutable GoogleBudgetFixture are all required.
  The fixture contains a fingerprint of the complete exact ExecutionAccount/source,
  workspace and privacy revision,
  the pinned extraction profile and bounded raw selected pages. It has no transport.
  A setting alone does not install a fixture or enable production acquisition.
- The existing service owns authorization, paid entitlement, scope/goal/source/privacy,
  head and event CAS, final authority and immutable receipt publication. Check runtime
  configuration before acquisition, each fixture page and before/after append. Replacing
  a bundle during a request refuses. No relaxed ownership or deadline checks.
- Disabled POST, including replay, refuses. Existing receipt/history GETs remain
  available under current authorization. No new invalidation API or automatic job.
- Browser acquisition is separate from customer application reports, limited to a
  displayed current Google DAILY shared-budget hypothesis. Explicit synthetic wording
  and acknowledgement; capability is descriptive, never authority. Existing pending
  request mechanism retains the exact body/key across ambiguous responses and scopes
  recovery to the original signed-in customer/workspace. No automatic retry or read.
- Fixture acquisition intervals measure replay, not provider observation freshness.
  Provenance remains injected_fixture, implementation/current reliance not_assessed,
  and comparison never establishes spending compliance, implementation, causality or lift.
- Existing erasure/archive/history behavior and legacy customer reports remain intact.
  No transport credentials, provider/model calls, live operations or broader platform work.

Qualification: actual assembled app on SQLite then PostgreSQL; disabled/missing bundle,
invalid mode, wrong policy/scope/privacy, CSRF/extra-evidence refusal, disable/replacement/
revocation during reads, rollback after insert when disabled, exact replay/conflict and
historical recovery when disabled. Actual HTTPS Chromium journey with real API commit,
forged POST authority, a lost receipt response, forged receipt actor, same-key
recovery after disable, and stale POST refusal. Re-run
existing retained service history/erasure and V7 customer-report correction coverage.
Use the frozen, bounded single-heavy-slot runner; retain first failures and unrun phases.

Review: existing failure_review accepted the interface with these gates, exact fixture
binding, immutable raw pages, timestamp caveat and late-disable/stale-browser coverage.
This is not production Q13 readiness or V6/V7 release qualification. All existing owner
decisions, no-push/hosted/live/deploy/spend gates and INLET-REL-20261012-01 remain open.
