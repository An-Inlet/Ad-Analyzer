# Q14 Unknown Parent Customer Flow — Bounded Acceptance

Baseline `d65df67`, local only. Frozen Q14 still lacks an assembled unknown-parent
customer journey. Existing parser and pure child-join checks do not establish the
customer result. No social reporting semantics, owner decisions or live calls are
needed for this existing target-catalog contract.

## Interface And Acceptance

Add a separate test-only MockHTTP scenario with ordered phases `original -> orphan
-> recovered`. Existing disappearance fixture is unchanged. Actual native readers,
metadata projection, receipt persistence, customer API, portal, generation, history
and exports remain production implementations. Never synthesize a catalog or plan.

Original inventory contains one campaign and child. The Google fixture supplies an
actual metadata ad-group response where the older common fixture supplies none.
Social fixtures retain their actual child IDs. Both display names are unchanged.
In orphan phase the child's parent becomes ID9, absent from the returned campaigns.
Google rejects metadata topology; social native collectors reject missing parents.
These are separate existing validation layers, not identical provider guarantees.
Recovered phase returns campaign9 and that child with parent9. This is synthetic
read evidence, not a claim that providers support reparenting an existing child.

1. Sign in, read owned targets, select the exact child, save and generate V1 through
   real browser controls. Retain actual document/export and selectors.
2. Edit and explicitly reread orphan inventory. Require real HTTP409, generic fixed
   diagnostics API error and existing safe portal 409 message, no target controls and no new receipt or partial planning graph.
   Save cannot submit old choices or an empty implicit replacement, even if the
   customer checks replacement confirmation. Cancel restores the saved view.
3. V1/current/history/export remain byte/digest exact. A failed fresh read never
   retroactively invalidates valid original as-of evidence. No guessed parent/name
   fallback, silently repaired catalog or provider-verification claim.
4. Explicit recovered read must return parent9 and the same child ID/name/account/
   advertiser. Child canonical identity stays stable; its snapshot selection changes.
   Original fixed choice is not prefilled. Save before replacement confirmation is
   refused locally. Explicit child choice and confirmation save revision2, then V2.
5. V2 carries the new parent and exact fresh selector, references V1's digest, while
   original historical/exported documents and digests remain unchanged. Export response
   wrappers truthfully change to current input revision2 and input_changed freshness;
   wrappers are not immutable document artifacts. Generation makes no provider rereads.
   Exact plan/input/version/receipt/event counts and zero execution attempts hold.

The new driver retains full original/recovered catalogs and generated/export payloads
for independent digest checks. No fabricated selected conversions or attribution.
No production edits are planned unless a concrete failing assertion exposes a defect.
No new schema, route, authority, retention or private-policy activation.

## Qualification

Six new actual TLS cases: Google/Meta/TikTok × SQLite/PostgreSQL. Six existing
three-provider disappearance TLS cases preserve the shared harness branches.
Whole Ruff, configured no-path mypy, new driver syntax and exact collection before
execution. One heavy slot, frozen source bytes, original exits/XML, bounded cleanup,
resource floors and stop-first-failure. SQLite gate precedes PostgreSQL; no broad
aggregate rerun. Independent design/source and final evidence review required.

This package only closes this mechanical Q14 topology join. Unsupported independent
manual verification, human usefulness, live provider verification and full Q14/Q13
acceptance remain open. All remote/live/release holds stay in force.
