# Selected ticket canonical boundary audit

Preimplementation source findings, not production approval. No application import, test body, SQL or provider call was executed for this audit. Reproducible AST inventory and24source hashes are at `/workspace/inlet-evidence/20261011/selected-kernel-source-inventory/`. The annotated graph yields80reachable classes including bases; this is a source audit aid, not a runtime validation oracle or claimed exhaustive Python behavior model.

## Concrete boundary inventory

Entry roots: GenerationTicket, SelectedPlanEvidenceBundleV1 and SelectedPairedEvidenceV1. Their field sets can be frozen in regression tests, along with the annotation/configuration graph, instead of traversing80class inventories on every production call. No Any-typed fields were found in the annotation closure. There is no manual payload projection in the proposed kernel: mandatory ordinary model validation still validates all actual fields, including future additions.

Three shared bases declare revalidate_instances=always: planning_documents.common.Frozen, planning_catalog.contracts.Frozen and campaign_performance.presence_contracts.Frozen. The installed Pydantic config.py documents that this policy belongs to each declared model, does not propagate automatically, and revalidation of nested subtype instances produces the declared field class. Most graph edges therefore reconstruct the declared model rather than preserve an arbitrary subtype.

Named legacy exceptions are GoalDefinition/MeasurementWindow and GoalSalesProgressV1/ClosedDayCoverageV1/MeasurementWindow. They are not covered by the always bases. ConfirmedGoalRef.definition has an explicit before-validator dumping a GoalDefinition instance to Python values before declared parsing. CommerceEvidence.document similarly dumps GoalSalesProgressV1 before declared parsing. These edges must be tested directly; do not infer their safety from the outer Frozen setting. Custom nested serializers can run on the original supplied instance at these boundaries, so preserve the original first parse and error order.

Existing PreparedSelectedPlanProjection and PreparedRawRangeTrafficProjection validate an incoming graph and then use private already-validated projection state. This supports the ordinary canonical-model/private-operation pattern, but does not grant broad ticket/source/currentness trust and does not authorize skipping SQL-separated assertions.

## Smaller candidate than a runtime registry

Reject the previously suggested80class runtime exact-inventory walk. Prefer ordinary mandatory validation plus private invariant body on its actual returned declared models. Keep exact top-level type checks only to select the original fallback for a subtype, preserving type(self).model_validate and custom public assert_ticket override semantics. Kernel dispatch must remain internal to the same synchronous lexical invocation; no trusted boolean, marker token, model cache, source cache, new authority or extended lifetime.

This candidate needs targeted compatibility characterization before it is sound enough to implement:

- Top-level selected/paired subclasses with validators/serializers/overridden assert_ticket: original behavior/fallback, including same exception and validation order.
- Nested declared-always subclass: prove actual returned field is the declared base; copied invalid nested fields still reject. Test an extra-field/custom-validator/custom-serializer subtype, not just exact base fixtures.
- Both named legacy edges: prove mandatory validation reconstructs canonical declared GoalDefinition/GoalSalesProgress and nested windows/coverage; custom original serializer behavior must be preserved, then no custom subtype may survive unnoticed.
- Datetime/timezone: AwareDatetime can retain a supplied datetime/tzinfo; always-model revalidation does not itself prove scalar canonicalization. Ordinary UTC/fixed-offset/ZoneInfo and DST-fold semantics must preserve bytes and errors. A custom stateful tzinfo remains an explicit unresolved compatibility edge; do not claim exactroot alone proves arbitrary callback absence. Prefer an original fallback scoped to any surviving custom behavior rather than a generic trusted graph traversal, if a bounded predicate can be established.
- Decimal count primitives already use exact-type before validators, so Decimal subclasses are rejected at relevant count boundaries; preserve that refusal.

## Decision and implementation gate

A runtime frozen graph registry would be disproportionate to the measured0.685s entire assertion budget and impose a maintenance hazard. A canonical returned-model kernel appears materially simpler, but source inspection alone does not close the legacy serializer and custom timezone edges. The exact public exception/unsafe-copy contract must remain, not be redefined as an optimization convenience. Independent review should decide whether standard mandatory validation plus named compatibility tests and conservative top-level fallback suffices, or specify a small named-edge fallback. If neither is defensible without a broad traversal, stop this optimization and report that precise blocker.

Do not implement production until that compatibility question is closed. The next bounded activity, if authorized, should be pure characterization of installed Pydantic behavior on the genuine selected fixture and the named subtype/legacy/timezone variants, with no SQL or performance run. Preserve prechange results. No more instrumentation or renewed authority is needed for this semantic question. A later repair must keep all public mandatory validation, all after-SQL assertions, both fresh selected passes, original5s guards and rollback acceptance.
