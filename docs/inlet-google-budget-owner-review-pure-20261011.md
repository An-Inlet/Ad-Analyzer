# Standalone Google owner investigation proof

This is slice A of `google-budget-owner-output-review-v1.md`, based on `3597e7c`.
Only new pure contract/composer/validator files and tests are added. No PlanVersion
field, capability registration, service/history integration, UI or V6 activation
is included. The integrated input-only generation refusal remains unchanged.

The proof retains complete original intent and full owner witness. Composition
uses the unchanged full-source active binding kernel; validation compares the exact
input commitment and full actual catalog-derived witness. Canonical investigation
actions contain no NativeBudget or proposed field and cannot be substituted with
Apply instructions. All affected campaigns stay in the witness. Explicit empty,
zero, privacy/source, copied primitives, conflicting actions, action count and the
existing 1MiB aggregate byte bound remain distinct and enforced.

The implementation reuses the witnesses returned by the existing binding kernel.
It deliberately preserves existing full witness revalidation rather than introduce
unchecked cache flags into reviewed contracts. That entails bounded repeated
validation (at most 20 reviews), not a claim of one parse per graph at every public
model boundary. No latency improvement or authority-window change is claimed.

Review identified direct unsafe-copy serialization as an additional boundary.
Wrap serializers on these two new DTOs revalidate before output; the proof's size
validator constructs its explicit field payload to avoid self-serializer recursion.
Existing global Frozen and historical model behavior are untouched.

Evidence is retained under
`/workspace/inlet-evidence/20261011/google-budget-owner-review-pure`.
Initial Ruff line-length failures are preserved. First configured mypy passed
1458 source files before the serialization repair. Final `pure01` passed 37 cases, zero failures/errors/skips, 5.457s JUnit: new
standalone cases plus the unchanged nested legacy byte/digest golden and all seven
existing generation-refusal boundary cases. Whole Ruff, configured no-path mypy
(1458 source files), diff checks, and separate fresh-process imports of each new
module passed. No database or provider operations ran. Independent final immutable
review is requested at freeze.
