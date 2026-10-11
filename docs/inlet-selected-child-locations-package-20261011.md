# Selected V4 Observed Child Locations — 2026-10-11

Base `32fb055`; implements the approved location boundary in
[Selected Q01/Q02 Common Basis Qualification V1](design/selected-q01-q02-common-basis-interface-v1.md).

Only `selected_composer.py` changes in production. `observed_child_steps` consumes
already validated catalog targets and matches full owned account identity, catalog
reference, provider platform, native advertiser and parent campaign ID. Excluded
children are omitted deliberately; unknown/other-parent and foreign-account children
do not attach. Duplicate names remain separate native identities. Canonical entity
keys determine ordering.

The five existing manual steps remain unchanged. Each included observed ad group/ad
set receives one bounded location-only step, retaining the campaign action's catalog
citation. It explicitly disclaims child metrics and child changes. There are no new
child actions, performance facts, budget advice or write authority. At most15 child
steps fit the existing20-step capacity; overflow or a step over2,000 characters fails
composition explicitly instead of truncating. No qualified children adds no steps.
Legacy composers and the default v3 policy setting are untouched.

## Checks

Evidence: `/workspace/inlet-evidence/20261011/selected-child-locations/`.

- New pure location tests plus existing selected paired composer: **42 passed**, zero
  skips, 21.863 seconds (`pure.xml`). Covers exact matching, duplicate names,
  exclusions, unknown parent, determinism, 15/16 capacity and oversized text.
- Additional Meta ad-set and TikTok ad-group formatter cases: **2 passed**, zero
  skips (`social.xml`). These are pure location fixtures, not provider qualification.
- Existing legacy composer: **20 passed**, zero skips (`legacy.xml`).
- Whole Ruff and configured mypy: passed, **1,364 source files**; diff check passed.
- The old complete paired fixture JSON hash was captured before implementation at
  the base commit. Removing only the newly added child steps reproduces it exactly.

No PostgreSQL, live calls, hosted tests, push, merge, deployment or default activation.
Actual Common Basis API tests are a separate dependent package; human usefulness and
live provider qualification remain unclaimed.
