# TikTok Native Discovery Parser V1

This package implements pure response projection from the supplied [rendered official
tables](tiktok-rendered-response-contract-20261007.md). Tests contain synthetic
examples; none is an advertiser response or a qualification fixture.

## Frozen Interface

`app.collectors.tiktok_discovery_contracts` defines immutable strict versioned
`TikTokIdentityPageRequestV1`, `TikTokPixelPageRequestV1`, and corresponding
`TikTokIdentityPageV1` / `TikTokPixelPageV1` results.

`app.collectors.tiktok_discovery_parser` exposes:

- `parse_identity_page(request: TikTokIdentityPageRequestV1, payload: object) -> TikTokIdentityPageV1`
- `parse_pixel_page(request: TikTokPixelPageRequestV1, payload: object) -> TikTokPixelPageV1`

Both raise sanitized `TikTokDiscoveryParseError` on malformed projected fields,
non-success envelopes, mismatched pagination, duplicate known IDs or contradictory
known ownership facts. They perform no IO and do not mutate inputs. Requests require
explicit page/size and identity type; BC identities require the exact BC scope.

Every result fixes `publication_eligibility=not_assessed`, `spending_authority=none`,
`collection_completeness=page_only`, and `pagination_consistency=unverified`. Page
metadata is a reported observation, not a validated complete inventory. A future
collector must validate total-count consistency, cross-page uniqueness, scope and
bounded traversal before claiming completeness. No collector is implemented here.

## Preserved Uncertainty

`ObservedFieldV1` distinguishes absent, explicit null and present values, separately
from applicability and enum recognition. Unknown enum strings remain verbatim and
unrecognized. Status applicability is known only for documented identity types;
CUSTOMIZED_USER availability does not become linked-account eligibility. Existing
CUSTOMIZED_USER publication/catalog contracts and their serialized bytes are untouched.

The rendered-table transcription does not establish exact scalar type columns for
pixel/event IDs. `ObservedIdV1` conservatively preserves strict string or strict
integer (no boolean/coercion), marked `scalar_shape_qualification=unverified` on
both observations and pixel result. This is an engineering observation union, **not**
a claim that documentation supports both. It must not be normalized into publisher
IDs until authoritative type evidence resolves that gap. Engineering bounds are
128 characters or unsigned 64-bit integers; oversize shapes fail closed.

Events preserve `deprecated` as strict observed boolean. `optimization_event` is
returned verbatim only; it is never derived from name, code, ID or type. PAGE_VIEW
with a nonnull optimization event is contradictory. Missing/null/empty events all
leave tracking readiness unknown; the documented delayed event refresh prevents an
absence inference. No readiness enum is invented from an activity-status example.

Unused pixel scripts, matching configuration, username/profile images, rules,
create times and monetary values are discarded. Optional strings are bounded to
512 characters; empty strings are preserved rather than silently converted to
absence. Per-page item bounds follow request limits; an engineering cap of 1,000
projected events per pixel rejects oversized input. Known ownership contradictions
reject; missing relation/ownership/BC fields remain unknown, never inferred.

## Validation And Remaining Work

Parser and existing TikTok runtime/social publication contract tests: **100 passed**.
The parser's synthetic cases cover absence/null/false, linked applicability, deprecated
events, unknown enums, strict ID shapes, page metadata/mismatch, duplicates, sanitizer,
privacy projection and JSON roundtrip. Existing runtime/publication contracts remain
unchanged. Whole-repository Ruff and configured mypy results are recorded in the ledger.

Not implemented by this package: native HTTP discovery, pagination aggregation,
owned source/generation/session binding, linked-identity publication contracts,
account eligibility, financial qualification or any live activation. Those require
separate reviewed work. No schema, runtime factory, route or publication gate changed.
