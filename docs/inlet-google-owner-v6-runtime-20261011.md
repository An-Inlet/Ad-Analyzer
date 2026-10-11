# Private V6 owner review runtime preparation

Status: diagnostic-only local source; API qualification failed and is not integration-ready. Based on `e8c7600`, reviewed
service interface `a33258c` and clarification `cba0b24`. The existing default V3
factory is unchanged; no UI or default public activation is included. Original
R01/R02 conflicts are not resolved or retested by this preparation.

The isolated changes recognize canonical private V6, require its explicit owner,
creative and selected inputs, use the genuine creative reader/owner composer,
and preserve old generation refusal and replay order. The save hook compares the
complete actual linked catalog tuple and active owner proof. Final SQL uses the
existing original receipt resolver once, then compares the entire original tuple
to the candidate and actual read. Existing selected/image/selected and final
transaction authority checks remain. The retained lane owns all retained/history
dispatch; these changes must not be exposed before that dependency is complete.

Actual fixture preparation reuses API-acquired Common Basis reporting/selected
captures, uploaded private image and original catalog receipt. Existing V5 setup
is followed by genuine private V6 discovery/capabilities against the same receipt
and original session, then save/generation. No positive plan or proof is seeded.
The additional Meta case declares the existing owned connection bootstrap and
uses exact MockHTTP catalog acquisition; it does not invent selected social data.

## Pending qualification

`/workspace/inlet-evidence/20261011/google-owner-v6-runtime/planned-nodes.json`
contains 13 exact node IDs per database (26 total), all successfully collected:

- Five generation/current/history/export/replay variants: nonempty, explicit
  empty, genuinely confirmed zero ceiling, unrelated included Meta, mixed Meta
  allocation and exclusion.
- Explicit tuple admission refusal and strict-valid candidate catalog substitution
  refusal at actual save, with exact no-row-delta assertions.
- New-session refusal, final-only original receipt scalar fault, post-flush forced
  expiry rollback. The last is controlled fault injection, not natural wall expiry;
  all ordinary authority clocks and limits remain unchanged.
- Actual original input-link deletion with fixed intended integrity refusals;
  this is a dependency erasure smoke, not full workspace-erasure qualification.
- Existing unchanged default V3 capability and V5 owner-input generation refusal.

Run disjoint SQLite then PostgreSQL after dependency closure and source review.
Do not repeat passed SQLite merely to obtain a unified cohort. Exact collection,
commands, XML/logs, failures and source hashes will be added before code freeze.
Required bounded API qualification remains incomplete. Final static outcomes are recorded below.
Scoped Ruff and diff checks passed during source preparation; no runtime success
is claimed. Initial draft import/line-length static findings were corrected by
formatting and remain described in `source-preparation-notes.txt` in that evidence
directory.


## First actual qualification failure

Retained dependency `b336e9b` was independently closed and integrated locally as
`1142aee` before execution. Source-01 JSON and patch preserve exact WIP provenance.
`collect-01` resolved the planned 26 nodes (22 new, two unchanged default V3,
two unchanged V5 refusal). Sole-slot SQLite-01 used normal clocks and `-x`.
The first `sqlite-owner` case saved input successfully, then actual POST generate
returned HTTP409 with fixed detail `planning_authority_expired`. No test passed;
12 remaining SQLite and all 13 PostgreSQL cases were not executed. The call took
15.35 seconds; JUnit suite time is 20.134 seconds. This response does not identify
which authority window expired. There was no ordinary retry, deadline extension,
authority refresh workaround, cache or optimization change.

The separately requested four pure positive registry cases have not run. This
package does not yet prove an end-to-end V6 plan or customer presentation. The
previous R01/R02 failures remain separate and unresolved.

Whole Ruff's first run found two line-length errors introduced by accurate V5/V6
error copy; formatting only repaired these. Whole Ruff-02 passed. Both initial
logs are retained. Configured no-path mypy-01 found four test-only typing errors: optional tuple access, two instrumented module aliases, and SQL result rowcount. An explicit non-null assertion in the substitution test and operation-equivalent Any/CursorResult casts fixed them. An intermediate Ruff-03 rejected constant getattr; module casts retain the exact original aliases. Final whole Ruff-04 and configured no-path mypy-02 pass (1473 files). No test was rerun for these changes.

Relative to source-01, production changes are only formatting the two fixed admission error lines; the failed sqlite-owner test body is unchanged. Other test-only typing changes are outside that failed case. `git diff --check` passes.

The parent authorized a diagnostic-only local freeze after static checks, then a
separately reviewed single instrumented execution. Existing authority observer and
helper census must remain unchanged. A diagnostic pass would be observational,
not closure of SQLite-01 or release qualification. Its exact manifest/authorization
will precede execution. All unused API cases remain held.
