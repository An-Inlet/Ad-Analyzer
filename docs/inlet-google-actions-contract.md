# B09 Google Search Action Preparation

The initial campaign matrix remains a proposed offline implementation boundary, not
owner approval to change live advertising. The existing live Google mutation function
still raises unconditionally. No customer route, worker schedule or configuration flag
can enable live writes from this package.

`GoogleState` binds customer/campaign/budget, standard Search, non-shared budget,
status, amount, negative keywords and observation time. `GoogleChange` accepts a
budget amount, pause/resume or reviewed negative keyword (exact/phrase), with unrelated
fields rejected. Preparation checks owned account and B08 generation, rejects stale or
unsupported state/no-op changes and stores an immutable B07 action and positive change
amount. Resource names and exact update masks are derived in a validate-only request
preview; caller-supplied arbitrary resource names cannot enter the operation builder.
Negative keywords join campaign/creative in the exact-owner-review policy.

Only the concrete in-memory fixture adapter can execute this worker. It reads state,
claims/reserves durably, reacquires locks, rechecks generation/current state and writes
B07's dispatch marker before the fixture side effect. Errors/timeouts leave an uncertain
record; there is no resubmission. Read-back must match the owned resource and intended
setting. A non-match is not proof of no effect. A match before mandate-period close
records the setting result but retains the reservation for future spend. Closing the
synthetic exposure window requires cumulative period consumption before settlement.
Neither matched settings nor historical correlation establish revenue causation.

Live B09 acceptance is still open: qualified provider current-state collection, actual
spending/exposure semantics, delayed reports, refreshed entitlements/source health,
transport validation/error classification and real read-back under an explicit mandate.
This release's exposure amount and observations are synthetic, never a zero-overage
promise. No 5/10/20% policy input grants spending authority. Compensation would be a new
reviewed/bounded action; past spend cannot be undone.

Official request-shape reference reviewed 2026-10-05:
[Google mutate resources](https://developers.google.com/google-ads/api/docs/mutating/overview).
Fixture coverage tests budget/status/negative-keyword preparation, review, mismatch,
reconnect generation, timeout-after-apply, read-back and held future exposure on SQLite
and PostgreSQL. B07 concurrency tests run alongside these. No new migration is needed.
