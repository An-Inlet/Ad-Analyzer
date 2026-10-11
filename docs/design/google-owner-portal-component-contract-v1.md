# V6 Owner Review Component Boundary

UI child of 5a9008d; default V3 and exact V1–V5 capability objects remain unchanged.
Host is exactly `#google-owner-inputs`; generated proof is `#google-owner-review`.

`renderGoogleOwnerInputs(host, {capability, workspaceId, saved, context, discover,
current})` returns `readIntents()`, `setBusy(bool)`, `clear()`, and
`invalidateChoices()`.

- `saved` is null or the ordered saved `inputs.google_daily_budget_intents` array
  of **ResolvedGoogleDailyBudgetIntentV1** objects. Component retains their full
  historical display metadata but projects request fields through an explicit
  GoogleDailyBudgetIntentV1 allowlist; server-only owner_key,
  representative_canonical_key, observed_amount_micros and source_binding_digest
  never enter a request. Original primitive values and order remain unchanged.
  Saved entries initially display historical/unready. All historical entries must
  be explicitly removed before adding fresh hypotheses; no receipt/generation
  remapping or implicit revalidation. Live duplicate checks use full AccountRef
  plus stable budget_owner_key, never names or option ordinals.
- `context()` returns `{catalogs:[{account,catalog}], reportingWindow, currency,
  totalCeilingMicros, scenarios, exclusions}`. Scenarios are the exact validated
  `scenarioHandle.readIntent()` result; incomplete alternatives throw, not defaults.
  Catalogs are original target-reader responses, not browser-derived evidence.
- `discover(request)` accepts exactly `{account_id,catalog_composite_digest,
  reporting_window}`. The caller performs the existing guarded same-origin API
  POST and original-session recheck, and rejects any uncompleted guarded operation.
- `current()` throws on editor/session/workspace invalidation. The component also
  checks its own mounted token, monotonically increasing discovery generation,
  and exact context snapshot before and after each async discovery. A changed
  context cannot revive through ABA, because event handlers increment generation.
- `invalidateChoices()` increments generation, clears discovered options and marks
  included selections historical/unready while preserving their original ordered
  values for visible removal. No automatic empty conversion or reattachment.
  Goal/account/window/target refresh/expiry and alternative/target exclusion changes
  call it synchronously. New discovery does not silently validate old inclusions.
- `clear()` permanently revokes this handle and empties/hides the host, including
  saved entries; editor/session teardown calls it. New mounting creates new state.
- `readIntents()` returns undefined for legacy capability; V6 returns the ordered
  explicit array, including `[]`, or throws for any unresolved historical entry.
  Removal is explicit. Inclusion appends once, at most20, one full account/owner.
- `setBusy` disables all component controls while the parent operation is active.

Data roles: owner-discover, owner-option, owner-scenario, owner-requested,
owner-include, owner-remove, owner-status, owner-members. Per-account/entry
`data-index` values are local ordinals only. Option values are local ordinals;
scenario option values are existing scenario keys. Every label uses textContent.

`appendGoogleOwnerReview(fragment, plan)` reads only the saved owner proof and
linked input catalogs; no discovery or provider IO. Six-decimal daily amounts,
all affected member names, original observation, alternative and investigate-only
limitations remain distinct from period planning allocations.

Browser lane owns fixtures/observer/TLS tests. Its customer actions must read fresh
catalogs/discovery and enter alternatives/hypotheses; fixture bodies are not posted
behind the browser. Partial unavailable discovery never becomes a selectable owner.

## Legacy Edit Compatibility

The actual planning controller checks edit compatibility immediately after the
verified capability and before media reads or editor population. Editing null or
omitted saved owner inputs under V6 refuses with read-history/create-new guidance;
it never silently converts legacy input mode to an explicit V6 empty list. V5
under V5, explicit V6 `[]` under V6, and new V6 plans remain available. The separate
controlled-Fetch Chromium controller test verifies this actual call-site behavior;
it does not claim authenticated API qualification.
