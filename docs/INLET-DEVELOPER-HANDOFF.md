# Inlet Developer Handoff — October 12, 2026

**Start here: this branch is an unqualified WIP candidate for developer review.**
It preserves the integrated development tree based on `f8107a9c5f60accb5e73e6d9fa82a5b4e33021dd`,
including pending source/tests and the historical work indexed below. It is not a
live-qualified, purchasable release. Main was checked at
`ea3591c5086fbf2cee8038bf9208ac7f0050de75`, the original audit baseline.

## Product And Operating Boundary

Product: Inlet. Company: An Inlet. Initial customers: Shopify ecommerce brands.
Planned advertising coverage: Google, Meta and TikTok; commerce: Shopify; customer
data: Klaviyo, HubSpot and Omnisend. Customers use supported tools they already own,
describe a milestone, confirm an editable goal, set budget/aggressiveness, review a
plan and monitor progress. These are scope commitments, not blanket completion claims.

The owner's later October 7 scope is **planning only: customers manually apply all
advertising changes**. No advertising writes, including reviewed publishing, are
part of this MVP. Draft 5%/10%/20% aggressiveness settings never increase an overall
spending limit. Existing execution code must remain disabled. Public webpage work
is separate and owner-managed; illustrative demos and email early-access buttons
are not signup, paid access or working account integrations. Do not redesign it or
publish new product claims as part of this handoff.

## Verified Work And Open Failures

| Area | Evidence and limits |
| --- | --- |
| B01 conversion diagnostic | Reproduced and repaired at `91fe009`; 100 clicks / 10 conversions / $100 does not produce a no-conversions finding. True zero, fractional positive, absent metrics, coverage and spend boundaries have focused regressions. Original focused cohort: 38 passed; original Full: 600 passed, 6 PowerShell skips. See [original ledger](inlet-progress.md#b01--conversion-diagnostics). These historical counts do not qualify today's whole tree. |
| B02–B04 customer foundation | Customer identity and revocable sessions, atomic workspace/owner provisioning, explicit import/job ownership and subsequent isolation repairs are implemented. Package checks, migrations and original CI links are in the [foundation ledger](inlet-progress.md#b02b04--customer-foundation) and [shared contract](inlet-foundation-contract.md). No live production qualification is implied. |
| Integrated planning and portal | [October 11 checkpoint](inlet-acceptance-20261011.md) records source-bound package acceptance; [capture handoff](inlet-capture-handoff-20261012.md) records 11 browser/API tests. Google/Meta/TikTok availability differs by capability; missing data must stay unavailable, not zero. |
| Prepared snapshot matcher candidate | 102 component tests and 40 exact runtime cases passed (20 SQLite / 20 PostgreSQL), with Ruff, mypy, exact collection and whitespace gates. Continuation preserved the original resource interruption. See [qualification ledger](design/prepared-snapshot-match-blocked-20261012.md). |
| Release reliability | `INLET-REL-20261012-01` remains open: prior larger PostgreSQL generation returned 409 after the five-second authority deadline. The changed-code larger-workload retry has NOT run. V3 remains default; V6/V7 remain release-unqualified. |
| HTTP admission candidate | 57 passes / 1 unresolved in its own recorded inventory; do not claim completion. See [HTTP admission status](inlet-q13-http-admission-20261012.md). Retention/reconnection policy remains an owner decision. |

No whole-suite run or hosted CI was performed for this publication snapshot. Passing
cohorts apply only to their frozen source and named cases. Original failures and
unrun cases remain recorded. Local `/tmp` and `/workspace/inlet-evidence` links in
older documents identify executor evidence, **not files downloadable from GitHub**.
Raw logs, databases, browser profiles and recovery archives are deliberately excluded.

## Code Map And Local Entry

Python 3.12 / FastAPI / Pydantic; SQLAlchemy and Alembic; PostgreSQL-compatible
persistence. Preserve this architecture. Start with [README](../README.md),
[workspace architecture](workspace-architecture.md), [customer portal](inlet-customer-portal.md),
[AGENTS.md](../AGENTS.md) and [automation policy](automation-policy.md).

- `app/api/customer_*.py`: authenticated customer API and ownership boundaries.
- `app/planning_documents/`: typed plan inputs, retained evidence, generation,
  currentness, immutable versions/history and export. Final authorization and atomic
  publication retain the five-second boundary; no cached permission decision is valid.
- `app/portal/` and `app/portal/static/`: existing customer UI and browser modules.
  UI changes consume server capabilities and typed contracts; the server remains
  authoritative for workspace, session, account, entitlement and source checks.
- `app/ads/`, provider modules and workers: explicitly owned acquisition/jobs;
  collectors and disabled execution paths remain separate.
- `migrations/`, `tests/`, `tests/javascript/`: schema, isolated fixtures and browser
  contracts. Integration tests must use disposable databases and synthetic transports.

For an isolated local checkout (no provider credentials):

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

See README for database setup/migrations and required validation. Run `ruff check .`,
`mypy` and an explicitly selected pytest cohort before proposing a change. Do not
point tests at production or start a full expensive suite merely to review this
snapshot. Runtime/browser fixtures document additional local dependencies.

Frontend/backend collaborators should agree the relevant DTO/API/capability contract
before parallel changes, use separate branches and name shared-file ownership.
This publication does not assign work to or grant repository access to Looly Labs;
the owner manages invitations and engagement.

## Complete Work Inventory

[Branch inventory](handoff/2026-10-12/branches.json) accounts for all **641 original
local heads** without publishing hundreds of redundant branches: 229 are already
ancestors of the primary tree, 230 have patch-equivalent nonmerge changes in its
history, and 182 are historical alternatives retained locally, not selected for this
handoff. Patch equivalence is a history comparison, not a claim of identical final
behavior or qualification. The inventory records exact SHAs and existing remote
heads (171 same-name matches). No local branch is deleted. Historical alternatives
are not changes to apply cumulatively and have not been declared obsolete merely
because their SHA differs.

[Worktree inventory](handoff/2026-10-12/worktrees.json) accounts for 546 registered
worktrees, including three missing registered paths. Ten contain actual source/test
changes. This primary tree includes the integrated candidate; nine other worktrees
are preserved as **unintegrated, unqualified patches** against their named base SHAs
under `handoff/2026-10-12/unintegrated/`. All nine patches reconstruct the original
22 changed files byte for byte. They use zero-context diffs: apply with
`git apply --unidiff-zero` only in an isolated checkout at the exact base SHA, after
reviewing whether the change already exists in the integrated tree. Four bases are
in primary history; five are preserved under explicitly listed
`review/inlet-20261012/patch-base/...` branches solely to make reconstruction possible.
Thus this handoff adds **one primary branch and five historical patch-base branches**.
Existing branches and PR heads remain unchanged. Cache symlinks and node_modules
are excluded. Original worktrees and indexes remain untouched.

Outgoing previously unpublished Git history and WIP files received a bounded secret,
credential and artifact scan plus contextual review of all flagged matches. Matches
were synthetic fixtures, development defaults and documented placeholders. No actual
credential blocker was identified; this is not a guarantee about arbitrary private
text. Publication stays in the existing private repository; no access changes.

## Next Package And Publication Policy

1. Review this WIP tree and inventory; select one integration branch rather than
   merging historical alternatives indiscriminately.
2. Resume the two PostgreSQL lock-expiry cases, then the single changed-code larger
   PostgreSQL workload retry. Stop and preserve evidence at an unexpected failure.
3. Only after those gates pass, run the bounded 29-case release matrix. Keep unchanged
   authorization, source-currentness, rollback and resource-floor requirements.
4. Resolve HTTP admission and owner retention decisions; reconcile remaining planning
   quality acceptance and live configuration obligations before any release proposal.

The owner authorized GitHub publication for developer review. This supersedes earlier
no-push statements only for this handoff. New branch-only pushes do not match the
reviewed repository CI push triggers. Draft PRs would trigger CI, so none are opened
for this snapshot under the existing $10 Actions cap. No workflows are changed or
skipped, no manual runs dispatched, and no new budget approved. Merging, deployment,
provider activation, visibility/access changes and live ad operations remain gated.
