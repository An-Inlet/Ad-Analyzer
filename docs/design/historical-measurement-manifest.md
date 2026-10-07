# Historical Measurement Manifest — Next Producer Contract

Design contract for the next B17 package, not an installed collector API or new
scheduler transport method. The current pure evaluator consumes `Observation`;
existing commerce projection deliberately emits `historical_manifest_unavailable`,
unknown generation/maturity and empty coverage. A producer must prove the following
fields before that reason can be removed. No persistence/migration is authorized
by this document alone; privacy invalidation must be implemented first.

## Versioned Output

Proposed immutable `inlet.historical-measurement-manifest.v1`, canonical JSON/hash
rules matching `app.outcomes.evaluator.canonical` with its own hash domain. All
mutable database/JSON values are copied into frozen scalar/tuple models. Never
export ORM objects or raw provider/customer payloads.

| Field | Required representation and producer obligation |
| --- | --- |
| `workspace_id` | Positive owned workspace; all referenced source/account/entity facts must join to this owner. |
| `source` | Existing `SourceScope`: provider, integration/connection ID, owned store or advertiser identity, proved generation and optional exact `AccountScope`. Shopify data revision is not a grant generation. A producer without identity-generation lineage returns unavailable. |
| `metric_basis` | Existing `MetricBasis`, plus canonical definition document digest, unit/grain/entity, currency, IANA time zone, aggregation time basis, attribution definition/mapping digest and maturity-policy version. No conversion of Shopify store totals into advertising attribution. |
| `requested_window` | Existing `Window`, local half-open dates and exact UTC boundaries. Exporters of unified inclusive UTC cohorts convert end with one UTC calendar day and declare source range semantics separately. |
| `as_of` | One UTC instant for the immutable published-source view used for both comparison windows. A database read timestamp alone is not a historical provider watermark. |
| `publication` | Opaque owned import-completion/batch IDs, publication revision, exact completed source window, provider/API version, source watermark, data-revision digest, manifest's `published_at`. All pages staged and the terminal page published atomically. A running cursor/job is unavailable, not complete. |
| `partitions` | Tuple of unique local dates, at most 400. Each has `state = complete_nonzero | complete_zero | missing | suppressed`, source revision, published-batch digest, row count and immutable aggregate snapshot digest. Missing/suppressed partitions have no spend/sales value. Explicit-zero requires a successful complete read or authoritative source coverage, never no rows. |
| `entity_coverage` | Sorted digest of the expected owned entity set plus expected/observed counts and grain. Parent and child grains are distinct and cannot be added together. A resource absent before creation is `baseline_absent`, not complete-zero. |
| `attribution_coverage` | Matched/unmatched counts, currency-mismatch count and supported model/mapping version; store total marks `not_applicable`, not 100% ad attribution. No journey/customer identifiers. |
| `maturity` | `policy_id`, `policy_digest`, `mature_through` inclusive local/cohort date, horizon/lookback parameters and `evaluated_as_of`. A clipped cutoff must remain explicit. Shopify refund processing has no qualified finality policy yet; return `maturity_policy_unavailable`. |
| `corrections` | `revision`, optional prior manifest digest, `settled_as_of | pending | unknown`, correction type enum, affected date range. No silent overwrite, and no assertion that future refunds/conversions are impossible. |
| `privacy` | Owned source invalidation epoch or equivalent consistent authorization proof and `available | invalidated | unknown`, checked in the caller's transaction immediately before consumption. Referencing an old manifest does not override erasure/retention. Production persistence must support deleting derived values. |
| `snapshot` | Aggregate-only ID/digest, finite value or null and relevant numerator/denominator, no CRM profiles/customer/order keys. Decimal strings for fractional conversion counts; integer monetary micros. |
| `availability` | `available` only when all required lineage/coverage invariants hold; otherwise `unavailable` with bounded explicit reason codes and no invented values. |

Proposed read-only producer boundary (to agree with measurement/collector owners):

```text
ManifestRequest(workspace_id, source_identity, generation, metric_definition,
                entity_scope, window, requested_as_of, expected_privacy_epoch)
    -> AvailableManifest(frozen_manifest, digest)
     | UnavailableManifest(workspace_id, request_digest, reasons)
```

This is a consumer requirement description, not a new method on an existing
scheduler/executor protocol. The producer may initially support only current
published as-of views; historical requests it cannot reconstruct must return
`historical_revision_unavailable`. It may not relabel current mutable daily metrics
as old observations. No live fetching or import scheduling occurs on this read path.

## Required Producer Tests

- Two replicas observe one atomically completed publication or explicit incomplete
  state, never mixed staged/published pages. Reconnect-generation changes cannot
  inherit the prior generation's manifest without a qualified continuity mapping.
- Daily facts without a completion manifest remain unavailable. Empty complete
  pages establish zeros only for their declared owned scope/date coverage.
- Duplicate pages/jobs do not create new values; corrected reimports produce a new
  manifest digest and explicit predecessor, preserving or deleting old content as
  existing privacy policy requires.
- Currency/time-zone/conversion definition/API/mapping changes alter the basis
  digest and do not compare automatically. DST and inclusive/exclusive boundaries
  map exactly. Parent/child aggregation cannot double-count.
- Cross-workspace entity/resource/generation references fail before export.
  Privacy erasure between read and consume fences consumption; old cache cannot
  resurrect deleted aggregate snapshots.
- All aggregation is synthetic/offline in tests. Producer installation does not
  grant provider collection, production persistence, activation or spending access.

## Scheduler Coordination Received

The scheduler owner confirmed no durable normalized production receipt projection
is installed yet. Planned fields include immutable receipt ID/digest, original
request/fence/dispatch time, `execution_environment = contract_test | live`, goal
and source-draft revisions, `purpose = create_paused | activate`, sequence and
explicit `supersedes_receipt_id`, plus action/mandate consent IDs. A late verified
receipt may supersede an unknown receipt for the same attempt; the earlier evidence
is not rewritten. Activation/effective interval stays unavailable without exact
activation proof. B17 will adapt only committed shared types. Its current
`ReceiptInput` accepts synthetic or unavailable-production evidence and cannot
assert a verified production effect.
