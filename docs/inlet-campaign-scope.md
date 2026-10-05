# Inlet Campaign And Action Scope

Status: proposed bounded pilot matrix for owner review, 2026-10-05. This is B01
scope preparation, not approved live advertising authority or an implemented
publisher. Current executable live-action eligibility remains empty.

| Platform | Proposed First Campaign Type | Proposed Existing-Campaign Operations | Reviewed Publication |
| --- | --- | --- | --- |
| Google Ads | Standard Search, excluding shared budgets, Shopping and Performance Max | Bounded campaign budget adjustment, pause/resume and reviewed negative-keyword additions where supported and validated | Supplied text/assets with customer-approved landing page and explicit draft version |
| Meta Ads | Standard auction website-sales campaign, supplied static image creative | Bounded budget adjustment and pause/resume at the supported budget owner; reject unsupported budget configurations | Customer-approved campaign/ad-set/ad draft and supplied image assets |
| TikTok Ads | Standard auction website-conversion campaign, supplied video creative | Bounded budget adjustment and pause/resume after supported resource semantics are verified | Customer-approved campaign/ad-group/ad draft and supplied video assets |

This is the recommended initial implementation boundary. Exact provider resource
support, permissions and current restrictions require official-documentation
verification during each adapter package and live pilot validation. Do not
advertise these as working features based on this document.

## Mandatory Eligibility Checks

- Active customer, workspace, subscription entitlement, connection and account.
- Explicit versioned spending mandate; supported campaign type and budget owner.
- Fresh required observations, verified current state and available spending
  reservation under cumulative limits; durable action claim before any side effect.
- All experiment spend shares the customer's overall approved spending limit.
  Draft 5%/10%/20% aggressiveness inputs never authorize raising that limit.
- New campaigns and creative require approval of the exact draft version;
  subsequent edits invalidate approval. A finding alone cannot authorize publication.
- Timeout or uncertain outcome requires reconciliation before another submission.
  Read back resulting state. Past spend cannot be rolled back.

## Diagnostic Semantics

`spend_without_conversions` requires available conversion metrics, sufficient
coverage, at least 20 clicks, positive spend and exactly zero conversions.
Positive fractional conversions count as conversions. Missing conversion data
does not mean zero. A high absolute CPA cannot be relabeled as zero conversions.

Existing `cpa_regression` compares measured CPA against a previous covered window
and remains separate. Goal-specific absolute CPA analysis is deferred until the
confirmed goal, currency, measurement source and time basis exist (B05/B06).

Owner review must confirm the matrix before action adapters are declared eligible.
It does not block the diagnostic correction or customer-foundation design.
