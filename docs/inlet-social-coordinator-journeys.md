# Durable Social Creation Journeys

The dependent package starts at coordinator4c103f7 and merges optimization PR135
cb416a8 without editing coordinator contracts, models, migrations or authority code.
`ScopedProviderMediaReader` bridges the existing private store to real social HTTP
transports: it selects the media row by workspace and ID, verifies the stored bytes,
revalidates actual image/video content and compares every reviewed binding field.
TikTok test assets are actual bounded FFmpeg-generated MP4s plus separately uploaded
PNG covers; no fake media reader or bypass of B14 source approval is used.

The integration tests provision native scoped Meta/TikTok connections, a real
current B14 campaign review and owner approval, and separately revised/consented
production-execution policy. Server-only qualification/exposure callbacks are
explicitly labeled `contract_test` scenarios. They do not qualify live provider
combinations or claim a real native spending bound. The coordinator's source_current,
owner, entitlement, current-generation, consent, ledger and exact approval checks
remain in the path; no fixture authority replaces them.

Each provider's five-step graph runs through prepare_creation, approve_creation,
create_run, claim_creation_step, execute_claim and read_owned_outcome_receipt using
real Meta/TikTok HTTP serializers and MockTransport responses. Upload requests carry
actual private bytes; creates remain PAUSED/DISABLE. Persisted normalized receipts
retain the original scope, attempt and fence and cannot claim a delivery interval.
The complete paused graph keeps its future exposure reservation held.

Timeout-after-effect tests preserve the unknown original attempt and reservation,
without replay or guessed absence. Reconnect, disconnect and cancellation after a
durable claim prevent emission. Duplicate execution and foreign-workspace receipt
access are rejected. A changed media validation digest or foreign media scope fails
before bytes can be used.

These are offline persisted creation journeys. Default factories remain disabled;
no live grants, credentials, provider calls, spending or deployment occurred.
Optimization durable dispatch remains dependent on a separate coordinator entrypoint;
PR135 transport tests do not substitute for that integration.

Validation: with disposable PostgreSQL enabled,
`pytest -ra tests/test_social_coordinator_journeys.py tests/test_provider_coordinator.py`
passed45 tests with1 expected SQLite independent-worker-lock skip in73.79seconds.
Log: `/tmp/inlet-social-journeys-final.log`. Whole Ruff, configured mypy378 files and
`git diff --check` passed. Full and hosted CI have not been verified for this child.
