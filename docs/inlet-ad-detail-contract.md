# Shared Advertising Detail — B10 And B11

Common daily metrics now support campaign, ad group, ad set, ad, keyword and query
grains. Ad metrics have exactly one ad-group/ad-set parent, a matching campaign and
platform, and no keyword/query fields. Compound database foreign keys enforce the
whole parent chain. Existing campaign totals stay campaign-only; parent and child
observations must never be added together. Duplicate source rows are idempotent;
conflicting duplicates reject the complete window.

Meta detail collection is a bounded separate read extension: current ad/creative
identity metadata, ad-set daily insights and ad daily insights. It collects all pages
before publishing child metrics in one nested transaction. Throttling, cursor cycles,
unknown parents, account/currency mismatch or incomplete windows preserve existing
published metrics. It does not disturb the existing campaign collector. The explicit
sync entrypoint requires `AD_ANALYZER_META_DETAIL_ENABLED=true` and existing sync
controls; default is false, and no existing schedule automatically invokes it.

Customer reporting is scoped through current customer membership, the native Meta
connection and active integration. It compares each grain's spend separately and
returns unavailable when a grain is absent. Equality is a reconciliation check, not a
forced adjustment; differing provider totals remain visible. Ad states include current
creative ID/name. Historical creative performance is explicitly unavailable: today's
creative association does not prove which creative served an older metric window.
No remote media is fetched, and no customer-profile or targeting data is introduced.

Migration0029 preserves existing rows while adding ad metadata, optional metric parent
columns and constraints. Its downgrade removes newly supported child-grain metrics
before restoring the old CHECK; run only on explicitly disposable databases during
validation. Production reversal requires a reviewed preservation/export plan.

The official Meta docs endpoint returned HTTP429 during preparation. Field/level shapes
were checked against Meta's generated SDK source instead:
[Insights](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adsinsights.py),
[Ad](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/ad.py).
No live API response or provider permission was verified. All acceptance used fixtures.

Next adapters should reuse `DailyMetricCreate` and scoped repository methods, not weaken
parent constraints or fold ad-level facts into campaign totals. TikTok adds platform
support separately; it can use ad-group/ad parent chains. Publication/media authoring
and provable historical creative attribution remain later work.
