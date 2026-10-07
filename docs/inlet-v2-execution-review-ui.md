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

Verification at the frontend checkpoint: three focused tests pass, including
versioned response/intent validation and DOM/fetch unit doubles exercising V1,
V2, exact POST fields, no consent/approval/execution requests, late-result rejection
and session clearing. Node syntax, Ruff and focused mypy checks also pass.
These are frontend checks, not real API/TLS acceptance. Actual configured
SQLite/PostgreSQL browser acceptance waits for the backend service/fixture freeze;
no runtime getter override or seeded execution records will substitute for it.
