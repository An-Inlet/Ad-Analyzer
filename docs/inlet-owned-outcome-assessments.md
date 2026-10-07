# Owned Outcome Assessments And Measurement History

This B17 increment persists actual owned provider-receipt lineage alongside an
actual retained terminal Shopify aggregate publication. It does not qualify
advertising performance, claim causal lift, or authorize spending. The installed
commerce producer has no approved maturity policy; every current assessment is
explicitly `insufficient`, with the actual values and specific missing evidence.
A paused campaign creation is never treated as activation.

## Interfaces

`POST /api/customer/v1/workspaces/{workspace_id}/outcome-assessments` requires a
current owner session and same-origin CSRF. Input is only an owned attempt ID,
owned publication ID, two non-overlapping half-open local date windows (each at
most400 days), and the installed `commerce_as_of_v1` policy. Provider envelopes,
amounts and success flags cannot be supplied by the customer.

`GET /api/customer/v1/workspaces/{workspace_id}/outcome-assessments/{id}` repeats
current owner/session checks and resolves the latest original-attempt receipt.
Both endpoints return `Cache-Control: no-store`. Explicit `contract_test` and
`live` environments remain distinct. Test fixtures use actual persisted
coordinator receipts backed by mocked HTTP, not invented production evidence.

The v2 payload type is `app.outcomes.owned_contracts.OwnedAssessment`; the model is
`app.outcomes.models.ActionOutcomeAssessment`. The immutable bounded JSON field is
`assessment` (maximum256KiB at creation). Exact source/receipt/policy/input hashes
are retained, with integer-micro aggregate observations. Raw customer identifiers,
provider requests, resource names, credentials and creative payloads are excluded.
The separate assessment digest covers the typed payload; the provider receipt
digest and normalized projection digest are deliberately different bindings.

The current latest receipt is resolved through the frozen coordinator reader.
A later unknown/conflict cannot resurrect an earlier verified receipt. Historical
assessments remain explicitly non-current when superseded, and never produce a
current comparison. Identical inputs return the existing immutable assessment;
new receipt evidence creates a new assessment. Saved evaluation time remains an
as-of time, not a claim of ongoing measurement qualification.

## Privacy And Ownership

Migration0057 descends from0056. Composite workspace foreign keys bind the original
attempt, receipt and publication. The publication foreign key uses `ON DELETE
CASCADE`: source erasure, rebind/disconnect invalidation and retained-publication
removal delete the derived assessment payload and its digest in the same privacy
transaction. Existing source invalidation bumps the workspace export privacy
revision; no new retention exception or closure disposition policy is introduced.
Provider execution audit facts remain independently protected. Derived aggregate
assessments have an explicit non-protected lifecycle classification.

Creation/read takes the common workspace fence before source access, revalidates
identity after blocking locks, and uses fresh clocks for retained-source checks.
A reader waiting behind privacy erasure receives404. An expired or invalidated
publication cannot be reconstructed from the saved assessment payload.

The lifecycle registry allowlists scalar metadata. Exporting the JSON payload
requires the export owner's separate strict typed serializer integration. This
package does not claim complete archive support before that integration.

## Customer Measurement History

`/app/measurement-history` is a public inert shell linked from Settings. Data is
loaded only through existing authenticated workspace/store/publication endpoints.
The page displays actual as-of time, source watermark, currency, store timezone,
complete/zero/missing/suppressed days and explicit maturity/attribution limitations.
No invented chart, optimization gain or financial comparison is shown. Values are
rendered with `textContent`; unsafe browser number ranges display Unavailable.
Erasure/access failures clear prior displayed values; logout revokes the session
and clears workspace names. This page is separate from the owner-managed public
marketing page and is not yet an assessment creation UI.

## Qualification Limits

Tests use synthetic records, disposable databases, mocked provider HTTP and
loopback HTTPS browsers. No live provider calls, customer data, production
migrations or real advertising effects have been exercised. Production exposure,
authoritative activation intervals, approved maturity rules and a qualified
comparison producer remain prerequisites for a future comparison-capable version.

## Descriptive History Form (Separate From Action Assessments)

Measurement History now offers current owners a confirmed-goal selector and two
half-open local date windows after loading the latest owned publication. It calls
the separately versioned read-only descriptive comparison endpoint. Exact Decimal
micros are formatted using BigInt rather than lossy JavaScript number conversion.
Results explicitly retain Maturity Unqualified, Action Attribution Unavailable,
null causal/recommendation claims and no spending authority. This does not expose
or enable a mature action assessment.

A prior-publication selector is not fabricated: the existing customer source API
provides latest/known-ID reads, not an owned history listing. This UI therefore does
not request reconciliation stability. Backend stability remains available through
its separately scoped contract. Source/session changes and erasure clear displayed
values; stale responses are ignored. Role changes are rechecked by the API and clear
comparisons; viewers can still load their owned measurement publications.

The unresolved maturity and timing decision is documented in
`design/b17-maturity-owner-decision.md`. No numeric policy was selected by this UI.
