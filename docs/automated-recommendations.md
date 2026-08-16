# Automated deterministic recommendations

## Purpose and boundary

Improvement step 7 turns eligible deterministic findings into a review queue after post-sync,
nightly, and weekly analysis. It covers account, campaign, ad-group, keyword, and masked
search-term scopes. The generator reads the analyzer's in-memory snapshots and writes local
recommendation and audit rows in the same transaction as the analysis result.

The generator does not call a collector, analytics provider, CRM, executor, or advertising API.
Every planned action uses `human_review_required` and the non-mutation marker
`none_without_human_approval`. A workspace owner or administrator must approve a proposal before
the existing dry-run planner can inspect it. Live advertising writes remain disabled.

## Deterministic policy

The version 1 policy:

- skips `stale_data` and `insufficient_data`, which are blockers rather than actions;
- ranks high, medium, and low severity in that order, then ranks higher current-window spend first;
- uses stable scope IDs and finding codes as final tie-breakers;
- creates at most 100 proposals per analysis run;
- expires proposals after 14 days; and
- suppresses an equivalent proposal for 14 days after rejection.

Review actions are fixed categories such as relevance/creative review, efficiency-regression
review, spend-shift review, keyword status/match-type review, and negative-keyword-candidate review.
They are operator prompts, not executable mutation payloads.

## Deduplication and auditability

Each proposal has a SHA-256 key derived from the generator version, workspace, platform, account,
campaign ancestry, scope type/local ID, finding code, and review action. It never contains a scope
label or search-term text. A partial unique index allows only one active row for a workspace/key
across `pending_review`, `approved`, and `executed_dry_run` states. The service also checks the key
before insertion and treats the database index as its race-safe final guard.

Generated recommendations store their source analysis-run ID. Analysis history exposes created and
deduplicated counts, while each new row receives a `generated` audit entry. Expired active rows
receive a system expiration audit before a current proposal can replace them.

## Search-term privacy

The lower-level analyzer never selects `search_terms.term`. Recommendation generation receives
only the masked display label (`Search term #<local id>`), numeric supporting metrics, and fixed
finding messages. Raw query text is therefore absent from rationale, planned action, supporting
metrics, the deduplication key, API responses, and dashboard rendering. Advertiser-authored keyword
text may remain visible to authorized operators.
