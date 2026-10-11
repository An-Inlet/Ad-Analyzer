# Selected ticket prechange characterization: first observation

Pure01 on unchanged production9fd75ab (docs head777b8d1) stopped as authorized: **5 passed,1 failed,10 unrun**, no skips. This is a failed characterization hypothesis, not evidence of a production validator defect. No production code changed, no SQL/API/observer or authority clock ran, and there was no retry.

Evidence: `/workspace/inlet-evidence/20261011/selected-ticket-characterization/`. Exact reviewed manifest18d571913ea608a7250ee0156317b57f105bb304bf7a39e6851c11408fbe5fba binds1694source/config hashes,16ordered nodes and unchanged runnerd002dff04ff8b03426fd40860ed7b1cebb7332606ff533f6e7e1008590ff69d3. Original exit1 was saved before XML interpretation. Process3.906134750s; XML suite2.019s; executed testcase sum1.522s. The failed case took0.187s. Source hashes remained unchanged. Original full test source is preserved separately in pure01-failed-test-source.py.

The three genuine pure selected/paired/V6 fixture repeated-validation byte/digest baselines passed. The two top-level selected/paired subtype cases passed: public override/custom validator behavior and original same sentinel propagate; declared reader parsing downcasts these subtypes without invoking their custom validator. These limited observations do not prove the entire annotated graph is inert.

The sixth node, nested planning subtype, failed at the mandatory `SourceFence.model_validate` call. The actual rejection is `account.extra_marker`, `extra_forbidden`; the previous expectation that the extra field would be discarded was false under this existing extra-forbid schema. The original mandatory parse therefore rejects this graph before any checked-kernel eligibility decision could arise. Preserve that rejection. Do not loosen configuration, suppress the extra field or reinterpret it as a performance regression.

The two other always-base cases, two legacy cases, four datetime cases and two unsafe-copy cases remain unrun. Current evidence establishes neither legacy canonicalization nor custom timezone fallback compatibility. Non-null ClosedDayCoverage subtype and stateful custom-timezone suffix/error parity are explicit additional requirements before production compatibility approval, to be folded into bounded existing cases.

The smallest source amendment proposed for review is to distinguish extra-bearing rejection from an accepted same-fields custom subtype: retain an explicit extra_forbidden assertion, then separately test a subtype with custom validator/serializer but no new field through the same declared parent. This separates mandatory refusal from downcast behavior rather than weakening the test to accept either outcome. Keep the successful first five cases distinct; a later authorized selection should cover only corrected sixth plus ten unrun cases, not repeat all16. This is a proposal only at freeze time.

Preparation findings are retained: initial Ruff import/line-length findings; mypy9test-only findings (dynamic class variable typing, using a None-return method as a value, missing abstract tzname); then final whole Ruff passed and configured no-path mypy1493passed. The final source passed exact16collect-only in0.71s before the one body run. No static repeat is needed for this documentation-only outcome. Code commit contains the exact failed hypothesis so the original result remains reproducible.

No kernel implementation, timing improvement, five-second acceptance or R01–R03 closure is claimed. Continue only after the parent and independent reviewer interpret this observation and authorize a narrow source amendment/remaining selection.

## Reviewed amendment and disjoint Pure02

The independently reviewed correction separates extra-bearing subtypes from same-fields custom subtypes in the three nested cases. Each first proves the exact original single `extra_forbidden` error and `(field, extra_marker)` location, then uses a different subtype with no added field to characterize declared canonicalization. No production validator or fixture helper changed.

Pure02 manifest aab26dfe25e94dc199e76afcaaa620103c1c2a78b776a5a9647e05fbdb715f5d selected exactly three changed nested cases plus eight previously unrun cases; the previous five passes were excluded. Original exit0, **11 passed**, no failure/error/skip/unrun, source unchanged. Process2.640694013s; XML suite1.048s; testcase sum0.649s. Combined successful characterization is16distinct cases, with the original failed hypothesis preserved independently, not hidden by an all-green rerun. Whole Ruff and configured no-path mypy1493 passed on the amended source before this run; collection found exact11 in0.40s.

Observed semantics support a bounded canonical-model path:

- All three same-fields custom nested subtypes returned the exact declared base type and original base JSON, without their custom validator/serializer callbacks. All extra-bearing variants retained exact rejection.
- Both legacy original document serializers ran once. Actual fixed-label traces were `document` for both cases; the nested MeasurementWindow subtype serializer was not dispatched by the declared-field serialization. Returned document/window types were exact base classes; a second parse had no custom callbacks; deliberately corrupt original serializer payloads still rejected.
- Exact UTC/fixed-offset/ZoneInfo and custom timezone instances all survived ReportingWindow validation with their resident timezone identity/fold and serialized bytes preserved. Thus AwareDatetime is not by itself a callback-free scalar guarantee: the custom timezone requires the original suffix fallback.
- Both copied-invalid nested source/count cases rejected through the current public assertion.

The proposed next production boundary remains the original mandatory prefix, followed by callback-free custom-scalar eligibility on its returned canonical graph. An ineligible graph executes only the original remaining suffix, not another prefix. This preserves custom callbacks and the current type(self) versus declared reader distinction. Public validators, all SQL-separated assertions, deadlines and authority are unchanged by this characterization.

Production implementation is still gated on the exact scanner/type-access contract and regression coverage for stateful custom-timezone/error suffix parity and a non-null ClosedDayCoverage subtype. These should extend existing bounded cases, not introduce an eighty-class runtime registry. This evidence supports the smaller approach; it does not establish timing savings or reliability margin.
