# Google Budget Input Binding Package

Standalone pure implementation of the approved
[original-admission interface](design/google-budget-input-binding-interface-v1.md).
No existing input fields, consumers, API, storage, policy or default behavior changed.

The helper validates the full account/source/privacy set, original admission UTC
chronology, bounded original catalogs and complete resolved owner-intent binding.
Named alternatives stay independent. Exclusions and allocations resolve by full
catalog identity; children of active or retained removed owner campaigns cannot
masquerade as independent pools. Multiple independent owners in one account work.
Empty intents still validate context. Raw copied catalog primitives are checked
before legacy model conversion, including exact boolean flags and bytes refusal.

This is not selector authentication, current session/TTL authorization, native
budget publication, or proof that daily settings bound period spending. Historical
validation with only linked source fences needs its separately reviewed adapter;
this admission helper retains the exact full input source set.

## Evidence

Local evidence: `/workspace/inlet-evidence/20261011/google-budget-input-bindings/`.
No external uploads or provider calls. Preflight: workspace 1721 MiB, scratch
4590 MiB, cgroup memory headroom 2380038144 bytes (maximum minus current).

- `pure-01`: 23 passed, 1 failed: projected test fixture appended to a tuple.
  Corrected fixture construction, no production relaxation.
- Reviewer found pre-conversion copied catalog primitive coercion; fixed with the
  existing strict original primitive walker before catalog revalidation. Regression
  includes real `platform` bytes and numeric false flags, active and empty paths.
- `pure-02`: 34 passed, zero skips, 1.676 seconds.
- `pure-03`: 39 passed, zero skips, 1.365 seconds, including full target alias,
  advertiser/account tampering and offset/numeric-time cases.
- First configured mypy found two local variable Optional reuse errors; renamed
  locals without changing validation. Initial diagnostics retained.
- Final focused pytest: 39 passed, zero failures/errors/skips, 1.583 seconds.
- Whole Ruff passed; configured no-path mypy passed all 1439 source files.
- `git diff --check` passed. No broad baseline, database or browser tests run.

Checks used `/workspace/inlet-venv/bin/pytest`, `ruff check .`, and
`mypy --cache-dir /tmp/inlet-range-publication-mypy`.
