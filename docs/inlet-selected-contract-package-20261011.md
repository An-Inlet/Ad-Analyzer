# Selected-Event Shared Contract Package — 2026-10-11

Implemented a separate pure immutable selection/capture contract and exact dependency
validation. Aggregate completions and existing presence/V3 behavior are unchanged.
Selection binds actual customer UUID, account/source scope, event owner/resource,
metric family, API version and query digest; captures bind exact aggregate completion,
manifest, privacy/generation, closed dates and independent selected count/value presence.
No label/default/aggregate inference or advertising authority is introduced.

Independent read-only review found four P2 issues (source/customer ID shapes, DST
fold comparisons, outer serialized-size accounting); all repaired and review closed
with no remaining P1/P2 within this pure-contract scope. Strict boolean/ISO timestamp
validation was also added. Review did not execute tests. Size-bound tests use the
actual small payload length as a reduced cap; they do not allocate32MiB payloads.

Checks actually run from `codex/inlet-w1-followup`:

- `python -m pytest tests/test_selected_reporting_contracts.py tests/test_reporting_presence_contracts.py tests/test_reporting_presence_summary.py -ra`: **140passed,0skips,0.44s**;65new contract cases plus75existing presence cases.
- `ruff check .`: passed.
- `mypy --cache-dir /tmp/inlet-selected-mypy app tests`: passed,1272source files.
  Initial pass found one test import/export typing error; exact log retained and
  import repaired before final pass. No product semantics changed for that repair.
- `git diff --check`: passed before commit.

Evidence: `/workspace/inlet-evidence/20261011/selected-contracts/` (first/focused
JUnit+logs, final Ruff/mypy and retained initial mypy log). First56-case run passed
with a deprecated instance model_fields warning, then repaired before focused run.
No full aggregate restarted. Frozen9d7aa2e qualification remains unchanged.

[Shared contract and activation obligations](design/selected-event-contract-v1.md).
[Concrete Q01–Q16 work and six human gate packets](inlet-quality-next-packages-20261011.md).

This package does not implement durable selection, capture publication, provider
imports or customer plan consumption. Those remain subsequent dependent work; no
provider or live behavior is qualified. Wider-window provenance remains explicit
engineering work. Google zero-row suppression and TikTok's unverified selected-event
mapping prevent inferring zeros/purchases from generic reports. No acceptance case
was weakened. No push, hosted retry, merge, deployment, live provider/model call,
advertising mutation, purchase or budget change occurred.
