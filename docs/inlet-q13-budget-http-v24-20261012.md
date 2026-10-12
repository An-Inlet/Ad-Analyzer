# Q13 Mocked V24 Budget HTTP Protocol

Continues 467a32b4 on local `codex/inlet-w1-followup`. Adds a bounded read-only
Google Ads v24 HTTP interface and complete transcript validation. This is mock
qualification, not authenticated provider evidence or live activation. The
[contract and official references](design/q13-budget-http-v24-20261012.md) record
field/version semantics and the separate admission boundary.

## Implemented Behavior

Immutable tickets bind owned workspace/connection/account, full source digest,
privacy revision, version/action, nonce and original deadline. Three server queries
use a fixed customer-scoped POST endpoint and canonical bodies. Ordered pages retain
raw response commitments, body digests, request IDs, timestamps and complete cursor
chains. Decoding preserves explicit zero/false and rejects missing fields, foreign
resources, broken joins, unknown fields, duplicates, loops and inconsistent counts.
Documented optional v24 int64 metadata is bounded; original raw responses are retained.

The runtime accepts only an explicitly injected exact httpx.MockTransport. Redirects,
proxies and retries are disabled; bytes/pages/rows/time are bounded; source/privacy/
authority are revalidated around IO, including failures. Invocation-local transport
identity checks refuse replacement. Context credential values are excluded from repr
and serialization, HTTP logging is private and errors are fixed safe strings. Tests
use synthetic credential strings only.

`INLET_CUSTOMER_GOOGLE_BUDGET_HTTP_MODE=disabled` remains the default/example.
The only optional mode is mock_http. No network factory, live mode, vault lookup,
refresh or customer route wiring exists. Packets state mock_http, provider_authentication
not_verified and implementation not_assessed. Old v22 proof/event parsers reject them.
Existing fixture UI/history/exports remain unchanged. HTTP 200 and request IDs do not
establish provider authenticity.

## Checks Actually Run

Frozen evidence: `/workspace/inlet-evidence/20261012/q13-http-v2401/`.
Manifest SHA-256 `2959384bf56c0e28764be1461f243824864ffd89328374aaa6ff63c20c07832c`.
All 10 commands passed; 1,904 source hashes verified:

- Whole-repository Ruff, configured mypy (1,587 files), exact collection and diff.
- 39 HTTP component tests: exact transcript/zero, 31 refusal cases, six tamper cases,
  and disabled/live-mode/subclass rejection.
- Existing Chromium historical renderer regression.
- Assembled request/configuration/recovery API and browser cases on SQLite, then
  the same two cases on PostgreSQL.

All 44 selected tests passed without skips. No interruption, source drift, kill
escalation or surviving test child was recorded. Process-duration sums: static 21.918s,
component 13.365s, SQLite 94.580s, PostgreSQL 111.613s. The qualified summary binds six
retained synthetic API/browser/route artifacts by hash. One frozen attempt; no failed
checks or retries. Disconnect notifications did not interrupt the package: commands
and filesystem remained available, frozen hashes matched and PostgreSQL continued;
no completed check was rerun. No full-suite or live-environment result is claimed.

Independent source review closed after fixing checked-versus-used transport identity.
Three replacement tests cover context resolution, authorization and post-read changes,
requiring zero substituted calls and zero original IO for pre-IO replacements. Final
evidence/docs review is recorded in the local commit binding.

## Launch Gates And Next Package

Next offline gap: an explicit v24 reader-version/service admission contract for
storage, history, receipts and exports. Preserve mock_http/not_verified throughout,
keep v22 records immutable, and qualify source/privacy, current identity, revocation/
erasure, head/CAS and receipt recovery on both databases. Never coerce the new packet
into the old injected_fixture envelope. This supersedes the previous status-only
priority following the latest delegation.

Authenticated owned credential/source coordination and real transport qualification
remain absent and require separately authorized live setup. V3 remains default;
V6/V7 remain release-unqualified. INLET-REL-20261012-01 stays open: these serial passes
do not diagnose its original expiry or qualify concurrent generation/capacity.
The six [expert usefulness decisions](inlet-owner-quality-gates-20261011.md), unfinished
Q01–Q16 work, commercial terms, live identity/payment/storage/provider setup,
intended-environment operations and customer pilots remain launch gates. Hosted checks,
merge and deployment retain separate authority requirements.

No push, PR, hosted CI, merge, deployment, live provider/model/payment call, actual
credential operation, advertising write or spend occurred. The webpage remains
owner-managed. Inlet is not yet a live-qualified purchasable release.
