# Q08 retained empty-query proof — concrete production interface proposal

Design only at `e5f7e8d`; no production changes or tests. The actual baseline is
owned by the separate Q08 fixture lane. This refines the approved baseline proposal,
not approval to activate account preparation or declare provider-wide emptiness.

## Cycle-free shared models and exact imports

1. New `app/planning_documents/catalog_evidence.py`: move the **unchanged** existing
   `CatalogEvidence` class from `ports.py`, including validator, annotations and
   field order. Imports only common.Frozen, context.EvidenceRef and
   planning_catalog.metadata_contracts.TargetCatalogV2 (plus validator support).
   `ports.py` explicitly reexports `CatalogEvidence as CatalogEvidence`; all existing
   callers retain the identical class object. Do not duplicate the model or use
   unresolved forward annotations. No PlanVersion/ports import in the new module.
2. New `empty_catalog_contracts.py`: imports that shared class, common types and
   AccountTarget/AccountRef only; never ports, documents or repository. Defines
   `EmptyDeclaredCatalogWitnessV1(Frozen)` with exactly:
   - schema_version literal `inlet.empty-declared-catalog-witness.v1`;
   - catalog_evidence: CatalogEvidence;
   - prerequisite_action_key: Key.
   `digest()` revalidates self before the existing domain-separated fingerprint
   over its complete JSON representation. No duplicated source scalars or new epoch.
3. `CreativeProposalV1` imports this witness and gains exactly:
   `target_basis: Literal['existing_campaign','observed_empty_account'] = 'existing_campaign'`
   and `empty_catalog_witness: EmptyDeclaredCatalogWitnessV1 | None = None`.
   A wrap serializer removes target_basis when existing_campaign and removes witness
   when None in both Python and JSON modes, including nested parent serialization.
   AccountTarget is admitted only for the new exact discriminator+witness pair;
   old campaign branch and all other restrictions remain unchanged.

Model extraction acceptance must prove old standalone CatalogEvidence schema,
Python/JSON dumps and digests equal; ports/newmodule class identity equal; standalone
fresh-process imports in either order resolve; old complete PlanVersion/creative
composition nested dumps and hashes remain byte-identical. Old omission is not
`exclude_defaults` globally: only these two new fields are removed at their model.
Explicit mismatched None/discriminator pairs reject. Unsafe model_copy paths revalidate.

## Recognized scope: freeze code-derived tuple, confirm against baseline

Only Meta, exact native+metadata schemas already emitted by the collectors:
`inlet.planning-target-catalog.v1`, `inlet.planning-target-catalog.v2` and
`inlet.planning-entity-metadata.v1`.

Native coverage must contain exactly campaign and adset, each with:
status=partial, scope=sdk_known_effective_statuses, observed_count=0,
reasons=('effective_status_scope_limited',).
Metadata coverage must contain exactly campaign and adset, each with:
status=partial, scope=sdk_known_effective_statuses, count=0,
reasons=('native_scope_limited',).
All native.targets, metadata.entities and composite.targets must be empty. Native
or metadata unavailable/complete, extra/missing kind, unknown scope/reason, orphan
child, nonempty array or exclusion-filtered nonempty catalog is ineligible.

These tuples are from projection.py and metadata_http.py. The actual native and
metadata HTTP requests share CAMPAIGN_STATUSES ACTIVE,PAUSED,ARCHIVED,DELETED,
IN_PROCESS,WITH_ISSUES; adsets additionally CAMPAIGN_PAUSED. Both use the existing
read-only v26.0 paths, pagination completion and owned source context. The separate author
reported an actual passing SQLite baseline matching these exact tuples; its frozen
both-database artifact will provide the final receipt reference before implementation. The projected DTO does **not** retain
all raw query parameters or a reconstructible raw inventory: request/inventory
hashes are commitments, not a self-contained proof of a specific HTTP transcript.
Do not add a fabricated query-profile field or claim the witness proves unseen
statuses, provider-wide inventory, delivery history or zero conversions.

Reference coverage must be partial with its actual original declared_scope,
reasons and metric_basis preserved. Existing CatalogEvidence binds exact account,
connection/version, source-binding digest, reporting window, observation envelope,
composite commitment and expiry. New witness checks the recognized arrays above;
no separate mutable lookup or latest catalog is introduced.

## Strict retained chronology and bounded encoding

Retain full CatalogEvidence rather than just EvidenceRef: a digest-only reference
cannot establish empty arrays historically. No raw credentials, private session,
creator identity or provider payload beyond the existing customer-visible catalog
is added. A witness's canonical JSON is bounded to256KiB; the enclosing existing
1MiB document cap still applies. Fail on overflow, never truncate.

Strictly require aware datetimes, rejecting numeric/coerced values and unsafe copied
nested models. Check all new instant comparisons/minima in UTC, including native,
metadata, reference and enclosing document boundaries, without restamping observations
or changing the original serialized values used by existing catalog hashes. The
extracted old model retains its validator unchanged; the new witness adds UTC
checks before accepting its result. Existing validators may remain conservatively
stricter, but no fold may admit a reversed real interval. Include offset-equivalent
and same-ZoneInfo fold regressions and forbid expiry extension.

Recompute existing metadata/composite commitments through their existing validators.
The opaque native inventory digest cannot be reconstructed from this projection;
validate its exact cross-binding, not a fictitious rehash of missing raw inventory.
The new witness digest additionally binds the complete retained projected graph.
Actual save equality and existing immutable document-row digest provide provenance;
a self-consistent rehash alone is not authentication of a provider observation.

## Document-level prerequisite and proof binding

New cycle-free `empty_catalog_validation.py` exports:

`validate_empty_catalog_proposals(*, inputs, proposals, actions, evidence,
 generated_at, valid_until, privacy_revision, sources: tuple[SourceFence,...]) -> None`

Types are existing PlanInputRevision, CreativeProposalV1, ManualAction, EvidenceRef
and aware datetime plus cycle-free source_contracts.SourceFence; the module must
not import PlanVersion/ports. Sources are the actual selected retained proof account
source_fences, unique by full account; each witness reference must match exact
account, source-binding digest, source_revision and privacy. AccountRef alone does
not contain this complete source commitment. PlanVersion's
exact V5 path invokes it after existing creative/selected proof validation. For
each new account proposal require:

- Same exact Meta AccountTarget on action and brief, owned account present in inputs;
  exactly zero confirmed ceiling, typed product, at least one witnessed image,
  explicit positive global creative capacity and existing constraint/capacity rules.
- Witness catalog reference identical to the unique evidence entry named by its key,
  account/connection/source version and privacy equal document/input/proof bindings;
  reporting dates equal the input primary window. Currency/timezone remain their
  reported facts; no native budget or FX allocation is introduced.
- Actual original observation completed by generated_at; generated_at strictly before
  witness expiry; valid_until no later than expiry (all compared as UTC instants).
- Exactly one prerequisite action with key `review:account_<account_id>`, same full
  AccountTarget, kind investigate, no native budget/proposed fields; exact catalog
  reference in its evidence_keys. New creative action names that exact prerequisite.
  The prerequisite key comes from the selected composer's actual output, not a
  separately invented graph. Reject wrong/missing/duplicate/campaign prerequisite.
- Existing creative proof binds original image/product/privacy independently, and
  the proposal/brief action identity and evidence keys remain exact. One proposal
  consumes one global creative slot; no one-per-platform exemption.

This validator is called on stored PlanVersion parsing, so history/export performs
complete structural proof checks without current media bytes, paid entitlement or
new provider IO. Existing historical READ_ROLES and privacy/source-erasure rules
still run. A later nonempty catalog alone does not alter this retained original
empty-query witness or historical digest. Currentness continues to compare current
source/catalog evidence through existing readers, separately from history. Persisted
SQL source/witness fences do not discover out-of-band provider campaign changes;
only fresh acquisition can observe those changes. No every-read live inventory
guarantee or provider-wide emptiness follows from SQL currentness.

## Actual composition and final save binding

Extend the standalone creative composer with keyword-only optional
`account_prerequisites: tuple[ManualAction,...] = ()`; existing callers/outputs stay
unchanged. The actual selected+creative composer supplies its already-created
measurement actions. Eligible empty Meta account preparation uses the corresponding
actual action; absent prerequisite means defer, not fabricate. Plain language says
nothing observed in the declared query, not an empty provider account. Production
steps are manually preparatory with production_required/not_assessed and no launch,
activation or buying instruction.

New helper `assert_empty_catalog_bindings(proposals, catalogs) -> None` compares
each embedded witness catalog against the unique fully revalidated actual
CatalogEvidence from the ticket's collected bundle, exact full model and digest.
Use it during composition and repository.save_generation after genuine bundle
unwrap and exact target/evidence binding, after completed replay earlyreturn and
before writes. No missing witness fallback. Final source/privacy/session/paid/goal
checks remain unchanged. Do not compare to a live later catalog during history.

## Required review/test sequence (not executed here)

Baseline actual API receipt first; then model extraction/omission goldens and fresh
imports; recognized-scope and unsafe-copy tamper negatives; exact prerequisite and
proof joins; UTC folds/expiry/size bounds; full actual-bundle substitution refusal;
pure historical reparse after a distinct later nonempty catalog; finally actual
V5 generation/read/export/replay on both databases with zero execution effects.
Include empty, nonempty-but-excluded, unavailable, orphan and unrecognized scope
cases. Keep old baseline documents and new documents separately. No full Q08,
expert, browser, live or default-policy qualification follows from these checks.
