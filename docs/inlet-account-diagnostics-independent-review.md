# Account Diagnostics Independent Review

Reviewed candidate `c6d72b6` on isolated branch
`codex/inlet-diagnostics-review`. Scope: customer diagnostics endpoint, concrete
native-reader assembly, original-session/owned-account boundaries, browser flow,
date bounds and safe response projection. No live calls or Full run.

## Concrete Finding And Repair

P2: a customer intent spanning `0001-01-01T00:00:00+14:00` through the next day
passes the positive/366-day duration test but cannot be represented in UTC. Google
performs provider reads before account-local date conversion raises an uncaught
`OverflowError`. Reproduced on SQLite and PostgreSQL. Meta/TikTok accepted the same
unrepresentable intent; their inventory-only responses did not exercise Google's
failing date conversion.

Baseline `/tmp/inlet-diagnostics-review-before.log`: six failing assertions,
comprising two actual Google overflow failures and four desired input-rejection
assertions for the social readers. These are not six identical server defects.

The shared customer observation validator now checks UTC representability with a
one-day margin at Python datetime's representable edges. This leaves room for any
account timezone and the exclusive-end conversion. Customer request validation
returns 422 before assembling a transport. The internal account observation request
uses the same guard. The existing positive/366-day and past-period checks remain;
there is no new product history or retention policy. Ordinary 1990 dates remain
valid. The historical mandate/native v1 request schema and its expected hashes are
unchanged. Minimum and maximum datetime edges have focused contract coverage.

## Other Reviewed Boundaries

- The route uses `MutationPrincipal` for the original cookie/CSRF pair and binds
  that exact session through `bind_authority`. Native context acquisition rechecks
  owned account/generation, owner membership, billing and data-sync control around
  IO, including after OAuth. The route rechecks again before projecting a response.
- Authorization transactions close before token exchange/native reads. New provider
  contexts cannot be supplied by the browser. Concrete endpoints, vault ownership
  and platform-specific readers remain the existing implementation.
- The default diagnostics switch prevents transport construction and provider IO.
  The response explicitly carries no qualified spending caps or reporting watermark;
  the projection exposes bounded counts and static explanations, not native resource
  names, token material or raw monetary fields.
- Browser context changes increment an epoch and clear output. Cookie/principal
  checks surround requests; returned text is rendered with textContent. The real
  browser fixture checks delayed/lost responses, logout, role loss and no automatic
  retry. This is bounded evidence, not a broad security certification.

No additional P1/P2 finding was established within this review's scope. The date
failure is repaired rather than hidden behind a generic server error.

## Checks

Exact targeted API baseline above. Final diagnostics contracts, API, native assembly,
UI and real browser tests, plus full-tree Ruff/mypy/whitespace results, are recorded
in the delivery PR. Historical serialization hash assertions are included. All
provider requests in these tests use fixture transports; none are live qualification.

Final diagnostics contracts/API/native assembly/UI/real-browser suite: **158 passed**
in 145.74s (`/tmp/inlet-diagnostics-review-final.log`). This includes both configured
databases, all three provider fixture transports and unchanged historical hashes.
Full-tree `ruff check .`, configured mypy (617 source files), and diff whitespace
checks passed. No new Full was run.
