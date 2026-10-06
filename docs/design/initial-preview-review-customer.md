# Initial Preview To Exact Review

The existing immutable preview remains non-authorizing, including its original
`review_available=false` field and digest. A separate owned, no-store
`GET /initial-planning/previews/{id}/review-status` validates the original session
and current preview dependencies and returns its server-computed digest.
`request_available` means only that the configured interface can attempt financial
qualification. Both endpoints use the same configured optimization dependency as
ordinary approval and require its planning policy digest and environment to match.
`financial_qualification=not_checked` and `spending_authority=none`
are fixed. Missing configuration, generic forward-guard context, Meta adapter, live opt-in, or exact native
proposal makes the request unavailable; no production financial source is supplied.

An explicit customer click posts only `expected_preview_digest` to
`POST /initial-planning/previews/{id}/review`. The original owner session and CSRF
are required. The bridge performs actual configured catalog, qualification, and
exposure reads; it atomically binds the immutable preview origin to the exact
review. This request never approves or executes the review. Lost responses are
not automatically retried by the browser; bridge idempotency retains one origin.

The returned review is linked to `/app/optimization?workspace=…&review=…`.
Query values are untrusted lookup keys. The existing owned review API supplies
all displayed review fields, and the existing explicit checkbox, approval, and
execution actions remain separate. Workspace/session/objective/native-selection
changes clear preview readiness and the review link. Retraction is enforced by
the core forward guard, independently of whether a customer still has a URL.

Offline tests use actual customer APIs, database transactions, native HTTP adapters
with mocked transports, and explicitly named contract-test financial readers.
They do not establish a qualified production financial source or live readiness.
