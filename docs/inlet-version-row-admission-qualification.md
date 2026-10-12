# Version Row Admission Qualification

Status: locally qualified repair candidate; not merged, pushed, deployed or live-verified.

## Behavior

In owner-review plan-version reads, the original stored-row decoder still runs first. An invocation-local proof holds immutable snapshots of that complete row and the resident document. The original fresh history SELECT still runs. Only an exact fresh row/document match in the same Session, root transaction, Connection and connection transaction permits skipping the redundant second decoder; unsupported state or any mismatch uses the original decoder/equality path.

The history statement is ORM-classified because mapped WHERE predicates propagate the ORM compile plugin. A one-use permit therefore binds the exact original statement object around its original execute. Other ORM statements, flushes, consumed/reopened permits, or detected scope/state mismatch decline reuse; original authority checks remain independent and unchanged. Cleanup removes invocation-local listeners and drops references. Original source, ownership, privacy and deadline checks remain unchanged. No schema, global cache, model cache, provider call or advertising write was added.

## Preserved Failures

The original baseline and first repaired mechanism runs both failed the named duplicate-decoder assertion after value parity succeeded. A no-database expression characterization established the ORM classification; the corrected permit then passed the mechanism regression. An initial pure test incorrectly assumed Pydantic treats absent and empty extra state differently; its failure and the corrected test hypothesis remain preserved. Production snapshot strictness did not change.

The phase-wide PostgreSQL parity run was resource-interrupted at 299.372537 seconds with original exit -15 and no final XML. Its 22 anonymous progress markers are not qualified outcomes. Exact triggering resource telemetry was unavailable in that original runner; do not claim a proven specific threshold crossing. The bounded-process successor preserves the same 24 identities and resource floors, saves each immutable original exit and XML separately, and records launch/terminal/trigger resources.

## Validation Evidence

- Whole repository `ruff check .`: exit 0.
- Configured `mypy --cache-dir /tmp/inlet-root-mypy`: exit 0, 1503 files.
- New regression selection: 83 distinct cases (35 pure + 23 SQLite parity + 24 PostgreSQL parity + 1 prior SQLite mechanism pass); no original failed attempt is relabeled as passing.
- SQLite runtime: all 8 exact cases passed with normal assertion rewriting, including intact V1/edit/V2/report/historical-retraction/export, original-receipt rollback, real expiry and ownership/source mutation cases.
- PostgreSQL runtime: all 8 exact cases passed, including the same intact multi-version journey and guard/rollback checks. Runtime16 is additional to the 83 regression cases.

No aggregate suite retry was used. Bounded subprocesses qualify individual intact cases, not continuous-process capacity or production latency. Earlier R01/R02/R03 incidents remain historical unresolved incidents; later passes do not erase them. No live environment or purchasable release is claimed.

## Evidence Locations

Evidence is local to this executor under `/workspace/inlet-evidence`:

- `20261011/version-row-admission-red/`: original decoder regression failure.
- `20261011/version-row-admission-green/`: first repair failure and corrected mechanism pass.
- `20261011/version-row-admission-parity/`: pure/SQLite results, original PostgreSQL interruption and static checks. Parity manifest `044474b0fc049956e28fa8c889825658d2dab0934666b77a4356ce9da7b53af1`; interruption freeze `a5e7302dfe3a45f75d6d59dcd29d7a73161e93a7f75f44ecba1d7a4ba42306bf`.
- `20261012/version-row-admission-postgres-bounded/`: exact 24-case recovery, manifest `cc7153d8c22003b01478afb4ae87b35d4984cd80771ce51be8c720cef2cd76bf`.
- `20261012/version-row-admission-runtime-bounded/`: intact runtime16, manifest `de810a0c8f1558cd6450b7a0fbcbe4d1ef43d09d24acd44a16386836eebf6a9a`.

Completion freeze `6f67a5ab187ac989f7ecbf9009c7b696847239497e038bca322d5848527690a9` binds 255 evidence files. Runtime process totals were 143.097395 seconds for SQLite and 199.133056 seconds for PostgreSQL.

All 1493 application/test source hashes were held constant through qualification. Failed and successful evidence remain separate. The full current suite was not rerun. Additional distinct-Session and Connection-wrapper fault tests remain external draft work; current connection fault coverage replaces the underlying transaction, not the Connection object.

Owner decisions on reconnect retention and artifact sharing remain pending. No pushes, hosted CI, provider/model access, credentials, merge, deployment or spend are authorized by this checkpoint.
