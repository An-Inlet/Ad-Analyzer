# Customer Budget Mandate Preparation

The ordinary configured app can prepare and consent a bounded existing-campaign
mandate independently of unavailable provider-write runtimes. It uses the current
original customer session, CSRF, current goal, actual owned native GET catalog and
separately configured operating policy. Customer input is total budget, named
aggressiveness and scope; the server supplies the technical limits. Consent records
conditional local authority. It supplies no exposure qualification or spend headroom.

Install the separate nonsecret JSON policy using
`AD_ANALYZER_BUDGET_MANDATE_POLICY_PATH` and
`AD_ANALYZER_BUDGET_MANDATE_POLICY_DIGEST`. `BudgetMandateOperatingPolicyV1` is the
strict schema; every rule number is required. It pins the exact existing planning
profile digest, environment and USD currency/exponent. There are no installed
production policy values or invented defaults. Canonical rules are ordered
conservative, balanced, assertive; each percentage is explicitly configured.

Policy is cached per process path/digest identity. A deployment must roll out
policy/profile settings coherently and drain old processes. A changed file at the
same path is not hot-reloaded; settings are not distributed revocation. Existing
mandate revocation remains independently available. Prior profile and preview v1
hashes are unchanged.

POST `/api/customer/v1/workspaces/{workspace_id}/initial-planning/budget-mandates`
prepares an exact draft, plus immutable minimal provenance atomically in0079.
POST the same prefix `/{mandate_id}/consent` re-reads owned native state and verifies
original-session authority, current goal, exact policy/profile, selection,
revision and preparation digest. An operating-policy change requires a new review
even when it happens to compile to identical money amounts. Existing accounting
period/account-set/held exposure and live-paid-work guards remain in force.

The preparation table contains no credential, native HTTP payload, performance
snapshot or session secret. It is protected authority provenance with an owned
revision FK and immutable DB triggers. Strict export binds scalar scope and digest;
nonempty migration downgrade refuses to erase it. Existing mandate revisions and
consent records are reused. A final authorization failure rolls back the draft,
ledger creation and provenance together.

Initial native coverage remains Meta/USD/daily budget only. Other supported launch
platforms still require corresponding read-side assembly; no product scope changes
are implied. Provider execution qualification, exposure, exact action/creative
review, activation and live verification remain separate requirements.

Offline acceptance uses actual imported history, normal goal edit/preview/confirm,
configured API calibration, GET-only HTTP mock native catalog, zero prior production
mandates and normal API prepare/consent/retry/v2 preview on SQLite and PostgreSQL.
`tests/budget_mandate_fixture.py:first_customer` is the reusable no-prior-authority
fixture. Browser acceptance is owned by the dependent UI package. It is not a claim
of provider live verification or approved empirical production policy values.
