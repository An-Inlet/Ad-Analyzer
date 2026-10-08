# Account-Level Planning Customer Page

`/app/planning` is linked from the customer workspace and uses the actual owned
planning APIs. Customers choose a confirmed goal and their connected accounts, enter
milestone/product/constraints/assumptions and a past reporting period, save inputs and
generate descriptive plans. The confirmed goal supplies the ceiling/aggressiveness;
this page does not silently edit it. Account-level edits refuse to discard advanced
selections or comparison windows. Target selection UI remains pending exact receipts.

The page provides bounded lists/version/event pages, explicit historical selection,
consecutive comparison and version-artifact export. Customer decisions, reports and
withdrawals are explicit actions on the displayed exact document/action/digests and
current global event sequence. Corrections select an exact visible prior event; the
server checks current chain-head, authorization and CAS. A customer report remains
unverified. No action invokes advertising execution. New decisions/reports require a
current unexpired document; exact historical withdrawal retains server checks.

Requests retain one original cookie snapshot across the whole operation. Session
replacement rejects late responses and clears owned display data. Evidence expiry
updates the document label and disables new records. A lost mutation response retains
an in-memory recovery reference and blocks another mutation until explicit receipt
lookup; it never automatically re-POSTs. Recovery survives a same-customer session
refresh and workspace selection, not a browser reload. Reload users must inspect
retained history rather than assuming the previous mutation failed.

Actually run: `tests/test_planning_documents_browser.py`, actual HTTPS Chromium,
real session/CSRF/router/service/SQL and native MockHTTP on SQLite/PostgreSQL:

- First cohort:2passed19.34s (save/lost-response lookup/two versions/comparison/logout).
- Extended decisions, customer-applied report and exact retraction:2passed11.71s.
- Final original-session replacement during an actual read, clearing and authorized
  reread: **2 passed in14.34s**. Same journey asserts one plan, two persisted versions,
  three separate immutable customer records, and zero provider execution attempts.
  Actual committed create response is discarded in transport; lookup does not repost.
  Literal hostile customer text is displayed without injected nodes.
- Whole Ruff and mypy1054 passed; module syntax and diff checks passed.

Evidence `/workspace/inlet-evidence/20261008/planning-browser-{initial,records,session}`
logs/XML. This is the account-level Google native MockHTTP browser journey; three-platform
API coverage is documented separately. No live customer/provider qualification, expert
recommendation quality, target-selection browser acceptance, or Full-suite pass claimed.
Independent review and root integration remain separate gates.

## Independent Review Repairs

The initial6c812e8 review found three P2 issues; the follow-up fixes:

- Ordinary operations compare the prior displayed-session cookie fence before starting,
  including same-owner replacement between actions with no focus/visibility event.
  Refresh/Sign Out remain explicit intended session-management paths.
- A receipt404 is not treated as definitive failure. Pending state retains the exact
  original path/body/key and offers an explicit same-key retry only after lookup.
  Other mutations remain blocked; no automatic POST occurs. A late original commit
  and explicit retry return one stored plan. Unknown/5xx outcomes retain recovery.
- Editing preserves blank/null creative capacity and untouched exact reporting times,
  including sub-minute precision. Changed times are validated from form values.

Final actual HTTPS regression: **2 passed in13.93s**, both databases. The journey
holds the original create before server delivery, observes authorized receipt404,
then explicitly retries with the same body/key after delivering the late original;
it discards the committed retry response and recovers through lookup. One plan/two
versions remain. It also tests real same-owner session replacement both during and
between operations and an actual persisted null-capacity/precise-timestamp edit.
Evidence `planning-browser-repairs.{log,xml}`. Whole Ruff/mypy1054/node/diff passed.
Independent repair closure is pending; no live qualification is implied.

Independent repair review closed44163af with no remaining P1/P2 in the account-level
flow. Root merged the unchanged tested app/tests tree; `git diff --quiet 44163af HEAD
-- app tests` confirmed no source/test differences immediately after integration. No
redundant rerun was made. Target receipt UI and broader product qualification remain
separate. Session/recovery behavior is verified with local real HTTPS, not live customers.
