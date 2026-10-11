# Payload-free planning expiry diagnostics

Status: source-only proposal from ce25c17. No implementation, tests or incident
reproduction authorized by this document. Existing five-second authority and
session deadlines, refresh count, exception/status, SQL and transaction ordering
remain unchanged. No R01/R02/R03 historical cause or closure claim.

## Existing surfaces and limits

`authority.final` currently checks identity/revocation, calculates monotonic fact
age, then short-circuits `not 0 <= age <= 5 OR session.expires_at <= time.time()`.
Both expiry predicates return the same409 `planning_authority_expired` without
logging. An age failure does NOT evaluate the session/time predicate. Preserve
that exact fact: diagnostics must not create a second session read or clock call
in that branch. Identity/revocation401 and unexpected errors remain untouched.

Repository save_generation has explicit final calls at replay, after retained
capture/before CAS, and after final publication flush (current lines560/594/669).
There are additional finals in authority.lock, read_context, service, repository
input/manual-event operations and catalog runtime. An unlabelled call must report
`unspecified`, not be guessed from stacks. The service's final identity refresh
remains at its current position before repository admission.

Main middleware adds security headers but no payload-free planning result logger.
Uvicorn access logging is filtered for OAuth callback URLs by app/shopify/logging;
it is not an appropriate new diagnostic carrier because paths can contain IDs.
Existing operations.record_safely uses a separate SQL sink and fallback logger;
do not reuse it inside locked authority validation or introduce telemetry SQL.

## Minimal exact interface

New private `app/planning_documents/authority_diagnostics.py`:

- `planning_route(route: PlanningDiagnosticRoute)` synchronous context manager,
  stores only a fixed enum in ContextVar and always resets the token in finally.
- `emit_expiry(*, phase: PlanningDiagnosticPhase, cause: ExpiryCause) -> None`.
- fixed enums: route `generate`, `current`, `history`, `version`, `unspecified`; phase
  `lock`, `replay`, `pre_cas`, `post_flush`,
  `unspecified`; cause `fact_age_outside_window`, `session_expired`.

Output is one bounded JSON message to a dedicated standard-library logger
`inlet.planning.authority`, with fixed keys only:
`event=planning_authority_expired`, `schema_version=1`, `route`, `phase`, `cause`,
`session_predicate=not_evaluated|expired`, `status=409`.
Fact-age cause includes negative/nonfinite age as the original predicate does;
no claim that it is only elapsed-age>5. Session-expired cause proves the original
fact-age predicate passed. Do not claim both predicates were evaluated or emit a
synthetic `both` classification. Exact ages, session expiration/remaining time,
wall/monotonic timestamps, IDs, hashes, principal/fact objects, exceptions, stack,
requests, raw paths, SQL, headers, bodies and credentials are never supplied.
The process logging infrastructure may add its ordinary timestamp externally.
No correlation identifier is generated; cause event includes its route/phase so
concurrent records do not require request-ID reconstruction.

Authority.final gains keyword-only diagnostic_phase with default unspecified;
public positional call compatibility remains. This is a diagnostic label, never
an authority control or reusable token. Invalid/non-exact label inputs map to
unspecified in the emitter, not to a new public failure. Preserve original first
identity branch. Calculate age exactly once at the same position. Rewrite ONLY
the expiry OR into equivalent ordered branches: if age predicate fails, emit the
age event then raise original409; otherwise evaluate the original session expiry
comparison with exactly its original time.time() call and emit session event only
if that predicate fails. No extra reads, conversions, sampling or validators.

Annotate authority.lock's existing final as lock and the three existing
save_generation final calls with their above literal phases. The lock label means lock-admission anywhere, including nested final-source
rechecks; it never identifies initial save admission. All other callsites
initially use unspecified; no phase inferred from global mutable state. Every
original final call remains, including calls across SQL/current-source boundaries.

A small private APIRoute subclass installed only on the existing planning plans
router sets/reset the route ContextVar around the original async route handler.
It chooses labels from a closed endpoint-name map configured by source:
`generate_plan`→generate, `read_plan`→current, `plan_versions`→history,
`read_version`→version; every other endpoint→unspecified. No raw URL/path/query is
read or emitted. The parent async context propagates to FastAPI's synchronous
worker; finally reset occurs for both response and exception paths. Original
handler executes once with its original request; no request is retained in the
record/context, and dependencies/response serialization order remain unchanged.
This avoids editing four endpoint bodies and covers failures before those bodies.
Only a fixed route enum crosses the sync worker boundary.

The same route wrapper can classify another HTTP409 with fixed event
`planning_route_conflict`, route, status409, reason=`other_conflict`, then bare-raise
the original exception. Compare detail only when its exact type is str; skip this
second record for exact planning_authority_expired, which authority.final already
records. Arbitrary detail objects are neither rendered nor compared using custom
equality. No response body interception or logs on success. Root explicitly approved this fixed other_conflict extension; core expiry
diagnostics alone cannot classify an unrelated R01 conflict. No correlation ID is needed: the expiry record itself
contains route, phase and cause. Already-handled framework responses are not
retroactively inspected; document any such coverage limit rather than parse bodies.

## Logging safety and durability

Construct the bounded record only from literal allowlists. No arbitrary kwargs,
exception text, exc_info, stack_info or object repr. The emitter encloses JSON
construction and logger dispatch in a narrow best-effort try/except Exception;
logging filter/formatter/handler failures are suppressed with NO fallback logger
(which might fail again). BaseException control-flow remains normal Python
behavior; do not swallow KeyboardInterrupt/SystemExit. Diagnostic failure must
never replace the original HTTP409. No async task, network, database, queue or
file creation in this code; use the deployment's existing application log sink.

This provides a stable event schema for durable retention by that existing sink,
not a new guaranteed-persistence system. Handler loss/disabled logging can lose a
record; do not claim incident closure without retained actual logs. Synchronous
handlers can delay returning an already rejected request; no successful request
gets logging overhead, and no authority check is postponed until after acceptance.
Changing the production log retention destination/policy is separate from this
minimal code boundary. Evidence packets may retain only these fixed messages.

## Qualification proposal (before any new ordinary acceptance run)

New focused pure tests cover age>5, age<0, nonfinite age, inclusive age5, actual
session expiry after passed-age, healthy path, 401/revocation, unexpected original
clock failure, and ordered short-circuit call counts. Use deterministic unit
clock stubs only for predicate parity; never alter actual API authority tests.
Assert exact status/detail plus events, no extra session/time read on failed age,
zero event on healthy401/unexpected failures, allowlist handling of hostile label
objects without invoking their repr, and no exception replacement for raising
logger/filter/formatter/handler/serialization failures. Capture logs with sentinel
identity/credential fields and assert none appear or are passed to logging.

Route context tests cover generate/current/history/version isolation, exception cleanup,
concurrent contexts and unspecified calls. If optional other_conflict is approved,
prove fixed classification without arbitrary detail serialization or duplicate
expiry messages. Check exact callsite phases with original-once spies. Reuse the
new real V6 final-flush two-DB delay test only if parent approves changed-source
integration: require the exact post_flush/fact_age_outside_window
record and original full rollback. It remains a deliberate negative, not a new
natural occurrence or reliability benchmark. No observer/retry/pass-chasing run.

File ownership: diagnostics module/newfocusedtests; narrow authority.py labels/
ordered branch; repository.py three literal kwargs; API router class wiring and its private route wrapper.
No service, storage, policy/schema, refresh, SQL or retained proof changes.
Root/reviewer must close the amended exact interfaces before implementation. Historical traces remain insufficient where originally
missing; new records can classify a future occurrence, not retroactively label it.

## Explicit test-wrapper compatibility scope

The existing original-final wrappers in `tests/test_plan_sales_progress.py` and
`tests/test_owner_review_runtime_authority_delay.py` must accept keyword-only
`diagnostic_phase` with the same unspecified default and forward it unchanged on
EVERY call to the original final. Do not discard/replace labels or broaden either
wrapper's original faults/refusal logic. These two narrow test edits are part of
the implementation scope; source search must confirm no other patched final
wrappers need equivalent forwarding. Production positional callers remain valid.
The actual V6 delay regression may additionally assert the exact fixed
post_flush/fact_age_outside_window event and no sensitive fields. Its future
changed-source SQLite/PG qualification is separate from its previous two passes;
it is not a retry of ordinary acceptance or a historical incident reproduction.
Focused sales-progress wrapper coverage verifies its existing refusal/late-boundary
semantics and phase forwarding. No new timestamp/identifier or sink configuration.
