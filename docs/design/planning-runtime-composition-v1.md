# Planning Runtime Composition V1

Baseline `5ee2a00396e8bb1a1872e71b2aeb21b30578ea50`. Local implementation and
fixture qualification only; no activation, live reads, deployment or spending.

The actual customer API constructs PlanningDocumentService without a policy;
its default is canonical descriptive-review/planning v3. Recent Google/Meta
journeys instead monkeypatch that constructor with private v4. Those tests do not
qualify production policy selection.

## Configuration Contract

Introduce `INLET_CUSTOMER_PLANNING_POLICY`, accepting exactly `v3` or `v4`.
Absent configuration retains v3 (presence-aware requested-window planning).
Explicit v4 selects the exact canonical descriptive-review.v4 and
 descriptive-planning.v4 pair (selected-event requested-window planning).
Do not allow arbitrary pairs, policy field overrides, policy digests or aliases.
Invalid/blank/unsupported configuration fails Settings validation; a runtime value
that bypasses validation must receive a fixed 503 before planning work, not fallback.
The route composition resolves the policy for each request; selection is immutable
for that request, not an owner authorization or a mid-request feature revocation.
No reporting/identity/media/provider configuration is enabled by this selector.

New-generation MVP composition supports v3 and v4 only in this package. v1/v2 are
historical policies; v5/v6 remain private because they require explicit creative
media-store composition and owner-review qualification, not just policy names.
This is not completion of those remaining creative MVP acceptance criteria.
Historical PlanVersion v1 (original/interim), v2 and v3 readers remain unchanged,
including supported historical policy pairs; selecting a generation policy must not
rewrite stored versions or their canonical digests. Typed provenance without settings uses outer PlanVersion v2; current request/effective
settings require outer v3. Planning policy and outer schema are distinct version axes.

## Qualification Contract

Use the actual app and route constructor with real Settings environment parsing;
fixtures may replace SQL, identity and provider transport, never the planner/service
constructor or policy adapter. Assert capabilities under absent, explicit v3 and v4
settings; invalid settings and defensive runtime 503 have no planner/provider side
effects. Run complete configured-v4 Google positive/zero/missing and Meta positive
customer browser journeys on SQLite then PostgreSQL; preserve exact range/timezone,
pagination, capture choice, goal/account/input save, generate and history/export.
Also exercise a complete absent/default-v3 generation journey on both databases.
Retain historical read/export cases. Validate all generated artifact documents and
digests. Keep provider defaults disabled and manual-action/no-spending boundaries.
Run full Ruff, configured no-path mypy and diff plus exact focused pytest partitions;
freeze sources, retain original failures, enforce existing resource floors and
bounded process teardown. Independent review precedes local commit.
