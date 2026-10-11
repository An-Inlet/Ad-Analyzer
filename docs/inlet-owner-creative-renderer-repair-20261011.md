# Exact V6 Creative Basis Renderer Repair

TLS01 on the private owner-review journey failed its first SQLite positive case
because `appendCreativeBasis` recognized only the exact V5 pair. The actual V6
service had returned successful generation/current responses before the browser
refused the creative proof. Preserve that result:0passed,1failed,3unrun. No
transaction-deadline explanation or authenticated UI qualification follows from it.
Original evidence remains in
`/workspace/inlet-evidence/20261011/owner-planning-browser/tls01-summary.json`
(SHA256 `d4c72755129beee2ac067a2a9e4eebd2ef21ba8c7c42b0aa62b1892c934d73d4`).

The narrow repair accepts either exact V5 or exact V6 policy/generator pair.
All downstream creative basis, workspace, requested-input, image count/hash and
observation checks remain unchanged. Mixed/unknown/legacy pairs still refuse
attached creative proofs; legacy absent-proof rendering remains unchanged.
Adjacent capability and owner-proof renderer gates already recognize V6; no
additional policy, service, schema or default-mode change was made.

One new actual-Chromium renderer node consumes genuinely Python-composed V5,
V6 and empty-owner V6 PlanVersion DTOs through `renderPlanDocument`. It confirms
both creative and owner panels, retained product/image observations, absence of
undefined fields, and mixed/unknown/legacy plus missing/mismatched basis refusals.
This is a pure DTO component check, not authenticated browser/API qualification.

Validation evidence:
`/workspace/inlet-evidence/20261011/owner-creative-v6-renderer/`.

- Reviewed source; parent authorized exactly one node with stop-on-first-failure.
- Manifest01 SHA256
  `47607ca6fa3e000b8d07bddc3a4de925adf29b8dfb890f12eba2540ea4293bb4`.
- `run01.xml`/`run01.log`/`run01-result.json`: **1passed in3.17s**, no retries.
- Whole Ruff passed. Clean configured no-path `mypy --no-incremental` passed
  **1484 source files**. An initial test import re-export typing error was corrected
  to the original fixture module; its failed log is preserved separately.
- `git diff --check` passed. Prior component cohorts were not repeated.

The original TLS failure remains immutable. Its three unrun cases are still
unrun, and a future authenticated browser continuation requires the separate
browser lane's reviewed manifest and parent authorization. No remote/live actions.
