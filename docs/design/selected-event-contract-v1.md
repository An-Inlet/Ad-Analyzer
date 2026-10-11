# Shared Selected-Event Contract V1

Implementation: `app/campaign_performance/selected_contracts.py`. This first package
is a pure validation boundary, not activated customer selection, storage, acquisition
or plan-generation functionality. DTO construction and dependency equality never
establish ownership, provider support or authorization.

## Frozen Decisions

- Existing aggregate completions, numeric rows, presence/V3 equality and historical
  document bytes retain their meanings. Selected count10 may coexist with aggregate
  count12; it must never be attached to the legacy sidecar as if they were equal.
- A selection names one exact provider namespace, event owner and native identity,
  metric family, API version and query-profile digest. It includes the confirming
  customer UUID and immutable revision UUID. Labels are not joins or authority.
  A known selection can still have unsupported/unknown acquisition capability.
- Each capture depends on one exact aggregate completion ID, manifest and complete
  ownership/generation/privacy/native-account/currency/time-zone scope, plus the
  complete immutable selection. Correction, reconnect, erasure or changed selection
  invalidates current use of the whole capture, even outside a requested slice.
  No independent selected-current pointer or second mutable source is introduced.
- Requested closed dates must fit that real aggregate dependency. Current seven-day
  Google and roughly30-day TikTok completions cannot establish August+September.
  A later separately reviewed range manifest or expanded actual import is necessary;
  editing header dates or reading old mutable daily rows is prohibited.
- Returned campaign/day observations are separate from aggregate traffic. Exact
  local/native mapping is bijective, duplicates reject, and missing days stay absent.
  Count/value presence is independent. Only actual present numeric tokens can become
  present zero. Complete pagination does not establish daily observation coverage.
- Domain-separated canonical commitments include all request/fact fields. Unsafe
  model copies are revalidated. Bounds:100pages,50,000facts,32MiB selected fact graph,
  4KiB/fact,8KiB request, at most400 reporting days. Private staging must enforce
  limits before accumulation and preserve phase/query/page receipts. It is not yet
  implemented; these DTOs do not verify a server's pagination claims.

## Required Runtime Implementation Before Activation

1. Persist immutable owner-confirmed selection under current customer permission;
   use database CAS and observed native event catalog, not client-supplied authority.
2. Load exact current aggregate and selection from the owned database before I/O.
   Acquire only a descriptor with documented native identity/metric semantics.
   Preserve original decimal JSON tokens before any legacy default/coercion.
3. Stage bounded pages with original query/window/selection/privacy commitments.
   Distinguish transient failure from unsupported mapping; errors never become
   missing/zero. Revalidate ownership/session/permission after external I/O.
4. Under the existing finalization locks, recheck source/selection/aggregate/privacy
   and publish atomically with checkpoint/outbox. Preserve original captured privacy
   and final publication privacy separately across the existing authorized calibration
   invalidation. Never adopt arbitrary newer privacy or publish a partial capture.
5. Add composite scoped FKs, immutable scalar/payload checks, graph commitments,
   export/erasure/archive fences and restore coverage before enabling readers.
   Current plan consumers must reread dependencies and reject stale captures;
   historical plan bytes remain historical, never rebound to new selections.

These obligations are not satisfied by the pure equality helper. No schema or
runtime port accepts these new DTOs yet, and no provider capability is enabled.

## Native Semantics Evidence And Limits

Public documentation reviewed2026-10-11 (no authenticated provider operation):
[Google conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting)
shows campaign conversion metrics segmented by conversion-action resource and states
that zero-conversion rows are excluded. [Zero-metric reporting](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics)
also describes suppression. Thus an empty selected query cannot establish zero.
The configured API query, wire omission behavior and manager-owned conversion
relationship still require exact descriptor validation. A parser fixture containing
zero is not proof that this query emits such a row in production.

TikTok's existing BASIC generic `conversion` metric has no verified customer-event
identity. The public documentation entry point did not establish a supported exact
selected-event mapping in this investigation. Keep unsupported; do not guess a
purchase field or infer event meaning from objective/pixel/account/aggregate count.
Owner approval cannot substitute for missing provider evidence.

Independent review requested before dependent implementation. Review identified
and repaired actual ID-shape mismatches: Google/TikTok source UUIDs vs Meta integer
source references, and confirming customer UUIDs. Full review/test result is recorded
in the package ledger. No provider writes, budgets or forecasts are introduced.
