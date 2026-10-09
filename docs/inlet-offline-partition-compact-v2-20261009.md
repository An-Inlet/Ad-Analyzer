# Offline Partition Compact Identity V2

Implementation branch from `d85db66`; approved design in
[the V2 contract](design/offline-partition-compact-identity-v2.md).
This package changes only the opt-in collection plugin, offline candidate tool,
focused tests and documentation. No current consumer IDs, workflow, application,
frozen checkout, database, shard execution or Full run changes.

## Implemented Contract

Collection/timing/candidate schemas are explicitly V2. Node and JUnit-name records
retain SHA256, strict UTF-8 byte length, a bounded leading display and exact text
only at or below 16KiB. Actual file and classname stay bounded ordinary fields.
Short identities validate exact mapping; long identities rely on captured hook
mapping and collision-resistant evidence, not literal or cryptographic run
attestation. Consumers hash actual decoded XML names and enforce exact one-to-one
matching and lengths. Duplicate digest references and inconsistent lengths reject.

The candidate stores compact references, one bounded identity index and whole-file
groups. It cannot turn hashes into pytest selectors. Historical wrappers preserve
three exact bounded IDs plus references; their independently pinned 249 child
manifests and tracked source proof are unchanged. Disjoint/exhaustive cardinality,
root/suite totals, all outcome/exit/timing checks, configuration/provenance checks
and the 32MiB/64MiB artifact limits remain. Pass/capacity flags stay false.

## Qualification

Focused invocation: `python -m pytest tests/test_partition_evidence.py --tb=short`
with JUnit retained in
`/workspace/inlet-evidence/20261009/offline-partition/v2-final.xml`.
**70 passed, zero skips/failures/errors, 5.42s.** All 56 existing guard regressions
remain, adapted to explicit V2 fixtures. New coverage includes genuine tiny Git
collect-only with an over-8MiB ID (no fixture/test-body execution; manifest under
4KiB), synthetic oversized XML correspondence with same-prefix/same-length distinct
suffixes, forged digest/length/class mappings, exact-text integrity and UTF-8
threshold/display boundaries. The oversized synthetic candidate stays under20KiB.
The prior schema-adapted 56-case run passed3.27s and overlaps these70.

Raw logs: `v2-initial.log`, `v2-final.log/xml/exit` in that evidence directory.
Initial bare mypy reported a test-only heterogeneous dictionary inference at the
XML classname argument; replaced it with the identical directly derived string.
That initial result remains in `mypy-v2.log`.

No third genuine frozen collection has occurred, and no actual candidate or timing
envelope is claimed. The two genuine V1 attempts and their exit4 evidence remain
unchanged. Independent review is required before another actual collection.

Final whole Ruff passed; bare mypy passed1127 source files; standalone plugin
mypy passed; diff check passed. Outputs retained as `ruff-v2-final.log`,
`mypy-v2-final.log/exit` and `plugin-mypy-v2-final.log`. The fixture-only typing
repair preserves the tested XML string exactly; it does not change source behavior.
