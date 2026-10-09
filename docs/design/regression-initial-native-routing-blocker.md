# Native Planning Regression: Routing Constraint

Read-only investigation from root `d89d797`, after approval of coherent precision profile proposal `a9bb760`. No test or production source edits yet.

A real current PlanningConsent requires `runtime.profile` (`planning_consents.checked_planning_limits`) and exact `runtime.configuration == runtime.profile.initial`. However, `customer_initial_planning.native_options` chooses the new native-budget reader whenever a profile exists, and `prepare` resolves `PreviewIntentV2` whenever a profile exists. It therefore calls `preview_v2_service.prepare_preview`, not original `preview.prepare_preview`.

Consequences:

- Coherent1micro configuration can reach the analogous V2 amount predicate, whose controlled409 is `native_budget_proposal_outside_consented_limits`; it cannot exercise the originally approved exact V1 message through the API.
- Original post-consent `runtime.native.execution.environment='live'` affects `native.catalog`, but the profile-backed API calls `native_budget.catalog` and never observes that field. Keeping the original mutation would no longer prove environment denial.
- Removing profile is invalid: current planning-consent validation rejects it. No profile omission, dispatch monkeypatch, synthetic consent or execution fallback is proposed.

## Proposed Separate Acceptance Boundaries

Preferred narrow option: preserve these original V1 compatibility checks through explicit direct calls to the retained **read-only** `native.catalog`/`preview.prepare_preview` using genuine API-created current PlanningConsent and coherent profile. All source/session/goal/native GET checks and exact original amount/environment denial still execute. Setup uses actual current preparation/confirmation APIs; direct V1 read is labeled service compatibility, not customer route acceptance. The API `/previews` checks should then be a separate current V2 case with its actual native evidence/environment binding, not relabeled as the old path.

Alternative: migrate the ten customer tests to current V2 APIs, explicitly review equivalent precision/environment predicates, and preserve old V1 coverage in a separate bounded service module. This is a larger classification/interface change and is not implemented under the original approval.

Root must choose the concrete scope before source edits. The original exact SQLite positive was invoked unmodified and fails at the expected execution-consent guard; logs/XML are retained in `/workspace/inlet-evidence/20261009/native-planning-confirmation/baseline.*`. No Full, source mutation, database reset or live provider calls.
