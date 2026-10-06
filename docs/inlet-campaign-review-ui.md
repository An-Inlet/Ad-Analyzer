# Rendered Campaign Review

`/app/campaign-review` is a separate customer page linked from the existing portal.
It uses the current customer session and workspace roles, with a bounded list of the
100 most recently revised drafts. It does not create a provider campaign or authorize
spending.

The page displays the saved name, platform, objective, account, connection, mandate
revision, landing page as literal text, exposure down to micros, schedule, audience,
supplied copy, call to action and exact review digest/revision. Supplied static images
load only from the workspace-scoped authenticated media endpoint. Failure to display
the validated image blocks the approval button. TikTok video validation remains an
explicit offline approval blocker. Publication prerequisites remain separately visible;
there is no publication control.

An owner/admin must acknowledge the displayed revision before approving its exact
revision/digest. A viewer can read but cannot edit or approve. The API remains the
source of authority: stale approval, changed bindings or revoked permissions fail
closed and clear the old preview. In-flight selection and mutation controls are
serialized and response generation checks prevent an old workspace response from
becoming the current review.

The form edits supplied name, destination, exposure and platform-specific literal
copy. It preserves the displayed account, mandate, schedule, audience and media.
Saving appends a revision, clears approval and reloads the exact new preview. Text is
rendered with DOM textContent; no supplied markup is executed and no landing URL is
fetched.

Validation: `pytest tests/test_campaign_review_ui.py tests/test_campaign_review.py
 tests/test_customer_portal.py -o addopts='' -q` with disposable PostgreSQL passed
53 tests, with one intentional SQLite skip for the PostgreSQL-only row-lock race.
Ruff and mypy (288 files) passed. Real Chromium against localhost HTTPS and the actual
customer APIs/database covered both SQLite and PostgreSQL: private image decoding,
failed image response blocking approval, exact Google revision approval, edit invalidation,
stale approval rejection after a concurrent edit, literal markup rendering and role
revocation. Identity verification and advertising data are offline fixtures; browser
fetch is not replaced. Full and hosted CI remain pending.

Remaining B14 work includes draft creation/media upload selection UI, richer audience
and schedule editing, video validation/processing, production private media lifecycle,
and concrete reviewed PublishPlan mapping. The screen is an offline content review,
not a provider placement preview or live-qualified publication journey.
