# Linked TikTok Contract Increment

Base: `7ca9f9305df9ad8eac08e2ceba4e6d0d8cd54a18`, 2026-10-07.
Source field evidence was supplied from the parent's rendered official tables:
[Create Ads](https://business-api.tiktok.com/portal/docs/create-ads/v1.3),
[Get Ads](https://business-api.tiktok.com/portal/docs/get-ads/v1.3),
[Identity Info](https://business-api.tiktok.com/portal/docs/get-info-about-an-identity/v1.3),
[Create Spark Ads](https://business-api.tiktok.com/portal/docs/create-spark-ads/v1.3),
[Advertiser Details](https://business-api.tiktok.com/portal/docs/get-ad-account-details/v1.3),
and [Spark Ads](https://ads.tiktok.com/resources/help/article/spark-ads?lang=en).
This increment introduces normalized strict types only, not an HTTP envelope decoder,
financial qualifier, API input, coordinator variant or enabled publication route.

## Frozen Module And Types

`app.publication.tiktok_linked_contracts` contains:

- `LinkedOwnerV1`: primitive immutable workspace/account/connection/external advertiser/
  connection-version scope. Consumers resolve it from actual owned context.
- `TikTokUserIdentityV1` and `TikTokBusinessIdentityV1`, discriminated as
  `LinkedIdentityV1`. BC ID is mandatory only on BC_AUTH_TT. AUTH_CODE and
  CUSTOMIZED_USER cannot be supplied.
- `ObservedBooleanV1`: explicit absent/null/present, strict boolean value; no coercion.
- `IdentityInfoRequestV1`, `IdentityInfoObservationV1`: owned exact identity and bounded
  interval, status, GPPPA, push/pull and BC-only ads-only observations. No usernames,
  image URLs or generic raw response retained.
- `AdvertiserCapabilitiesRequestV1`, `AdvertiserCapabilitiesObservationV1`: exact special
  field set `(ads_only_mode, can_use_custom_identity)` with no ordinary profile fields.
  Readers must separately prove response advertiser binding. Records are not proof
  simply because they parse and are never accepted from customer JSON.
- `LinkedPushCreativeV1`: server-resolved library video, exactly one cover, required
  reviewed copy, media-review commitment and explicit new-linked-post acknowledgement.
- `LinkedPullCreativeV1`: exact server-owned post commitment, inherited-copy and
  existing-post visibility acknowledgements; forbids video ID, cover and replacement
  ad_text. `LinkedCreativeV1` is the route-discriminated union.

Both creative variants explicitly require SINGLE_VIDEO, DISABLE, ads-only ON,
Creative Center display consent false, SHOP_NOW, HTTPS destination, and a separate
commercial-music-rights review commitment. Creative Center consent is never identity
or post authority. No defaults silently grant these acknowledgements. This is a
bounded supported profile, not the entire TikTok API: OFF, ID-precedence CTA,
Reach/Frequency, specialized shopping creative_type and AUTH_CODE are excluded.
Text supports a conservative non-symbol subset, rejects emoji/control characters,
and weights Chinese/Japanese ad copy twice toward100; names have their distinct512
character bound. The stricter supported subset is not claimed as the whole API rule.
Resolved IDs/media digests are server inputs from original archive/owned bindings;
they are not a new raw-ID customer form. Aspect-ratio equality belongs to the prior
private-media/cover review and must be rechecked by the compiler, not inferred here.

## Next Coherent Implementation Boundaries

1. Actual owned identity/info + special advertiser-info readers, bounded HTTP, exact
   response owner/identity/BC matching and original-session/source checks before/after
   IO. Need exact advertiser response envelope from rendered table; never reuse the
   ordinary advertiser profile decoder. No locks across HTTP.
2. Versioned linked configuration/review, compiler, plan/request union and separate
   serializer/readback branch. Parent table proves all creative keys nest inside
   `creatives`; exactly one ad per immutable attempt is Inlet's narrower bound. Push
   post ID is optional before ad review; Pull expects exact post and null video.
   No ENABLE default, synthetic authorization, or invented post mutation.
3. A named pure obsolete-route predicate applies to NEW legacy CUSTOMIZED_USER
   TikTok-placement creation at prepare/approve/admit/claim/final emission. It must
   not enter generic historical parsing/reconciliation/settlement paths. Original
   holds and existing campaign optimization survive; historical activation is not
   blanket blocked by a new-ad rule.
4. Versioned runtime/profile and strict export union registration, then named customer
   choice/review UI and ordinary configured API/HTTPS bothDB. Old v1 hashes unchanged;
   explicit mocked scenario only, no financial promotion/default source/live enable.

Pull's creation/readback rules are known. Its actual owned post discovery producer
still needs the exact identity/video/get envelope, list/pagination and visibility
fields; this is a narrow remaining decoder gap, not a blocker to Push implementation.
BC publishing permission requires actual owned BC authority; can_push_video alone
must not fabricate it. Current BC discovery UI remains unavailable until that owned
lookup is implemented.

## Validation

19 focused pure cases pass: strict booleans, wrong route/identity/BC/fields, text
bounds, exact cover cardinality, HTTPS credentials, explicit rights and status,
immutable JSON roundtrips and absence-vs-false. Scoped mypy2 files and Ruff pass.
No legacy class was edited, no new schema/table or runtime setting was introduced,
and no provider call or live publication was performed.
