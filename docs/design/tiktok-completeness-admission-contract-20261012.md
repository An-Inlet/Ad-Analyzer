# TikTok Completeness Admission Contract

Status: offline dependency contract; provider completeness semantics unresolved.
No durable producer, async task, customer route, capability or runtime activation is
implemented by this document. The existing pure parser remains unchanged and refuses
complete capture. This advances the [options investigation](tiktok-uncapped-evidence-options-20261012.md)
into explicit admission and acceptance requirements, without inventing provider proof.

## Source Findings And Limits

Targeted official reads on 2026-10-12 confirm task create/check interfaces and query
fields in the [reporting SDK](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/ReportingApi.md)
and [task request model](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/TaskCreateBody.md).
The returned [InlineResponse200 model](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/business_api_client/models/inline_response200.py)
leaves `data` as an object and refers back to endpoint documentation. Thus it does
not specify terminal states, files/parts or completion semantics. The
[ad filter model](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/FilteringAdGet.md)
provides status/campaign/origin filters, but no historical-superset or snapshot guarantee.
These mutable-main sources are interface evidence only; an immutable revision could
not be retrieved. No supported-combination or uncapped guarantee is inferred.

The official portal rendered no endpoint text. A targeted gateway read and public
SDK revision read failed through the web tool; consumer-environment public-document
reads also returned URLError. No credentials, login, access-control workaround or
provider account call was attempted. Search produced no usable authoritative completion
contract. Stop this bounded research pass; do not repeat inaccessible-page retries.

## Decision And Shared Boundary

Do not turn synchronous `TikTokCountProofV1` into an async task by adding success flags.
Its exact schema and historical bytes remain stable; page coverage is not ad-universe
coverage. Inventory counts from SQL or current ad enumeration cannot admit capture.
The existing `require_complete_capture()` refusal remains the correct boundary.

Prefer a distinct async evidence variant only after official endpoint semantics satisfy
the matrix below. Async is a proposed alternative, not a validated cap bypass. Its
manifest must bind the same exact owned campaign partition, report profile, dates,
timezone, event and exclusions as the synchronous query; it cannot inherit sync support
merely because request fields have matching names. No schema number, migration or
positive proof constructor is selected until those semantics and all readers are reviewed.

| Admission Obligation | Required Evidence | Current Disposition |
| --- | --- | --- |
| Exact async query support | Versioned official support for BASIC/AUCTION/AUCTION_CAMPAIGN, campaign/day, complete_payment and explicit status/origin filters | Unresolved |
| Uncapped coverage | Explicit exact-query truncation/completeness rules and every async cap/partial-success condition | Unresolved |
| Terminal outcome | Documented state vocabulary; distinction between completion, failure, cancellation and expiry | Unresolved; do not guess SUCCESS |
| All parts | Documented result enumeration and total-part/row/byte integrity semantics, or an equally explicit complete-file guarantee | Unresolved |
| Safe retrieval | Documented download mechanism/allowed origins, expiry, format, compression and limits | Unresolved |
| Inventory alternative | All contributing historical/deleted IDs plus stable acquisition/reconciliation guarantee matching report scope | Unresolved; current inventory insufficient |
| Local authority | Original session, workspace, advertiser, connection generation, entitlement and privacy binding before/after IO and commit | Required existing invariants, independent of provider completeness |

A digest proves which bytes were received; it does not prove no part was omitted.
Repeated inventories can agree while both omit historical records. Neither observation
admits a positive proof without its provider coverage guarantee.

## Proposed Acquisition Lifecycle

After source qualification, review typed states `requested`, `pending`, `terminal`,
`downloaded`, `validated`, `committed` as local concepts, not invented provider enums.
Each transition must retain the immutable owned query digest and original task binding.
Task creation is an analytics POST, still prohibited live here. A timeout after creation
is ambiguous: do not automatically create a duplicate task; only documented idempotency
or reconciliation may recover it. Polling is finite and recognizes only documented
states. Failure, unknown state, expired task, partial success and exhausted bounds refuse.

Download uses an explicitly qualified origin and fixed content/byte/part limits; no
redirect following, credential forwarding or arbitrary returned URL fetch. Download
URLs may carry secrets and must not enter logs, customer exports or durable evidence.
Every response closes. Compare all parts and their query/task/account scope before
parsing; normalize counts with current missing-versus-zero/date/ownership rules.
No partial publication. Original local authority and sources must still be valid just
before a single atomic capture commit; never hold a SQL transaction across network IO.

Retain only the minimal provenance needed for the qualified guarantee: source-contract
revision, owned query digest, task binding, bounded state/request observations,
part inventory/integrity data and safe derived totals. Exact native task identifiers,
erasure behavior and access scope need the existing privacy/retention review. Hashes
alone must not be mislabeled anonymization. The retained evidence must be committed
by the capture digest, read by explicit reader floors, exported without secrets and
erased with its owned capture. A mutable side table cannot substitute for that binding.

## Offline Fixture Acceptance Before Runtime Work

Freeze source-backed response fixtures only after the wire contract is known. Then
qualify exact successful single/multipart output and all of the following refusals:

- Unknown/partial/failed/expired status; polling exhaustion; create timeout with no
  duplicate POST; task/account/query substitution; reordered or regressing states.
- Missing/duplicate/foreign parts; changed totals or integrity; truncated or oversized
  bytes; unknown format/compression; redirect and foreign origin; response cleanup.
- Positive, explicit zero, missing and dash counts; malformed/nonfinite/negative
  numbers; duplicate campaign/day; foreign campaign, date or timezone; absent money
  and unknown attribution preserved rather than upgraded.
- Original-session replacement/revocation, grant/connection generation, paid access,
  selected event, campaign mapping and privacy changes during acquisition; late
  failure leaves no capture, completion receipt or partial derived facts.
- Storage/export/history corruption and reader floors on SQLite before PostgreSQL;
  unchanged legacy serialization/digests and erasure of owned retained proof.

Use bounded original exits/XML/artifacts, exact test IDs and stop-on-first-failure.
Do not create positive fixtures labeled complete until authoritative completion evidence
exists. The next dependency is a readable versioned official endpoint contract covering
the unresolved matrix, not an owner choice to waive completeness or a live credential.
Independent customer work can proceed while this provider-evidence gap remains open.
