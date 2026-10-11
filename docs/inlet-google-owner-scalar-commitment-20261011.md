# Original Owner Commitment From Retained Scalars

On integrated pure input binding `ed594ad` (author `83a6107`,39 focused tests
passed and independent review CLOSED), extract the original discovery commitment
into `google_budget_owner_selection.original_owner_selection_id`. Its scalar
arguments are actor ID, session digest and authenticated epoch plus exact original
source and witness. Current discovery delegates without changing the fingerprint
payload. Future historical validation can use validated retained receipt scalars;
it must not construct an ORM principal or claim current authority.

The new helper validates strict IDs and a nonnegative exact integer epoch. It has
no database, provider, current-clock or paid/session eligibility lookup. The
pre-extraction fixed fixture hash is unchanged, and retained scalar arguments
remain unchanged when a separately held current principal changes.

## Checks Actually Run

-16 focused pure tests passed: new scalar/golden/coercion checks plus existing
 discovery commitment tests. Zero failures, errors or skips.
- Whole Ruff and configured no-path mypy passed over1,447 files, also covering
 integrated standalone input binding and receipt discovery.
- Independent final review CLOSED exact `afde942` with no P1/P2.
- Initial scoped Ruff import-order finding corrected before tests; no product
 guard or golden value changed. No database/browser repeat was needed for this
 exact byte-preserving extraction.

Evidence: `/workspace/inlet-evidence/20261011/google-owner-scalar-commitment/`.
No history consumer is activated by this extraction. The separate historical
linked-receipt wrapper and atomic input integration are next. No live, remote,
provider, upload, merge, deployment or native setting action occurred.
