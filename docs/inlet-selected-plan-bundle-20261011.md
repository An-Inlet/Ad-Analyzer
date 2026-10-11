# Pure Selected Plan Bundle — 2026-10-11

Implemented `app/planning_documents/selected_plan_bundle.py` against retained proof
894a470 and the frozen interface3972821. This is a pure value validator, with no
SQL, collector, composer, route, capability registration or runtime activation.

`SelectedWindowEvidenceV1` binds an exact selected window document to its owned
catalog campaign, source fence, document commitment and reference. The bundle
retains one whole capture per explicit input selector, matches its recomputed pin
to `SelectedRetainedProofV1`, and recomputes every projection through
`SelectedPlanProjectionV1`. No captured summary alone substitutes for the graph.

`assert_ticket` recognizes only the exact canonical V4 policy digest locally;
V4 remains unavailable in the capability registry. It enforces the complete owned
account × actual catalog campaign × primary/comparison window success-or-gap set.
The five closed gap reasons distinguish no requested capture, unsupported profile,
campaign outside the captured map, unavailable catalog and actual empty catalog.
Bad explicit selector/proof/graph bindings abort rather than becoming data gaps.

Successful Google windows require `selected_presence.PRODUCER`, the exact
`query_profile_digest` for the explicit metric family, API v24, supported capability,
and same-advertiser conversion-action resource ownership. Generic fixture profiles
and unknown capabilities cannot produce successful selected observations. Catalog
advertiser identity, units, source revision and privacy remain exact. Omitted
rows/cells remain typed missing observations; full-window explicit zero and value
presence remain independently determined by the complete graph.

References preserve exact capture start/completion instants, retain conservative
partial/unavailable coverage, and cannot outlive the actual catalog deadline.
Collection instants normalize to UTC; numeric/naive collection times are rejected.
Full bundle serialization is bounded32MiB with20accounts/400combinedwindow slots.
No generic aggregate conversion or fabricated V3 document is introduced.

## Checks And Evidence

- New bundle tests plus existing selected projection/proof, V3 window and document
  contracts: **165 passed, zero skips, 7.12 seconds**.
- Whole Ruff passed; configured mypy passed **1,331 source files**.
- `git diff --check` passed. No database, Full, live or hosted checks.
- Durable logs/XML: `/workspace/inlet-evidence/20261011/selected-plan-bundle/`.
  Initial fixture/type-check failures are retained. They were corrected without
  relaxing contract checks: actual partial catalog coverage, missing test imports
  and explicit optional/tuple annotations.

## Remaining Engineering

This validates selected count/value evidence only. Aggregate clicks/cost context,
owned collection, retained-document assembly, composer behavior, V4 registration
and actual plan journeys remain separate. It does not close Q01's full
100clicks/10selected/$100 diagnosis or establish live provider qualification,
attribution accuracy, recommendation quality or advertising spend authority.
