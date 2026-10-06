# Omnisend OAuth And Authenticated Brand Evidence

Checked 2026-10-06. **The two prior implementation blockers are resolved by current
first-party SDK source:** the authorization parameter is `scope`, and the authenticated
current-brand response contains a top-level, nonempty string `brandID`. This is source
contract evidence, not live provider qualification. No customer account/API request,
credential, grant, dynamic registration or provider mutation was performed.

## Provenance

Omnisend's [verified GitHub organization](https://github.com/omnisend) owns
[wp-omnisend](https://github.com/omnisend/wp-omnisend). Its current public `main` was
read at exact commit **`fdfc72021e90d3fb333e7c1b2d77017dc69f850d`**, committed
2026-09-24T12:57:34+03:00. Read-only local clone:
`/tmp/inlet-omnisend-official-wordpress`.

The source is a first-party consumer of the current API, with request/response
regression tests. It supplies the missing minimum identity shape; it is not a complete
OpenAPI response schema. Do not add guessed optional brand fields.

## Authenticated Brand Proof

- [Official endpoint reference](https://api-docs.omnisend.com/reference/get_brands-current)
  documents **GET `https://api.omnisend.com/api/brands/current`**, required
  `Omnisend-Version: 2026-03-15`, scope `brands.read`, and 400 requests/minute.
- [SDK brand reader, lines 96–110](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-connection.php#L96)
  sends that GET using the authorization supplied for the current connection.
- [OAuth connection, lines 335–369](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-connection.php#L335)
  obtains the OAuth access token, constructs Bearer authorization, reads the brand,
  rejects absent/empty/non-string `brandID`, and stores that returned brand identifier.
- [Response parser, lines 35–76](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-apiresponse.php#L35)
  directly returns the decoded success body. There is no `data` or `brand` wrapper.
- [Current request headers](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-apirequest.php#L16)
  set the revision and Bearer scheme.
- [Official OAuth tests, lines 363 onward](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/tests/Omnisend/Internal/OAuthConnectionTest.php#L363)
  exercise an authenticated current-brand read and retain its identifier. Other cases
  reject malformed brand bodies and missing identifiers.

**Implementation consequence:** Inlet may bind a grant to the exact returned `brandID`
and compare that value on later proof reads. Request neither a caller-selected brand
ID nor a Shopify-domain-derived ID. Do not issue POST/PATCH `/brands/current`: those
connect/change a merchant store and are unnecessary for this read-only integration.

## Authorization, Token Exchange And Renewal

[Official OAuth guide](https://api-docs.omnisend.com/reference/oauth) supports the
Authorization Code grant for revision 2026-03-15. Its table says `scopes`, but its example
uses `scope`. The ambiguity is resolved by the current
[SDK authorization URL builder, lines 49–59](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-oauthclient.php#L49):
GET `https://app.omnisend.com/oauth2/authorize` with `response_type=code`, `client_id`,
`redirect_uri`, **singular `scope` containing space-separated values**, and `state`.

The guide and [SDK token request, lines 149–178](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-oauthclient.php#L149)
agree on POST `https://app.omnisend.com/oauth2/token`,
`Content-Type: application/x-www-form-urlencoded`, with client ID/secret in the body.
Authorization-code exchange adds `grant_type=authorization_code`, `code`, and the same
`redirect_uri`. The guide shows JSON `access_token`, `refresh_token`, `expires_in`,
`scope`, and `token_type: Bearer`. No PKCE requirement was verified in these sources.

The guide's claim of non-expiring access conflicts with current SDK lifecycle code.
The [SDK refresh implementation, lines 121–145](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-oauthclient.php#L121)
uses the same token endpoint with `grant_type=refresh_token` and `refresh_token`.
Its [storage implementation, lines 185–202](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-oauthclient.php#L185)
honors `expires_in` and preserves the current refresh token if no replacement is returned.
[Official renewal tests](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/tests/Omnisend/Internal/AuthModeTest.php#L79)
cover rotation and omitted replacement. Inlet should honor explicit expiry and fail
closed on malformed responses, not assume immortality. No revocation endpoint was
verified; do not invent one.

## Least-Privilege Scope For Inlet

`brands.read` is documented for identity proof. `contacts.read` is documented by the
[contacts endpoint](https://api-docs.omnisend.com/reference/get_contacts), which also
specifies revision 2026-03-15 and cursor paging. Therefore Inlet's read-only requested
scope is **`brands.read contacts.read`**. The official WordPress plugin requests extra
write scopes because it connects stores and writes contacts/products; those are not
required for Inlet's reader and must not be copied. No partner account-creation or
session-write scopes are required.

## Remaining Boundaries

The official [LLM index](https://api-docs.omnisend.com/llms.txt) was accessible, but linked
`get_brands-current.md` and `oauth.md` returned web-reader internal errors. A single
executor read of the HTML docs was denied by its network proxy (403). No bypass was
attempted. The linked Postman collection also failed to render. The public official
GitHub SDK is an independent primary source and supplies the missing evidence above.

A full OpenAPI schema, actual partner-app provisioning, live consent/grant qualification,
expiry/refresh behavior under the granted client, canonical Shopify-customer matching,
CRM retention/deletion policy and runtime lifecycle scheduling remain separate work.
These findings authorize no live operation. The research made no runtime change; the subsequent implementation is documented in
[inlet-omnisend-runtime.md](inlet-omnisend-runtime.md).
