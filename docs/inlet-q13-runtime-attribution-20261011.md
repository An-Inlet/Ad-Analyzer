# Q13 SQLite diagnostic observation

Executed exactly reviewed/authorized manifest02 c60f055c (not later documentation-only manifest03). Candidate9c6b96c app/tests unchanged. One original exit0/pass, no skip/error/unrun; process33.905885593s, XMLsuite31.722s, testcase29.972s. This is one instrumented cause-oriented observation, not replacement acceptance or a retry that erases the earlier uninstrumented failure.

| Observed scope | First generation | Successor generation |
| --- | ---: | ---: |
| Generation wall seconds | 5.539216 | 6.959062 |
| Save wall seconds | 2.355453 | 2.928040 |
| Save SQL calls | 2385 | 2406 |
| Save-entry fact age seconds | 0.000282 | 0.000138 |
| Pre-CAS after-bracket fact age | 2.269592 | 2.845013 |
| Post-flush after-bracket fact age | 2.355683 | 2.927966 |
| Prior-version span wall / SQL | absent | 0.663120 /21 |
| Final-sources wall seconds | 1.293289 | 1.133927 |
| Retained-capture wall seconds | 0.712874 | 0.702335 |
| Frames / save-final calls |229 /34|233 /34|

All completion/truncation/accounting/restoration flags clean. Each save's descendant exclusive wall sums to its inclusive wall; exclusive SQL sums to2385/2406 respectively. All recorded helper/public assertions have zero inclusive completed and failed SQL. Full exact disjoint direct-child records are in measure01-summary.json; the table above contains nested categories and must NOT be summed together.

The successor's prior-version read is a concrete additional mixed validation/history/SQL phase in this observation. Its0.663120s is NOT pure model parsing and NOT the net observed save delta; other phases varied. The caller's parent digest remains outside this span in save residual. First generation's second selected entry helper took0.207904s versus0.046429s in the successor, illustrating within-run variability. No removed validation or further optimization is authorized by these observations.

Save-entry age accounts for the otherwise unpartitioned prefix since original fact completion. It was small in this run only. Original application guard semantics/clocks remain unchanged; observer brackets are not the original predicate samples. All observed guards returned; no claim about the earlier pre-CAS refusal's cause beyond its preserved fixed diagnostic. This passing observation does not establish timing margin, capacity, five-second reliability, or R01–R03 closure. Previous PG observer04 has different source/database and public-span coverage; no direct performance-saving subtraction is valid.

Static provenance correction: initial Ruff01 failedS110/RUF100, inherited from observer04, while shell's subsequent compile success masked it. The original failedlog/source and inaccurate-pass correction are preserved. Only noqa placement was repaired, with AST equality; explicit subprocess Ruff02/compile02 each returned0. Original04 artifacts remain untouched. Manifest03 merely adds this historical correction note and was NOT the executed manifest.

No additional measurement/test is requested or performed. Final freeze binds exact source and evidence; independent outcome review follows. Any next repair requires source proof preserving complete historical/currentness validation and all SQL/authority boundaries.


## Immutable Review And Assertion-Mode Limit

Root and independent review verified freeze02 SHA
`aca3757543dd937c2cf6ad29a8a1d71d2fdba3910c87c1a7262f5576e476443b`,
1,799 candidate sources and25 evidence hashes. Exact XML, original process exit,
all save-descendant wall/SQL sums and clean observer flags were independently
reconciled. Evidence root: `/workspace/inlet-evidence/20261011/q13-sqlite-kernel-diagnostic/`.

# Assertion mode is a diagnostic comparability limitation

The authorized measurement used --assert=plain to avoid rewritten assertion value exposure. The preserved qualification used pytest's normal rewrite mode. Assertions remain enabled, but generated test code and failure introspection differ. Together with observer overhead and uncontrolled environment variability, this prevents treating this pass as a controlled counterfactual of the earlier failure.

Source-only trace of the Q13 fixture chain finds assertion-bearing HTTP transport callbacks in q16_fixture, selected_q01_q02_fixture and google_budget_owner_discovery_fixture. Their exact rewrite eligibility depends on pytest import registration; ordinary helper names are not automatically assumed rewritten. The SQLite PRAGMA assertion in prepare_selected_common_basis is setup-time. Q13 itself adds no save-time monkeypatch callback; API service override is functools.partial of the real service. FakeProvider.check_active contains conditionals/raises rather than asserts. Real final-source callbacks are defined in production service code. The current source scan therefore does NOT establish a rewritten assertion callback as the cause of the save-time difference, nor quantify any mode effect. Transport callback cost is not automatically inside the final fact interval; source acquisition precedes final refresh.

No assertion-mode experiment, import tracing, additional runtime instrumentation or rerun was performed. Any later assertion-specific causal hypothesis requires an exact reachable save-time callback and measured boundary, not extrapolation from faster whole-test time. Preserve mode difference prominently regardless of whether such a callback is found.
