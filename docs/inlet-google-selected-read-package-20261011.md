# Injected Google Selected Read Package — 2026-10-11

Implemented `GoogleSelectedHTTPRead`, an explicit injectable reader with no default
factory or public route. It uses only Google Ads search POSTs: exact advertiser
currency/timezone metadata, exact conversion-action owner/resource, then selected
campaign/day metrics. Requests are bound to the frozen selection/profile/dates;
original bytes feed the exact parser. It retains empty-page request provenance and
never infers a zero or selected event from aggregate totals.

The server supplies excluded-secret context plus a mandatory revalidation callback.
That callback runs before/after I/O; time checks bracket it so a slow callback cannot
admit an expired query or return. Streaming checks deadline on each chunk, with
bounded response sizes and transport timeouts; redirects and environment proxies
are disabled. A blocked transport read may still consume its phase timeout, so this
is not hard wall-clock cancellation. Mapping is copied before I/O. No credentials
were provisioned or used; deterministic tests use clearly synthetic placeholders.

Independent review found two P2 deadline gaps (callback expiry and trickling body),
then closed both repairs with no remaining P1/P2 in the injected-reader scope.
Reviewer did not rerun tests. Source/session ownership remains the future server
resolver/calling service obligation; no public caller may supply that authority.

Checks actually run:

- Initial MockHTTP+raw cohort81passed,0.59s.
- Final `pytest tests/test_google_selected_http.py tests/test_selected_raw_observations.py -ra`: **84passed,0skips,0.63s** (20HTTPcases +64rawcases).
- `ruff check .`: passed.
- `mypy --cache-dir /tmp/inlet-selected-mypy app tests`: passed,1280files.
  Initial negative-test mock callback typing error retained and repaired.
- `git diff --check`: passed before commit.

Evidence: `/workspace/inlet-evidence/20261011/google-selected-http/` includes
first/finalJUnit+logs, finalstaticchecks and retained initialRuff/mypy findings.
No HTTP request contacted a provider; all used MockTransport. No aggregate rerun.

## Explicit Remaining Limits

This is not source-job staging/publication, an owned context resolver, event-option
catalog, customer event confirmation or actual plan wiring. The parser/query profile
is pinnedv24; existing publication catalog usesv25 and a narrower WEBPAGE/PURCHASE
policy and cannot be reused as reporting authority. Exact configured-version/provider
query compatibility remains unverified, as do live zero-report semantics. Manager-
owned action support stays unavailable pending its own verified relationship.
TikTok selected-event support remains explicitly unsupported. Requested August/
September provenance still requires actual immutable range imports.

Durable selected storage/lifecycle implementation is under separate review. No
advertising mutation, spend authority, website work, live call, push, hosted retry,
merge or deployment. Q01–Q16 and six human review gates remain open as documented.
