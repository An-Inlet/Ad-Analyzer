# Plan Provenance Version Boundary

Baseline `a9c4bc3`. This supersedes the prior conclusion that backward reading alone
was sufficient to reuse the document tag for newly enriched output.

## Investigation

The V6 integration design calls `inlet.plan-version.v1` extensible, but extensions
were explicitly bound to new exact policy/generator pairs. Typed provenance changed
neither. Pydantic nested models forbid extras. `storage.document_for_row`, API
current/history/replay, workspace archive `export_serializers.serialize` and its
historical checks all use PlanVersion; the browser currently accepts only v1.
Repository insertion uses `plan_version_storage_pair`. Rollback instructions do not
currently account for already-written incompatible JSON. No released/live enriched
rows are known or authorized; local qualification artifacts do exist and must survive.

## Minimal Explicit Boundary

Use `inlet.plan-version.v2` for newly generated plans containing typed selected
provenance. Keep the same PlanVersion Python class and canonical digest domain: the
explicit tag is part of hashed canonical content. Existing policy/generator pairs
continue to describe planning behavior, not reader support. No new policy activation,
API route, SQL table/migration or public application version is necessary.

Reader recognition is a closed v1/v2 set. V2 requires typed provenance for every
retained selected capture (and at least one). New v1 writes forbid any typed provenance.
Legacy v1 readers in this build accept both original un-enriched rows and interim
`a9c4bc3` enriched v1 rows as a documented read-only compatibility bridge. They never
rewrite, enrich, relabel or re-sign those rows. The canonical repository writer rejects
new enriched v1. V1 with no selected captures remains v1. Unknown versions reject.
Browser recognition enforces the same v2 completeness and closed tag set.

## Upgrade And Rollback Contract

Before permitting v2 generation, deploy a reader-capable build coherently across API,
workers/export/restore processes and frontend assets; do not mix older readers with
new writers. This is a release prerequisite, not authorization to deploy here. Existing
v1 rows need no migration. Once v2 exists, rollback only to a build that reads v2 and
retains the original integrity/export checks; disable generation during rollback.
A pre-v2 binary is unsupported against a database containing v2. Do not strip fields,
rewrite tags/digests, drop rows, silently skip export data or downgrade the DB. Recovery
is a reader-capable roll-forward or a separately approved full consistent restoration,
not an automatic lossy conversion. Interim enriched v1 also requires a provenance-aware
reader; its pre-change strict rollback barrier is explicitly retained, not hidden.

## Focused Acceptance

Genuine un-enriched v1 and interim enriched v1 artifact payload/canonical digest preserved;
real storage parser/export serializers accept v1/v2 with full scalar/digest checks.
Writer rejects enriched v1 and malformed/unknown v2. Composer emits correct tag. Actual
SQLite/PostgreSQL current/history/export/replay and workspace archive reader accept v2;
legacy omission flow remains v1. Browser accepts supported formats and clears unsupported
or mismatched versions. Existing storage-pair/kernel inventory checks reviewed, full Ruff
and configured mypy plus focused bounded pytest; no unchanged full-suite repeat.

No dependent social producer until this boundary is qualified. Continue official-source
research afterwards. Retention/sharing/live/hosted/push/deploy/spend holds unchanged.
