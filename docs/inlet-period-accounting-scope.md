# Immutable Consented Period Accounting Scope

Review reproduced two defects on SQLite and PostgreSQL (six failures): a settled
account's spend could be omitted by a new or revised mandate on the same period
ledger, and unresolved holds in another currency were added as numeric micros.

The period ledger retains a scalar portfolio high-water. Without per-account
accounting it cannot safely replace or expand its account set. The first actual
consent now pins stable account IDs, platforms and external advertiser identities
for that period/environment. Every later revision, consent and admission checks
all persisted consented revisions under workspace/ledger serialization. Drafts
remain editable before first consent; competing draft consents cannot choose two
different sets. Changing connection generation does not itself change accounting
identity. Restoring the original set never resets spend, reservations or actions.
Even settled accounts remain in the original set. Supporting arbitrary in-period
account changes requires a separate immutable per-account accounting implementation;
this package deliberately rejects that unsupported operation.

Historical inconsistent consented sets fail closed; no existing accounting or
consent is rewritten. Current scalar data cannot reconstruct omitted historical
spend safely. Unresolved held reservations in another ledger currency block new
mandate work. No currency conversion policy is assumed. Same-currency prior-period
holds continue to count conservatively. Settlement and original late receipt
reconciliation remain separate from permission to admit new work.

Evidence: actual Google creation/authoritative settlement fixture records A spend60,
settles its hold, then rejects B-only replacement under the same cap100. Both new
mandate and revision paths are covered, including replacement during unlocked
settlement source IO and restoration without losing A's60. Draft editing, concurrent
PostgreSQL conflicting consents, and existing concurrent original claims are covered.

- Baseline:/tmp/inlet-period-accounting-before.log,6 failed.
- Accounting/consent/settlement/exposure suite:74 passed.
- Consent/account/concurrent claim checks:10 passed,2 SQLite-only skips.
- Final expanded accounting race checks:9 passed,1 SQLite-only skip.
- Ruff and configured mypy433 passed. No live provider calls or migration.
