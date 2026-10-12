# Prepared Selected Witness Investigation

Status: source inventory and proposed boundary only; not an approved implementation
contract. No new production interface, test, migration or authority is introduced.
See the measured [PostgreSQL timing](../inlet-postgres-authority-timing-20261012.md).

## Candidate Boundary

Investigate a private per-generation preparation of deterministic selected evidence
before the final identity refresh. Keep preparation inside existing authorized read
contexts and close them before provider IO. A proposed prepared value contains only
bounded immutable commitments and deterministic results, bound to the exact ticket,
candidate, account selection and source dependencies. It does not carry authority.

The final save still obtains a fresh original-session fact and locks/rereads current
dependencies. Only exact equality with the complete prepared dependency sets could
permit reuse of pure construction. Reread on both sides of creative callbacks; keep
final source checks, expiry checks and CAS/rollback behavior. Unsupported input or
incomplete coverage must retain the original path or refuse. No serialization of
private source rows into files, logs, hashes or public documents.

Start with selected graph/traffic reconstruction, not an all-purpose preparation
cache. Preserve goal/commerce, saved catalogs, receipts, media, policy and authority
checks on their existing paths until their own complete dependency contracts exist.

## Dependency Inventory To Prove

The existing `OwnedSelectedPlanContext._raw_witness` is a useful same-transaction
reference, not a sufficient cross-refresh witness. It covers these row families:

| Dependency | Required Fresh Coverage |
| --- | --- |
| Workspace | Exact workspace row, status and export privacy revision |
| Advertising account | Exact owned account row, currency/time zone, native identity and connection |
| Workspace integration | Exact integration row and active state |
| Google/Meta/TikTok source | Complete scoped source set, exact public and private values; absence/duplicates fail |
| User/session/membership | Fresh original actor/session, active membership and scope; never prepared authority |
| Selected capture | Exact header and complete bounded fact set, canonical JSON and scalar metadata |
| Event selection | Original selection row plus current head, including missing/invalidated state |
| Performance completion | Exact referenced completion and current pointer |
| Campaigns | Complete account campaign set, native mapping and platform, including additions/removals |
| Daily metrics | Complete referenced date-range set over the account campaign set |

Paired traffic adds dependencies absent from that context's inventory:

- `ReportingSemanticsRow` and complete `MetricPresenceRow` set, with explicit absent
  header/sidecar states. Unknown present provenance remains an error, not a gap.
- The complete bounded `RangeReceiptRow` membership query for workspace/account/
  completion, not only the selected receipt. Duplicate/additional receipts change
  the result. Validate all canonical payload and scalar metadata dependencies.
- Receipt selection and aggregate dependencies, current scope and complete manifest
  relationships from `range_receipts._dependencies`, `_aggregate`, `read_presence`
  and `service.manifest` must be traced transitively before declaring coverage closed.
- Explicit unsupported-platform and missing-traffic gap semantics and their exact
  selected capture/aggregate/campaign-map bindings.

The selected reporting proof also invokes qualified `_reporting`, which has its own
complete manifest/presence and private-source comparison requirements. Its dependency
inventory is not closed by merely collecting the rows above. Final authority,
entitlement, time and goal checks are dynamic predicates, not cacheable row equality.

## Open Security Proof Obligations

1. Define complete source read sets and deterministic ordering/bounds; prove complete
   membership, absence and duplicates, not only equality of rows already observed.
2. Prove which writer locks/epochs fence every dependent mutation. Equality after
   releasing preparation locks alone does not prove that no intermediate change
   occurred. Do not silently replace any existing generation/epoch semantics.
3. Keep the original session, actor and account selection bound across refresh;
   detect direct/nested model mutation, custom callbacks and reused preparation.
4. Guard clean SQL transaction/connection identity and reject mutation even if a
   callback swallows a flush/transaction error. Use fresh SQL, not ORM identity-map
   assumptions. A preparation object must not outlive its single generation.
5. Establish error/replay behavior and direct-call fallback before changing public
   helpers. Preserve all public validators and v3/v4/v5 compatibility.

Required mutation tests cover every listed row family and complete set, including
insert/delete, changed-then-restored inputs, private source rotation, absent/present
sidecar transitions and duplicate receipts. Include callbacks before/after creative
reads, session revocation/expiry, entitlement/privacy/goal/head races, replay, CAS,
pre-CAS/post-flush five-second expiry and complete transaction rollback on SQLite
and PostgreSQL. Independent security review must close the inventory and protocol
before implementation. Performance qualification follows correctness; no promised
timing gain or acceptance claim is made from this proposal.
