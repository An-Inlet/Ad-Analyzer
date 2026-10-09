# W1 Actual Offline Partition Evidence

Reviewed V2 tool `e61a6cba06642cc7b5c5670d1ec8b022a6f375c0`; docs-only evidence
successor. The original aggregate remains failed. No test execution, shard execution,
workflow change, database action, Full rerun or hosted action occurred in this package.

## Genuine Frozen Collection

Third attempt, after root authorization and independent V2 review:

```sh
# cwd /workspace/inlet-w1-validation-final
PYTHONPATH=/workspace/inlet-partition-compact-identity-v2/scripts \
PATH=/workspace/inlet-venv/bin:$PATH \
python -m pytest -p inlet_partition_collection --collect-only \
  --partition-manifest /workspace/inlet-evidence/20261008/w1-aggregate/partition-collection-v2.json
```

**Exit 0; 6,581 unique collected parent nodes.** Source before/after remains clean
`6a3b0f16f9ebc9c0a80dbab60140c0b8f9324f46`. Only the standalone reviewed scripts
directory was added to PYTHONPATH; successor app/tests were not substituted into
the frozen collection. The hook never deselects items or executes fixtures/tests.
Tracked configuration and historical manifest/source/PIN checks passed.

Artifacts under `/workspace/inlet-evidence/20261008/w1-aggregate/`:
`partition-collection-third.log/exit`, `partition-collection-third.source-head`,
`partition-collection-third.source-status`, `partition-collection-v2.json`.
First and second exit4 attempts remain preserved in their original log/exit files;
neither was rewritten or reclassified. They generated no accepted V1 manifest.

## Terminal Binding And Offline Commands

The V2 timing envelope was built by validating the collected manifest, asserting
its commit equals original `aggregate.result.json` freeze/final hashes and recorded
third-collection source hash, asserting terminal exit1/clean status and collection
exit0/clean status, and hashing actual canonical collection and raw `aggregate.xml`.
No terminal result was inferred from costs, and no passing exit was substituted.

From the reviewed successor tool checkout:

```sh
python -m tests.partition_evidence \
  --collection /workspace/inlet-evidence/20261008/w1-aggregate/partition-collection-v2.json \
  --timing /workspace/inlet-evidence/20261008/w1-aggregate/partition-timing-v2.json \
  --junit /workspace/inlet-evidence/20261008/w1-aggregate/aggregate.xml \
  --output /workspace/inlet-evidence/20261008/w1-aggregate/partition-candidate-v2-n3.json \
  --shards 3
```

N3 exited0. The same command with `--shards 2` and fresh `...-n2.json` output also
exited0. Separate `partition-candidate-v2-n3.log/exit` and `...-n2.log/exit` preserve
results. Neither command has an execution capability.

Both candidates prove exactly **6,578 current parent references + three distinct
historical wrapper references = 6,581**, disjoint and exhaustive against collected
items, observations and identity index. There are428 current files. Historical
child manifests remain separately verified at142 +19 +88 =249 nodes, pinned to the
captured source/PIN; children are not added to parent counts.

## Measured Candidate Groups — Not Runtime Forecasts

| N3 current group | Files | Nodes | JUnit seconds subtotal | Failed | Skipped | Unknown durations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 143 | 2,357 | 2,047.271 | 460 | 20 | 0 |
| 1 | 143 | 2,087 | 2,047.271 | 433 | 32 | 0 |
| 2 | 142 | 2,134 | 2,047.271 | 437 | 31 | 0 |

N2 current groups:213 files/3,373 nodes/3,070.907 measured seconds/682 failed/44
skipped, and215 files/3,205 nodes/3,070.906 seconds/648 failed/39 skipped. Both have
zero errors and zero unknown durations. Current subtotals sum to6,141.813 seconds.
The deterministic balancing happens to produce equal N3 millisecond subtotals;
this is arithmetic over measured cases, not independently measured concurrent jobs.

Three passed parent-wrapper durations are1,098.858s original,355.701s UI supplement,
and832.846s initial forward. These include wrapper overhead and differ from the
nested child pytest durations. Child summaries recorded246 passed/three expected
skips; parent observations do not erase those child qualifications.

All1,330 frozen failures and83 skips remain. Candidate `capacity_qualified` and
`pass_qualified` are false. Failed/skipped case seconds are explicitly not passing
runtime estimates. Fixing setup blockers may exercise previously masked, slower
paths. No job parallelism, runner provisioning, DB setup, billed minutes, wall-clock
saving or CI90-minute/120-minute capacity has been demonstrated. Raw XML/logs remain
authoritative; compact digest references are collision-resistant correspondence
only, not selectors or cryptographic test-run attestation.

## Byte Sizes And SHA256

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Collection V2 | 4,702,305 | `4d68c99fdb94746572120d93750a6295014ec19834192c9025bb52007902f203` |
| Timing envelope V2 | 303 | `7f58e6b805c8820dc0d787bad4c6e833e467fde6c0bcb3216b4f09856be8f022` |
| Candidate N3 | 3,715,225 | `2fd47d6aaa9f39ddc894e510a5436ee0d25b59b6d63551ea8c959edf07f561f2` |
| Candidate N2 | 3,714,959 | `f120c64d95f58eecebf2cc0ba87de87bc744c36f57d8fe58e15048e361a6c6f1` |
| Original terminal result JSON | 1,534 | `311e05ee4b49062c03d0ff7ad1bcff7ace81964b4fe9f3d16bfef1950c5f53c6` |

Original raw XML SHA256:
`e3263f5e2bca0d484b4657d6672a32dfdc44539ee1cbed8257bf1a7187488037`.
The collection file is canonical JSON, so its raw and canonical digests coincide.
All artifact bounds remain unchanged. Docs diff check passed; no tests were rerun
for this evidence ledger. Root review remains required before using the candidate
for any separate workflow proposal, and no execution authorization is implied.
