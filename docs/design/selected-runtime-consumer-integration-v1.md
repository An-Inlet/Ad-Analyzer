# Selected Runtime Consumer Integration Boundary

Implementation follows reviewed paired collection/composition qualification. Register
only the exact v4 policy/generator/digest, with mode selected_requested_window and
local witness local_reporting_v3. Existing v1–v3 dispatch and bytes remain unchanged.
Registration recognizes the private consumer; default deployed policy stays unchanged
until the browser and release gates are met.

GenerationEvidence adds SelectedPairedEvidenceV1. Service dispatches v4 to
OwnedSelectedPairedReader and SelectedPlanComposer; persisted selected selectors
are consumed exactly, never latest. Empty explicit selection is meaningful; absent
selectors fail v4. Final save rechecks the actual complete selected and traffic graph
under original-session authority after outside-transaction identity refresh.

Repository save validates the exact paired bundle and candidate proof, reads catalog
and selected refs from bundle.selected plus every traffic reference, and compares
complete candidate evidence and native targets. No flattened or fabricated v3 bundle.
Current retained-source dispatch uses capture_selected_retained_sources and
recheck_selected_retained_sources. Match existing bounded error semantics: propagate
401/402/403, convert expected integrity ValueError/409 into RetainedSourcesChanged.
Never catch authority failure as missing-data evidence. Normalize all new temporal
comparisons and minima to UTC, including final expiry after the last SQL read.

Historical saved plan validation checks exact stored document, full dependencies,
chosen selected capture and each traffic pin. It does not require current metrics,
TTL or source heads. Customer read/export still requires current viewer/lifecycle
authority. Semantic erasure removes the retained graphs and revokes prepared export.

Required qualification: genuine requested range + explicit event selection + capture
+ saved input through service/API into persisted v4; original-session revocation,
changed receipt/map/source/privacy, replay and missing-data behavior; authenticated
historical read/export after ordinary refresh, erasure failure; real TLS portal
flow. No live provider, advertising write, default-policy change or deployment.
