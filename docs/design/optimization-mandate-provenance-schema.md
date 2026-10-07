# Optimization Mandate Origin: Additive Schema Proposal

Standalone schema implementation: migration `20261007_0080` follows0079. Existing0079
and all policy/document v1 hashes remain unchanged. Runtime preparation, generic
consent and forward-gate enforcement are subsequent work; this package does not
claim an end-to-end configured consent journey.

## Why0079 Or No Migration Does Not Honestly Fit

`initial_budget_mandate_preparations` binds calibration/observation/native-v2 choices
and a planning-reporting profile. Existing-campaign qualified discovery has different
qualification and target-owner lineage. Inventing calibration IDs/profile digests,
changing its existing parser, or relabeling native observations would be dishonest.

ProviderExecutionRevision.policy is the hash-committed existing financial policy;
adding source fields in that JSON changes v1 hashes. An in-memory cache cannot retain
exact consent origin, and comments/JSON in unrelated records lack immutable ownership
and fresh export validation. A dedicated minimal immutable sidecar is warranted.

## Proposed Strict Document And Table

Strict `OptimizationMandatePreparationV1`:

- explicit schema version `inlet.optimization-mandate-preparation.v1`;
- workspace_id, mandate_id, mandate_revision, environment;
- provider_policy_digest (existing financial revision digest);
- goal_digest; exact goal ID/revision are retained in the intent selection;
- exact `OptimizationCustomerIntentV1` (owned goal/account selection, opaque option,
  customer-confirmed total and named aggression; no technical knobs);
- account_scope_digest, target_set_digest, inventory_request_digest,
  inventory_digest, native_state_digest;
- qualification_id, qualification_revision, qualification_digest and
  evidence_profile_digest (real source lineage, never generated placeholders);
- exact `OptimizationOperatingPolicyV1` document and operating_policy_digest;
- preparation digest computed over this strict canonical document.

The operating policy is bounded three-rule numeric authority provenance, not a
provider response, report, performance snapshot or credential. Keeping its exact
small document makes the retained source of derived caps and aggression reproducible
when a deployment policy file is replaced. Existing financial policy revision still
owns the actual period/currency/caps; origin cannot override it.

Proposed `optimization_mandate_preparations` table:

```
mandate_id              varchar(32)  PK
mandate_revision        integer      PK, >0
workspace_id            integer      NOT NULL
provider_policy_digest  varchar(64)  NOT NULL
preparation_digest      varchar(64)  NOT NULL
document                JSON         NOT NULL
UNIQUE(preparation_digest)
FOREIGN KEY(mandate_id, mandate_revision, workspace_id)
  -> provider_execution_revisions(mandate_id, revision, workspace_id)
  ON DELETE RESTRICT
```

Insert guard checks parent revision scope, existing financial digest, origin marker
and preparation digest. UPDATE and DELETE prohibited. Application strict parser
also binds every scalar/document field and confirms document/operating-policy digests;
unknown fields/version, duplicate keys or oversized payload deny. A bounded serializer
must never fall back to arbitrary JSON. No email/name/order/media bytes/native HTTP
payload or raw provider identity belongs in this table.

## Required Origin Marker: Absence Must Not Be A Legacy Bypass

A sidecar lookup alone is unsafe: missing/deleted provenance must not cause generic
consent or forward execution to treat a new prepared revision as legacy.

Add to the immutable provider_execution_revisions row:

- `origin_kind`: legacy | optimization_customer_v1; existing rows/default legacy.
- `origin_preparation_digest`: nullable digest; NULL iff legacy, required otherwise.

The implemented deferred FK is the nullable single digest column referencing the
sidecar's globally UNIQUE preparation digest. A UNIQUE index on the parent digest
prevents two parents claiming the same not-yet-inserted proof. An immediate sidecar
INSERT trigger requires exact mandate/revision/workspace/financial-policy-digest and
parent origin digest. The immediate reverse parent guard rejects borrowing an
existing sidecar under another scope. Thus parent-first exact insertion can commit;
sidecar-first or either wrong-scope order cannot. Missing proof fails at commit.
The strict document digest itself commits the same identity.

Both columns are additive ALTER TABLE operations, with the nullable FK and CHECK
inline on the second column. No financial parent rebuild or disabled integrity is
used by0080. Populated downgrade/reupgrade preserves legacy revision policy bytes
and its RESTRICT consent child. Downgrade drops dependent sidecar triggers before
columns, and refuses any retained marked origin before changing schema.

Inspection found no preexisting global DB immutability trigger for financial
revisions.0080 therefore adds a narrow guard: every marked revision is immutable,
and every revision's origin discriminator/digest is immutable. Legacy unrelated
updates retain existing behavior; legacy-to-marked UPDATE is forbidden. Sidecars
are immutable and cannot be deleted.

PostgreSQL enforces the deferred FK directly. Existing SQLite/common fixture
connections do not universally enable foreign keys. This package does not silently
change all engines: marked-origin INSERT explicitly denies when
`pragma_foreign_keys != 1`. Future configured preparation must preflight this too.
SQLite users need integrity enabled before their transaction. Legacy inserts remain
compatible. Tests prove the actual FK-off connection cannot create marked authority
or relabel a legacy revision. No claim of universal engine configuration is made.

Preparation chooses IDs/digests before writes, inserts new immutable revision with
origin and exact sidecar in one transaction, then rechecks original session/goal/
source/current pinned policy before commit. `revise(commit=False)` must gain a
trusted explicit origin argument before its initial INSERT, not update an immutable
revision after flush. Existing callers default legacy, preserving old hashes and
behavior. Failure rolls back both records. Identical replay returns exact existing
origin; changed policy/intent requires a new revision.

Generic consent and all forward review/approval/claim paths dispatch on immutable
origin_kind: optimization_customer_v1 requires the exact strict sidecar and current
configured policy/profile/selection validation. Missing or mismatched origin is
unavailable, never fallback. Original reconciliation/receipt/settlement continues
to retain its historical authority and money when future use becomes invalid.

Configured customer optimization assembly must require optimization_customer_v1
origin for newly consented and forward-selected policies. It must reject the legacy
technical-knob creation route as an alternative for that configured flow; attach
this requirement in trusted runtime/service code, not a client field. Existing
legacy revisions remain readable/reconcilable and old explicitly injected runtimes
retain compatibility. Do not silently upgrade a legacy consent. Fresh explicit
customer preparation/consent can append an eligible revision under the same ledger
without changing account-set/period/currency/overall-budget invariants.

## Lifecycle, Export And Downgrade

Classify as protected execution-authority provenance, matching retained policy/
consent records. Include in canonical model/ownership registry and customer export
with a versioned strict serializer and scalar/JSON bindings. Resolve ownership via
composite mandate revision/workspace; no standalone lookup across workspaces.

Source/privacy/goal/qualification/profile drift disables future use through current
checks but does not erase original attempts, receipts, holds, ledger or immutable
consent origin. No new advertising/performance evidence is retained here. Derived
numeric evidence keeps its own erasure rules. Export fresh authority checks and
workspace privacy fence must apply as they do to existing authority rows.

Downgrade refuses if any sidecar or origin-marked revision exists. When empty,
remove the deferred revision FK/marker CHECK, sidecar guards/table and new columns
without changing prior policy bytes or authority rows. Roundtrip tests populate
legacy revisions before upgrade and verify exact bytes/rows/holds preserved;
nonempty downgrade must fail without partial destruction.

## Validation Required Before Production Implementation Freeze

BothDB atomic successful preparation, original-session final-guard rollback,
missing/wrong sidecar commit failure, cross-workspace parent rejection, update/delete
denial, origin-marker mismatch, stale policy at consent, legacy-route bypass denial,
exact replay/new revision and period/account/ledger invariants. Strict export rejects
unknown keys/scalar mismatch and retains allowed authority after derived evidence
erasure. No raw report/credential retention. These runtime acceptance cases remain pending the next assembly package; schema
checks alone do not qualify a provider or supply financial headroom.
