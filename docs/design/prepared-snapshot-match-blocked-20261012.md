# Prepared Snapshot Comparison Qualification — 2026-10-12

Branch: `codex/inlet-w1-followup`; base HEAD `f8107a9c5f60accb5e73e6d9fa82a5b4e33021dd`.
Draft offline work only. No push, PR, merge, deployment, live provider access or advertising changes.

## Problem And Change

The preserved PostgreSQL larger-workload inventory failed during final atomic publication: final fact age 5.623817–5.624141 seconds, save 5.623164491 seconds. Successful preparation was 4.716 seconds. This is distinct from the repaired preparatory staged-read failure. Five-second freshness limits, final transaction atomicity and complete fresh dependency checks remain unchanged.

The passing small-workload diagnostic measured 31 prepared-generation snapshot rebuilds and 14 candidate snapshot rebuilds within save. A private matcher now prepares an exact immutable comparison pattern before the final authorization refresh. At every existing validation point it compares current values, exact classes, scalar representations, tuple order, graph aliasing, private/extra state and candidate field sets. It does not cache SQL, authorization or source-currentness results. Unsupported metadata selects the original scanner. Session/transaction guards, candidate copy isolation, issued-copy seals, poison state and cleanup remain intact.

Admission re-scans original operands under pinned metadata. Before and after comparison, it checks original scanner contracts, ordinary model descriptors, field identity/order/annotations/exclusions and recursively bounded typing-alias origins/arguments. Exact FieldInfo constraint metadata is opaque because the original scanner ignores Annotated constraint metadata. Unknown annotation objects select fallback without invoking getters.

## Independent Review And Focused Evidence

`/root/failure_review` identified and closed precompile metadata drift, mutable typing aliases, callback/capacity handling and actual-model eligibility findings before database qualification.

- `snapshot-match-component01`: Ruff passed; mypy failed on one Any return. No tests run. Original exit and unrun checks preserved; fixed with a bool return.
- `snapshot-match-component02`: four statics passed; 47 tests passed, then actual-root eligibility failed closed. Remaining tests unrun. Exact FieldInfo metadata leaf support fixed this eligibility issue; no security bypass was observed.
- `snapshot-match-component03`: **102 tests and all four statics passed**. Ruff, mypy (1614 sources), exact collection and git diff check. Original exits/XML/cleanup and all 1932 source hashes verified. Manifest `d39aac2a58c99f422c8c100f857577b169e5c0cc3e6644a0f429080c23b607b6`.

Pure production-matcher study (20 iterations, no SQL or acceptance claim):

| Facts | Original Rebuild Mean | Match Including Guards | Preparation Mean |
| --- | --- | --- | --- |
| 61 | 1.887 ms | 0.968 ms | 3.121 ms |
| 244 | 7.996 ms | 2.107 ms | 12.177 ms |

Result `/tmp/inlet-evidence-20261012/production-matcher-study01.json`; matcher SHA256 `3d830e9a266c0e077d841b1be1c3ae07e0b5e4168c3502a3e29461d466765bd3`.

## Runtime Status

`snapshot-match-runtime01`, manifest `3d87f5e5154a971c9f3bedddf1718078bdae0aa583a459ec0d443f684d24ac53`: four statics, **20 SQLite tests and two PostgreSQL tests passed**. The third PostgreSQL test (owner membership mutation) was interrupted after 6.202 seconds by the workspace resource guard, with original process exit -15 / wrapper exit 241. Free space was 1,073,598,464 bytes, 143,360 bytes below the 1 GiB floor. Cleanup confirmed no remaining worker processes; all 1932 source hashes matched. XML and release evidence for the interrupted test are incomplete, so its application result is unknown. This is not an observed assertion failure.

Seventeen later PostgreSQL cases remain unrun. The interrupted case also remains unqualified. The separate two-case PostgreSQL lock-expiry package, single changed-code larger PostgreSQL inventory retry and full release matrix have not run. No unchanged retry was attempted. Restore resource headroom and independently gate a fresh continuation package before resuming. Pure benchmark results and partial runtime passes do not establish application deadline success or release readiness.

Evidence roots are in `/tmp/inlet-evidence-20261012/` because workspace headroom is close to the required 1 GiB floor. Preserve and archive this evidence before environment retirement. Earlier staged-read evidence and unresolved historical failures remain linked by `v6-staged-reads-publication-blocked-20261012.md`.

## Reviewed Recovery And Runtime Continuation

The owner authorized bounded resource recovery and continuation. Removed only 33
reviewed regenerable cache files, then 30,620 duplicate pinned test-source files
from 20 historical fixture directories. Every duplicate matched Git commit
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`; the authoritative source archive and
restoration pointers were retained. Unique source, worktrees, database files,
logs and generated test evidence were preserved. The original checkpoint archive
now also resides in durable workspace storage with its original SHA256
`f8f95effdfd7bbb44d4a8f32f274d2c47332e24353ca77e3f6875e2d115ff65a`.

A static launch attempt stopped before starting any command because memory
headroom was insufficient. Reviewed read-only POSIX_FADV_DONTNEED hints on bounded
inventories of old task files changed no file contents. Four subsequent samples
over nine seconds recorded minimum workspace space 1,475,436,544 bytes and memory
headroom 2,164,568,064 bytes. The 1 GiB disk and all memory floors were unchanged.

`snapshot-match-pg-continuation01` ran only the interrupted PostgreSQL membership
case and the 17 previously unrun cases. **All 18 passed**, plus four static checks.
Manifest `548d660d6f89bde41afd940c11894ccb86d6a70055bfa9e88c67e96bb21e03b2`.
Combined with the original package's 22 completed cases, the bounded runtime
checkpoint is now **40 exact unique passes: 20 SQLite and 20 PostgreSQL**.
Independent review verified original zero exits, exact XML identities, complete
recorder artifacts, cleanup and all 1932 unchanged source hashes. The original
interruption remains recorded; a continuation pass does not erase that evidence.

The owner then prioritized publication of Inlet progress for developer review at
this safe boundary. Lock-expiry coverage, the single changed-code larger PostgreSQL
inventory retry and the release matrix remain pending. The larger publication
failure and release-readiness incident are not closed. The publication authorization
does not authorize main merges, deployment, repository access changes, live provider
operations or additional spending.
