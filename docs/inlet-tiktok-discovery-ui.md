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

The focused JavaScript test covers exact request shape, contract rejection, literal
label rendering, unknown events, and stale selection/session output. Configured
API/HTTPS acceptance is pending the backend fixture freeze; this frontend checkpoint
does not claim that journey has passed. No live provider calls or writes are enabled.
