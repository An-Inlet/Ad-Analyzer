# Retained Owner Context Restriction

Implementation from root7c493a8 under the reviewed restriction-only context design.
Only `creative_retained_sources._Context` and the two public owner capture/recheck
callsites change. The context always fully validates the document, applies any
strict exact-pair restriction as an additional requirement before time/SQL access,
then keeps the existing canonical creative descriptor and all transaction/authority
checks. Owner callers use `context.document` instead of immediately validating once
before a context that would validate it again.

Historical `_owner_document`, top dispatcher validation, all checks across SQL or
callback boundaries, complete dependency validation, both original receipt reads,
V5 wrappers, original clocks and final authority remain unchanged. The restriction
cannot enable an unknown policy, bypass model validation, renew time, or cache a
proof. No storage-pair, registry, service, schema, portal or advertising change.

## Evidence And Limits

Local evidence: `/workspace/inlet-evidence/20261011/owner-context-restriction/`.
`selection.json` records the exact pre-execution source hashes and bounded selection.
Preflight recorded workspace1521868800 bytes, scratch4585349120 bytes, cgroup memory
headroom1769234432 bytes, all above the required floors.

`pure01` passed all16 cases (new14 and existing public-wrapper2). It checks strict
restriction shapes, matching unsupported legacy-shaped policy rejection, wrong-owner
policy refusal before even invalid time/SQL, copied invalid native flags/time/version,
and separately owned checked context values with unchanged V5 default behavior.

The approved actual cohort selects only `old_wrappers or between_delegated` in the
existing retained component module: four nonempty/empty positives and ten controlled
transaction/mutation/expiry/error negatives across SQLite/PostgreSQL. This uses
actual acquired input/receipt/reporting/media followed by standalone V6 composition
and explicit component SQL persistence; it does not qualify service generation.
`actual02` passed all 14 cases, zero skips, in 223.910 seconds. Its two
transaction-cleanup warnings came from the intentional connection replacement cases.
Together with `pure01`, this is 30 distinct passing cases.

Initial whole static checks are preserved in `ruff03.log` (SIM102 nested-if style)
and `mypy03.log` (two test-only fake-session identity typing errors). After these
successful tests, the nested restriction was combined into equivalent short-circuit
AND form and the two test identity operands gained typing-only casts. No actual DB
case was repeated. `pure04` passed the same 14 new pure cases in 2.896 seconds;
these overlap earlier coverage, not 14 additional cases. Final whole Ruff passed;
configured no-path mypy passed all 1471 source files. `git diff --check` passed.

`selection.json` preserves pre-style tested source hashes. `manifest.json` records
final source and evidence hashes plus exact XML node/status reconciliation. The
post-test changes above are explicitly distinguished from the actual DB-tested
source; final pure/static checks cover their resulting expression and typing.

The earlier zero-case remaining04 run expired after retained capture/before CAS;
stage05 passed that pre-CAS guard and failed the later post-flush final guard. Source inspection and the restricted change do not establish a root
cause or a sufficient timing margin. R01/R02/R03 remain distinct and unresolved;
no incident closure, latency guarantee, authority relaxation or repeated diagnostic
pass-chasing is claimed. Separate combined service/save qualification is required.
