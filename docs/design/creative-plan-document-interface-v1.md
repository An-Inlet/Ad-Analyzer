# Pure Creative Plan Document V1

Preparatory document validation only, after selected reporting contracts and
creative retained proof. No service/capability/retained-source/history dispatch,
SQL persistence, UI, default change or runtime activation in this package.

Add optional omitted-on-None fields to PlanVersion:
`creative_proof:CreativeRetainedProofV1 | None = None` and
`creative_composition:CreativeCompositionV1 | None = None`.
Use only document-safe leaf imports. Existing v1–v4 serialized bytes/digests,
including explicit-null omission, remain identical.

Replace the temporary blanket creative-document rejection only for the exact
canonical v5 policy/generator pair. V5 requires explicit inputs.creative,
selected_reporting_proof, creative_proof and creative_composition, including
explicit empty values where meaningful. All other policies reject these new
proof/composition fields and creative_basis evidence references; existing legacy
creative-input and selected-policy checks continue unchanged. Mixed/unknown
policy pairs cannot use the creative proof path. Reporting proof/input/privacy
validation is identical to v4; no retagging or altered reporting hash semantics.

Extend EvidenceRef.kind with creative_basis. Add a pure helper in a new
`creative_plan_document.py`:
`creative_basis_reference(proof,inputs,valid_until)->EvidenceRef`.
Revalidate inputs/proof, bind exact inputs/privacy, and emit exactly one reference:

- key=creative:basis, kind=creative_basis, account=None, reporting_window=None;
- document_schema/source_revision=proof.schema_version;
- document_digest=proof.digest(), source_binding_digest=proof.source_binding_digest();
- workspace/privacy exact basis scope; expires_at=valid_until;
- observation_started_at=min(inputs.created_at, original image observed_at values),
  observed_at=max(the same values), all comparisons normalized to UTC;
- coverage=complete_in_declared_scope, with fixed text explicitly limiting scope to
  customer-declared input and owned image bytes observed at recorded times;
- reasons exactly customer_supplied_claims, visual_assessment_unavailable,
  production_required; fixed metric_basis states no measured performance,
  suitability, rights or continued availability qualification.

Validator for a genuine v5 document requires exact equality of its single creative
reference with this helper. It binds proof to saved inputs and the common evidence
privacy; composition.assert_basis(proof.basis); and every typed proposal action and
brief must equal the corresponding ordinary document action/brief. No additional
untyped creative_review action or brief may remain. All production basis_evidence_key
values equal creative:basis. An unknown/zero asset capacity permits no proposals;
positive capacity bounds the global proposal count and existing required-assets
checks remain. Existing document target/catalog/account/exclusion/priority/reference,
ancestry, budget, authority and byte ceilings continue to validate normally.

Keep the matching helper in the document-safe module; it must not import PlanVersion
or ports at runtime. PlanVersion can call a validator with explicit inputs, proof,
composition, evidence, actions, briefs and valid_until, or implement equivalent
checks locally; avoid a cycle. Parsing alone grants neither observed ownership nor
persistence authority. Runtime v5 remains unregistered and existing v4 composer
continues to refuse v5. Later genuine v5 composition constructs the final document
once from verified inputs/evidence; never generate v4 then rewrite its tags.

Tests construct full validated canonical v5 fixture values from typed input/basis/
proof/proposal sources (not a retagged old document), assert every omission/mismatch
fails including empty cases, field/value digests, added/dropped generic creative,
foreign targets, capacity, reference scope/time, copied models and mixed policies.
Assert v1–v4 byte/digest goldens and v5 capability/composer refusal unchanged. Run
whole Ruff/configured mypy. Historical/persistence acceptance stays separately gated.

Review clarification: v5 document checks normalize input creation, generated_at,
valid_until and all reference observation/expiry instants to UTC before bounds
comparisons (including DST folds). Do not rely on legacy same-zone comparisons.
This does not change v1–v4 serialized values. Future genuine bundle/composer must
validate the full canonical policy/digest, not infer it from version strings.
