# Original-receipt Google budget owner discovery

This slice adds POST `/planning/google-budget-owners` only. It does not add input
fields, actions, native setting instructions, spending authority, UI, or a public
policy switch. The ordinary configured service factory must select exact canonical
private V5; default V3 refuses discovery.

The customer supplies an account, original composite catalog digest and reporting
window. Original owner/session authentication, CSRF, paid/source/privacy gates and
existing strict receipt loading establish one original retained catalog. Discovery
performs no provider reads, receipt cleanup, commit or insert. All reporting
instants are compared in UTC. The complete bounded result is constructed before
final source/paid/authority checks; receipt expiry is checked again after the read
context finishes. No lifetime is extended.

Each returned option names its representative and all affected campaigns, original
observation interval, current daily amount and currency, two evidence digests and
an opaque original-authority selection commitment. Its amount is an observation,
not a total spending cap or economically qualified instruction. Available means
eligible returned options; it does not claim complete shared-budget inventory when
other owners are ineligible. Unavailable explicitly requests fresh targets/review.
More than20 eligible options or a response over1MiB fails without truncation.
No raw session/actor binding is serialized or logged.

## Authority and strict-boundary review repairs

Independent source review found and closed three pre-qualification issues:

- Limit ValueError normalization to pure reconstruction. Unexpected provider and
  clock callback errors remain unchanged instead of becoming ordinary receipt409.
- Reject copied `review_only=1` before Literal coercion, including model instances.
- Resample strict-aware expiry after final context authorization/SQL waits.

Actual endpoint callback tests and copied-model regressions cover the first two.
Controlled receipt expiry passes expiry+1s to the original `_load` through the real
endpoint exactly once, using the actual stored receipt. This is a controlled
loader-time fault, not a natural end-to-end wall-clock expiry demonstration. It
changes no authentication, source or paid clock and disables no validation.

## Evidence and fixture boundary

Evidence root: `/workspace/inlet-evidence/20261011/google-budget-owner-discovery`.
The new isolated fixture uses the existing actual Common Basis APIs and Q06
paginated MockHTTP read shape. It changes no default shared fixture or historical
artifact. Parent metadata prerequisite689f56d makes the genuine Google metadata
read request/retain campaign status; old receipts missing status remain ineligible.

- `sqlite-01`: 4passed/1failed. The session probe logged in a different subject and
  correctly got foreign-workspace404. Corrected to the original q16-owner subject.
- `sqlite-02`: 6passed/1failed. Advancing the entire service clock reached the
  existing paid snapshot freshness gate (402) before receipt expiry. Retained as
  a failed expiry-target attempt, not counted as separate paid qualification.
- `sqlite-03`: 20passed,13PostgreSQL deselected,39.44s:13actual API cases plus7pure.
- `both-04`:26actual SQLite/PostgreSQL cases passed, zero skips/failures/errors,156.03s.
  The13SQLite observations overlap sqlite-03; the7pure cases are not repeated.

The actual matrix covers eligible shared owner/full members, partial membership,
window/digest mismatch, same-owner replacement session, authenticated foreign owner,
controlled receipt expiry, default policy, invalid copied receipt evidence, privacy,
CSRF, and unexpected identity/clock callbacks. Successful replay has identical
public response and no additional native calls. Every case preserves retained plan
rows/request receipts and relevant catalog/financial/execution counts.

Public synthetic catalog/discovery outputs and hashes are retained separately;
no private full owner witness or authentication inputs are written to artifacts.
The endpoint is not a browser/UI or full Q06 quality qualification.

Final whole Ruff and configured no-path mypy (1443 source files) passed;
`git diff --check` passed. `artifacts/manifest.json` retains eight public synthetic
catalog/discovery artifacts from available/partial cases across both databases.
The disposable PostgreSQL fixture uses isolated schemas; existing databases,
workers and frozen evidence were not reset or modified.
