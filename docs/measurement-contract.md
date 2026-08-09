# Workspace measurement contract

## Purpose

Step 2 establishes the measurement rules that must exist before Ad Analyzer correlates ad
engagement with qualified leads, sales, revenue, or customer value. The contract is owned by one
workspace. It prevents the platform from silently treating an ad-platform conversion as equivalent
to a CRM-confirmed business outcome or from presenting modeled lifetime value as realized revenue.

This change defines and displays the contract only. It does not change recommendation rules,
contact external systems, upload conversions, or enable advertising writes.

## Source hierarchy

1. CRM lifecycle and value events are the proposed authoritative source for qualified leads,
   sales, cancellations, and observed revenue.
2. Google Ads and Meta Ads conversions remain diagnostic signals. They may explain behavior, but
   they do not establish qualified-lead, revenue, or customer-value truth.
3. Modeled lifetime value remains disabled until an approved model has enough realized outcome
   data and documented validation.

The API and dashboard report `analysis_ready=false` whenever the workspace contract is missing,
structurally incomplete, or still a draft. Downstream analytics must fail closed on that signal.

Step 3's unified outcome service enforces this signal. It returns no outcome metrics until the
contract is active, and then applies the contract's click-lookback, outcome-maturity, event-mapping,
authority, value-behavior, and currency rules. See
[unified outcome data](unified-outcome-data.md).

## Denticode draft

Migration `20260806_0009` creates a proposed version 1 contract for **Denticode Ad Analyzer**:

| Setting | Proposed value | Meaning |
|---|---|---|
| Status | Draft | No outcome-based analyzer rule may rely on it yet. |
| Optimization goal | Qualified lead | Rank traffic by CRM-confirmed lead quality, not form volume alone. |
| Business-value outcome | Sale won | Judge eventual business performance using CRM-confirmed sales and observed value. |
| Source of truth | CRM | CRM outcome events outrank ad-platform conversion counts. |
| Ad-platform conversions | Diagnostic only | Useful evidence, but not authoritative business results. |
| Attribution model | Last eligible paid touch | Use the latest eligible paid touch recorded on the lead. |
| Click lookback | 90 days | A paid click must fall within 90 days of the outcome. |
| Engaged-view lookback | 0 days | View-through attribution is disabled until reliable view data exists. |
| Outcome maturity | 90 days | Avoid prematurely judging cohorts whose downstream outcomes are still developing. |
| Customer-value mode | Observed revenue only | Do not invent or predict LTV in the first measurement contract. |
| Customer-value horizon | 365 days | Retain one year of observed post-lead value for later cohort analysis. |

## Funnel and event definitions

| CRM event | Normalized stage | Role | Monetary behavior |
|---|---|---|---|
| `lead_created` | Lead | Leading indicator | Ignore |
| `appointment_scheduled` | Appointment scheduled | Leading indicator | Ignore |
| `lead_qualified` | Qualified lead | Optimization outcome | Ignore |
| `proposal_sent` | Proposal sent | Leading indicator | Ignore |
| `sale_won` | Sale won | Business outcome | Set observed value |
| `sale_lost` | Sale lost | Negative outcome | Ignore |
| `sale_cancelled` | Sale cancelled | Negative outcome | Adjust prior value |
| `revenue_adjusted` | Revenue adjustment | Value adjustment | Adjust observed value |

Every currently accepted CRM event type has exactly one authoritative mapping. Event mappings use
a compound workspace/stage foreign key, so one client's source event cannot be mapped to another
client's funnel definition.

## Activation requirements

An owner must approve the proposed business definitions before the draft becomes active. At
minimum, confirm:

1. whether `lead_qualified` is the correct optimization goal;
2. whether `sale_won` and CRM value are the correct business-value truth;
3. whether the 90-day paid-click and outcome-maturity windows match the Denticode sales cycle;
4. whether the 365-day observed-value horizon is appropriate; and
5. whether view-through attribution should remain disabled.

Activation requires a separate, audited configuration change that sets an effective timestamp.
This implementation intentionally does not add a public mutation endpoint.

## Privacy and safety

The contract stores stage names, event-type names, policy values, and workspace IDs only. It does
not store names, email addresses, phone numbers, treatment details, diagnoses, free-text CRM notes,
patient data, click IDs, credentials, or raw event payloads. Existing CRM allowlists and PHI
rejection remain unchanged.
