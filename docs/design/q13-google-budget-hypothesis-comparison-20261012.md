# Google Daily Budget Hypothesis Comparison

This is a pure Q13 prerequisite, without a reader, writer, event, route or activation.
The existing V6 owner review retains an explicitly requested daily amount. Its action
is an investigation, with no supported ProposedField. Compare only that hypothesis
against a later retained setting. Do not widen native_budget or ReadObservedStatus.

## Read Semantics And Extraction

Reviewed 2026-10-12 against the versioned Google Ads API v22 references:

- [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v22/CampaignBudget):
  amount_micros is the average daily budget in account currency, at one million micros
  per currency unit, for DAILY period; total_amount_micros is mutually exclusive.
  The immutable budget resource identifies the shared owner. explicitly_shared describes
  sharing intent; reference_count reports campaigns using the budget.
- [Campaign](https://developers.google.com/google-ads/api/reference/rpc/v22/Campaign):
  campaign_budget names that campaign's budget resource.
- [Customer](https://developers.google.com/google-ads/api/reference/rpc/v22/Customer):
  currency_code is the account's immutable operating currency.

This documents one version's field semantics, not compatibility of an arbitrary
configured API version. No live account was read. Existing diagnostics acquisition
does not retain the API version or an authenticated raw transcript in CatalogEvidence;
those remain exact prerequisites for a future qualified production reader.

Use existing derive_google_daily_budget_owner on the complete retained catalog:
the native settings' budget_amount_micros is an exact nonnegative integer with no
rounding or FX conversion. Require DAILY, STANDARD, ENABLED, explicitly shared true,
no total amount, two through 200 nonremoved ENABLED/PAUSED campaign members, agreement
of every repeated owner setting, complete native/metadata campaign coverage and exact
reference count. These are conservative local eligibility rules. The provider's phrase
"actively using" does not independently prove a simultaneous nonremoved membership
snapshot. Missing/defaulted sharing or count cannot pass this profile; missing amount,
unknown status, partial coverage or inconsistent joins cannot become zero/matching.
The catalog retains normalized rows and opaque source commitments, not raw provider
provenance. Existing collection is nonatomic. Preserve those limitations.

## Pure Packet And Admission

Retain the exact original PlanVersion, VersionBinding, comparison time, current privacy
revision and source binding, an explicit integrity state (clear or invalidated), and an
optional fresh GoogleDailyBudgetOwnerWitnessV1. Full original plan retains the original
review intent, catalog and action. Full fresh witness retains the new normalized proof.
Revalidate the complete packet on construction and serialization; bound its bytes.
The integrity state is caller-supplied context, never an authorization capability or
proof of provenance. An invalidated packet refuses comparison; later server invalidation
and persistence/history contracts remain separate work.

Bind the exact action/version/document. Require its existing owner review. Compare full
owned account and connection generation, owner key, source binding, privacy revision,
currency and time zone. Require the same stable member identities (full account,
provider reference, canonical key, kind and owner); ignore display names and transient
selection/evidence keys. Include removed owner members and their removed/nonremoved
classification; require the same reference count. Addition/removal or a transition
to/from REMOVED invalidates comparison. A status change
within the eligible ENABLED/PAUSED profile is allowed, but is not itself compared.

Require plan.generated_at <= fresh observation start <= observed_at <= compared_at
< fresh expiry. Original plan validity is not extended: this is historical hypothesis
comparison, never permission to apply an expired plan. New source/privacy generation
requires a new plan; it cannot silently rebind the old hypothesis. Expired, foreign,
substituted, invalidated and malformed evidence refuses. No evidence yields unavailable.

Compare integer equality only: matches_hypothesis, differs_from_hypothesis, unavailable.
Even if a formerly decreasing hypothesis now exceeds the freshly observed amount,
the result is only different; it does not recommend increasing it. Computed output
always retains application unavailable, causality not_assessed, no actor attribution,
no spending authority and no advertising writes. No inference of implementation,
daily spend, period cap, delivery, outcomes or lift is permitted.

## Verification Scope

Synthetic deterministic fixtures will exercise genuine V6 composition, exact equality,
difference and missing evidence, stable identity versus name changes, freshness boundaries,
generation/privacy/source/topology refusal, malformed/copy serialization rejection,
zero amounts, byte bounds and honest authority flags. No DB or browser change is needed.
This closes only the pure comparison dependency. It does not close Q13 writer admission
or the open INLET-REL-20261012-01 incident; V6/V7 remain release-unqualified.
