# Linked TikTok Push Compiler Checkpoint

This local checkpoint adds an independent `LinkedPushPublicationReviewV1`,
`LinkedPushPlanV1`, and `LinkedPushBoundRequestV1`. Existing social v1 documents
and hashes remain unchanged. The new five-step graph uploads a reviewed video and
matching-aspect cover, creates a disabled campaign and ad group, then creates a
linked Push ad. This is compiler code, not a configured customer publication path.

`compile_linked_push(review)` reconstructs the exact graph.
`materialize_linked_push(plan, plan_id, step_id, receipts, requests, fence, now)`
accepts only verified original dependency receipts bound to the same plan, scope,
request digest, original fence and observation interval. Every declared dependency
must be verified, including dependencies that do not supply a direct resource
reference. Resource names remain advertiser-scoped.

`creative_body(creative)` emits documented nested creative fields only. Rights,
media and observation commitments remain review evidence, never invented TikTok
wire fields. `matches_linked_ad` permits the Push post ID to be absent before ad
review; it requires the reviewed library video and linked identity. Pull contracts
remain separate and require an exact existing post, with explicit null video on
readback. No delivery, ad-review, financial qualification or spending authority is
inferred from these comparisons.

The owned capability reader is integrated from `7618b56` (local cherry `8c33c81`).
TT_USER capability presence is retained without interpreting BC-only ads-only
fields as TT_USER permission. Current supported creation remains ads-only ON.

Validation: 25 compiler/contracts/wire tests passed; whole-repository Ruff and
scoped mypy on six changed source/test modules passed. The receipt test verifies
missing non-resource dependencies, mismatched request/fence/plan, future receipts
and unresolved receipts all reject. No provider calls occurred.

Remaining implementation: linked HTTP adapter, coordinator discriminated dispatch,
configured owned runtime/profile and customer review composition, separate
activation, and genuine configured API/TLS acceptance. The new-CUSTOMIZED_USER
forward guard is staged separately and is **not integration-ready** until positive
future-creation fixtures and the configured path use linked Push. Historical v1
readback/reconciliation and existing-campaign optimization must remain supported.
The official Pull catalog schema is now available; actual catalog implementation
is still pending, not blocked by a missing response contract.
