# Review Finding Resolution At Verified PR73 Head

Head `7b7ab2963b79e23d99f945dc83624da6584cab93`, basePR72
`4d1506ac60f4f68556383c709755fc4d3067a0c4`. Full local914passed+6PowerShell skips;
CI37398286003 all gates passed,920tests/zero skips. CI checked merge
`73fa85711a7c98bef8c8362a3ace8c686063e532`; its tree equals head tree.
All named regressions below are in `tests/test_inlet_review_regressions.py`.

| Review finding | Repair and regression evidence |
|---|---|
| Rejected claims roll back validated spend observation | `test_rejected_api_claim_preserves_highwater_without_reservation`: real API/session-close sequence persists50/110 observations under cap100; later10 cannot lower highwater, no reservation/fence allocated. |
| OAuth callback access logs expose code/state | `test_actual_uvicorn_access_capture_excludes_oauth_queries_preserves_normal_events`: actual uvicorn logger/handler capture for Google/TikTok/Klaviyo/Shopify/Meta; ordinaryhealth remains. Logger disabled flag isolated after migration tests. |
| Generic drafts mislabel executable Google payload/accounting | `test_generic_persisted_draft_cannot_mislabel_google_operation`: kind/exposure/resource/positive-change identity binds before provider apply. |
| Stale executor session overwrites prior reservation | `test_stale_executor_session_cannot_overwrite_existing_reservation`: two sessions/two campaigns cannot turn60+60 into an under100 claim;60 reservation and one apply retained. |
| Google1000-row cap rejects documented pages | `test_google_sdk_documented_page_size_keeps_cursor_and_rows`:1001/10000-row mocked SDK pages with cursor continuation and identical retries. Total-window bounds retained. |
| Rejected source page starves healthy tenants | `test_tiktok_rejected_page_backs_off_without_starving_next_connection`: batch1/default20, wrong account, repeatedcursor and failedpublication backoff permit healthy tenant progress. |
| Prior transient marker preserves invalid TikTok staging forever | `test_tiktok_prior_read_failure_does_not_preserve_rejected_staging`: transientfailure→successfulpartialpage→cursorconflict. Current typed exception decides preservation; bad staging/cursor clears, published data unaffected. |
| Klaviyo list suppression treated as global unsubscribe | `test_klaviyo_list_suppression_is_not_global_unsubscribe`: subscribed consent and list suppression remain distinct without storinglistIDs. |
| Unknown checkout expires before ID recovery | `test_uncertain_expired_checkout_is_recovered_before_attempt_retirement`: timeoutaftercreation, recoveredID retained during lookup outage; only canonical expired/no-subscription permits newkey. PR76 extends to null URL. |
| URL expiry creates second purchase before delayed completion | `test_completed_checkout_without_webhook_cannot_issue_second_purchase` plus scheduler regression: completed session adopts subscription instead of issuing another purchase. |
| Replacement purchase cannot adopt new subscription | `test_repurchase_requires_terminal_old_subscription_and_owned_completed_session`: current old terminal proof and owned completed-checkout lineage required before replacement entitlement. |
| Replacement lookup outage bypasses event backoff | `test_replacement_lookup_failure_backs_off_before_dispatch_limit`: two limit-one ticks at same time let healthy event behindfailedlookup complete. |

Outstanding code is tracked separately from live gates in `inlet-acceptance-matrix.md`.
PR76 adds real Stripe HTTP code but older-than-retention unknown attempts still fail
closed pending recovery workflow. Billing-management branch adds old terminal-event
acknowledgment/currentpurchase preservation. Provider revocation/renewal, detailed
Meta performance, actual optionalCRM transports, complete customer journeys,
publication, scheduler qualification and live acceptance remain unfinished.
