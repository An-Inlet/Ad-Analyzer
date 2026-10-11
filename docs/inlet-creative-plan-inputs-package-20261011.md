# Reserved Creative Plan Inputs — 2026-10-11

Base `8ae895a`, branch `codex/inlet-w1-followup`. Implements the reviewed
[reservation interface](design/creative-plan-input-reservation-interface-v1.md).

Customer and saved input DTOs retain exact typed creative intent, including an
explicit empty object. Null values remain omitted, preserving legacy serialized
bytes and digests. Owned preparation copies the value; resolution checks equality;
input validation binds optional price currency to the confirmed goal and
revalidates nested copied models.

Existing v1–v4 composers and service admission/generation reject typed creative
inputs. Unsupported policies return the established409 conflict; malformed DTOs
retain422. The exact v5 pair is reserved only: no capability registration or runtime
activation. PlanVersion rejects every non-null creative input, including reserved
v5, until actual creative document proof validation is implemented.

## Verification

Evidence `/workspace/inlet-evidence/20261011/creative-plan-inputs/`:

- `pure01.xml`:33 passed,0 skips/errors/failures,2.048 seconds.
- Final `pure02.xml`:34 passed,0 skips/errors/failures,2.566 seconds; includes
  historical selected-input golden bytes/digests and direct unproved-v5 rejection.
  This overlaps and replaces the initial pure cohort, not an additional34 cases.
- `api01.xml`:8 SQLite/PostgreSQL cases passed,0 skips/errors/failures,9.442 seconds:
  existing request replay, changed/new request and edit denial before native reads
  or input persistence, plus owned preparation/resolution.
- `generation02.xml`:2 affected SQLite/PostgreSQL cases passed,0 skips/errors/
  failures,4.784 seconds after strengthening saved-draft generation denial. These
  overlap the API cohort. Neither native reads nor document/head persistence occurs.
- Final whole Ruff passed; configured no-path mypy passed for1,374 source files.
- `git diff --check` passed. Independent source review closed with no P1/P2 findings.

Default v3 remains unchanged. No hosted CI, push, live providers, advertising
writes, credentials, merge or deployment. This is an input reservation, not a
customer-available creative planner or expert quality qualification.
