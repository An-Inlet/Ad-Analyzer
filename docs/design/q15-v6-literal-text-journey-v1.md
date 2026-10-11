# Q15: Native Names And Customer Text Through Actual V6

Source-only proposal from preserved `9fd75ab` (runtime parent `d99b0ea`). No code,
tests, live/network requests or remote writes. Diagnostics candidate qualification
remains separate; this proposal does not close its prior failure.

## Closest Gap

Prefer one **actual V6 native-name/customer-text → selection → saved proof →
browser → JSON export** journey, rather than a new Q13 producer or another Q06
owner-count scenario. Existing Q15 foundations are partial, not absent:

- `tests/javascript/planning_documents_browser.mjs:12,32` already submits a hostile
  milestone and asserts literal rendering/no injected DOM under the older planning
  journey. `tests/test_planning_document_view.py` adds pure renderer hostile text.
- `tests/test_owner_review_planning_browser.py` and
  `tests/javascript/planning_owner_review_browser.mjs` actually qualify the private
  V6 original-session catalog/discovery/input/generation/history/export path, but
  the native names and customer text are benign (`Mug Campaign 1/2`, ordinary
  scenario title/product restrictions). The new owner-member renderer is therefore
  not joined to actual hostile native metadata in those passing cases.
- `docs/inlet-planning-quality-evidence-20261008.md` explicitly retains the assembled
  malicious native-name/note/export gap for Q15.
- Q14 disappearance/same-name replacement already has actual API coverage and
  `planning_target_disappearance_browser.mjs`; simultaneous duplicate-name and
  unknown-parent topology remain separate. Those would require a distinct
  acquisition failure/reselection specification and should not be folded here.

## Existing Interfaces And Narrow Fixture Change

Reuse the actual TLS owner browser harness, original cookie transfer and default
positive form journey, without triggering lost-response/edit/partial-transition
subjourneys. Add a distinct `literal_text` variant, two new DB nodes only; do not
rerun the three existing variants for acceptance counts.

An additive **test-only** optional native campaign-name map, default None, can be
threaded through `configured_owner_review` → `ready_inputs` →
`acquired_owner_catalog` to the existing MockTransport response construction in
`tests/google_budget_owner_discovery_fixture.py:93`. Apply the map before *all*
initial and browser-fresh metadata reads. Only names change; IDs, owner topology,
source generation, budget values, count/coverage/pagination and authentication stay
untouched. Do not edit retained receipts, source models, DTOs or serialized proof.

Use bounded ASCII HTML-like native names on both shared members (within160chars),
such as `Mug <img src=x onerror="window.q15Injected=true"> A`, and a second distinct
name with `<svg onload=...>`. `metadata_http.entity` preserves bounded observed
names rather than interpreting them; all normal parsing must still run. No real
URLs or external exfiltration targets. Customer milestone, scenario title and
product restriction text are filled through actual controls, including one inert
spreadsheet-like formula string. No new user-facing inputs or product policy.

## Minimal Acceptance

1. Browser owns fresh catalog read, exact target choice by canonical/native identity,
   owner discovery, explicit scenario/owner inclusion and actual customer form save.
   No prebuilt request or synthetic proof behind the browser. Assert actual native
   strings appear in the returned catalog and affected members before UI checks.
2. Before and after save, corresponding target option/member list nodes expose exact
   literal text. Assert no injected `img`, `svg`, `script`, event attributes or extra
   links in these specific text hosts, and `window.q15Injected` remains unset.
   Scope checks to text hosts: legitimate private product image preview must not
   produce a false failure. Use both structural DOM checks and sentinel checks;
   CSP alone must not make an unsafe inserted element count as safe.
3. Generate genuine V6 and validate server document/digest with `PlanVersion`.
   Saved witness contains exact owned member identities and exact observed names;
   requested customer strings survive in exact input/product fields. Owner panel
   and normal document/creative sections show the strings as text without executing
   them. Preserve no-Apply/period-compatibility-unassessed boundaries.
4. Click existing Export. Assert real response status/content type JSON, attachment,
   nosniff/no-store headers; exact document/digest and literal strings match retained
   V1. Parse artifact as JSON, never execute or inject it as HTML. Existing endpoint
   is **JSON**, not CSV or standalone HTML: no formula-safe spreadsheet/export
   rendering claim. Inspect the actual in-app readable document separately.
5. Read history/request receipt through existing authenticated routes and assert
   unchanged document. Original browser session preserved using Boolean-only
   `hmac.compare_digest`; scoped data cleared on logout if reusing existing final
   cleanup. Keep financial six-model baseline unchanged and provider transport
   fixed to existing allowed read endpoints, no new native effects.
6. Save synthetic server document/export plus DOM assertion results and normal
   bounded observer logs. No cookies, raw provider bodies or session digests in
   artifacts or assertion messages. Freeze source and exact two-node runner before
   execution; preserve failures/unrun and do not retry unchanged source.

## Ownership And Qualification Limits

Proposed files: additive fixture keyword plumbing in the three existing test
helpers; one bounded branch in existing owner TLS Python/JS harness. Shared
production API/schema/renderers remain unchanged unless a separately reproduced
concrete safety defect is reviewed. Existing helper defaults/old variant semantics
must remain byte-compatible. Reuse the already reviewed source/manifest/resource
and per-node SQLite→PostgreSQL discipline; no broad harness rewrite.

This closes only the stated actual V6 literal-text composition slice. It does not
newly qualify foreign selections, during-I/O role/session revocation, expiry,
Q14 unknown parents/duplicate topology, causal evidence, CSV safety or human
usefulness. Those keep their existing separate evidence and remaining gaps.
