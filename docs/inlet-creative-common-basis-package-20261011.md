# Private V5 Common Basis API artifacts — 2026-10-11

This test-only package implements the reviewed
[qualification interface](design/creative-common-basis-artifact-interface-v1.md)
on root `4a74f72`, with the unchanged-interface reporting-pass prerequisite
`b7c779c`. It does not change production code, canonical default v3, live
configuration, provider permissions or execution authority.

## Actual path and preserved predecessors

The optional `owned_image_upload` fixture callback is omitted by all existing
callers. Original Q16 dated clocks, direct-service image upload, wrapper and
assertions remain unchanged. The selected and social Common Basis wrappers only
forward the optional callback. The new helper uses the actual media API with the
original owner's session, exact tracked synthetic mug PNG, and one trusted private
store shared with the genuine canonical-v5 service. It adds typed customer facts
for the same $25 reusable travel mug and selects the returned image ID/hash.

Google uses actual same-account range, event-options, event selection and capture
APIs, then actual saved-input, generate, replay, read and export APIs. Social uses
its existing actual owned native MockHTTP catalogue fixtures and explicit empty
selected reporting; no Google metrics are transplanted. Only provider wire IO and
trusted server configuration are injected. No plan, proof, saved receipt or
execution record is seeded.

Tests assert the unchanged New York September/August windows, November goal/budget,
$12,000 target, complete $8,000 Shopify baseline, $1,000 ceiling, balanced
aggressiveness and capacity one. Google primary 10/0 and comparison zero use
bounded numeric extraction and Decimal equality; missing is unavailable. Meta and
TikTok keep unsupported selected-reporting gaps and partial catalogue coverage.
Their creative proposals bind the exact observed image, retain production-required
and not-assessed statuses, and give TikTok a three-shot video-production plan rather
than claiming an owned video. Native child locations do not acquire campaign
metrics. Exact image bytes/creator/scope and complete stored creative/reporting
witness kinds are checked. First generation legitimately performs current read-only
catalogue acquisition through the bounded MockHTTP readers. Generation creates no
execution, attempt, approval or reservation rows; replay/read/export preserve financial counts, original session,
version/document/proof observations and native-call counts.

## Evidence and limits

Evidence directory: `/workspace/inlet-evidence/20261011/creative-common-basis`.
Initial SQLite artifacts are retained separately. Final packet filenames distinguish
all five cases and both databases; manifest binds actual file SHA256 and document
commitments. Earlier selected/social packets are not overwritten.

Initial scoped Ruff found two long lines, corrected by formatting before whole
Ruff. Independent WIP review caught substring count assertions; these were repaired
before any pytest run. No assertion or production guard was relaxed. Exact test
commands/results and final static evidence are recorded below after qualification.

This is partial deterministic synthetic Common Basis qualification, not full
Q01–Q16 completion. No human expert score, browser journey, visual suitability,
commercial rights, causal effect, native budget/delivery or production default-v5
claim follows. Ordinary owned JSON export here is not a new authenticated-archive
qualification. The tracked PNG has not been substituted or visually reassessed by
this package. Full social frozen-case statistics remain unavailable in this
catalogue-only fixture boundary.

## Qualification results

- Initial new SQLite gate: **5 passed**, zero failures/errors/skips, 30.633 seconds
  (`sqlite-01.log`, `sqlite-01.xml`).
- Final SQLite/PostgreSQL cohort: **24 passed**, zero failures/errors/skips,
  215.890 seconds (`both-02.log`, `both-02.xml`): ten new cases, six unchanged
  selected Q01/Q02 cases, four unchanged social cases and four dated Q16 cases.
- No pytest failure occurred in this package. The pre-test review/static repairs
  above are retained in `pre-test-notes.txt` rather than presented as test failures.
- Final whole Ruff, configured mypy and diff checks passed before this commit;
  their outputs are `ruff-final.log`, `mypy-final.log`, `diff-final.log` in the
  same evidence directory. Mypy covers 1,410 source files.

Commands (using `/workspace/inlet-venv/bin` on PATH):

```sh
pytest -q tests/test_creative_common_basis.py -k sqlite \
  --basetemp=/tmp/inlet-creative-common-01 \
  --junitxml=/workspace/inlet-evidence/20261011/creative-common-basis/sqlite-01.xml \
  --durations=20
pytest -q tests/test_creative_common_basis.py tests/test_selected_q01_q02.py \
  tests/test_social_common_basis.py tests/q16_exact_acceptance.py \
  --basetemp=/tmp/inlet-creative-common-02 \
  --junitxml=/workspace/inlet-evidence/20261011/creative-common-basis/both-02.xml \
  --durations=20
ruff check .
mypy --cache-dir /tmp/inlet-v5-common-basis-mypy
git diff --check
```

The second invocation uses the approved local disposable PostgreSQL fixture database
and its explicit disposable marker, with per-test isolated schemas; no database
reset or frozen evidence mutation. PostgreSQL was serialized with other lanes.
Scratch caches and test directories use `/tmp`; all qualification logs and the
copied artifacts are retained under `/workspace`. Resource reserves remained above
1 GiB workspace and 2 GiB scratch throughout qualification.
