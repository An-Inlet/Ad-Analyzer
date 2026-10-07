# Configured Candidate Reads And Separate Review

This package adds the ordinary customer API and scheduler reachability described in
[the scoped interface](design/candidate-owned-runtime-interface.md). It does not add
qualified learning producers, automatic first-decision epochs or automatic spending.
Google/Meta use the existing separately admitted native optimization assembly;
TikTok's configured optimization inventory remains a separate unsupported path.

## Configuration And Resource Ownership

Three optional server settings identify the candidate manifest, its exact digest
and policy bundle: candidate_assembly_manifest_path,
candidate_assembly_manifest_digest and candidate_policy_bundle_path. The existing
optimization manifest must match its pinned digest/environment. Source registration
remains empty by default. No JSON proof, dynamic module path or configured descriptor
is enough to qualify actual evidence. Candidates-only mode is assembled; automatic
mode remains unavailable with first_decision_producer_unavailable.

configured_candidates creates one owned optimization context per original principal.
selection_for(binding) captures the exact original consent/ledger period. The
OwnedCandidateReads reader and source-fence builder use private short sessions and
never commit or roll back their caller. Catalog transport/vault contexts use the
existing original-session, actual-engine, generation and final authority checks.
The source fence explicitly retains V1 commerce publication semantics; no V2 report
is cast into supported candidate evidence. Unqualified observations have no direction
or observation count and compile to blocked decisions. An explicit contract scenario
may exercise the existing separate review path but is not empirical/live evidence.

Generic review approval uses a lazy candidate guard only for protected candidate
reviews. It checks the request's exact original session and reconstructs the pinned
candidate dependencies while reusing the already-owned native runtime. Missing
candidate configuration does not change manual or V2 preview availability. Source
retraction and original-session/goal/policy guards remain mandatory; historical
reconciliation contracts and financial reservation semantics are unchanged.

## Customer And Worker Entry Points

The candidate API exposes capabilities, POST reads with mandate/policy references,
owned GET read status, and POST result review with an exact decision digest. It never
accepts evidence or target-state objects and never approves or executes a review.
Capability labels use owned goal/account/currency/budget and actual policy step/count,
not hash prefixes or invented aggressiveness defaults. No frontend is added here.

customer_candidate_reads_enabled defaults false. The existing customer runtime tick
runs the candidate stage only when enabled; the runner checks ALL_DATA_SYNCS before
source/identity construction. Existing session automation remains separate. The
candidate worker selects bounded due jobs and reconstructs each persisted original
actor/session in its own context. No global per-session runtime or credentials.

A scoped-factory failure is durably deferred by60 seconds under canonical workspace
then exact job locks. This changes only due_at and a sanitized error code, preserves
claim/fence/lease/attempt counters, skips active leases/concurrent future scheduling,
and creates no retry authority. It prevents an unavailable original session from
permanently hiding a newer job in its workspace or consuming a bounded batch ahead
of other tenants. Transient unavailable setup is retained rather than deleted.

## Validation And Limits

- Actual configured API→separate0080consent→selection/jobs→run_customer_tick→native
  Google/Meta MockHTTP→result on both databases. Unqualified results stay blocked;
  explicit scenario results can prepare an exact review and receive separate
  customer approval. No getter override or seeded candidate/job/admission/attempt.
  Revocation before assembly and during native IO produces no result or provider write.
- Final configured/manual/V2 cohort:22 passed,48 deselected,108.99s, before the
  scheduling-only fairness repair; /tmp/inlet-candidates-final-configured.log.
- Final repaired scoped-factory/API/scheduler cohort:58 passed79.69s;
  /tmp/inlet-candidate-fairness-final.log. Includes limit1/10, factory raise/None,
  same-workspace two-tick recovery and distinct-context closure. Fairness unit cases
  use existing lower-level service fixtures and are distinguished from the actual
  no-seeded-job configured API acceptance.
- Broader candidate/selection/review/scheduler cohort:156 passed,4 expected SQLite
  concurrency skips, terminal0; /tmp/inlet-candidate-assembly-regressions.log.
- Whole Ruff/mypy843/diffcheck and fresh-process assembly/API/main imports passed.

The original fairness defect was reproduced independently on SQLite and PostgreSQL:
two jobs in one workspace, revoked first original session and limit1 yielded
unavailable on both ticks. The preserved before logs are
/tmp/inlet-candidate-starvation-before.log and -before-pg.log. The repaired test
selects the valid second session on the next tick without changing original authority.

An earlier API-contract test used invalid nonhex fixture IDs and failed, while a
trailing static command masked the pytest exit status. The2-case corrective rerun
passed with valid32hex IDs; the production contract was not relaxed. The erroneous
initial pass report was corrected to the parent immediately. The original log was
overwritten by the corrective rerun; its observed excerpt is retained at
/tmp/inlet-candidate-api-initial-failure-excerpt.txt. Subsequent cohorts checked
pytest terminal statuses separately.

No Full, live account calls, remote writes, merge or deployment. This closes the
candidate-only runtime composition slice, not qualified automatic learning, initial
decision generation, configured TikTok optimization or a complete customer UI.
