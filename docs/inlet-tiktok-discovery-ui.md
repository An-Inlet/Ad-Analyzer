# TikTok Customer Discovery UI

The execution page has a separate read-only TikTok discovery section. Customers
explicitly load owned accounts, choose an identity type, and request observations.
It consumes the versioned customer projection; provider identifiers and publication
proofs are not browser inputs. Business Center discovery has an explicit unavailable
state until an owned selection can be verified.

Reported identity status and permissions do not authorize publication. Missing or
null event lists remain unknown, including the possibility of delayed reporting.
Traversal counts and bounded display truncation are separate. Provider labels are
rendered with `textContent`, never HTML. Workspace/session resets erase results;
local account/type changes invalidate delayed responses. Existing review, creative,
publication, and approval controls retain their independent behavior.

Validation uses the actual configured API, original-session login, owned vault and
source, and low-level MockHTTP transports. The HTTPS browser journey passes on
SQLite and PostgreSQL: 21 observations with 20 displayed, explicit Business Center
unavailability, unknown events, and revocation during a GET that clears all output.
Exactly seven provider GETs cover two complete traversals and the interrupted read;
Business Center selection performs none. Financial evidence builders, provider
writes, reviews, attempts, receipts, and reservations remain at zero. No runtime
getter override or execution-record seed is used.

The focused JavaScript test covers exact request shape, contract rejection, literal
label rendering, unknown events, and stale selection/session output. Existing
configured TikTok publication browser compatibility is also checked independently.
No live provider qualification, publication permission, or tracking readiness is
claimed by this discovery feature. Native execution qualification remains separate.
