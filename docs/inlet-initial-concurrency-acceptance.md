# Initial Automatic Start Adverse And Concurrent Acceptance

Test-only successor to `4ec67ee`, isolated branch
`codex/inlet-initial-concurrency-acceptance`. No production change or root/frozen
qualification artifact change. Tests use actual configured preview/native HTTP
fixtures and original customer Start; no approval, candidate result, admission or
execution attempt is seeded.

## Exact Coverage

`tests/test_initial_rule_acceptance.py` exercises:

- **Stale authority:** after actual Start, revoke its original mandate. The former
  consent cannot authorize a later worker action; no admission, approval, attempt
  or provider POST results. This case specifically covers consent invalidated by
  revocation, not an assertion that every possible consent-revision race was tested.
- **Spent budget:** advance the existing owned ledger's spend high-water to its
  complete50000000micros approved allocation before worker admission. No approval,
  admission, attempt or provider POST results. Fixture money is not production policy.
- **Competing workers:** two independent PostgreSQL worker transactions start at a
  barrier for the same original Start. Outcomes are exactly completed/not_due;
  one consumed origin, one admission, one attempt and one provider POST, with zero
  human approval rows. SQLite explicitly skips this row-lock concurrency assertion.
- **Populated0085 refusal:** invoke the actual0085 downgrade using Alembic Operations
  against the test's real retained Start graph; it refuses deletion and preserves
  the Start commitment on both DBs. This is an actual migration-function refusal,
  not a full populated backup/restore drill or every predecessor migration cycle.
- **Configured maintenance:** use the pinned initial policy/source configuration and
  ordinary `run_configured_session_automation`, not a replacement runtime getter.
  It emits one admission/origin/attempt/POST with zero human approvals. The fixture
  supplies the same fake identity provider to the direct worker identity boundary.

The positive fixture explicitly chooses120second native/preview lifetimes before
producing evidence, matching the existing positive Start test. Ordinary30second
production defaults are unchanged and have separate expiry evidence. Worker cadence
and lifetime are test policies, not registered launch defaults.

## Complementary Author Coverage

`tests/test_initial_rule_start.py` (mode unknown) retains the original attempt/fence,
returns an uncertain provider result, then Stops and erases the candidate before
reconciling the original target state. Its held reservation and exactly one POST
remain. That case belongs to the initial implementation author's validation;
this package does not claim a new rerun. The author's separate HTTPS normal and
lost-Start-response journeys, original-session/late-options checks and30second
expiry cases are recorded with `9e3ea5a`; no tests are duplicated here.

## Recorded Results

Initial -x attempt:3passed1expectedskip, then configured maintenance failed because
only the API identity boundary had a fake provider. The actual maintenance entrypoint
uses the identity factory directly. Added a fixture-only identity substitution;
no runtime factory or authorization bypass. Evidence:
`/tmp/inlet-initial-acceptance-first.log`,1failed3passed1skipped23.17seconds.

Final complete narrow suite: **9passed,1expectedSQLiteconcurrencyskip149.94seconds**,
`/tmp/inlet-initial-acceptance-second.log`. Both database variants use isolated
schemas in disposable `inlet_oct07_next_integration_ci`; the frozen Full database
was untouched. Command: `python -m pytest -x -ra tests/test_initial_rule_acceptance.py
--tb=short --durations=10`.

Whole Ruff and prescribed mypy934files passed; mypy log
`/tmp/inlet-initial-acceptance-mypy.log`. No Full, hosted retry, live provider,
credentials, remote push, deployment or merge. Parent's unknown provider and
configured HTTPS results remain separately attributable; focused passes do not
qualify the full assembled artifact.

Strengthened positive cases explicitly assert one `InitialRuleAdmissionOrigin` as
well as one admission/attempt/POST and zero approvals. Affected maintenance bothDB
and PostgreSQL competing-worker rerun: **3passed7deselected131.58seconds**,
`/tmp/inlet-initial-acceptance-origin.log`; no skips in that subset. Whole Ruff/mypy
were repeated successfully after the assertion; final diff check passed.
