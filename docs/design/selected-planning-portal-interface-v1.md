# Selected Reporting Inputs In The Planning Portal

Proposed next customer-application package after private v4 persistence tests.
The public marketing webpage remains outside this work.

Keep the production default planner v3. An authenticated, no-store planning
capability read must reflect the actual server-owned configured canonical policy;
UI visibility is descriptive and grants no authority. Selected inputs appear only
when the private v4 service is configured. Existing v3 input JSON remains unchanged.
The server still validates every persisted selector and rejects unavailable policy.

For each chosen advertising account, allow an explicit retained capture ID from
Reporting Reads, with the option to provide none. Never choose latest, reuse a
capture from another account/workspace/session, or turn a blank field into observed
zero. Save exact account/capture pairs; an explicitly enabled v4 plan with no chosen
captures serializes an empty selection tuple, distinct from omitted legacy input.
Edits display saved pairs and require review after account/window changes. Changing
workspace or original session clears unsaved choices and pending mutation state.

The reporting page may hand off exact receipt identifiers to the planning editor
only after a current original-session check, with visible review before save. No
automatic plan generation or repeated acquisition POST is permitted. Until that
handoff is implemented and tested, retain honest manual receipt-copy wording.

Qualification uses actual TLS browser→API→saved input→paired reader/composer→SQL
version; only provider transport is injected. Cover both a chosen capture and
explicit absence, cross-scope rejection, original-session changes, lost-response
same-key recovery, exact saved pairs and immutable output. Policy recognition or
UI controls alone do not constitute deployed availability.
