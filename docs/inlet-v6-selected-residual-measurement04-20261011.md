# Selected-current residual measurement04

Exactly one separately authorized instrumented normal PostgreSQL owner case passed. Original exit0; testcase31.020s/XMLsuite33.710s/process36.520756s. Application/tests9fd75ab unchanged; source doc-head dd13322. All1794 source hashes/Git state unchanged. No retry. Report5e9d5ec4 complete235frames/34save-final calls, no truncation/accounting/recording/restoration errors. No fixed expiry event.

Save3.792293s, process-wideCPU3.156106s,2385SQL/0.896699s execution. Pre-CAS guard returned with observer age3.693833→3.693847s; post-flush returned3.792411→3.792427s. Brackets are not exact predicate values. Pass is neither acceptance nor R01–R03 closure.

## Disjoint interpretation

Paired assertion exclusive0.196226s plus selected assertion exclusive0.488626s =0.684852s, about18.1% of save. All16 assertion invocations have zero inclusive completed/failed SQL (including descendants). Paired inclusive0.492346s overlaps nested selected assertion and must not be added to selected-inclusive0.488626s. This is a measured pure domain-assertion boundary, not a measurement of removable duplicate validation.

selected_start8calls0.155831s/280SQL; saved_catalogs2calls0.089491s/114SQL; goal_progress3calls0.030483s/51SQL. Other currentness work remains mixed; selected-current exclusive residual0.583250s/300SQL is not pure. No SQL duration subtraction is treated as pure CPU or lock time.

| Family | Calls | Inclusive wall s | Exclusive wall s | Exclusive SQL | Exclusive SQL s |
| --- | ---: | ---: | ---: | ---: | ---: |
| save | 1 | 3.792293 | 0.068709 | 50 | 0.033000 |
| generation_entry | 1 | 0.233459 | 0.120125 | 0 | 0.000000 |
| paired_assert_ticket | 6 | 0.492346 | 0.196226 | 0 | 0.000000 |
| selected_assert_ticket | 10 | 0.488626 | 0.488626 | 0 | 0.000000 |
| authority_final | 34 | 0.000466 | 0.000466 | 0 | 0.000000 |
| actual_bindings | 1 | 0.001919 | 0.001919 | 0 | 0.000000 |
| owner_bindings | 1 | 0.139455 | 0.064896 | 0 | 0.000000 |
| final_sources | 1 | 1.969041 | 0.000981 | 0 | 0.000000 |
| selected_current | 2 | 1.832537 | 0.583250 | 300 | 0.084950 |
| selected_start | 8 | 0.155831 | 0.155606 | 280 | 0.071964 |
| selected_historical | 12 | 0.168699 | 0.168699 | 60 | 0.042604 |
| selected_scope | 78 | 0.376079 | 0.376079 | 546 | 0.202946 |
| selected_aggregate | 22 | 0.523289 | 0.053722 | 66 | 0.034416 |
| aggregate_current | 30 | 0.332745 | 0.225047 | 280 | 0.110104 |
| saved_catalogs | 2 | 0.089491 | 0.089491 | 114 | 0.031383 |
| retained_reporting | 8 | 0.230054 | 0.155526 | 160 | 0.059745 |
| goal_progress | 3 | 0.030483 | 0.030483 | 51 | 0.015758 |
| image_current | 1 | 0.053073 | 0.053011 | 103 | 0.023367 |
| original_receipt_current | 1 | 0.082450 | 0.082450 | 56 | 0.012753 |
| retained_capture | 1 | 1.297470 | 0.039436 | 0 | 0.000000 |
| owner_retained | 1 | 1.258034 | 0.046213 | 69 | 0.022849 |
| retained_context | 2 | 0.077420 | 0.077420 | 0 | 0.000000 |
| owner_original_evidence | 2 | 0.087428 | 0.087428 | 8 | 0.005125 |
| creative_retained | 1 | 1.084821 | 0.024662 | 36 | 0.014035 |
| selected_retained | 1 | 0.840698 | 0.338019 | 165 | 0.100173 |
| image_retained | 1 | 0.128254 | 0.086998 | 41 | 0.031527 |
| creative_witness | 2 | 0.094616 | 0.094616 | 0 | 0.000000 |
| storage_pair | 1 | 0.082189 | 0.082189 | 0 | 0.000000 |

All save descendant exclusive spans sum exactly to3.792293s; inclusive rows overlap. CPU is process-wide and residual includes unwrapped work/observer overhead. No comparison across differently instrumented runs demonstrates improvement.

The evidence supports reviewing a model-specific same-call strict-validation/kernel contract for the two ticket assertion domains. It does not support removing an assertion after SQL, either fresh selected pass, privacy/session/goal/paid checks, or changing the original deadline. The0.684852s is the full assertion budget, not promised savings. No production edit or repair execution is authorized by this result.

Evidence `/workspace/inlet-evidence/20261011/v6-normal-save-subphases04/`: manifestd84bc3b0/plugin d9685ffb/runner f78eee22; XML/log/result/report/summary retained. External Ruff/compile passed before run; no redundant post-outcome checks. Earlier outcomes and failures stay separate.


## Correction To External Lint Provenance

Subsequent Q13 observer review found that the preserved `ruff01.log` for this
measurement contains S110 and RUF100 at the report-write fallback: the S110
suppression was placed on `pass` instead of the enclosing `except`. The earlier
statement that external Ruff passed is incorrect. The original log and immutable
freeze remain untouched. This is an external diagnostic source-style finding;
the measured result, exact observer source and accounting limits remain preserved,
but this preparation must not be described as lint-clean. The successor observer
corrects comment placement with unchanged executable AST and retains individually
captured check exit codes before any new execution.
