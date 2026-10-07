# Google Original Total-Envelope Observation — Proposed Interface

Source inspected: `2a520d0`; requirement traceability: `0a192f8`. Proposal only;
no new source qualification, mutation, schema or profile registration.

## Reuse And Concrete Gap

`GoogleNativeInventoryHTTP.__call__` already returns `GoogleNativeInventory`: owned
request, complete bounded campaign/budget reads, current native total amount, period,
sharing/reference count, campaign budget linkage, channel/bidding/schedule, observation
interval and expiry. It explicitly returns null financial bounds and unqualified cap
semantics. Its account-v2 request avoids fabricating a financial mandate for diagnostic
reads. `NativeDiagnosticService` supplies private-session authorization/vault contexts,
checks before/after HTTP and releases its transactions before transport I/O.

`coordinator.evidence_lock` and `read_owned_outcome_receipt`, plus
`google_execution_completion.read_execution_completion`, already validate exact owned
original request/response/receipt/capture lineage. The public completion projection gives
only a commitment; it is not enough by itself to reconstruct resource scope. The new
binder must also use the original validated typed request, not guess a resource from that
commitment or create a second capture parser.

`GoogleSearchTotalPublicationFields`, `GoogleCreateTotalBudget`, compiler/readback and
customer review already exist. `ProviderExposureReservation` preserves amount, owner,
ledger/environment/state and original evidence. A reservation amount is **not necessarily
the native total amount**: the current fields carry both `reservation_micros` and
`total_budget_micros`. The observer must retain both without silently equating them.

Missing ordinary code: a current owned observation joining the original reviewed native
total configuration and exact created resource lineage to the existing current inventory,
with clear unmatched scope/drift and original allocation commitments. No second collector
or new terminal-evidence producer is needed.

## Narrow Supported Input

Start with an Inlet-created Google total-budget Search/manual-CPC run. Require a complete
original budget and campaign creation pair with validated synchronous captures and latest
nonconflicting owned receipts; resolve the campaign's budget reference through the exact
same-run original request/resource receipts. Imported campaigns with unknown earlier
configuration, DAILY budgets and partially known creation pairs return unavailable; they
are not silently enrolled. Activation is neither required nor inferred.

The observation describes one run's original allocation, not the whole portfolio. Native
inventory completeness means the collector finished its bounded reads, not an atomic
snapshot or proof of historical spending. Include current siblings for the exact budget
and compare reference_count; ambiguity blocks a match.

## Proposed Types And Callables

New module `app/publication/google_total_envelope_observation.py`, strict contracts in
`google_total_envelope_contracts.py`; existing request/document bytes remain unchanged.

- `OriginalTotalEnvelopeBindingV1`: exact `ExecutionAccount`, environment, run/review/plan
  commitments, original `ProviderMandateBinding`, original budget/campaign attempt and
  request/capture/latest receipt commitments, exact resource names, approved currency and
  timezone, compiled native start/end, original total micros, original reservation ID,
  amount/state/ledger and original policy commitment. Internal only; no credentials.
- `GoogleTotalEnvelopeObservationV1`: schema discriminator, original binding commitment,
  inventory commitment/observation interval/expiry, outcome `matching_configuration`,
  `configuration_drift` or `unavailable`; original total and current observed total as
  distinct optional facts; fixed reason codes; original reservation facts. Exact drift
  fields are a fixed allowlist, never arbitrary native payloads.
- Constants: `quantity='native_campaign_total_budget_setting_micros'`,
  `financial_basis='unqualified'`, `financial_upper_micros=None`,
  `spending_authority='none'`, `settlement='not_assessed'`,
  `outside_writer_prevention='not_asserted'`,
  `portfolio_coverage='single_original_run_only'`.
- `bind_owned_original_total_envelope(db, workspace_id, run_id, actor, *, authorize,
  clock) -> OriginalTotalEnvelopeBindingV1`: local workspace-first original-session,
  owner and original-lineage checks. No provider I/O or commit. Historical consent is
  identified, not treated as current forward authority; closing/deleted-source cases
  cannot initiate new native reads.
- `observe_total_envelope(original, inventory, *, now)
  -> GoogleTotalEnvelopeObservationV1`: pure strict comparison, exact account/environment/
  currency/timezone/native references/date interpretation. No qualifying arithmetic.
- `read_owned_total_envelope(session_factory, principal, identity_provider, workspace_id,
  run_id, diagnostic_service, clock) -> GoogleTotalEnvelopeObservationV1`: private local
  binding transaction ends, existing diagnostic service performs native reads, then fresh
  original-session/current-source/owned binding and latest receipt comparison before
  delivery. Concurrent local drift returns unavailable. No locks held through HTTP.

Do not call `mandates.checked` merely to read historical evidence. Current session,
workspace/source read eligibility, entitlement and master read control still apply to
new acquisition. Reauthorization must retain the actual original principal rather than
inferring an owner. Final expiry is capped by native/context/session expiry with a fresh
DB clock after blocking work. No persistence, table, retention or background factory.

## Actual Consumer For Review

Propose an explicit owned/CSRF **POST**
`/api/customer/v1/workspaces/{wid}/execution/runs/{run_id}/envelope-observation` using the
existing configured diagnostic factory and its default unavailable gate. It performs
read-only provider acquisition only after an explicit customer request; do not put
network work in historical receipt GET. Body empty; all account/period/resources derived
from the owned run. Projection exposes local run ID, original versus observed native
amount, currency, dates, reservation amount as a separately labeled allocation, observation
age and fixed reasons. No raw provider IDs or claim that “matching” means financially safe.

This consumer and its owned API tests are the proposed package boundary. If root chooses
not to expose that read, freeze the design only rather than shipping an unused producer.
Existing diagnostic query intervals constrain reported-cost dates; derive a completed
historical observation interval independently from the original campaign's possibly
future schedule. Do not extend the collector's date contract or present that reported cost
as total-envelope coverage.

## Financial Quantity And Customer Assumptions

The immediately supportable quantity is a **native lifetime campaign budget setting**,
not a financial upper bound. A subsequent financial profile should propose, explicitly,
“Google's documented campaign media-charge quantity for this finite total-budget
campaign,” with taxes/fees, credits/adjustments and cross-period charges enumerated before
approval; not silently call this all-in cash or gross served cost.

A concrete conditional customer promise to review is: Inlet never requests a total above
the original fixed allocation or extends its period; it keeps the full original allocation
reserved and stops further actions on known outside changes. No reallocation from reduced
settings or delayed reported spend. This does not promise to prevent all outside changes.
It also does not prove an earlier outside raise-then-lower never incurred extra charges.
That historical liability and exact accounting basis remain missing source facts for
financial qualification, not grounds to fabricate U/F/P or silently reduce MVP scope.

## Required Acceptance Before Implementation Completion

Reuse actual configured Google total creation fixture with no seeded execution evidence:
create reviewed paused graph, capture original pair, perform actual inventory MockHTTP,
observe exact matching native settings, assert no mutation calls from observation and all
reservations/ledger states unchanged. Both SQLite/PostgreSQL.

Negative cases: DAILY/imported/partial run; foreign run/account/generation; unknown latest
receipt; wrong budget parent or multiple owners; current cap lower/higher, schedule/channel/
sharing drift; original native total differs from allocation (preserve both); expired
native context; revoke original session or change source while HTTP blocks; closing workspace;
failed second/final read does not expose partial facts. Validate strict null financial
fields and v1 serialization compatibility. No arithmetic allocation release or activation.

Qualification remains deliberately unavailable. This package supplies genuine native and
local provenance observations; a reviewed financial source/profile is a separate consumer.
