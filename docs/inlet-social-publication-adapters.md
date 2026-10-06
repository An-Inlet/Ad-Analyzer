# Inlet Social Publication Adapters

This package adds concrete, injectable Meta v26.0 image and TikTok v1.3 manual
video publication transports. Constructors open no sockets. The runtime factory
still returns `None`; no route, worker, grant, credential, or live account is wired
to these transports. These are offline engineering deliverables, not a claim that
B16 or production publication is complete.

## Reviewed Graphs And Readback

`compile_social` emits a bounded graph from the frozen social review contract.
Meta uploads the reviewed image, creates a PAUSED campaign and ad set, creates the
reviewed image creative, and creates a PAUSED ad. TikTok uploads the reviewed video
and separate reviewed cover through multipart requests, creates a DISABLE campaign
and ad group, and creates a DISABLE video ad. Every parent/media reference resolves
from a verified receipt belonging to the exact plan, connection generation, scope,
step and immutable request archive. No customer-supplied provider request body is
accepted. Google and fixture compiler/contracts are unchanged.

Serializers carry explicit identity, conversion event, attribution, targeting,
placement, budget, schedule, creative and status fields from the shared contract.
Meta uses exact integer currency minor units. TikTok rejects monetary conversion
that would round and converts schedule instants using the reviewed UTC wire setting.
The setting is explicit; its applicability to the complete provider field combination
still requires qualification. TikTok tracking pixel numbers beyond signed 64-bit
range are rejected locally. A lifetime budget is not asserted to be an independent
hard spending cap; this package does not activate delivery or expand a mandate.

The injected private media reader must supply verified bytes from the reviewed
workspace/binding. The adapter checks byte length and SHA-256 again before upload.
Tests use a fake reader, so they do not establish real video-validation, storage or
customer media eligibility. TikTok's upload signature is file MD5 for its protocol;
review binding remains SHA-256. Neither adapter accepts remote media URLs.

Acknowledged identifiers are canonicalized into provider/account/resource-kind
namespaces. Readback uses that exact identifier and account filter, checks parent
relationships, reviewed values, media metadata and paused/disabled status, and
requires all expected fields. Missing evidence is unknown; changed ownership,
parents or values conflict. Meta requests automation-related creative fields and
rejects returned nonempty automation specifications. Their omission does not prove
provider defaults harmless and remains covered by qualification blockers.

## Uncertain Effects And Transport Bounds

There is one mutation request per `apply_once` invocation and no hidden retry.
HTTP failures or malformed acknowledgements yield unknown. Reconciliation reads
only a previously acknowledged exact identifier. Missing IDs, empty lists and name
searches are never treated as proof that no effect happened; multiple acknowledged
identifiers conflict. Coordinator fencing and at-most-once invocation remain the
caller's responsibility, including the crash window before acknowledgement is saved.

Requests have 12-second HTTP phase timeouts, a checked 30-second response-reading
deadline, a two-megabyte response bound, no redirects and identity compression only.
The elapsed check occurs between chunks, not as an interrupt of an executing custom
transport. Exceptions expose constant codes. HTTPX request logging is suppressed in
the active request context so Meta app-secret proofs cannot leak from GET URLs.
Credentials are supplied as excluded secret context fields and never persisted here.

`validate_only` honestly reports **local_schema**, with no network request. Neither
provider's complete supported validation-only behavior has been qualified for this
profile. It is not publication authorization. Nonempty qualification blockers and
the disconnected runtime factory remain intact.

## Evidence And Remaining Qualification

The implementation uses frozen shared contracts from PR110 head `4425416`.
Primary source review used the official [Meta Python SDK](https://github.com/facebook/facebook-python-business-sdk)
at `efd8423a2e595ea8d4c04eb824ce113f2f1d68cd` and official
[TikTok Business API SDK](https://github.com/tiktok/tiktok-business-api-sdk)
at `f809c396520df2d7b201a9ccc5378d822b728ed3` for endpoint/schema inspection.
TikTok's [conversion-event table](https://business-api.tiktok.com/portal/docs?id=1739361474981889)
identifies SHOPPING for web purchase; its
[video information documentation](https://business-api.tiktok.com/portal/docs?id=1740050161973250)
describes advertiser-scoped IDs, signature, dimensions, duration and allowed placements.
SDK field existence is not evidence that every selected combination is eligible.

Still unverified: complete manual create/readback schemas for the target account
profiles; TikTok upload response variants; account currency/minimum budgets; actual
identity, pixel and event eligibility; attribution and UTC schedule compatibility;
regional disclosure requirements; optional automation defaults; permissions and app
review; real media processing/readiness; provider idempotency guarantees. Missing
readback fields deliberately prevent verified-effect receipts. No live provider
request was made. Actual customer qualification, coordinator integration and
end-to-end approved publication journeys remain separate work.

## Checks

On the adapter candidate based on `4425416`:

- `pytest -ra tests/test_social_publication_http.py tests/test_social_publication_contracts.py tests/test_provider_publication_contracts.py tests/test_google_publication_http.py`: **66 passed**.
- Adding `tests/test_publication_core.py` with disposable PostgreSQL enabled: **99 passed, 1 expected SQLite row-lock skip**. Without PostgreSQL configured: **82 passed, 18 skips**.
- `ruff check .`: passed.
- Configured `mypy`: passed, **305 source files**.
- `git diff --check`: passed.

The new HTTP suite exercises both full graphs, independent payload assertions,
TikTok multipart bytes, media tampering, foreign context/account/parents, changed
status/cover/identity, missing evidence, unexpected creative automation, expired
context, lost acknowledgements, bounded/error/redirect/compressed responses,
receipt substitution, read-only reconciliation and secret-log exclusion. PostgreSQL
is not required by these pure compiler/transport tests. Full and hosted CI have not
been run for this candidate; their results must be recorded separately.
