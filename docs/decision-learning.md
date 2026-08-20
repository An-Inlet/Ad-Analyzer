# Auditable decision learning

## Purpose and boundary

Improvement step 8 learns from which deterministic recommendations workspace operators approve or
reject. The source of truth is the existing immutable recommendation audit trail. Learning is
workspace-scoped and groups decisions by recommendation type, scope type, and fixed review action.
It never reads another workspace's recommendations.

The service uses only the `approved` and `rejected` action codes. Operator identity and free-text
reason fields are deliberately excluded from aggregation, API responses, dashboard output, and
future proposal metadata. Generated search-term proposals therefore remain masked and no raw query
text is selected or introduced by learning.

## Version 1 evidence policy

For each profile, version 1 exposes:

- approved, rejected, and total decision counts;
- the observed acceptance rate;
- an add-one-smoothed acceptance rate, `(approved + 1) / (decisions + 2)`; and
- the latest decision timestamp.

One through four decisions are labeled `limited`; five or more are labeled `established`. A
profile with no history receives a neutral `0.5000` smoothed rate when a proposal is generated.
This evidence label is descriptive only and does not gate recommendations.

Proposal selection still orders severity first and spend impact second. The smoothed acceptance
rate is the next key, so learning can change only the order of candidates whose severity and spend
impact are equal. Stable account and scope keys remain the final tie-breakers. The exact evidence
snapshot is stored in `planned_action.decision_learning` for later audit and reporting.

## Safety properties

Decision learning does not:

- change deterministic finding thresholds, eligibility, severity, or analytical confidence;
- suppress rejected signal categories beyond Step 7's fixed 14-day equivalent-proposal cooldown;
- invoke collectors, analytics providers, CRM providers, executors, or advertising APIs;
- approve, reject, defer, execute, or mutate a recommendation; or
- create opaque or self-modifying model state.

Operators can inspect the aggregate through
`GET /api/v1/workspaces/{workspace_slug}/decision-learning` and the authenticated workspace
dashboard. The next roadmap step can consume the same transparent evidence when producing the
weekly learning report without changing this safety boundary.
