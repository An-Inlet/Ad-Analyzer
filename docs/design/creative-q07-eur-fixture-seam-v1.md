# Q07 local EUR seam — review before implementation

Add only `tests/creative_q07_fixture.py`; do not change the Q05 helper/defaults.
The public helper will be:

`add_owned_eur_target(engine, q05: CreativeQ05Basis, patch) -> OwnedEurTarget`

Frozen result fields: `account_id: int`, `selector: dict[str, Any]`,
`catalog: dict[str, Any]`, `native_calls: list[tuple[str, str]]`.
The catalog is the real customer endpoint JSON retained only inside the test.
No returned field is a fabricated receipt or authority callback.

Create a separate Meta WorkspaceIntegration/AdvertisingAccount/MetaConnection in
Q05's existing workspace using its existing synthetic MetaVault key and app secret.
Distinct fixture external account124 (not existing123), unique integration key,
EUR currency, America/New_York timezone, original owner/session unchanged. Seal
an ordinary synthetic grant through MetaVault. Do not reset keys or mutate any
existing account/source/catalog. This is declared owned-source bootstrap only.

Capture the current Q05 diagnostic transport factory before wrapping it. The new
MockTransport handles only GET graph.facebook.com `/v26.0/act_124` and its exact
campaigns/adsets read endpoints, including the existing metadata-name requests.
Responses follow the existing MetaServer schemas: account124/EUR/New_York;
campaign15/account124; adset16/account124/campaign15. Names are fixture labels.
No write method accepted. All other requests delegate unchanged to the captured
Q05 factory (which already rejects unknown hosts and unsafe methods). No request
URL or owner is rewritten to trick an existing123 server into accepting124.

Call the actual target-catalog-v2 endpoint under Q05's original session and exact
primary reporting window. Assert200, native observation workspace/account,
returned currencyEUR, exact owned campaign15, and nonempty real receipt/selector
bindings. Independently load the owned account to assert EUR/124/current linkage.
The ensuing create body includes the EUR local account in account_ids and uses
its actual selector. Keep USD goal/product and the other selected targets fixed;
replace one allocation rather than increase total. Amounts still total1000USD.

To establish currency-specific refusal, require the actual rejection's fixed
currency error or validation location/message (bounded, no payload dump), plus
positive ownership/current receipt assertions and unchanged persisted plan graph.
Do not accept an arbitrary409/422 as currency proof. If acquisition rejects before
issuing a selector, or another gate fires first, preserve that evidence and stop
for review; do not manufacture a receipt or bypass the boundary.

No implementation, database changes, tests or provider calls were performed for
this seam proposal. Later arithmetic/goal-revision tests remain as specified in
the approved Q07 interface; this seam does not change shared Q05 behavior.
