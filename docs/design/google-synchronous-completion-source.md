# Google Original-Response Completion Source Proposal

2026-10-06, after native diagnostic assembly PR188. This is a narrow source proposal,
not runtime enablement, financial qualification, or permission to emit any mutation.

## Implementable Next Source

A **successfully received original synchronous mutation response** can supply stronger
operation-completion evidence than subsequent state readback. The proposed first source
covers only the existing Google v25 single-operation campaign-budget update and campaign
PAUSED update. It does not cover timeout/unknown attempts, asynchronous batches, creates,
activation, Meta/TikTok, or hypothetical retries.

Authoritative protocol evidence read on this date:

- [Resource service mutates](https://developers.google.com/google-ads/api/docs/mutating/service-mutates)
  describes atomic resource-service operations with partial failure disabled.
- The v25 [campaign-budget service schema](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/campaign_budget_service.proto)
  defines the fixed REST endpoint, false partial_failure transaction behavior, validate_only
  distinction, and resource-name results for successful operations. Mutable resource
  response content is explicitly after mutation. The
  [campaign service schema](https://raw.githubusercontent.com/googleapis/googleapis/7c0638cf893464ba844aeb04683026406eb3f8ca/google/ads/googleads/v25/services/campaign_service.proto)
  defines the same semantics for campaign updates.
- [Mutate overview](https://developers.google.com/google-ads/api/docs/mutating/overview)
  distinguishes synchronous mutate from asynchronous batch jobs. Batch jobs are excluded.

**Inference requiring review:** an exact successful original response for this synchronous
single-operation profile evidences completion of that original configuration operation.
It does not prove all later advertising effects are impossible. Delivery under the updated
configuration and incurred/pending cost must remain in financial exposure. Unknown-response
requests still need a different authoritative lookup/no-later-effect mechanism; none is
identified by this proposal.

## Current Code Gap

[GoogleOptimizationTransport.apply_once](../../app/executors/google_optimization.py)
validates a single exact resourceName result and returns only
`OptimizationResponse(request_digest, outcome='acknowledged')`. The shared
[response model](../../app/publication/optimization_contracts.py) and
[durable response recording](../../app/publication/optimization.py) retain that normalized
response, not protocol/version/operation-result provenance. A later reader cannot turn an
old generic acknowledged record into this stronger source retroactively. Existing verified
state receipts likewise do not establish original response completion.

## Additive Contract For Review Before Implementation

`GoogleSynchronousCompletionV1` (server-origin evidence, never customer input):

- exact `ExecutionAccount`, environment, original optimization request digest;
- existing original attempt ID and fence bound when persisted by the coordinator;
- pinned protocol/profile `google.v25.single_update.synchronous_response.v1`;
- endpoint enum `campaignBudgets:mutate | campaigns:mutate`, expected native resource;
- digest of the one emitted operation and explicit `partial_failure=false`,
  `validate_only=false`, operation_count=1;
- exact validated original response-result digest and server received timestamp;
- assertion limited to `original_configuration_operation_completed`;
- no money, watermark, settled-cost, effective-delivery-time or future-exposure fields.

Capture happens only inside the actual adapter after successful bounded HTTP decoding,
with exactly one matching result and no partial-failure/error/async envelope. HTTP success
alone is insufficient. Transport retries remain disabled. Malformed/contradictory responses,
foreign resources, missing results, exceptions and timeouts yield no completion evidence.
No generic caller-supplied acknowledged response can manufacture the evidence.

Persistence should be additive and leave existing social request/response serialization
unchanged. Prefer a separate typed evidence record tied to original attempt/fence over
adding optional fields that silently change shared JSON digests. Any schema change needs
an explicitly reserved migration after review. A small coordinator port may accept the
actual adapter's typed evidence, but it must bind it to the already-durable original
attempt and request before recording. Recovery after losing the response remains unknown.

Retention follows the original execution attempt and financial lineage, not a short-lived
diagnostic cache. Use composite owned foreign keys and prevent deletion while a referenced
hold, replacement ancestor or unresolved request remains. Account closure/export/native
backup/restore must include the new sanitized record and its request/fence linkage before
release. Store only the bounded typed protocol fields/digests above, no access tokens,
HTTP headers or raw provider payload. Completion is a historical immutable observation;
current authorization, scope/generation and accounting validity are separately rechecked
when consuming it. A newly reconnected generation must not silently reuse it for a new
request; historical identity remains available to audit old obligations. Existing retention
and closure rules need targeted integration tests if a new evidence table is introduced.

A read-only `GoogleOriginalCompletionReader` loads exact owned original request plus the
new evidence, revalidates request/operation/endpoint/profile/digests and immutable fence,
and returns either typed completion or an explicit unavailable reason. It must not promote
legacy records, readback receipts, another environment/account/generation, generic logs,
provider request IDs, or a different attempt. No provider network call is required to read
this already-captured evidence. No default source factory is enabled.

Only **after review of the narrow inference** may an adapter map valid completion into
`ClosedOriginalRequest(basis='authoritative_request_terminal')`. That mapping closes an
original operation, not its financial reservation. `ReplacementEvidence` still requires
independently qualified current/proposed/delayed/no-effect/residual transition and portfolio
bounds for every account and ancestor. No replacement/settlement factory becomes usable
solely from this source. Held reservations and high-water remain intact.

Offline acceptance: actual MockTransport success capture, wrong-resource/partial-failure/
validation-only/async/malformed/timeout rejection; durable SQLite/PostgreSQL exact attempt
binding; crash before persistence remains unknown; foreign account/session/fence and
legacy acknowledged records rejected; unknown attempts never closed; no automatic hold
release/replacement and existing social document digests unchanged.

## Financial Sources Still Blocked And Alternative Work

No reviewed native source supplies a sound complete reporting residual U, unchanged-future
F, proposed-transition P, or preventive writer boundary for the existing profiles. A daily
budget, reporting SLO, current pause, account balance, cap field or local lock cannot fill
those fields. No additional credentials or owner approval can turn absent semantics into
code. See the [source matrix](production-spending-source-readiness.md).

The next independently implementable financial **observation** source, if preferred, is
bounded Meta account-level Insights spend and regular TikTok reported spend, selected from
the same current owned mandate context. Proposed output: exact source metric, native
decimal string/currency, local requested and returned date boundaries, page completion,
missing-row distinction, observation expiry, `accounting_basis=unqualified`, U/F/P and
watermark null. Missing days never become zero. Existing imports already parse spend;
this would add strict account-window observation lineage, not a qualified financial source.
It is lower priority than capturing original response evidence because it does not resolve
new cap/finality semantics.

No owner monetary-basis decision is required to capture this completion evidence. A later
financial profile does require explicit monetary-basis selection plus provider-backed
preventive enforcement/residual semantics. Recommendation remains to preserve strict
fail-closed optimization while completing these additive engineering sources.


## Implemented Capture And Reader (Still No Terminality Mapping)

The approved narrow implementation is in
[Google completion contracts](../../app/publication/google_completion_contracts.py),
[capture/owned reader](../../app/publication/google_completion.py), the actual
[Google adapter](../../app/executors/google_optimization.py) and coordinator response
transaction. Migration `20261006_0066` branches from `20261006_0060` and creates the
separate `google_original_completions` table with owned original-attempt foreign key and
unique fence. Populated downgrade refuses to erase evidence.

The adapter returns an excluded in-process capture field, leaving normalized optimization
response JSON and all social bytes unchanged. Only the exact `results` envelope for the
one expected resource is accepted: extra/error/async fields, missing or foreign results
and transport exceptions do not capture evidence. The coordinator adds a server
`recorded_at` timestamp after receiving the response and persists both records in its
original evidence transaction. This timestamp is record receipt time, not provider
execution/effective-delivery time. Repeated identical capture retains the original
record; conflicts fail. There is no application update/delete operation for this record.
The database remains trusted storage; the document digest is an integrity/binding check,
not a cryptographic provider attestation or defense against a privileged database writer
rewriting all original evidence.

The owned reader checks the complete original persisted review/request/fence plus the
protocol/operation/resource/result digest and retained scalar columns. Legacy responses
and crashes before durable capture yield no document. It does not reinterpret an unknown
request from state readback or allow a different attempt/environment/account/generation
to borrow evidence. No `ClosedOriginalRequest`, replacement proof, settlement proof,
financial source or enabled factory is returned or configured.

The lifecycle registry marks the record protected; strict typed export retains the
sanitized document and rejects unreviewed payload fields. Focused tests cover actual
MockTransport capture, real SQLite/PostgreSQL storage, account closure retaining original
evidence/held obligations, unchanged social exports, composite ownership constraints and
native pg_dump/pg_restore equality with populated evidence. No live provider qualification
or authority to emit advertising mutations is implied by these tests.

Remaining external guarantees are unchanged: unknown original requests lack an
authoritative request-status/no-later-configuration-effect source; synchronous operation
completion does not bound downstream delivery, outstanding charges, reporting residuals
or future writers. Even a later reviewed mapping into request closure cannot fund a
replacement or release a reservation without a separately qualified financial envelope.
