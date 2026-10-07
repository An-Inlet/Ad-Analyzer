# Candidate-Only Owned Runtime Composition Interface

Proposed implementation freeze after root review; base736ef1348c3faa0318a0d12d2f5bf6b7e11e1bdf includes approved configuration/source ports64c1b76. No schema or producer changes proposed.

## Concrete Correction To The Earlier Proposal

There is no current customer candidate API consuming get_candidate_runtime,
get_candidate_selection_runtime or get_candidate_review_runtime. Existing customer
routes consume only get_session_automation_runtime. Candidate service/selection/
review callables and standalone run_candidate_reads exist. Merely replacing four
None functions would not make a candidate-only flow reachable. A small additive
candidate API is necessary; an automatic Start cannot honestly substitute while
first-decision epochs remain unresolved.

## Exact Proposed Assembly Ports

`production_runtime/candidate_assembly.py`:

```
@dataclass(frozen=True)
class CandidateRuntimeBundle:
    candidate: CandidateRuntime
    selection: CandidateSelectionRuntime
    review: CandidateReviewRuntime
    automatic: SessionAutomationRuntime | None  # None in this slice
    automatic_unavailable_reason: Literal['first_decision_producer_unavailable']

@contextmanager
def configured_candidates(db: Session, principal: CustomerPrincipal,
    identity: IdentityProvider, configuration: Settings
) -> Iterator[CandidateRuntimeBundle | None]: ...

@contextmanager
def candidate_job_runtime(engine: Engine, workspace_id: int, job_id: str,
    identity: IdentityProvider, configuration: Settings
) -> Iterator[CandidateRuntimeBundle | None]: ...
```

Use approved load_candidate_configuration and validate_candidate_source before
building evidence callbacks. Add three optional Settings file/pin inputs named
candidate_assembly_manifest_path, candidate_assembly_manifest_digest and
candidate_policy_bundle_path; all absent returnsNone, partial/mismatch sanitized409.
Only candidates_only mode is assembled in this slice. Session automatic mode remains
unavailable, not silently downgraded. No default registry entry or learned producer.

Enter configured_optimization exactly once per original principal; validate its
pinned optimization manifest against the candidate manifest. Same clock, actual
Session engine and execution instance for candidate/selection/review. Bind original
principal with customer_optimization.bind before reusing execution. The trusted
source builder receives candidate_base and this exact original principal; run
validate_candidate_binding, then attach only existing authorized evidence hooks.
No credentials/runtime survive the context. Do not alter manual/V2 runtime getters.

Owned reader(db, CandidateScope, now) releases its own pre-read transaction before
actual configured catalog IO. Read with original_mandate=scope.mandate; match exact
scope/goal/target/budget-owner/full-targetset, then original-session/source recheck.
Base evidence is unqualified/no direction/no observation count. Bound expiry is
at most the actual native catalog expiry and existing five-minute evidence cap;
no fabricated financial proof or finality. An admitted source may transform evidence
through existing original-principal callbacks, never substitute state or authority.

Owned source_fence_reader(db, SelectionReadRequest, now) resolves the actual current
goal's store and supported commerce publication, records its existing source/privacy
manifest fields, then calls source_current. Current v1 support remains literal:
V2-only publications fail unavailable until a separate version-aware change. No
snapshot writes and no invented receipt lineage.

## API Ports (Additive, Approval Requested)

Prefix `/api/customer/v1/workspaces/{workspace_id}/execution/candidates`:

- GET `/capabilities`: named current registered policies and separately consented
  optimization mandates, bounded20 each; available only for configured assembly.
  Explicit automatic first-decision unavailable reason; no source proof in browser.
- POST `/reads`: exact intent `{mandate_id, mandate_revision, policy:{policy_id,revision}}`.
  Resolve current binding server-side, call actual enqueue_candidate_selection;
  return existing CandidateSelectionBatch and bounded owned job IDs. No client
  CandidateWork, SourceFence, qualification object or raw target JSON accepted.
- GET `/reads/{job_id}`: original-session owned state/result via existing load/read_result,
  no processing mutation from GET. Result unavailable until worker completes.
- POST `/results/{result_id}/review`: existing CandidateReviewIntent only; prepare
  separate ordinary exact review through CandidateReviewRuntime, not approval/run.

One yielded FastAPI configured bundle dependency per request; original authorization,
CSRF on POST, owner scope and no-store throughout. Existing no-argument None getters
remain explicit legacy injected test seams only, never fallback after configured
admission failure. No new frontend in this package.

## Worker Interface

Extend existing run_candidate_reads with optional keyword scoped provider and
explicit selection environment/clock metadata, retaining legacy factory behavior
only when scoped provider is absent:

```
CandidateJobRuntimeProvider(engine, workspace_id, job_id)
    -> AbstractContextManager[CandidateRuntime | None]
run_candidate_reads(engine, factory=legacy, *, limit=10,
    scoped_provider=None, environment=None, clock=None)
```

Configured entrypoint supplies metadata only after pure pins/source descriptor
admission; descriptor is not evidence. One bounded eligible job per tenant is
selected with existing due/lease/backoff rules. For each job, use canonical workspace
lock then existing principal_for on its actual actor/session, validate owner/current
session, release initial locks before IO, and assemble a new context. Recheck exact
job authority in existing process; close every context in finally. Failed first
workspace must not starve later ones. No global current user, credentials or mutable
runtime cache. Existing claim/attempt/exposure machinery is unchanged.

Proposed scheduler exposure is an optional candidate read stage in jobs/customer_runtime,
controlled by explicit default-false customer_candidate_reads_enabled plus existing
ALL_DATA_SYNCS gate. No second automatic tick and no calls to session run_due using
a global configured runtime. Before adding this stage verify existing scheduler has
no candidate tick; currently only session_automation is wired. Automatic per-run
factory changes are deferred until genuine epoch composition is reviewed; capability
remains explicitly unavailable, not silently pretending all four runtime gaps closed.

## Acceptance And Ownership

Implementation files: new production_runtime/candidate_assembly.py and candidate
owned-reader helpers, new api/customer_candidates.py/dependency, minimal Settings/main
and existing run_candidate_reads/customer_runtime integration. No shared contracts,
financial models, epoch producers or schema change. Freeze these callable types
before any dependent UI work.

Ordinary API creates actual separate0080 consent, selection and jobs; actual scheduler
entrypoint reconstructs each original session and performs native MockHTTP reads.
Both databases; no getter overrides or seeded candidate/job/admission/attempt. An
unqualified registered source yields an honest blocked result and zero writes. An
explicit contract scenario may test existing candidate review without pretending
it is production learning or automatic first-decision authority. Two original
sessions/tenants prove resource/credential isolation and closure; revoke during IO,
goal/source/profile drift and badpins deny; failedfirst tenant doesn'tstarvesecond.
Preserve manual/V2 tests and retained financial reconciliation semantics.

## Approved Callable Correction And API Schema Freeze

Bundle exposes `selection_for(binding: ProviderMandateBinding)` instead of a single
selection field: TargetReader lacks the mandate argument and the first catalog read
precedes the source-fence callback. Capturing the resolved per-intent binding avoids
reconstructing the financial period or guessing a mandate. Existing selection types
are unchanged. Root approved this refinement.

Concrete additive API schemas are in optimization_candidates/customer_contracts.py.
CandidateReadIntent accepts only mandate ID/revision and CandidatePolicyRef;
CandidateCapabilities exposes bounded named policies/mandates and explicit
first_decision_producer_unavailable. CandidateReadPrepared returns existing selected
batch and job IDs; CandidateReadStatus returns owned progress and optional actual
decision/result ID. CandidateReviewIntent remains existing exact result/digest input.
No caller proof objects or execution authority fields are accepted.
