# Requested-Window Runtime — Frozen Bounded Packages

Freeze base `42e3ec4`: pure projection, private evidence, and owned reader are
independently reviewed. Follow the [runtime proposal](planning-window-runtime-integration-proposal.md),
with its final addenda authoritative over earlier uniform-composer and catalog-gap
wording. The following two independent packages share the already frozen evidence
and reader contracts. Neither changes the application default, routes, existing
composer/adapter bodies, repository, service dispatch, migrations or public UI.

## A. Pure V3 Composer

New `app/planning_documents/window_composer.py`:

```python
class WindowPlanComposer:
    def compose(self, *, ticket: GenerationTicket,
                evidence: WindowEvidenceBundleV1,
                policy: PlanningCompositionPolicy,
                generated_at: datetime) -> PlanVersion: ...
```

Use the genuine ticket, exact canonical v3 policy/digest and
`evidence.assert_ticket(ticket)`. Derive all actor/version/parent/input fields from
the ticket; never fabricate tickets or old bundles. Pure validation establishes no
live ownership. Preserve existing scenario, fixed allocation, ceiling, creative
capacity/constraint and manual-only behavior under the new policy. Existing helper
functions may be imported; old composer bodies and old goldens remain unchanged.

Primary assessment uses requested summaries only. Comparison is separately labeled
literal observation or exact known gap; retain all successful references and all
gap identities. Fixed Decimal context, no floats, rates, causal claims, forecasts,
cross-platform aggregation or native spending authority. Follow the proposal's
lossless gap grouping and inverse-set coverage checks; capacity overflow aborts
explicitly, without partial output. Include all prior policy caveats and distinguish
collection-time catalog failure from current provider absence.

Tests cover exact positive/zero/missing, distinct primary/comparison counts despite
larger original totals, successful/gap combinations, UTC instants, exact references,
lossless multi-account gap groups and actual field/count bounds. Representative
dozens-of-campaign Google/TikTok gap plans must remain representable. Preserve
customer scenarios/fixed allocations/exclusions/constraints/creative capacity and
old composer/policy golden bytes. Existing production composer still rejects v3;
this new explicitly called composer is not production activation.

## B. Owned V3 Collection And Final Recheck

New `window_adapter.py` with `OwnedWindowEvidenceReader` matching the existing
owned reader constructor and `collect(ticket) -> WindowEvidenceBundleV1`.
New `window_local.py`:

```python
def recheck_window_sources(
    db: Session, *, principal: CustomerPrincipal, ticket: GenerationTicket,
    bundle: WindowEvidenceBundleV1, authorize: Authorize,
    clock: Callable[[], datetime],
) -> None: ...
```

The callback is current DB-only authority; external identity validation belongs to
the existing caller before SQL. Sample the supplied clock and database time after
waits, as the owned reader does; do not freeze time in a closure around an earlier
`now`. This refines the proposal's earlier `now` signature. A later service package
will wire the actual callback and clock. No provider/identity IO occurs under SQL.

Follow the proposal's exact collection/pin/deadline/source/receipt/commerce rules.
Use a fresh owned context per account/read transaction and in final recheck. Close
contexts on all exits and before persistence. All successes and known reader gaps
are reconstructed; collection-time catalog failures have only the explicitly stated
in-process provenance and repeatable local checks, not independent current provider
absence proof. All-catalog-unavailable still aborts for lack of a real deadline.
Do not call the old full adapter to manufacture or transform an incomplete old
bundle. Version-specific new helpers may reuse existing narrow validated functions;
do not refactor existing runtime bodies in this bounded package.

Tests explicitly inject canonical v3 tickets/policy; leave old fixture policy `1`
and old production paths alone at this stage. Use actual owned source/native
MockHTTP reads and both databases, not ready-bundle stubs. Cover exact source/pins,
full slot success/gap matrix, parent/native target identity, absence/corruption,
source changes outside requested subsets, original session/goal/privacy/expiry,
foreign ownership and rollback, with fresh contexts and closed observers. This
qualifies adapter/rechecker calls only; the later actual-import-to-customer-API
package and production dispatch remain outstanding.

Both packages require focused tests, whole Ruff, bare mypy, diff checks, durable
raw artifacts/ledger and independent review. Do not sum overlapping cohorts or
claim aggregate, live, expert-quality, purchasable-product or customer API readiness.
