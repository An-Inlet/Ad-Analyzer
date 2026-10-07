# Linked TikTok Customer Review

The separate `/app/tiktok-linked` page consumes the configured linked Push API
contract from c21653c and the author-reviewed safe projection. It requires explicit
video/cover, commercial rights, new linked post and Ads Only declarations. It
hashes and decodes owned media, verifies saved exact media commitments, names the
server-derived linked identity and displays targeting/behavior and creative before
configuration confirmation. Existing active spending consent is separately
selected; exact paused execution approval and run creation are separate actions.
The resulting saved run opens the existing explicit advancement/activation page.

Workspace/draft/identity/cover changes clear reviewed state. Request epoch,
selection and original CSRF-cookie fencing reject delayed or changed-session
responses, including session changes between actions before API IO. No local
storage grant, automatic approval, polling or automatic provider dispatch is added.
The currently supported API schema is contract_test only; UI calls it a contract
test and never represents it as live qualification.

Read-only independent review found a P2 response-shape mismatch: mandates expose
`policy.environment`, not top-level `environment`. Fixed before commit. Actual
response-shaped DOM fixture now verifies valid mandate selection, exact amount,
separate approvals, rendered media, XSS-safe text, invalidation and late responses.

Validation: pytest tests/test_tiktok_linked_ui.py **2 passed3.02s** after final
safe projection and original-session guard; earlier2passed4.18s. Real Chromium
HTTPS DOM and owned-byte media pipeline, with response fixtures only. Ruff whole
repository, prescribed mypy887, Node syntax and diff checks passed. An exploratory
`mypy .` command found duplicate script module discovery; the prescribed no-argument
command passed. No API/runtime qualification is claimed by these tests. Ordinary
configured API/browser integration is still required against the backend package.

## Ordinary Configured Customer Journey

Backend494ec217 integrated locally asf7a5667 above UI72b2df6. Actual HTTPS
browser→owned API→configured runtime now passes on SQLite and PostgreSQL:
**2 passed70.06s**, zero skips (31.38s/36.32s call durations). The customer chooses
server-discovered linked identity, reviews hash-verified media and exact settings,
records explicit rights/confirmation, selects separately API-consented spending
limits, approves the exact paused plan, creates/advances its durable run, then
separately reviews/approves/advances activation and signs out. Tests assert zero
initial execution rows, exactly5 paused-creation requests and3 activation status
requests, and one retained exposure reservation at completion. No runtime getter
overrides or seeded execution records. Provider identity/capability/status evidence
is MockHTTP plus explicit registered contract scenarios, never live qualification.

Independent backend-author UI source review found no additional actionable issue.
A known usability limitation remains: reloading this page does not recover a saved
configuration review by ID; the customer can prepare a new exact review. Saved
execution runs remain recoverable through the existing execution page.

Whole Ruff, required mypy895 and diff checks passed after this assembled test.
These checks do not qualify older CUSTOMIZED_USER future-creation fixtures; their
migration and immutable successor Full remain separately pending.
