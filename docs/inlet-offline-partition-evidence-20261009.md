# Offline Partition Evidence Tool

Base `3b39199`; reviewed private interface `5f38adb` plus approved canonical-invocation
and configuration binding refinements. Worktree `/workspace/inlet-offline-partition-evidence`,
branch `codex/offline-partition-evidence`.

The standalone opt-in `scripts/inlet_partition_collection.py` refuses execution,
filters, override/config changes, dirty roots, prior outputs and deselection. It
captures genuine ordered collect-only items, exact installed pytest JUnit mappings,
configuration hash and commit; it never mutates items. Its scripts-only import path
avoids shadowing the frozen app/tests. There was NO actual frozen-W1 collection.

`tests/partition_evidence.py` validates bounded collection/timing inputs, exact
terminal XML mappings and outcome totals, the three parent wrapper identities and
separate disjoint249 historical child manifests. It produces deterministic whole-file
candidate groups with exhaustive/disjoint coverage proof, measured subtotals and
explicit failure/error/skip/unknown counts. Decimal context is explicit. Optional
seconds accept at most32 digits, nanosecond precision and1e9 maximum; unsupported
precision fails closed rather than silently rounding. Every output remains a
nonexecutable candidate, with pass/capacity qualification false. Operator-supplied
provenance is not a cryptographic attestation of a test run.

## Qualification

Final focused invocation:

```
python -m pytest tests/test_partition_evidence.py --tb=short --junitxml=/workspace/inlet-evidence/20261009/offline-partition/closed.xml
ruff check .
mypy
mypy scripts/inlet_partition_collection.py
git diff --check
```

**39 passed, zero skips/failures/errors,3.11s**. Tests exercise malformed/duplicate/
missing/unknown reports, provenance mismatches, failure/skip/missing-time labels,
ambiguous class/parameter identities, manifest mismatches, exact disjoint whole-file
balancing, ambient Decimal independence and empty partitions. Nine tiny throwaway
Git-repository subprocess cases exercise the real opt-in hook, including parameter
IDs with `::` and dots and attempted execution/filter/config/environment/deselection.
Their test/fixture sentinel never executes. These are not repository-wide pytest
runs, actual shards, DB/browser/provider tests or real performance qualification.

Whole Ruff passed; bare mypy passed1125 app/tests source files; standalone plugin
mypy passed separately; diff check passed. Artifacts:
`/workspace/inlet-evidence/20261009/offline-partition/closed.log/xml/exit`,
`ruff-closed.log`, `mypy-closed.log/exit`, `plugin-mypy.log`.

Earlier29-case focused run passed4.10s; expanded39-case run passed2.33s before final
static-only test import/variable naming repair. These overlap, not additional cases.
Initial Ruff found line wrapping; formatting repaired it. Initial bare mypy found
four test-only errors (implicit BATCHES reexport and reused tuple/list variable),
recorded in `mypy-first.log`; final direct import and distinct variable name passed.
No production, workflow, existing historical harness, deadline or skip changed.

## Remaining Gate

Root independent review remains required. No final frozen timing/collection pair
exists yet, no timing envelope was fabricated, and no real candidate/runtime saving
is claimed. Actual frozen collection may occur only after the original aggregate
is terminal, with only the standalone scripts directory added to PYTHONPATH.
Any CI partition execution or workflow change remains a separate reviewed package.


## Reviewed Configuration Provenance Repair

Root review found that an ignored auto-discovered `pytest.ini` could shadow tracked
configuration while Git status remained clean. The plugin now requires active
configuration bytes to equal the tracked HEAD blob, before collection/manifest
production. This does not ban other ignored generated files or change collection.
The added tiny Git fixture proves its ignored override leaves Git status clean but
is rejected specifically for missing tracked configuration; no manifest/test body
is produced. All original39 cases remain.

Final repair: **40 passed, zero skips,2.89s**, `config-repair.log/xml/exit` in the
same evidence directory. Whole Ruff, bare mypy1125, standalone plugin mypy and
`git diff --check` passed. No actual frozen collection or aggregate/DB interaction.

## Independent Historical Provenance And Root Totals Repairs

Independent review found that matching historical counts did not bind supplied
child files to the collected commit. The collection manifest now captures the exact
three historical file paths/hashes plus the snapshot source hash and literal PIN,
only after verifying every byte against tracked HEAD blobs. Fully absent historical
files are permitted only for nonhistorical collection; partial files are rejected.
Candidate generation requires complete provenance and matches all supplied manifest
bytes and the actual snapshot source/PIN against it. A same-count substitution no
longer qualifies. This remains operator-produced evidence, not cryptographic test-run
attestation.

Optional `testsuites` root totals now agree with actual aggregate test/failure/error/
skipped counts, in addition to existing suite-level validation. Contradictory totals
are rejected rather than silently ignored.

Final focused invocation uses the same module and `--tb=short`, with JUnit at
`/workspace/inlet-evidence/20261009/offline-partition/provenance-final.xml`:
**53 passed, zero skips/failures/errors, 3.11s**. All prior 40 cases remain. Added
coverage includes substituted PIN/source/path sets, missing provenance, same-count
child substitution, each contradictory root count, matching root totals, and genuine
throwaway Git collection with tracked historical files, ignored historical files and
partial historical files. No collected fixture/test body executes. The preceding
50-case repair run passed in 2.13s; it overlaps this final result.

Whole `ruff check .`, bare `mypy` (1125 source files), standalone plugin mypy and
`git diff --check` passed. Evidence in the same directory: `provenance-repair.log/xml/exit`,
`provenance-final.log/xml/exit`, `ruff-provenance.log`, `mypy-provenance.log/exit`,
`plugin-mypy-provenance.log`. Independent successor review is pending. No actual
frozen W1 collection, DB, workflow, shard execution or aggregate change occurred.
