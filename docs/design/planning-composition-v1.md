# Deterministic Planning Composition V1 — Implementation Design

This design consumes the reviewed document contracts and forthcoming shared trusted
evidence ports. It does not qualify recommendation quality or authorize a production
numeric policy. Root's frozen quality cases remain the evaluation inputs. The pure
composer has no database, identity provider, network, credentials or write transport.

## Evidence And Output

Compose only from exact owned inputs and server-bound catalog, performance and
Shopify progress documents. Reparse nested evidence and reject any stale or foreign
binding before composing. A missing read is an explicit gap; an authorization or
source-integrity failure cannot become a gap. Native names/IDs come from V2; campaign
metrics join by the resolved native campaign identity, never by name. Preserve source
coverage, reporting event/window, currency, attribution and unqualified maturity.

Current provider settings and hypothetical period allocations remain separate.
Only exact supported fields in the trusted source can produce typed current values.
Unavailable units/ownership/field evidence produce an unavailable proposal and
specific manual discovery steps. No implicit micros, forecast, conversion-to-sales
mapping, hardcoded transfer percentage or daily-to-period spend guarantee is allowed.
The 5/10/20% draft figures are not an implementation default.

## Deterministic Action Selection

Use explicit rule identifiers and a documented ordinal ordering, not measured
confidence or expected lift. Within an equally prioritized category, order by stable
owned identity; do not rank mixed currencies or incomparable conversion definitions.

1. Resolve measurement, scope and source gaps that prevent reliable decisions. A task
   names the exact account/campaign, missing field or window, recovery step, and what
   evidence the customer should inspect before changing advertising.
2. For present, explicitly described reported conversions, distinguish positive,
   exactly zero and unavailable. Positive conversions can never produce a
   spend-without-conversions assertion. Present zero with positive spend can trigger
   a tracking/landing-page investigation; it does not justify a claimed return or an
   automatic pause. Missing rows/events never become zero.
3. Preserve a defensible maintain/review outcome when no qualified change is supported.
   State the observed facts, current limitation and measurable review criterion.
4. Offer a specific creative task based on customer-supplied product/offer facts and
   available asset constraints. Google text, Meta image and TikTok video directions
   remain channel-specific. Facts are explicitly attributed; hooks/storyboard ideas
   are hypotheses. Do not invent discounts, testimonials, assets or health claims.

Each action includes its target/reference, rationale and evidence, assumptions,
prerequisites, manual steps, verification/measurement criterion and risks/limitations.
Account-level prerequisites and creative work support empty native inventories.
Exclusions and production capacity constrain selection, not just displayed copy.
An unsupported bidding/targeting/status change must not appear as a supported typed
proposal merely because a model/schema can express it.

## Scenarios

Always reconcile each alternative independently to the exact confirmed ceiling,
preserving fixed allocations and the planning remainder. Customer-supplied alternative
allocation intents are resolved and validated by the service, then retained with that
provenance. Never parse numeric allocation instructions out of freeform text.

An optional descriptive baseline may illustrate the observed spend mix only when
the source adapter qualifies comparable complete spend windows, exact currency,
coverage and a nonduplicated campaign set. If implemented, its exact proportional
arithmetic and residual rounding must be versioned and tested; it must be labeled a
historical-mix assumption, not a forecast or recommended optimum. The current reported-
rows-only evidence contract does not by itself meet that prerequisite. Otherwise
retain fixed/customer allocations and an explicit unallocated remainder with steps to
choose a scenario. This limitation is visible in section readiness and quality review.

No higher total is generated from aggressiveness. A scenario is not a provider setting,
verified remaining balance, consent or instruction sent to an advertising platform.
Shared native budget owners cannot be double counted as independent editable budgets.

## Quality And Lifecycle

Output records exact generator/policy versions, evidence references, read intervals,
earliest actual expiry, partial sections and explicit assumptions. Local customer-
context and policy references are derived by the trusted service, not invented by
the composer. Plans remain `not_expert_qualified` until the independent expert gate
is actually completed. A schema-valid plan with generic text is not accepted as a
comprehensive recommendation.

First acceptance covers the frozen positive/zero/missing conversion cases, each
single-platform brand, shared/ambiguous budgets, independent customer alternatives,
constraints/zero budget and new-brand creative work. Every factual claim, quantitative
amount and target must trace to evidence or labeled customer input. Then evaluate
campaign-specific usefulness, manual feasibility, creative capacity and complete
journeys through saved versions, decisions, reports, export and corrected progress.
Any unmet quality case remains an explicit product gap, not a silent pass or reason
to weaken the case. Source refresh/CAS/authorization/privacy and persistence remain
service responsibilities and are tested at the assembled boundary.

## First Descriptive Implementation Boundary

`inlet.descriptive-planning.v1` implements campaign measurement review, exact native
locations, a fixed/unallocated baseline, unchanged customer alternatives and one
platform-specific concept per selected account within stated production capacity.
It preserves raw positive conversion facts. The current performance port cannot
qualify event presence for zero; both zero and missing produce an investigation,
never a factual no-conversions assertion. This does not change B01's qualified legacy
zero behavior. Native budget proposals and performance forecasts remain unavailable.

This is a foundation, not the completed comprehensive recommendation package. The
first composer does not interpret freeform operational constraints, compare historical
windows, compose catalog-field-specific bidding/targeting changes, optimize allocation,
or generate substantive product-specific copy/storyboards. Customer constraints remain
visible in immutable inputs. Those capabilities and expert usefulness review against
the frozen quality cases are still open; schema and synthetic regression passes are
not expert-quality acceptance. Do not expose this composer as a completed planning MVP.

Independent review repair: nonempty freeform constraints now defer all creative
proposals, preserve the exact constraints in section limitations and force measurement
clarification actions. No text parser claims to understand them. Manual steps always
ask the customer to compare settings against their ceiling and constraints, never
instruct unconditional continuation of existing spend. Zero ceilings force investigation
even with positive reported conversions. Added concrete no-creative/no-video and zero-
ceiling/positive-results regressions. 89 focused cases, Ruff and mypy (1,023 files) passed.
