# Shared Selected Reporting Reader V1

Use reviewed selected_policy_contract (root795f7ab) in the internal reporting
collection path only. Genuine canonical v4 and reserved v5 tickets may collect
reporting evidence; this does not establish complete v5 document readiness.

Replace duplicated exact-v4 policy construction in
SelectedPlanEvidenceBundleV1.assert_ticket and check_selected_start with
assert_selected_ticket_policy. Revalidate ticket and apply validate_creative_policy:
v4 requires absent creative input, v5 explicit typed creative input. Preserve the
existing explicit selected_reporting requirement and every source/goal/session/
privacy/paid guard. In OwnedSelectedEvidenceReader.collect apply
assert_selected_composition_policy to the supplied policy and genuine ticket
before any authority/provider/native I/O, plus the same creative input guard.
Retain each existing public exception boundary: local/API conflict versus pure
ValueError, never masking unrelated provider/clock errors.

Do not alter SelectedPlanComposer, PlanVersion, retained-source dispatch, history,
policy_capabilities, service routing or defaults in this package. They continue
to reject unsupported creative generation. Existing local_reporting_v3 proofs,
traffic hashes, retained catalog logic and original-session final rechecks remain
byte-for-byte semantically unchanged. No fake v4 ticket, stripped input, changed
policy digest or document retagging to reuse the reporting path.

Focused tests construct genuine canonical v5 policy/ticket/input/context bundles,
not a v4 document with a new tag. Test pure bundle and actual owned paired reader
on SQLite/PostgreSQL using existing mock-native acquisition fixtures; explicit
empty typed creative input is enough since this collector does not inspect media.
Assert exact saved creative/policy context, unchanged selected metric/traffic proof,
and continued v5 capability/composer/document denial. Test mixed/altered policies,
wrong ticket digest and missing v5 creative input before native I/O; v4 legacy byte
and digest regressions must remain unchanged. Run existing affected collector/pure
cohorts and whole Ruff/configured mypy. Coordinate the PostgreSQL slot.
