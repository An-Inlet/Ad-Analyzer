# Existing Creative Save Admission — Evidence-Only Observer Proposal

Status: design only. No observer code, application changes or tests run. Read with
[the preparation proposal](creative-generation-save-preparation-interface-v1.md).
Independent review approved its architecture conditionally, but measurement must
justify that complexity **before** implementation.

## Priority: Identify The Failing Operation

The browser Generate flow performs POST generate, GET current plan, then GET versions.
Its existing generic409 message does not identify which request failed. The separate
browser diagnostic lane owns a bounded original sequence (four SQLite cases followed
by PostgreSQL Google) with fixed route/status/detail observations for these three
operations. A failed current/version read is not a failed generation transaction.
No automatic reruns, timeout extensions, catch-and-continue, policy changes or source
substitutions. Exact response-detail recording uses its independently reviewed fixed
allowlist, never arbitrary provider/customer response bodies. This proposal must not
replace that diagnosis with a performance theory.

## Smallest Observer Patch

One evidence-only pytest plugin outside application/source directories, adapted from
`inlet_v5_browser_timing.py`. Keep the original real API fixture and all calls exactly
as executed. Parent authorizes the bounded execution separately. The observer installs
reversible wrappers, invokes each original callable once with unchanged arguments,
returns the exact returned object, and re-raises the original exception untouched.
It does not call any validator, serializer, property getter or source method merely
for measurement. Retain and restore exact method descriptors in teardown, including
methods originally inherited rather than present in the class dictionary.

A ContextVar span stack opens only inside the actual service generation request.
Repository-specific counters open at `repository.save_generation`; record both
request totals and repository-only totals. No customer object, argument, stringified
exception, SQL text/parameters, media ID, session digest or proof enters evidence.
Span labels and model-class labels are fixed enums; counters are bounded.

### Exact Callable Boundaries

| Existing callable | Fixed stage | Interpretation |
| --- | --- | --- |
| `GenerationTicket.model_validate` | ticket_validation | Real strict ticket parsing, including nested inputs. Wrap this class descriptor only. |
| `PlanVersion.model_validate` | candidate_validation | Real strict complete document parsing. May contain nested validators. |
| `CreativePairedEvidenceV1.assert_ticket` | creative_bundle_admission | Real full ticket/paired/image binding. Includes its internal nested parsing; no extra call. |
| `repository.creative_proof_from_collection` | creative_proof_derivation | Wrap the repository alias actually called, not just the defining module. |
| `repository.creative_basis_reference` | creative_reference | Actual reference derivation and validation. |
| `repository.targets` | catalog_target_projection | Actual owned catalog target projection, including its pure validation. |
| `Frozen.digest` | model_digest | Existing inherited digest calls, retaining real `self`; use only a fixed allowlisted model label. Includes any nested validation. |
| `repository.canonical` | persistence_serialization | Actual canonical serialization used for the version row. |

Do not wrap global `BaseModel`, all validators, `model_dump`, JSON internals or
Python tracing hooks. Those would increase overhead and change the meaning of the
measurement. The classmethod wrappers must preserve binding and `strict`/context/
other keyword arguments exactly, and restore inheritance after the probe. Instance
method wrappers preserve their existing descriptor behavior. Validation called via
Pydantic's internal compiled schema is included in its enclosing span; it must not
be reported as an independently observed Python call.

Retain existing coarse `identity_refresh`, `authority_lock`, `authority_final`,
`selected_final_recheck`, `image_final_recheck`, `retained_witness_capture`,
`save_generation`, `generate_total`. Add fixed mixed SQL envelopes only for the
repository's `inputs` and `version` loaders so their embedded parsing/digests are not
mistaken for candidate-only preparation. Engine cursor counters retain only count
and elapsed time; no SQL text. No Session.flush span for every implicit flush: those
thousands of rows drown out useful output; aggregate flush count/time instead.

## Disjoint Accounting And Interpretation

Each span records monotonic elapsed, process CPU, SQL-call delta and SQL elapsed delta.
Stack parent identifiers allow interval-union/exclusive accounting, including recursive
digest/validation nesting. Sum only disjoint outermost pure intervals **within the
repository save**; report nested rows separately, never add them to ancestors. Do not
subtract global SQL time from wall time and call the remainder pure validation:
network waits, scheduling, ORM work and unwrapped Python remain unattributed.

Label each pure interval by its nearest enclosing mixed/coarse stage. Preparation
candidates are only top-level repository candidate admission, proof/reference/target
and persistence serialization. Pure work inside selected/image/witness rechecks or
SQL-loaded current inputs/history is NOT movable by the proposed slice. Keep this
separation even when the same digest/model method appears in both places.

Any SQL within a supposedly pure interval is a finding to investigate; it cannot be
excluded silently. Constructor validation, comparisons/comprehensions and Python
work with no wrapped callable remain `unattributed_repository_time`. Thus measured
pure admission is a conservative observed subset, not full wall-time attribution.
The proposal does not justify moving unmeasured work solely because it looks pure.

The report answers:

1. Which exact API request failed and which allowlisted domain error occurred?
2. What fraction of final fact-window time belongs to observed independently movable
   pure admission, versus fresh source checks and unattributed work?
3. Which validators/digests run repeatedly, and are those repeats inside or outside
   the movable boundary? Record counts before claiming redundancy.
4. Is moving the observed work plausibly worthwhile after defensive snapshot and
   type-aware commitment overhead? The current evidence alone cannot answer this.

No fixed speedup target or desired result is imposed. Small pure cost means defer the
preparation mechanism and investigate query shapes with a separately reviewed observer.
High pure cost supports an implementation proposal but does not establish why the
original409 occurred. Instrumented passing durations are observer-affected measurements,
not production latency guarantees or permission to relax the five-second fact gate.

## Ownership And Execution Gate

Customer-signin lane owns diagnostic browser/route observer and actual test selection;
this lane supplies only this boundary contract. Root selects whether to combine the
pure observer in that one bounded sequence or run it later after failure attribution.
Avoid two concurrent probe suites and avoid duplicating source wrappers in two plugins.
Root approval is required before any observer code or test execution. Original evidence
and application sources remain unchanged; retain every outcome including unavailable
metrics, failed requests and unexpected observer errors.

## Conservative Attribution Refinement Before Execution

Review found that a direct repository `Frozen.digest` call may be for SQL-loaded
input or a historical PlanVersion rather than the candidate. The observer therefore
excludes **every standalone digest span** from movable cost unless it is nested
inside an already eligible pure admission span. This also excludes genuine standalone
candidate digest cost: it remains measured but unqualified, without additional object
identity tracking. No preparatory benefit is inferred from ambiguous model type or
call-site proximity. The executable observer is retained outside production source
under `/workspace/inlet-evidence/20261011/creative-save-admission-observer/`.
