# Private Window Evidence Contracts — 2026-10-08

Base `206e03f`; branch `codex/inlet-window-evidence-contract`.
Interface: `docs/design/planning-window-evidence-contract-v1.md`.

Added only private `policy_capabilities.py`, `window_evidence.py`, pure tests and
this ledger. No existing runtime, ports, fixture, report, reader, policy defaults,
composer, database or public API changes. The new v3 contract remains inactive.

The closed policy/generator table recognizes exactly v1/v2/v3. Ticket lookup
reconstructs the canonical existing PlanningCompositionPolicy and requires its
exact digest; unknown/mixed pairs and altered digests fail. Old v1/v2 canonical
hashes are pinned by tests; the unchanged composer rejects v3.

Window evidence binds the requested projection to original report scope,
manifest/generation/privacy/completion and exact native campaign/catalog target.
Requested-row presence cannot be borrowed from another part of the import.
Selected counts require actual explicit-event cells; missing remains unavailable.
Reference coverage never exceeds partial. Original currency/time zone must match
the owned catalog. Expiry remains bounded by actual catalog evidence.

The separate bundle independently revalidates nested inputs and retains existing
source, commerce, context, goal, privacy and freshness rules. Every selected
account has an exclusive actual catalog or catalog gap, plus an exact reporting
pin. Every catalog campaign × requested window has exactly one success or gap;
empty/absent catalogs require the corresponding null-target gaps. Snapshot selection,
provider reference/parent, name, owner and catalog key all match. No fake old bundle
or relabeled source header is constructed.

Entry keys use the frozen fingerprint domain and UTC-normalized ISO instants.
Slot/reference window comparison also uses UTC instants: ordinary Python same-zone
datetime equality ignores fold, so it cannot establish exact requested instants.
No original window representation/digest is rewritten.

## Qualification

**103 passed in 5.41s**, covering new contracts and unchanged old ports/composer/
requested-window projection suites. Whole Ruff passed; bare configured mypy passed
**1,095 source files**; diff check passed.

Included cases: three closed pairs and canonical hashes; unchanged composer v3
refusal; one/two windows; success/gap mixtures; exact100clicks/10conversions/USD100;
selected zero and missing; requested subset empty despite original rows; wrong
selector/name/account/pin/window/source/privacy/expiry and copied authority values;
actual empty catalog and explicit catalog absence; context/commerce binding;
UTC-equivalent key identity and distinct DST folds; actual200campaign×2window=400
complete gap slots with omission/duplication rejection; combined401 count refusal;
actual32MiB serialized bundle accepted and +1byte rejected.

The byte-bound fixture repeats valid evidence entries at construction (before
assert_ticket's separate duplicate-slot rejection), padding the unchanged legacy
exact decimal spelling while each projection remains below2MiB. This proves the
collection byte guard, not that duplicated entries constitute an accepted ticket.
No truncation or production cap changes were used. The actual400-slot positive
uses separately projected real catalog contracts and exact distinct targets.

```text
/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_window_evidence_contract.py tests/test_planning_document_ports.py tests/test_planning_composer.py tests/test_requested_window_projection.py --junitxml=/workspace/inlet-evidence/20261008/window-evidence/pure-final.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Retained raw artifacts: `/workspace/inlet-evidence/20261008/window-evidence/pure-final.log`
and `pure-final.xml`. Earlier `pure.log/xml` predate the final UTC-fold hardening and
are not the final source qualification.

No DB, API, native importer, whole-graph source authenticity, customer comparison,
quality-case completion, Full or live qualification. Next dependent package is the
separately reviewed owned window reader/context; runtime activation remains gated
on later adapter/composer integration and actual acceptance.
