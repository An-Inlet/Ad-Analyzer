# Normal PostgreSQL save measurement02

Changed observer only; application/tests remain9fd75ab. Source9435fc4. The observer correction removes per-call flush spans and records authority brackets only during save; caps remain unchanged. All measure01 artifacts remain immutable. Exactly one separately authorized run, no retry.

Original exit0, one case passed without skips/unrun: testcase24.370s, XMLsuite26.091s, process28.252921s. Report43cc7110 has no truncation, accounting errors, recording errors or restoration errors. First generation56frames/34save-final calls; replay1generation frame/no save. All1788 source hashes and Git state were unchanged.

## Disjoint save partition

Save3.086127s; process-wideCPU2.795252s;2385 SQL executions/0.508601s. Direct child inclusive spans plus root exclusive residual sum exactly to save. SQL counts are save-scoped, not full-journey counts.

| Direct span | Wall seconds | SQL count | SQL seconds |
| --- | ---: | ---: | ---: |
| generation_entry  | 0.132976 | 0 | 0.000000 |
| authority_final lock | 0.000017 | 0 | 0.000000 |
| actual_bindings  | 0.001862 | 0 | 0.000000 |
| owner_bindings  | 0.133315 | 0 | 0.000000 |
| final_sources  | 1.819665 | 1561 | 0.336342 |
| retained_capture  | 0.860092 | 774 | 0.146908 |
| authority_final pre_cas | 0.000013 | 0 | 0.000000 |
| storage_pair  | 0.079345 | 0 | 0.000000 |
| authority_final post_flush | 0.000016 | 0 | 0.000000 |
| save_unattributed_residual  | 0.058826 | 50 | 0.025351 |

## Nested interpretation

Within final_sources1.819665s: two distinct fresh selected-current passes0.921148s/701SQL and0.775016s/701SQL, image-current0.046033s/103SQL and original-receipt-current0.076467s/56SQL. These are children, not additions to the top-level table. Within retained_capture0.860092s, selected_retained0.494016s/620SQL is the largest recorded descendant. Distinct proof/freshness passes remain required; these measurements do not authorize their removal or reuse across callbacks/SQL.

Pre-CAS original final returned with observer fact-age bracket2.996500→2.996513s; post-flush returned3.086234→3.086248s. No fixed expiry event occurred. These are bracketing samples, not original predicate values. Generation8.236057s includes5.149930s outside the save span; replay generation0.753896s.

The measured concentration supports next source-only review of the selected-current and selected-retained subtrees. It does not identify row-level causes or establish redundant validation, contention, guaranteed margin, removable CPU, or original R01–R03 cause. Any repair needs a concrete source mechanism and separate review; no new probe/production change is authorized by this result. This is instrumented measurement, not acceptance or incident closure.

Evidence directory: `/workspace/inlet-evidence/20261011/v6-normal-save-subphases02/`. Manifest14b4c193/plugin c5fe29f0/unchanged runnerf78eee22; collection01 reused only after exact prior-source equality. External Ruff/compile passed before run; no application changes or additional checks after outcome.
