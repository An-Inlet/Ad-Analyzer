# CRM Worker Push Authentication

The shared application now authenticates `/internal/pubsub/crm-events` before
constructing its processor. Cloud Run IAM remains an independent deployment
boundary; customer sessions, operator keys, IAP assertions and proxy headers never
substitute for the push identity. Hiding a route from OpenAPI provides no protection.

## Contract

Both nonsecret settings default to empty, which returns a generic 503 and prevents
processing:

- `AD_ANALYZER_CRM_PUSH_OIDC_AUDIENCE`: the exact HTTPS Cloud Run worker service URI.
- `AD_ANALYZER_CRM_PUSH_SERVICE_ACCOUNT_EMAIL`: the exact Pub/Sub push service account.

Requests require exactly one Authorization header containing a bounded compact
JWT with the Bearer scheme. The Google Auth library verifies its signature,
Google issuer, audience and time claims. Additional checks require exact audience
and service account email, Boolean `email_verified: true`, integer issue/expiry
times and a nonempty subject. Invalid identities return a generic 401. Exceptions,
claims and tokens are not logged or returned. Valid token reuse is allowed while
unexpired; the existing delivery idempotency boundary handles redelivery.

The verifier retrieves public certificates only from Google's fixed OAuth2
certificate endpoint. Its transport refuses alternate URLs and methods, disables
redirects and environment proxies, applies timeouts, bounds the response to 256 KiB,
and closes responses/clients on success and failure. There is no customer-provided
certificate location or credential provisioning.

The primary protocol reference is Google's
[authenticated push subscription documentation](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions).
The implementation uses the installed `google.oauth2.id_token.verify_oauth2_token`
contract, including its fixed Google OAuth2 certificate endpoint.

## Compatibility And Release Gate

Previously perimeter-only worker deployments must explicitly configure the expected
audience before release. Terraform passes the new default-empty
`worker_push_oidc_audience` variable to the worker and uses the existing push service
account email. The subscription's token audience remains the worker URI. Supply the
exact approved existing worker URI as the variable; deriving the environment value
from the worker resource itself would create a Terraform self-reference. No IAM
permissions or public access are added by this change.

The intended deployment must verify that the original signed Authorization bearer
reaches the application intact, that the configured audience matches subscription
and Cloud Run settings, and that Google push identity permissions are correct.
Stripped signatures fail closed; proxy headers are not a fallback. No infrastructure
was applied and no real Pub/Sub delivery, Google certificate fetch or IAM setup was
performed for this package. Terraform CLI was unavailable; static infrastructure
tests are evidence of wiring only, not a successful Terraform plan or validation.

## Offline Evidence

Focused tests: **102 passed, zero skipped**, covering worker authentication,
processor behavior, import ingress, existing IAP/API boundaries and Terraform wiring.
The PostgreSQL cases ran alongside SQLite. Whole-tree Ruff, mypy (316 source files)
and `git diff --check` passed. Full and hosted CI are not claimed.

Tests generate an ephemeral signing key and certificate in memory and exercise the
actual Google signature verifier through mocked HTTP. They reject tampering,
unknown signing keys, expired/future tokens, wrong claims, duplicate/oversized
headers, malformed configuration, certificate redirects and transport/stream errors.
A customer signs in through the actual session API and still cannot invoke the worker.
Resource cleanup and sanitized failures are asserted. Processor-only unit tests
explicitly override this dependency; separate authentication tests do not.
