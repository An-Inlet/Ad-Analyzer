# Operational Reported Feedback Customer Surface

This consumer is separate from the initial-preview exact-review handoff. The new
`/app/reported-comparison` page is reachable from Your Workspace and links to
Measurement History and Initial Preview. It does not change the 0076 page or its
approval behavior. No production policy parameters are supplied.

All API routes are under
`/api/customer/v1/workspaces/{workspace_id}/reported-feedback`:

- `GET /options`: current original-session owner; bounded recent owned Meta
  campaign-budget action choices resolved through the actual current anchor, and
  current same-session unadjusted initial previews validated by their owned reader.
  Explicit server comparison/feedback policies are displayed, never accepted as input.
- `POST /comparisons`: frozen ComparisonIntentV1 (action/goal IDs, revision and
  explicit reported-event CPA objective). Original session and CSRF required.
- `GET /comparisons`: at most 20 recent same-original-session requests, freshly read.
  Supports recovery from uncertain responses without automatic mutation retry.
- `GET /comparisons/{request_id}/status` and `GET /comparisons/{request_id}`:
  current owned progress/detail. Detail commits the service's immutable local derived
  assessment/dependencies; it performs no provider acquisition or advertising mutation.
- `POST /comparisons/{request_id}/reobserve`: explicit new acquisition request after
  an insufficient comparison, retaining the original opportunity. No policy/proof input.
- `POST /previews`: frozen FeedbackPreviewIntentV1, comparison and baseline IDs only.
- `GET /previews/{preview_id}`: owned current result; no cached proof accepted.

The UI shows both local-date windows, reported spend/events/CPA (null is
Unavailable), missing dates, actual acquisition times, revision agreement,
configuration dispatch/observation bracket and unsettled-correction warning. It
states that unseen external edits, delivery onset and causal lift are unknown.
An insufficient result cannot enable the update action. Re-observation is explicit;
there is no background customer-page polling or implicit acquisition replay.

An updated preview displays the unadjusted baseline, bounded change, proposed
amount, both CPAs, distinct original-action count, exact applied policy parameters
and expiry. It is recomputed from current contributions rather than compounding
an earlier adjusted preview. Review handoff and spending authority remain unavailable.
Workspace, original-session, input and selected baseline changes clear affected
state; asynchronous replies are fenced by the current UI epoch and original cookie.

Tests distinguish actual API/SQLite/PostgreSQL receipt admission and default-off
HTTPS behavior from controlled-projection browser rendering tests. Complete actual
Meta fixed-window acquisition → comparison → updated preview qualification belongs
to the composed core/acquisition acceptance run after those dependencies freeze.
