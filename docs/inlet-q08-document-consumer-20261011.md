# Q08 Retained Document And Save Consumer

Local source builds on `d649010` on `codex/inlet-w1-followup`.

The additive private V5 empty-query preparation now validates exact retained account,
source binding/revision/privacy, evidence, UTC reporting window and expiry, zero-budget
creative inputs and the actual account investigation prerequisite. New generation
compares the complete embedded catalog witness with the actual collected catalog,
before generation writes. Exact completed replay remains before that new check.
Old campaign variants and default V3 remain unchanged.

Independent source review found no P1/P2. The focused consumer cohort passed 98 tests
in 7.01 seconds: document joins, existing creative documents/composer/repository
checks and account-preparation composition. Whole Ruff and configured no-path mypy
passed (1,431 files). `git diff --check` passed. Earlier fixture source-revision
failure and tuple-annotation mypy failure are retained, followed by their targeted
corrections. Eighteen new pure document/binding cases also passed separately; counts
overlap and must not be added.

Evidence: `/workspace/inlet-evidence/20261011/q08-document-validation/`.

This is not API/browser qualification. The next bounded package must prove a
strict-valid substituted embedded catalog is rejected by the real save path with
exact conflict reason and no generation writes, then exercise positive Q08 on
SQLite/PostgreSQL and the planned seven-case browser integration milestone. The
original R01 browser conflict remains unresolved. All artifacts remain local;
no live, hosted, remote, release or advertising operation was performed.
