# Planning Native Budget Semantics: Gap And Proposed Read-Only Interface

Read-only investigation at root `dcdce0d`, 2026-10-08. **Proposal, not a frozen
contract or implementation.** No external documentation, live provider calls, tests,
new collection, advertising writes or production code changes were performed. Provider
semantics below describe local code; anything not established there remains unqualified.
Reporting selected-event semantics are a separate coordinated investigation.

## Current Local Evidence

| Surface | What the current code establishes | What it does not establish |
|---|---|---|
| Google native inventory | `app/collectors/google_native_inventory.py` reads owned account currency/time zone; campaigns with exact `budget_resource`; budgets with amount/total micros, period/type/status, shared flag and reference count. Campaign query includes ENABLED/PAUSED/REMOVED. `topology_complete` requires every campaign's owner to exist and each owner's reference count to equal observed **nonremoved** campaign references. Pagination/deduplication is bounded. | Reads are non-atomic; daily amount is not a total cap; total-budget profile, billing/obligations and external writers are unqualified. `explicitlyShared` defaults to false and `referenceCount` to zero when absent in raw response, so the DTO alone cannot prove presence of those fields. |
| Google planning catalogs | `app/planning_catalog/projection.py` creates the existing source-bound owner key once per budget resource, projects native micros/period/type/status/reference count, and reports campaign coverage from `advertising_inventory_read_complete`. V2 adds exact names/entity/parent references; observed Google ad groups have no native-settings row. | An owner key is identity, not a full affected-set proof. The catalog repeats the same budget settings on each campaign; summing those settings double-counts shared owners. Do not derive an ad-group native budget from its parent. |
| Meta account inventory | `app/collectors/meta_native_inventory.py` retains nullable daily/lifetime native integers, configured/effective status, campaign/ad-set relationships, schedule/sharing/rebalance flags and account currency. Scope is known effective statuses. `unit_semantics='native_integer_unqualified'`; V1/V2 owner keys are null. | Amount presence does not prove independent/ad-set versus campaign-pool ownership, supported unit conversion or complete affected set. `all_effective_statuses_complete=False`; native read completeness does not upgrade that limit. |
| TikTok account inventory | `app/collectors/tiktok_native_inventory.py` preserves exact decimal **strings**, budget mode and campaign optimize flag with regular-family campaign/ad-group relationships and currency. `unit_semantics='native_decimal_unqualified'`; owner keys remain null. | Neither unit/cadence interpretation nor full family/owner closure follows from decimal syntax or flags. `all_campaign_families_complete=False`. Never coerce these decimal strings into an integer native amount or assume they are micros. |
| Existing Meta budget reader | `app/initial_planning/native_budget_contracts.py`, `native_budget.py`, `app/collectors/meta_budget.py` have a separate campaign-specific read profile with explicit owner/affected-target topology, mode, amount micros, flags and bounded observation. `app/meta/budget_currency.py` supports only USD exponent2 and refuses others. Financial qualification is explicitly unavailable. | It is not evidence attached to the general V2 catalog, and its objective/cohort/profile lineage is not a universal planning prerequisite. Do not borrow its values or silently promote general Meta catalog rows based on the existence of this reader. Reuse pure checked arithmetic only after an independently reviewed planning evidence binding; do not import execution mandates/admission. |

## Existing Planning Contract Limits

`app/planning_documents/actions.py::NativeBudget` requires owner/evidence keys,
`micros|minor_units`, currency, `daily|lifetime`, integer current/proposed amounts and
an exact delta. It cannot represent raw decimal major units and has no affected-target
set, currency exponent or qualification-policy reference. Its presence is not proof
that an adapter checked those semantics. `UnavailableBudget` correctly keeps amounts,
owner and unit null. The current descriptive composer does not produce qualified native
edits; that remains appropriate.

`documents.py` checks owned native evidence, goal currency and contradictions for the
same `(account_id, owner_key, native_budget)` setting. **Identical duplicate owner
proposals can still pass**; conflicting ones fail. Scenario/input contracts reject two
allocations with the same nonnull owner key, which avoids double counting but does not
express a single shared-owner allocation with the full affected campaign set. Keep this
conservative restriction until a separate grouping contract is reviewed. Do not loosen
it merely to make Q06 pass.

`fields.py` supports only typed `delivery_status`, `landing_page`, `country_targets`;
`bidding` and `native_budget` may be explicitly unavailable. Native catalogs do not
currently supply landing-page or country-target observations. A status string must not
be normalized from effective status into configured enabled/paused without a supported
provider/field mapping. Google bidding-strategy enum presence alone is not a typed
bidding proposal. Field shape/schema validity never substitutes for exact observed
field provenance, parent/owner scope and meaningful verification criteria.

## Minimal Proposed Shared Interface

Add a **planning-only, versioned, server-derived sidecar**, without changing legacy
inventory digests or V2 receipt payloads. Suggested pure module
`planning_documents/native_budget_semantics.py`; names below require root review.

```
qualify_native_budgets(
    retained_payload: ReceiptPayloadV1,
    catalog: TargetCatalogV2,
    policy: NativeBudgetSemanticsPolicyV1,
) -> NativeBudgetSemanticsV1
```

The adapter must revalidate exact canonical payload/catalog correspondence, never accept
caller-set completeness flags as proof. Source ownership/current principal/privacy and
original expiry remain the service/receipt resolver's responsibility. This function does
no I/O, no SQL and no currency lookup. An exact configured policy digest is a dependency,
not an implicit trusted string/version. Preserve current receipt expiry; no new lifetime.
If required field-presence provenance is absent from the retained schema, return an
explicit gap until an additive **new read-evidence schema** supplies it. Do not reconstruct
missing raw-field presence from a parsed default or change old digest meaning.

Proposed output (bounded by existing inventory limits, strict/revalidated frozen types):

- Header: schema version, exact owned AccountRef, source binding/revision/privacy,
  receipt/catalog composite/native inventory digest, qualification policy digest,
  original observation interval/expiry, `atomic_snapshot=false`,
  `spending_authority='none'`, `financial_qualification='unavailable'`.
- One row per distinct observed native owner, or per target with unresolved owner.
  Discriminant `qualified_observed_setting|unavailable`; stable scoped owner key plus
  **typed provider-native owner reference** when known (Google budget resource is a
  budget resource, not a fabricated campaign ProviderReferenceV1).
- Qualified row: raw field name/value, exact current integer amount, unit
  `micros|minor_units`, explicit scale/exponent and currency, cadence
  `daily|lifetime`, time zone, exact observed provider period/type/status, and evidence
  refs. `proposed_amount`/`delta` are **absent**: qualification describes a setting,
  not a recommendation. For future decimal support use a distinct exact decimal/scale
  type or proven lossless conversion; never float or integer truncation.
- Topology: sorted unique **all observed member campaign references**, separate exact
  nonremoved affected-member set, removed-member statuses, provider reference count,
  explicit field-presence evidence, scoped topology digest, and closure status
  `complete_in_declared_scope|partial|unavailable`. A qualified row requires a nonempty
  exact affected set and complete closure in its explicitly named scope. Members resolve
  to exact owned catalog IDs, not display names; an unrepresented member is a gap.
- Unavailable row: explicit typed reason codes (e.g. `unit_unqualified`,
  `owner_unresolved`, `affected_set_incomplete`, `field_presence_unproven`,
  `unsupported_period`, `unsupported_budget_type`, `currency_mismatch`,
  `source_topology_changed`). Keep qualified amount/unit/cadence/affected-set claims
  null. Raw observations remain accessible in existing catalog evidence, clearly labeled
  unqualified; no partially populated qualified amount leaks into a proposal.

For the first Google slice, allow only explicitly present supported DAILY micros
settings with supported period/type/status and fully checked observed owner closure;
exact supported enum set must be frozen from reviewed fixtures/profile before code.
Do not map total_amount_micros to lifetime by inference. Reference-count equality,
unique owned resources, every link, correct removed/nonremoved classification and
coverage must be checked together. Non-atomic readings remain non-atomic even when
these checks pass: this is a consistent **observed** affected set, never ongoing
portfolio/financial coverage or a guarantee against external changes.

General Meta/TikTok rows remain unavailable in this first slice. Their raw settings,
partial coverage and account currency stay visible. A future explicit read profile may
qualify a bounded owner family only with present flags, supported conversion, complete
family/child topology and exact original evidence binding. The existing USD-only Meta
reader is a possible reference implementation, not an automatic qualification bridge.

## Proposal And Counting Rules

1. Observation qualification must precede any typed native recommendation. Extend the
   proposed-budget/action contract separately with a qualification reference and exact
   full affected set; the final trusted resolver must reproduce this sidecar from the
   saved payload/policy. No complete client PlanVersion or sidecar is accepted as proof.
2. Render one owner setting and one proposed owner change, listing all affected campaigns.
   Reject **both equal and conflicting duplicate owner-edit actions** in V1; do not rely
   only on the current contradiction detector. Compare scope+owner+field+unit+currency+
   cadence+baseline+proposal. Child references are informational, not additional amounts.
3. Customer hypothetical allocations, historical spend and native settings remain three
   different quantities. Never add a shared native setting once per member. Existing
   scenario duplicate-owner rejection remains until explicit owner-group allocation
   semantics are separately frozen. Alternatives independently reconcile to one goal.
4. A daily/lifetime setting is not the confirmed total planning ceiling. Even qualified
   current settings do not justify a new proposed amount by multiplying days, applying
   aggressiveness percentages, or assuming lifetime remaining spend. Numerical proposal
   feasibility needs a separately supported period/cap model; otherwise keep the proposal
   unavailable and provide exact manual prerequisites. No advertising write is enabled.
5. Proposed-field verification compares exact supported configured fields and their
   provenance. Effective delivery, successful manual application, actor/change time and
   business lift are separate claims. Unsupported bidding/URL/country observations must
   remain unavailable rather than generated from generic narrative.

## Future Actual API Acceptance (Not Yet Run)

- Q06 real Google MockHTTP reader → V2 receipt → exact input/generation → JSON/readable
  output: two campaigns share ownerA, third uses ownerB. Show ownerA once with both
  exact campaigns; no repeated amount in totals. Same-label campaigns stay distinct.
- Missing owner/reference count/shared-field presence, count mismatch, duplicate resource,
  pagination overflow, omitted affected member, removed-member mismatch and mid-read
  topology change: unavailable or controlled abort, never a complete owner/edit claim.
  Test unchanged settings under a different generation and changed settings under the
  same owner; stale receipt/session/expiry cannot be promoted by the sidecar.
- Equal duplicate and conflicting duplicate owner proposals reject before persistence;
  no partial version/receipt/event/head changes. Exact owner amount/currency/unit/cadence
  correspondence is rechecked against trusted evidence, not hashes supplied by a client.
- Q03/Q04 Meta/TikTok amount-present cases stay unavailable, including fractional TikTok,
  absent flags, unsupported currency and partial affected families. A future explicitly
  qualified Meta profile is tested separately; no dependency on execution records.
- Q05/Q07 combined customer alternatives and confirmed ceiling remain exact and
  independent; native settings never become scenario totals or a financial upper bound.
- Read-observed tests must distinguish matches/partial/conflict/unavailable for the exact
  proposed fields and owner topology; no provider mutation request or execution record.

Implement after root freezes the sidecar/presence-provenance and proposed-action
interfaces. First ship honest observation qualification/gaps; broader recommendation
policy and numerical feasibility are separate dependencies, not defaults introduced here.
