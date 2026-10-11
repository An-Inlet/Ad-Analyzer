# Selected paired pure consumer — exact dependent ports

Approved interface against root `3b8181e` and selected-paired-consumer-interface-v1.
Dependent implementation follows integrated traffic-proof and prepared-projector ports.

## Owned files and public pure symbols

New `app/planning_documents/selected_paired_evidence.py`:

```python
class TrafficWindowEvidenceV1(Frozen):
    reference: EvidenceRef
    target: TargetRef
    document: SelectedTrafficWindowV1

class TrafficWindowGapV1(Frozen):
    account: AccountRef
    target: TargetRef
    requested_window: ReportingWindow
    reason: Literal["range_traffic_provenance_unavailable", "unsupported_traffic_profile"]
    reporting_pin_digest: Digest  # complete retained account state_digest()
    explanation: Text

class SelectedPairedEvidenceV1(NoAuthority):
    selected: SelectedPlanEvidenceBundleV1
    traffic_graphs: tuple[RawRangeTrafficGraphV1, ...]  # <=20, unique account
    traffic: tuple[TrafficWindowEvidenceV1, ...]  # <=400
    traffic_gaps: tuple[TrafficWindowGapV1, ...]  # <=400, combined slots <=400
    def assert_ticket(self, ticket: GenerationTicket) -> None: ...

def traffic_window_key(account_id: int, campaign_id: int,
                       window: ReportingWindow) -> str: ...
```

Key domain `traffic_window:` + fingerprint(`selected-traffic-window-entry`, exact
account/campaign/UTC half-open window). Document digest domain
`selected-traffic-window` over the complete typed window. Reference metric basis
`provider_reported_raw_traffic`; kind `reported_metrics`. Scope/revision/privacy
comes from the graph source fence. Both observation_started_at and observed_at equal the retained receipt.completed_at
(and matching header.completed_at): the actual publication observation time. Earlier
acquisition start is not retained and is never reconstructed from a digest or
restamped with collector time. Deadline is
no later than the corresponding account catalog deadline (and the original
selected evidence deadline). Explicit partial/unavailable coverage; no complete
attribution claim.

Pair slot identity: full AccountRef + campaign local/native ID + UTC window.
Every selected success has exactly one traffic success or intact-provenance gap;
no traffic for selected gaps. Success requires same source, aggregate dependency,
full-map commitment and currency/timezone as its paired selected window. Complete
traffic graph once per account must match the saved non-null traffic_pin. Missing
receipt/profile gaps require saved traffic_pin None. Present graph corruption or
mapping mismatch rejects, never a gap. The exact graph set is every account with a non-null saved traffic pin, including
accounts lacking a catalog or selected success. Such bound unconsumed graphs are
retained and verified; no extra graph without a saved pin is allowed. Full selected assert_ticket, nested copied
model revalidation, arithmetic recomputation and combined 32 MiB cap are mandatory.

If raw traffic's public projector reparses full graphs per window, coordinate a
safe prepared projection class (validating constructor, no unchecked public flag)
with its author before using it for <=400 windows. No weakened validation to save
work. This is an implementation efficiency seam, not a new authority port.

New `app/planning_documents/selected_composer.py`:

```python
class SelectedPlanComposer:
    def compose(self, *, ticket: GenerationTicket,
                evidence: SelectedPairedEvidenceV1,
                policy: PlanningCompositionPolicy,
                generated_at: datetime) -> PlanVersion: ...
```

Separate implementation over the actual paired DTO; never construct V3 evidence
or relabel a V3 document. Preserve existing manual actions, constraints/exclusions,
fixed allocations, scenarios, ceilings and creative-capacity scaffolding. It may
reuse pure target/location/text helpers, but old composers/bytes are untouched.
Attach selected.reporting_proof and all selected, traffic, catalog, commerce and
context references. Existing document evidence limits still apply: overflow
rejects instead of dropping references. Gap renderings preserve each exact window.

Descriptive text names the exact selected event resource and metric family
(conversions/all_conversions). Exact Decimal selected count and integer micros are
rendered separately from traffic. 100 clicks / 10 selected / $100 cannot produce
no-conversions wording. Complete explicit selected zero alone permits observed
zero wording; positive observed spend additionally permits spend wording. Partial
spend is a subtotal, partial zero is not full-window zero, and absent traffic is
unavailable, never 0 clicks/$0. No causal lift, ROI, forecast or budget authority.
A positive primary count may retain the existing descriptive retain action,
overridden by unresolved constraints/zero ceiling; all actions remain manual.

## Root/other lane dependency contract

Root owns optional omitted-None `SelectedRetainedAccountProofV1.traffic_pin`, exact
pin/selected equality, current/history reconstruction and future owned paired
collector. Google lane owns traffic producer/DTO/projector/SQL reader. This lane
owns only the two new pure modules, pure tests and package ledger, no proof/schema,
reader, service, registry or historical-export edits.

Tests include both families, positive count, true zero, partial zero, omitted
traffic, separately sliced primary/comparison, unsafe copied graph/window/proof,
foreign or duplicate/extra/missing slots, changed receipt/map/aggregate/source,
limits/deadlines, all references, and old full plan/input golden bytes. Actual
range+selected acquisition to owned paired collector remains a later composition
test, not falsely claimed by these pure fixtures.
