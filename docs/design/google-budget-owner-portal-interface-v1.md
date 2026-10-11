# Private Q06 Owner Review Portal: Proposed Consumer Interface

Design only, inspected rootbeccf61 and reviewed V6 document contractdee53c4.
No UI code, browser/API tests, live reads or default policy change. API generation
implementation must freeze before dependent UI implementation/qualification.

## Existing Application And Missing Join

The existing `/app/planning` flow owns original-session fences, capability lookup,
account/window choice, target reads, alternatives, exact idempotent mutations,
current/version/export views and manual decision history. Reuse it. The owner
receipt endpoint already exists at
`POST /api/customer/v1/workspaces/{wid}/planning/google-budget-owners`; it accepts
account_id, catalog_composite_digest and reporting_window, returns no-store
GoogleBudgetOwnersViewV1 with named full member TargetRefs, observed amount/currency,
opaque selection and observation/facts commitments, expiry and unavailable recovery.
It performs receipt lookup, not a new provider acquisition.

Current `plan-capability.mjs` recognizes only exact V1–V5 pairs and returns creative
only forV5. Current `planning.mjs.inputs()` emits creative/selected inputs and
scenario selectors but no Google owner hypotheses. `plan-document.mjs` has generic
actions/creative rendering, not an owner-proof panel. Thus a configured V6 service
is not usable through the portal today; this is missing frontend integration,
not a provider credential issue.

## Minimal File And Capability Delta

- Extend the exact capability pair parser only after server V6 capability freezes.
  Derive `{selected:true,creative:true,ownerReview:true}` for exactV6; existing pairs
  retain their current flags, and unknown/mixed pairs refuse. Browser cannot choose
  policy/version. DefaultV3 remains untouched.
- Add a small `plan-google-owner-inputs.mjs` component inside the existing editor,
  host `google-owner-inputs`; wire lifecycle in `planning.mjs`. Keep existing
  target/scenario editors. No second app, public webpage or Squarespace changes.
- Add owner proof rendering in a separate `plan-google-owner-review.mjs` called
  from `plan-document.mjs`; current and historical display share the same literal
  renderer and exact saved document. Existing public/legacy bytes remain unchanged.
- No backend field additions assumed beyond the reviewed V6 contracts. Any needed
  capability/response change must be frozen with the API author first.

## Editor State And Discovery

Once actual target catalogs are loaded, a user explicitly chooses **Review Shared
Google Budget** for an included Google account. POST the exact displayed original
catalog digest and primary reporting window through the existing guarded API
wrapper. Recheck turn/session/workspace/account/window after await before rendering.
Never construct a receipt, derive a selector in JS, or search other catalogs.

Show each returned group using server-provided campaign names and its complete
member list (up to200). Names are literal text; identity remains the full server
TargetRef/opaque option, never a name match. Do not truncate or hide omitted members;
an inaccessible/oversized response is unavailable, not partial approval. Provider
IDs/digests are internal comparison values, not customer-entered identifiers.

Selecting a group requires choosing exactly one existing named customer alternative
containing one allocation to an eligible member. Show other affected members and
warn that campaign allocations are planning amounts, not independent native budget
settings. Allow at most one hypothesis per account/owner across alternatives;
independent owners remain separate. Check exclusions and affected children using
available full catalog relationships for prompt feedback, with server validation
authoritative. Unknown relationships must not be guessed independent.

Controls: **Observed Daily Setting** (read-only exact currency/amount),
**Requested Daily Setting** (editable, nonnegative, no more than observed),
**Customer Alternative**, **Include This Review**, **Remove This Review**.
Use existing exact decimal-to-micros parsing extended/reused only if it preserves
six fractional digits and rejects exponent/overflow/extra precision. Never derive
a daily amount from the monthly/period allocation. Zero ceiling permits only zero
request; still no implication that a zero native setting is provider-valid.

Proposed component handle: `readIntent()`, `setBusy(bool)`, `clear()`.
Inputs provided by caller: verified capability, current account catalogs, scenario
intent snapshot, confirmed currency/ceiling and guarded discovery callback. Returned
intent is the exact reviewed GoogleDailyBudgetIntentV1 primitive, including opaque
selection and expected observation/facts digests. Server fills resolved fields.
Do not submit owner_key, source digest or representative as browser authority.
Scenario edits notify the component; missing/renamed alternatives clear the binding
and require explicit reselection, never silently move a hypothesis to another one.

## Absent, Empty, Edit And Replay Semantics

For V1–V5 omit `google_daily_budget_intents` entirely. For verified V6 always submit
the explicit tuple/list, including `[]` when the customer chooses no owner reviews.
Do not treat `[]` as absent, silently upgrade a V5 saved input, or strip a populated
field to force generation. Display the server's mode/refusal if a stored input is
incompatible with currently configured capability; owner removal is an explicit
customer edit under current revision CAS, never automatic recovery.

On editing V6 retain original saved requested amount/scenario and identifiers for
display without normalizing untouched values. A saved option not in fresh discovery
remains visibly historical; it cannot be quietly replaced. New save/revise requires
current original-receipt validation and selection where the server requires it.
Expired/replaced target receipt clears current submission readiness, not saved
history. Refresh targets through the existing explicit replacement flow, rediscover
owners, then ask the customer to confirm new group/amount/scenario. Do not match
old/new selections by campaign display names or restamp original observations.

Existing stable request key/payload handles unknown save/generate outcomes. First
recover/replay the exact request; do not issue a fresh key or discard pending owner
fields on a timeout. Changed payload requires the existing explicit revision path.
Session cookie/actor changes clear current discovery/editor state and pending
owned choices through established origin fences; never reuse options across sessions.

## Customer Copy And Generated/History Rendering

Persistent editor notice:
“Daily Settings And Plan Allocations Are Different. This is a request to review an
observed Google setting. A daily setting does not guarantee total spending within
your confirmed plan ceiling. Inlet will not apply this change.”

Generated panel uses exact `google_budget_owner_review` plus retained input catalog
proof, not an independent interpretation of current discovery. Display original
observed/requested amounts with currency and **Per Day**, full affected campaigns,
chosen alternative, observation time and current/history state. Preserve the period
ceiling and independent alternative allocations in their existing panels.
Positive requests, including reductions, remain **Review Required — Not Qualified
Against The Period Ceiling**. Zero remains **Manual Review Required**, not supported
execution or guaranteed zero exposure. All corresponding actions are investigate
only: no NativeBudget/proposed fields, no Apply/Publish/transfer button. Existing
accept/report controls, if applicable, retain manual descriptive meanings and cannot
be relabeled provider execution. Show the composer’s exact recovery steps literally.

For partial owner coverage show “Shared Budget Review Unavailable. Read fresh
targets and review the full affected campaigns.” Keep ordinary campaign planning
available where supported; never infer missing native membership from names or
complete metadata. No-rights/no-visual-assessment and existing creative copy remain.

## Recovery Matrix And Qualification

- available+complete: editable hypothesis, explicit inclusion; still no execution.
- unavailable response: recovery above, no owner submit; do not present as no owners.
-401/session replacement: clear owned state, explicit sign-in/session refresh.
-402/403: existing billing/access recovery; no data/role bypass.
-409 source/receipt/CAS/expiry: retain saved historical display, disable stale draft
  submission, refresh/reselect explicitly; distinguish pending idempotent recovery.
-422 input conflict/constraint/currency/ceiling: display bounded server validation,
  preserve typed values, no auto-adjusting amounts/scenario/reserve.
-unknown network result: exact replay/recovery; no optimistic success.

After API freeze, component tests must preserve V1–V5 request bytes, V6 absent/empty
matrix, exact micros, out-of-list saved selections, complete member rendering,
scenario/exclusion changes, safe malicious names, session switch, expiry and error
recovery. Actual local TLS/API tests then drive the real discovery endpoint and
create/revise/generate/current/history/export, including A/B shared versus C
independent, partial membership, changed receipt and lost-response replay on both
DBs. No fake frontend API or preconstructed proof. A private injected V6 service
and actual MockHTTP native catalogs are qualification configuration, not live enablement.

No new architecture or owner product decision is required for this manual review
UI. Positive native-setting economic qualification remains a concrete engineering
and provider-guarantee gap, not permission to weaken the ceiling.
