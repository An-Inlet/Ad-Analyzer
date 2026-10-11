# Q10 Local Actual V5 Test Interface

Base: `2059b78`. Test-only; shared Q05/Q07/Common Basis fixtures remain unchanged.

A private `_prepare` helper in `tests/test_creative_q10_common_basis.py` calls
`prepare_creative_common_basis(..., platform="meta_ads")`, then requests the actual
owned target-catalog-v2 API for its existing two campaigns and their children.
It returns the unchanged creative fixture, a deep-copied new input request, and the
complete API target records. No seeded plan, proof, selector, or generated output.

The new request excludes campaign 5 (A), fixes campaign 7 (B) at USD 200, preserves
the USD 1,000 confirmed goal and one-asset global capacity, and explicitly supplies
“No discount claims.” alongside the existing health/testimonial restriction in
this new product input. A separate parameter adds that same restriction to global
constraints: the expected current behavior there is explicit creative deferral,
not a useful proposal or complete Q10 acceptance. No constraint is moved or removed.

Assertions inspect canonical target identities and full owned provider parentage
on actions, briefs, proposals and allocations. Excluded A and its children may
remain in immutable source evidence; they must not become actionable outputs.
B is counted once per independent alternative, no native edit/forecast is produced,
and any produced brief must retain the exact restrictions and observed image basis.
Actual generation, current read, export and exact generation replay preserve the
document; read-only native-call counts do not increase after generation. Financial
and execution row counts remain zero. Both supported fixture databases are intended.

No tests execute until the Q07 lane releases the slot. No production edits, provider
calls, remote activity, default-policy changes or human-expert qualification.
