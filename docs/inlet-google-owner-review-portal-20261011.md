# Private V6 Owner Review Portal

Local UI child of `5a9008d`; no remote operations, provider calls, schema changes,
new policy version, default-policy change or advertising authority. The shared
component boundary was frozen in `a35bf74`; implementation follows the closed
portal interface and implementation plan.

## Implemented

The existing planning editor recognizes only the exact V6 pair in addition to its
unchanged V1–V5 capability objects. V6 includes creative and selected-reporting
support plus explicit owner-review input arrays, including empty arrays. Legacy
requests omit the owner field. V3 remains the default server configuration.

Customer discovery uses the original owned target catalog and current reporting
window. The component binds returned member references to the original catalog,
including connection generation, selectors, provider identity and stable owner.
Customers choose a complete alternative and exact six-decimal daily hypothesis;
period allocations remain separate. At most20 ordered reviews are permitted,
with duplicate full-account/owner rejection. Historical resolved inputs retain
original values but cannot silently adopt new observations; server-only fields
are excluded from the primitive request allowlist.

Goal/account/window/target/scenario/exclusion changes invalidate discoveries;
mounted-handle, generation, exact-context and original-session checks reject late
successes and failures. Expired or historical selections require explicit removal
and reselection. Existing unknown-mutation result handling retains its exact
request key and body. No Apply control is introduced.

Saved document rendering shows all affected campaign names, exact daily amounts,
original observation timestamps and manual-review limitations. It refuses malformed
scope/currency/scenario/timestamp or policy attachments. Expired historical evidence
remains displayable. Legacy saved inputs cannot silently become V6 empty reviews:
the actual controller refuses that edit before media reads or editor population,
with read-history/create-new guidance. Compatible V5/V5 and V6-empty/V6 edits remain.

## Validation Actually Performed

Evidence directory:
`/workspace/inlet-evidence/20261011/owner-portal-components/`.

- Reviewed manifest02 `6e46618cf928c92e73af8a86ffbee53d651c28e1910620349bf0467a9c3fc1a8`:
  exactly two nodes, **2 passed in6.40s**, `selected-01.xml`/`.log`/`-result.json`.
  New actual-Chromium component covers exact legacy capability objects/omission,
  V6 empty mode, micros, bounds,20/21st inclusion, order/removal, full-owner
  duplicates, original-catalog generation/selector/member mismatch, historical
  projection, stale success/failure, expiry/session/old-handle clearing, unavailable
  discovery, zero ceiling and literal saved proof without execution controls.
  Existing document renderer regression verifies its new import dependencies and
  preserves prior display assertions.
- Reviewed manifest03 `631afb79555ae943eefa7b76ddc7b2d8b79f502192915a5ed72af5733c5541dc`:
  exactly one additional node, **1 passed in3.22s**, `controller-01.xml`/`.log`/
  `-result.json`. It serves actual planning HTML/modules and exercises saved-plan
  Edit through the controller with controlled Fetch. Null and omitted legacy
  fields refuse under V6; V5/V5, explicitV6-empty/V6 and newV6 open normally.
  It asserts no mutation/discovery and no media read/editor population on refusal.
- Between those runs, the only changed previously tested source was the separate
  inline compatibility guard in `planning.mjs`; component modules, first driver,
  document renderer and dependency harnesses retained their exact manifest02 hashes.
  The second run adds the controller harness/driver and contract documentation.
  Prior two nodes were not repeated.
- Whole repository Ruff passed. Clean `mypy --no-incremental` with configured
  no-path targets passed **1481 source files** after the final source changes.
  Logs: `controller-ruff.log`, `controller-mypy.log`. `git diff --check` passed.
- Both execution manifests used fail-fast, configured strict markers, sanitized
  PYTEST/OBSERVER/PYTHONPATH environment, explicit `/usr/bin/chromium`, fresh isolated
  cache/temp/log/XML/result paths and sole-test/resource preflight checks. No retry.

These are component/controller checks, not authenticated API or production browser
qualification. The separate browser lane owns actual TLS/original-session API,
private V6 fixture, discovery/save/generation/history/export and unavailable-path
qualification on SQLite/PostgreSQL. Those results remain outstanding for this UI
package; service qualification elsewhere must not be relabeled UI qualification.

No live integration, purchase readiness, provider-edit validity, remaining-spend
assurance or period-spending compatibility is claimed. Website work remains paused;
manual review does not resolve the outstanding launch/human gates.
