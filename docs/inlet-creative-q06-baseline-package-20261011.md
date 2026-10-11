# Q06 Actual Shared-Owner Baseline

Base `9be093a`; branch `codex/inlet-creative-q06-baseline`. New isolated
`tests/test_creative_q06_baseline.py` only, no shared fixture or production change.
The baseline is separate from unapproved owner-intent/witness/native-edit work.

Actual Google Common Basis/Vault/API paths read campaign A on page one and B/C on
page two, with real native budget response shapes. A/B share owner 2; C owns budget
4. Tests bind full returned settings (amount, total amount, period/status/type,
sharing and reference count), original account/connection/generation/advertiser,
three named child-parent mappings and original customer session. All references
come from the actual target-catalog API, not generated selectors.

A+B independently allocated within one scenario receives exact current 422 detail:
"Planning selections and scenarios must match the confirmed budget and constraints."
All retained planning graph rows and six financial/execution counts are unchanged.
Changing only B to C makes that same request valid. The generated A+C alternative
reconciles $300+$200+$500 reserve to $1,000 exactly and has no forecast. Native
settings remain unavailable throughout all actions, including complete topology.
Actual generation/current/export/replay preserves the document with no additional
native calls after generation or financial/execution effects.

The partial variant reports reference_count=3 for the two observed shared members.
Native campaign coverage is partial with `advertising_inventory_incomplete`, while
all three campaign and adgroup metadata names/parents remain completely observed.
That metadata does not repair native membership. Native adgroup settings are
unavailable in both variants and are never inferred from names.

This does NOT close positive Q06 shared-setting acceptance: current policy emits no
exact native budget edit or retained affected-set instruction, and has no specific
shared-owner refresh/reselect recovery step beyond generic coverage/measurement
caution. Those remain concrete production interface/implementation gaps. A complete
campaign query is not an atomic native snapshot or financial spending guarantee.

## Qualification Evidence

Directory `/workspace/inlet-evidence/20261011/creative-q06-baseline/` preserves
commands, logs/XML and separate complete/partial catalog/document/export JSON with
per-case SHA-256 manifests, plus a directory evidence manifest. Local only.

Initial SQLite gate stopped on the test's wrong expected generic error variant:
the API correctly rejected duplicate ownership earlier than the later validation
boundary quoted in the draft. Source service.py confirmed the exact earlier text;
only the test expectation changed. No product/authority/clock repair or relaxation.
The failed log/XML remains alongside corrected evidence.

Resource preflight: workspace 1,691 MiB and scratch 4,635 MiB available. Initial
`free` output was host memory, not effective reserve; corrected cgroup measurement
was memory.max 17,179,869,184 minus memory.current 14,741,430,272 = 2,438,438,912 bytes
(~2,325 MiB), above the 512 MiB floor. No database reset or live calls.

Terminal checks:
- sqlite-01: 1 failed, 0 skipped, 5.222s, exit 1 (expected-string mismatch above).
- sqlite-02: 2 passed, 0 skipped, 20.102s, exit 0.
- both-03: 4 passed, 0 skipped, 54.357s, exit 0; SQLite/PostgreSQL fixture schemas.
- Whole Ruff and configured no-path mypy passed (1,432 source files), before and
  after the assertion repair; format/diff check passed before freeze.
- Test/PG slot released immediately after both-03 terminal. No broad cohort run.
