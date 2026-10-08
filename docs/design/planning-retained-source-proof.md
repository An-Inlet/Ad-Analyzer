# Retained Planning Local Source Proof

Frozen interface2026-10-08, coordinated with persistence. No SQL migration or public document changes. Existing PlanDependencyRow immutable/scoped/privacy/export lifecycle is reused. This proves current *local* dependencies within the retained native observation deadline; it never claims a fresh provider inventory read.

## Typed Witness And Row Set

`RetainedSourceWitness(Frozen)` has exactly the existing dependency scalar columns: workspace_id, plan_id, version, evidence_key, account_id, connection_id, store_id, kind, source_binding_digest, document_digest, source_revision, observed_at, expires_at, privacy_revision. Positive IDs, strict bounded strings/digests, timezone-aware ordered timestamps and nested revalidation use existing primitives.

Required keys are `local:reporting:{account_id}` for EVERY selected account, kind `local_reporting_v1`, owned account/connection populated and store null; plus exactly `local:commerce:{store_id}`, kind `local_commerce_v1`, account/connection null and exact confirmed store populated. The reserved `local:` namespace must not collide with customer document EvidenceRefs. Witnesses bind exact workspace/plan/version/privacy, actual capture time and expires_at equal the document.valid_until. Reporting source_revision is the exact connection_version; commerce revision is the actual store revision. Source binding and document-state digests have distinct meanings and never substitute for each other.

Persistence appends these witnesses atomically with ordinary EvidenceRef dependency rows, only AFTER successful generation recheck_local_sources while canonical workspace/goal/account/store locks remain held, BEFORE final authority-age/time checks and insert. The full persisted dependency set must equal ordinary document EvidenceRef rows plus this exact witness set. Missing legacy proof, omissions, duplicates, extra/unknown rows, mismatched scalars or digests cannot return current. No missing proof is synthesized on read.

## Shared Service Interfaces

```python
capture_retained_sources(
    db: Session, *, principal: CustomerPrincipal,
    document: PlanVersion, now: datetime,
) -> tuple[RetainedSourceWitness, ...]

recheck_retained_sources(
    db: Session, *, principal: CustomerPrincipal,
    document: PlanVersion, dependencies: Sequence[PlanDependencyRow], now: datetime,
) -> None
```

Both are DB-only: no identity/provider HTTP, commit or rollback. Caller supplies an already freshly authenticated principal and owns transaction/authority finalization. Local guards permit existing READ_ROLES, including viewer; capture's caller already holds owner generation authority. No owner-only callback is introduced on retained reads. Dependencies passed to recheck are the COMPLETE version dependency row set, not a prefiltered subset. Recheck validates ordinary row projections as well as typed witnesses. `RetainedSourcesChanged` exposes a bounded reason (`source_changed`, `source_integrity_unavailable`, `proof_unavailable`) for a not-current projection; authentication failures remain authentication failures, never an authority override. Expired documents stay expired under the service's existing precedence.

## Recomputed State

Reporting state is domain-separated `inlet.local-reporting-state.v1`. Resolve exact owned account/current connected source independently of evidence-key strings. Include account/native advertiser, currency/timezone, current source connection/generation/reporting configuration and current workspace privacy revision. Include explicit CurrentPerformance absence OR its exact pointer, all completion scalar fields, recomputed full-window metric manifest/count, and a bounded sorted imported campaign mapping (local ID, native ID, platform/account plus display/status/type). Mapping cap10000 and existing metric cap100000 abort on overflow; no truncation. A current completion uses the existing current reporting reader with a DB-only READ_ROLES callback and an owned campaign witness to validate metadata/source/generation/privacy/manifest integrity. Ordinary Meta coverage is mandatory; no acquisition anchor fallback. A present completion without a verifiable owned campaign witness is unavailable, never qualified from copied hash fields.

This whole-account local state captures absence and wrong-window states as well as selected reported evidence. Therefore absent→available, wrong-window→requested-window, completion replacement, same-pointer metric corruption, mapping/source changes all invalidate the retained proof. No campaign is reconstructed from display name or an EvidenceRef key. Stored proof is a comparison value; each read independently validates current ownership and source integrity.

Commerce state is domain-separated `inlet.local-commerce-state.v1`: exact current confirmed goal/definition/store and privacy, stable current store/source fields, and actual private DB-only GoalSalesProgress projection excluding only its moving as_of timestamp. The helper recomputes closed-day coverage, net sales, availability/reasons and retention/watermark predicates at fresh read time. New day/staleness/status changes invalidate proof naturally; signed amounts and genuine missing-history/no-closed-day states are preserved. Source errors/ownership failures cannot become current by hashing an error. No personal order data or credentials are retained in witnesses.

Native EvidenceRefs continue their separate local source binding and observed expiry semantics. No native digest is equated with a performance manifest. Legacy plans lacking these new witnesses remain readable as history but cannot be labeled current. Existing foreign keys, immutable dependency triggers, export field inventory and erasure behavior apply without schema changes; at most MAX_ACCOUNTS+1 extra bounded scalar rows are stored per version.

## Qualification

Actual SQLite/PostgreSQL regressions must cover all three providers, unchanged viewer reads with zero provider IO, missing-reporting→available, mismatch→matching/replacement, same-pointer metric corruption, native/local mapping drift, generation/privacy change, commerce revision/watermark/measurement/state changes, omitted/duplicate/extra/legacy proofs and exact ordinary-row binding. No unverified live behavior or production latency claim.
