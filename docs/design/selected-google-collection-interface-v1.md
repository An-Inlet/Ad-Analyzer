# Selected Google Collection Interface V1

`collect_google_selected_capture(request, campaign_mapping, read_page, revalidate,
clock)` collects one bounded complete capture using the existing selected DTOs and
Google page reader. All dependencies and native/local campaign mapping are loaded
by the owned customer service. DTO construction does not establish authorization.

The collector snapshots the mapping and revalidates before/after every page and
before returning. It binds empty and nonempty pages to the exact request, rejects
cursor cycles and duplicate campaign/day rows across pages, and enforces the existing
100-page, 50,000-fact and 32MiB canonical bounds. A single operation is limited to
60 seconds from request start, with monotonic and UTC checks after callbacks. A
blocked underlying call can consume its transport timeout before control returns.

Partial pages remain only in process memory and are discarded on failure. No new
durable staging or resumable job authority is introduced. Terminal empty pagination
is a complete empty capture, never zero observations. `supported` means the explicit
adapter's selected profile was used, not that live provider compatibility was proved.
TikTok has no analogous selected collector until its mapping is qualified.

The caller must reauthorize the original session and exact selection, aggregate,
source and privacy under locks before atomic `store_selected_capture` and commit.
Collection itself neither writes SQL nor grants background continuation, advertising
writes or spending. Wider requested dates must already be covered by genuinely
acquired aggregate provenance; this collector cannot relabel a seven-day completion.
