# Initial Source Validation Factoring — 2026-10-07

Branch `codex/inlet-initial-source-factoring`, isolated successor to frozen initial
backend `4ec67ee`. This package changes only calibration/preview/initial-source
composition and tests; it does not alter policy lifetimes, defaults, execution
admission, consent, or financial qualification.

## Change And Boundaries

The private calibration reader returns its freshly validated report, objective and
ordered observations together. Public `read_calibration` and `read_objective` still
perform complete independent validation. Preview input resolution uses that one
result instead of reconstructing the same calibration again and reading its selected
observation a third time. Consented preview reads retain their second full input
validation after the mandate check.

The private initial-source resolver returns its work, preview and calibration inputs
within the same locked DB-only operation. The initial reader reuses these immutable
values for direction and evidence rather than repeating preview/calibration reads.
It retains final current session/source checks and a newly sampled effective expiry,
explicitly bounded by preview, selection, calibration and every input observation.
Every document commitment, exact dependency set, original-session/source check and
calibration reconstruction remains checked. These private return values are not
accepted as arguments to authority APIs and are never cached across requests,
transactions, native IO or worker stages.

## Actual Before/After Profile

Same actual PostgreSQL configured Start→worker test and explicit fixture-only
120-second policy from the predecessor, with SQLAlchemy statement counting and
worker elapsed instrumentation in `/tmp/inlet_source_profile.py` (outside repository):

| Measurement | Unmodified `4ec67ee` | Factored source |
| --- | ---: | ---: |
| Worker SQL statements | 52,895 | 36,884 |
| Worker elapsed | 30.16 s | 22.39 s |
| Entire test-call SQL statements | 70,203 | 50,348 |
| Entire test-call elapsed | 42.25 s | 32.55 s |

Both single-test runs passed; total pytest wall time was 47.10s and 35.20s respectively.
Evidence: `/workspace/inlet-evidence/20261007/initial-source-before.jsonl` and
`initial-source-after.jsonl`, with corresponding `.log` files. Commands used
`python -m pytest -p inlet_source_profile tests/test_initial_rule_start.py
-k 'configured and postgres' --durations=3` with the external plugin on PYTHONPATH.
These elapsed samples share an executor with other work and are not isolated
benchmarks. About 30% fewer worker queries is demonstrated; remaining latency is
material. This does not qualify the ordinary 30-second profile or live operation.

## Regression Evidence

`tests/test_initial_source_fresh_boundaries.py tests/test_initial_rule_source.py`:
**18 passed in 107.05s**, no skips, SQLite and PostgreSQL. New tests alter authority
at the post-mandate preview boundary: erase a historical observation, revoke the
original session, or advance time beyond expiry. Each denies the read. A separate
standalone objective read after committed erasure denies reuse of prior validation.
Existing source checks retain current success, expiry, revocation, historical erasure
and native budget drift. Log: `initial-source-adverse.log` in the same evidence folder.

Whole Ruff, repository `mypy` (934 files), and `git diff --check` passed.
Compatibility checks are recorded below after their terminal result. No Full,
remote, hosted retry, live provider action, deployment or merge was performed.

Compatibility cohort `tests/test_initial_calibration.py tests/test_initial_preview_v2.py
 tests/test_initial_preview_binding.py tests/test_initial_rule_worker.py`: **31 passed
in 55.83s**, no skips. This includes actual SQLite/PostgreSQL central worker→exact
review success and subsequent original-session/observation-erasure denial.
Log: `initial-source-compatibility.log` in the evidence folder above. Together with
the 18 adverse/source cases and profiled configured positive case, 50 successor
checks passed. The predecessor profile is separate evidence, not an added successor
check. PostgreSQL used isolated fixture schemas within disposable
`inlet_oct07_next_integration_ci`; no qualification database was reset or modified.
