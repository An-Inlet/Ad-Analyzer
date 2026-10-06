# Customer Execution Review Context Repair

Two approval-clarity defects were reproduced against frozen `1c82e03` with real
HTTPS Chromium requests to the actual customer API on SQLite and disposable
PostgreSQL:

- A prepared social review could arrive after selection changed to B and become
  approvable under B's summary. Both database variants failed the delayed-success
  assertion. The backend still enforced tenant/plan ownership; this was a customer
  approval-context defect, not evidence of a backend tenant bypass.
- Two genuinely persisted configurations for one campaign/revision, with different
  Meta Page references, produced identical option labels. Both variants failed the
  independent distinguishing-label assertion.

`execution.mjs` now uses a monotonically increasing context generation and a captured
form snapshot. Every API response is checked after network completion and again after
body parsing, before caller state assignment. A readable session nonce also fences
responses across session changes; server authorization remains authoritative. Workspace,
draft, configuration, Google settings, policy settings, run selection, session refresh
and logout invalidate old review/acknowledgement state. Workspace/run navigation is
queued while a prior request settles rather than silently ignored. Returning A→B→A
cannot reuse A's earlier request generation. Recovering a saved run clears unrelated
proposal/configuration panels. Separate activation shows the original canonical plan,
not a different configuration still selected elsewhere on the page.

Late successes and errors cannot restore or approve a different context. A lost
mutation response explicitly says the request may have completed, clears local approval
state, and does not automatically retry. The browser regression creates a real durable
run, drops its response, and recovers that same run through owned saved status without
re-admission. No claim is made that a client-side invalidation cancels a dispatched
server request.

Configuration choices, selection summaries and exact reviews now distinguish Meta
Page/Purchase Pixel or TikTok Identity/Purchase Pixel references and actual media file
references. These are derived only from the owned canonical API projection. Historical
catalog display names were not persisted in version 2; the UI therefore identifies the
values honestly as owned references instead of inventing names or fetching a new native
catalog just to label historical records. Full digests remain the backend authority.

Both selection and exact review show authenticated private image/video/cover previews.
The helper accepts only fixed supported MIME types, bounds reads to 64 MiB and the exact
reviewed byte count, verifies SHA-256, and waits for image load or video `loadeddata`.
A 30-second timeout, context/session changes, replacement and logout abort old loads and
revoke object URLs. A failed or stale preview cannot enable preparation/approval. The
actual TikTok-cover tests use two different persisted image byte sequences and verify
visible decoded images and video, not metadata-only success.

No backend service, schema, provider proof, credentials, spending authority or default
runtime changes. This is a customer application repair; public marketing is unchanged.
Full and hosted qualification remain root-owned and pending for the assembled candidate.
