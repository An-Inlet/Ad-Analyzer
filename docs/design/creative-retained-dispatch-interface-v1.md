# Genuine V5 Retained-Source Dispatch V1

Design only, based on `2b1d6fe` and approved standalone creative currentness
interface `40b6ceb`. Implementation waits for that currentness module's frozen
reviewed head. No service, generation, capability, repository, public default or
policy registration change is authorized by this interface.

## Existing boundaries

`selected_plan_witnesses.capture_selected_retained_sources` currently admits exact
v4, verifies its complete selected reporting proof twice around the real commerce
witness, and returns `local_reporting_v3` plus `local_commerce_v1`. Its recheck
first validates the complete saved dependency set. Reporting/commerce observation
timestamps are original-save timestamps, compared for validity but excluded from
comparison with newly sampled current witnesses.

`retained_sources.capture_retained_sources` and `_recheck` dispatch exact v4 before
legacy capability handling. The outer `recheck_retained_sources` currently invokes
SQL `_guard` before dispatch. The new v5 path must reject dirty/nested/replaced
transactions before this first SQL/autoflush; do not weaken existing legacy paths.

`creative_history.creative_local_witness` commits the complete original proof,
including empty selections. `capture_creative_retained_source` checks current SQL
image metadata and returns that exact immutable witness, without storage/provider
IO or paid entitlement. Complete historical validation already recognizes genuine
v4/v5 and validates every ordinary/selected/traffic/commerce/creative dependency.

## Narrow shared reporting helper

In `selected_plan_witnesses.py`, extract the existing capture body into:

```
capture_selected_reporting_sources(
    db: Session, *, principal: CustomerPrincipal,
    document: PlanVersion, now: datetime,
) -> tuple[RetainedSourceWitness, ...]
```

This internal helper recognizes only exact v4/v5 through `selected_policy_contract`
and revalidates the genuine PlanVersion. It requires the full selected proof and
explicit selected inputs, preserving current selector/head/source/full selected
capture/traffic comparisons through `capture_selected_reporting_pin`, all reporting
and commerce fields, original READ_ROLES semantics, and existing before/after
transaction/goal/privacy/time checks. No copied v4 document, policy replacement,
proof removal or reduced dependency validation is permitted. Its return is explicitly
the reporting/commerce subset; it is never a complete v5 witness set.

Existing `capture_selected_retained_sources` remains an exact-v4 wrapper with the
same signature, rejection behavior and returned values. Existing v4 recheck stays
unchanged and calls that wrapper. Extraction must preserve old witness digests,
timestamp semantics and error classification. No new paid or generator-actor check.

## Exact V5 orchestration

New `creative_retained_sources.py` exposes:

```
capture_creative_retained_sources(
    db: Session, *, principal: CustomerPrincipal,
    document: PlanVersion, now: datetime,
) -> tuple[RetainedSourceWitness, ...]

recheck_creative_retained_sources(
    db: Session, *, principal: CustomerPrincipal,
    document: PlanVersion, dependencies: Sequence[PlanDependencyRow],
    now: datetime,
) -> None
```

Both require genuine exact-v5 typed documents. Before any SQL, require a clean,
active, nonnested Session root and bind the underlying Connection root; require
both identities and cleanliness unchanged around every delegated call. Validate
strict aware `now`, normalize comparisons to UTC, and sample max(now,fresh DB UTC)
after waits. Caller retains fresh external identity fact, workspace-first ownership
and final identity freshness checks. These functions do not open/commit sessions
or transactions and perform no provider, decoder or storage IO.

Capture performs original SQL READ_ROLES guard, confirmed-goal and exact privacy
checks, calls the shared reporting/commerce helper with the same original document,
then calls `capture_creative_retained_source`. It returns reporting witnesses in
existing account order, commerce, then exactly one creative witness. Verify exact
expected key cardinality (one per account + commerce + creative), no duplicates,
all scope/privacy bindings, and creative equality to `creative_local_witness`.
Repeat original-session SQL guard, goal/privacy and fresh generated_at<=now<valid_until
checks after all delegated reads/locks and before return. Underlying root identity
and clean state remain mandatory, including empty images. Do not restamp the proof
or creative witness and do not claim current blob availability.

Recheck first runs `validate_selected_historical_dependencies(document, dependencies)`
on the COMPLETE set: ordinary EvidenceRefs plus reporting/commerce/creative rows.
It may not filter out creative rows or bypass that validator. Capture the actual
combined current witnesses as above. Compare every reporting/commerce field using
the existing v4 rule: saved observed_at must be within the original document interval
and not after fresh UTC now; all other fields equal. Compare the creative row in
FULL, including its original generated_at commitment. Its proof retains every
original image observed_at. Finish with the same root/authority/goal/privacy/time
guards after comparison. Missing/extra/foreign rows fail; no partial successful
subset or empty-proof omission.

## Generic internal dispatch and errors

Add only exact `(CREATIVE_POLICY_VERSION, CREATIVE_GENERATOR_VERSION)` branches in
`retained_sources`. Use local imports to avoid cycles. The v5 branch is chosen from
a revalidated document and must reach the new transaction-clean preflight BEFORE
any generic `_guard` SQL; keep the legacy/v4 outer guard ordering unchanged.
Capture delegates to combined capture. Recheck delegates to combined recheck;
legacy/v4 complete validators and capability behavior remain intact.

Keep the corresponding existing entrypoint error boundaries: authorization errors
retain status, source changes use RetainedSourcesChanged, expected malformed-proof
ValueError/Shopify errors become proof_unavailable, and existing HTTP409/current
integrity normalization remains unchanged. Unexpected RuntimeError/DB errors must
propagate. No new blanket exception or paid-work check. Source-kind recognition is
not capability registration; reporting_capability(v5) still rejects.

## Qualification before implementation freeze

- Genuine actual reporting + owned image collector + pure v5 composer fixture;
  direct immutable test persistence is labelled, never claimed as v5 public generation.
- Both databases: generic capture yields all required exact witnesses; generic
  recheck accepts complete stored set; empty/multiple images; no new image timestamps.
- Missing/extra creative or ordinary/reporting/commerce rows; capture/traffic/source
  and image creator/time/hash/scope changes; goal/privacy/session/membership drift.
- READ_ROLES viewer and canceled-billing positive; no identity-provider/storage IO
  in SQL; expired/future/DST instants fail correctly; clean root/Connection replacement,
  dirty/nested/absent transaction refusal before autoflush; callback/DB errors propagate.
- Media metadata loss stales currentness while immutable history remains readable;
  semantic privacy erasure removes the graph. No visual/rights/byte-availability claim.
- Exact unchanged v4 capture/recheck/event/selected-history regressions and old
  witness/document byte/digest coverage. No fake v4 creative fixture or validator stub.
- Whole Ruff/configured mypy; bounded coordinated SQLite/PostgreSQL cohorts only.

No migration or new dependency kind is needed: history already supplies the exact
creative kind/key and mandatory complete dependency row. Future service finalization
must additionally use the actual private collection SQL recheck, compare returned
proof with candidate, and persist atomically; that remains outside this package.
