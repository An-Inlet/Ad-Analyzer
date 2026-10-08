# Plan-Bound Sales Progress V1 — Proposed Interface

Investigation only, base `f0ac35d`. No schema, runtime, API or UI change. This makes
current Shopify sales readable against one exact retained planning version; it does
not change the saved plan, measure causal lift, assess achievement, or authorize spend.

## Concrete Additive Contract

New module `app/planning_documents/progress_contracts.py`:

```python
class PlanSalesProgressV1(NoAuthority):
    schema_version: Literal["inlet.plan-sales-progress.v1"]
    workspace_id: Positive
    plan_id: Id
    version: Positive
    document_digest: Digest
    goal: ConfirmedGoalRef
    binding_status: Literal["matched", "unavailable"]
    binding_reason: Literal["goal_changed", "goal_unavailable"] | None
    sales: GoalSalesProgressV1 | None
    as_of: AwareDatetime
    manual_application: Literal["not_assessed"] = "not_assessed"
    attribution: Literal["unavailable"] = "unavailable"

    @computed_field
    @property
    def net_sales_micros_exact(self) -> str | None: ...
```

Reuse the exact `document.inputs.goal`, including confirmation reference, confirmed
revision and complete validated GoalDefinition. Do not construct a smaller reference
that drops store/window/target/budget identity. `document_digest` is recomputed from
the actual loaded canonical PlanVersion, never supplied by browser or cached scalar.
A service-owned construction helper accepts the loaded PlanVersion and sales result,
checks workspace/plan/version/digest/goal equality, and constructs the projection.
Pure DTO validation alone does not establish that a document is owned.

Required invariants:

- Matched binding requires `binding_reason=None`, `sales` present, and exact outer
  workspace/goal ID/revision equality. Unavailable binding requires one reason and
  `sales=None`; the original retained goal reference remains present, never replaced.
- Matched does not mean sales available. Preserve sales' own `available_as_of`,
  `not_started`, or `unavailable` status and reasons without flattening them.
- Reparse nested `GoalSalesProgressV1` from `model_dump(mode="python")`, as for the
  existing ConfirmedGoalRef definition. Its legacy Frozen base does not revalidate
  unsafe nested copies; use the reparsed result in all new binding checks.
- Match sales.store_id, target_micros, target_window, currency and time_zone exactly
  to the confirmed definition. Validate sales.definition_digest with the existing
  `app.publication.contracts.fingerprint("inlet.goal-progress-definition.v1", definition)`.
  This is deliberately NOT the planning reference's `common.fingerprint("goal-definition", definition)`.
  Both fingerprints derive from that same exact validated definition, in their own
  existing domains. Do not compare the two digests as if their domains were equal.
- `as_of == sales.as_of` when matched; unavailable binding samples a fresh effective
  server/database clock. Preserve signed sales values, closed-day coverage, partial
  versus full-window extent, source revision/watermark, and all existing unavailable
  rules. Zero is not missing; corrections/refunds may reduce amounts below zero.
- `net_sales_micros_exact` is an output-only computed field, never accepted as client
  input or stored as a second amount. Derive it exclusively from the revalidated
  matched `sales.net_sales_micros`: `str(value)` for an actual integer, otherwise
  null (including unavailable binding or unavailable sales). Its canonical grammar
  is `^(?:0|-?[1-9][0-9]*)$`: no plus sign, whitespace, exponent, leading zero or
  negative zero. Do not derive it from a floating-point conversion, request field,
  cached scalar or separate calculation. Preserve the nested GoalSalesProgressV1
  contract unchanged; its existing integer can exceed JavaScript's safe range.
- No new snapshot digest, progress-history row, imported metric default, percentage,
  forecast, achievement threshold or completed-action percentage is introduced.
  Authority fields remain exactly false/none; old goal contract remains unchanged.

## Service And HTTP Boundary

Add to `PlanningDocumentService`:

```python
def sales_progress(
    self, principal: CustomerPrincipal, wid: int, plan_id: str, version: int,
) -> PlanSalesProgressV1: ...
```

API: `GET /api/customer/v1/workspaces/{workspace_id}/planning/plans/{plan_id}/progress?version=N`
with REQUIRED positive version (422 if missing/invalid), existing Principal/Provider/
Database dependencies and `Cache-Control: no-store`. Return200 for a readable retained
version with an unavailable binding or unavailable measurement. Unknown/foreign/erased
plan or version remains owned404. No generated version is also404 for the explicitly
requested version, not a fabricated version0 projection. No implicit current-version
selection, request body, refresh/import side effect or execution permission.

Use existing `service(db, provider, principal)` detach/rollback factory so provider
identity refresh happens outside the API auth transaction. In the service use exactly
one hardened `_read_session(principal, wid)`:

1. Refresh external identity before SQL, lock current customer/workspace authority
   with existing READ_ROLES owner/admin/analyst/viewer and current billing semantics.
2. `repository.owned` locks the exact plan; `repository.version` loads and validates
   the selected retained canonical version/scalars/privacy binding. Do not call
   `self.read()` from inside this transaction or resolve via mutable current inputs.
3. Lock/refresh the existing owned goal, inspect the current revision and confirmation.
   Compare current goal revision, confirmed_preview_id, revision.confirmed_at,
   GoalPreview's goal/revision and parsed definition with the saved ConfirmedGoalRef.
   Missing owned goal => binding unavailable/goal_unavailable. Changed revision,
   lost/replaced confirmation or definition mismatch => unavailable/goal_changed.
   Return no current replacement definition or current replacement sales in either case.
4. Only on exact match call existing DB-only
   `_read_goal_progress_locked(db, current, wid, saved_goal_id, saved_revision, clock=self.clock)`.
   This preserves actual store locks, signed merchandise ledger semantics, current
   watermark/revision, import/privacy suppression, closed-day prefix, retention and
   fresh source-age checks. Do not call the public read_goal_progress wrapper, which
   would perform external identity I/O under these locks. Do not call
   repository.check_goal: its generation/baseline assessment is a different gate
   and would conflate live source unavailability with a changed goal identity.
5. Revalidate result/definition binding and final effective clock; build the projection
   inside this transaction. `_read_session` performs its unchanged final one-shot
   five-second monotonic/session authority check after all plan/goal/store waits and
   before return. No retry/provider I/O while locks are held.

Exception mapping must be narrow: only the owned goal lookup's404 and the explicit
revision/confirmation mismatch become binding reasons. Do not catch a broad404/409
around the transaction: authorization, billing, workspace closure, authority expiry
and privacy/plan deletion denials must remain failures. Existing source unavailability
is already a typed GoalSalesProgress result. Corrupt canonical plan or internally
contradictory progress cannot become matched or fallback values; fail closed with a
bounded409 `plan_progress_integrity_unavailable`, without exposing stored payloads.

A saved document can be expired or historical while its unchanged goal has readable
current sales. That is intentional: this endpoint does NOT assess plan freshness,
input-head equality, recommendation validity, native ad-account freshness or customer
action eligibility. Those remain the existing independent plan read/decision paths.
An ad connection change alone cannot fabricate or suppress Shopify sales progress.
No original-login requirement is added; current authorized readers can read retained
versions after creator logout. Privacy-erased graphs cannot be reconstructed.

## Presentation And Independent State

UI requests the exact displayed plan/version and accepts a response only when current
session/workspace/plan/version/document digest still match its request epoch. Clear
old values on navigation/logout/version switch; ignore late callbacks. Display the
original target, closed-day prefix, as-of, currency/time zone, source watermark and
unavailability reasons literally. Read sales amounts only from the canonical
`net_sales_micros_exact` string, validate its grammar, and format signed `BigInt`
micros using integer quotient/remainder with the actual currency display rules.
Never convert that amount through `Number`, floating-point division, percentages or
locale formatting that first coerces to Number. `response.json()` may round the old
nested integer, so it must never be used for monetary display or to regenerate the
exact string. Preserve null versus zero, negative values and fractional micros;
reject noncanonical strings rather than guessing an amount. The original goal target
is bounded at1e15 micros and remains safely representable; this does not impose a
new bound on the existing signed sales metric. Use exact monetary formatting. Label it current observed Shopify merchandise net sales, not plan
performance, action impact or achieved milestone. An expired plan may show both its
separate stale-plan notice and current matched-goal sales without implying validity.

Keep existing manual reports, corrections/retractions, customer decisions and any
future read-observed advertising status in separate sections and event chains. This
endpoint neither reads nor writes those events and cannot convert a reported action
into measured success. Explain that ledger corrections/refunds can change a later
reading; no retrospective delta or correction cause is asserted without stored proof.
Viewing or explicit refresh performs only this GET, never starts an import, advances
an acquisition job, publishes a campaign, or records an application assertion.

## Acceptance And Ownership Split After Freeze

1. Pure contract tests: copied nested unsafe values, wrong plan/document/goal/revision,
   mismatched fingerprint domains/store/window/target, status-null consistency, false
   authority flags, zero/negative amounts and partial/full closed-day coverage.
   Computed output tests cover both signs beyond2^53, exact zero, null/unavailable,
   canonical strings without negative zero, and rejection of a supplied computed
   field as input. UI tests use actual JSON with an unsafe nested integer plus the
   correct exact string; verify display follows the string without rounding. Reject
   malformed exact strings and never fall back to the unsafe nested numeric value.
2. Both-DB real service/API: create confirmed goal and generated plan through actual
   current paths; later closed-day ledger additions and same-period corrections
   appear without rewriting the saved PlanVersion. Existing ads report acquisition
   is not a new prerequisite. Confirm version-specific digest and definition.
3. Changed goal revision/confirmation yields controlled unavailable without leaking
   replacement goal/amount. Missing/stale/importing/privacy-suppressed commerce uses
   original typed reasons; erased plan404. Expired/historical document with unchanged
   goal remains readable; wrong/foreign version404 and viewer positive.
4. Identity revoked during pre-SQL check, detached identity changed, local revocation,
   final blocked-lock authority timeout, billing/closing denial and semantic erasure
   remain fail-closed. Instrument provider checks outside SQL and no external/native
   requests or newly written plan/event/import/execution rows.
5. Actual HTTPS UI: exact selected version, later source correction, unavailable
   revision, stale response after navigation/session switch, literal safe rendering,
   and separate unverified manual report display. No polling/import/mutation claim.

Backend lane owns new DTO/service method and focused tests; API/UI lane consumes this
frozen method/response after review. No migrations, persisted progress or new numeric
recommendation policy. This document proposes the seam; no acceptance has been run.
