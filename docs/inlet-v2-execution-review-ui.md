# V2 Execution Review UI

This frontend package consumes the frozen `bf29197` options and handoff contracts.
It adds no API, financial source, consent, migration or runtime configuration.

A native V2 preview offers an explicit read of separately consented execution plans.
The customer chooses a named account/scope; the page shows exact USD total,
per-plan and positive-change limits, with the server's time zone and end-exclusive
period. No option is selected by default. Truncated results are labelled. Missing
runtime, absent separate consent and incompatible existing consent have fixed,
sanitized explanations and an Existing Campaigns link.

The POST contains only expected_preview_digest, mandate_id and mandate_revision.
Its response must match that selection and policy commitment. Success links to the
ordinary owned exact review page; approval and execution are separate actions.
V1 retains its existing review-status and review endpoints. No V2-to-V1 cast or
promotion of planning consent is performed.

Goal/objective, campaign, workspace, budget and native selection edits clear the
prior preview/options. Async responses are fenced by the existing UI epoch and
session-cookie checks. Late options after goal edits or a session change cannot
repopulate owned values. Refreshing choices clears the old review link; unknown
POST outcomes are not automatically retried. Names are rendered with textContent
or Option text, never HTML.

Verification: three focused frontend tests cover strict response/intent validation,
V1/V2 rendering, exact POST fields, no consent/approval/execution requests, late
results after goal edits and session clearing. The actual configured TLS browser
suite passes on SQLite and PostgreSQL for both available and absent separate
execution consent (four cases). It uses backend `063243c`'s actual imported
history/configured native adapters, API-created original session, real planning
consent and real separate execution-consent APIs. There are no runtime getter
overrides or seeded execution reviews, attempts or approvals. Only provider HTTP
is replaced with MockTransport and explicit contract-scenario evidence.

The browser creates a fresh capture/calibration/native V2 preview, reads the actual
options endpoint, makes an explicit selection, submits the exact handoff and opens
the normal optimization page for separate approval. Database assertions verify
exact preview amount, retained V2 proof, distinct consented mandates on one ledger,
one review/approval, zero attempts/reservations and zero provider writes. Missing
execution consent displays the fixed recovery reason and cannot submit a review.
This is offline contract qualification, not live financial-source qualification.
Final combined cohort: 15 passed in 84.63 seconds. Whole-repository Ruff, scoped
mypy for the three affected Python test modules, Node syntax checks and
`git diff --check` passed.

The first test run exposed two fixture assumptions: its static allowlist omitted
the optimizer's session-automation module, and it selected a random first mandate
instead of the API-created planning mandate. Both were corrected without changing
production authority checks or weakening assertions. Existing V1 planning and
first-budget TLS checks also pass (eight both-database cases). No Full, remote
operation, credential access, recording or advertising mutation was performed.
