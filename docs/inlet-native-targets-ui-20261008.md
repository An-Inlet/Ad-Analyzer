# Native Target Display — 2026-10-08

Branch `codex/inlet-native-targets-ui`, worktree `/workspace/inlet-native-targets-ui`, base382895e (integrated V2 backend plus current planning customer fixes). Root approved renderer/controller interface before code. No API/schema/provider changes.

Account Diagnostics now offers a separate explicit Read Native Targets button using the currently selected owned `/planning/accounts` account and bounded past reporting window. New reusable display-only `native-targets.mjs` validates bounded response arrays, source/account/platform/window, coverage and observation freshness, then renders names/native IDs/parent IDs, separate native-settings and names/hierarchy coverage, both read intervals and earliest expiry. Missing/over-bound names remain explicit unavailable states. All DOM content uses textContent; no guessed URLs, HTML injection, target-selection authority or spending claims. Server checks remain authoritative; browser hashes are opaque identifiers.

Selection/period/workspace changes, session refresh/logout, failed reads and malformed/expired results clear output. Original request epoch and cookie/post-response session checks reject out-of-order and cross-session responses. One bounded expiry timer clears current output without rereading; cancelled/old timer callbacks cannot clear newer output. Focus/visibility detects changed CSRF cookies and clears displayed data. Native reads never start automatically. Existing account diagnostics action stays distinct.

Restored customer navigation link Account Diagnostics And Native Targets in `/app/settings` after root approval; the old optimization route is now history and no longer links here. Updated this page's history label accordingly. Existing account-diagnostics browser fixture now uses the source-only customer/account seed rather than attempting execution mandate approval in the planning artifact. No capability monkeypatch was introduced.

Checks actually run:

- Final `pytest tests/test_native_targets_browser.py tests/test_account_diagnostics_ui.py` with SQLite and disposable isolated PostgreSQL schemas: **7 passed in33.51s** (six actual HTTPS/browser/provider paths and one shell/asset/navigation check).
- Existing account diagnostics HTTPS/browser paths after source-only fixture repair: **6 passed** in a run taking20.91s; the same run had one stale navigation assertion failure, subsequently fixed and passed in the final shell check above.
- Whole Ruff passed. Whole mypy passed1012 source files. `node --check` passed for renderer, controller and browser driver. `git diff --check` passed.

Browser tests use actual owner APIs, sessions, vault rows and concrete provider readers through MockTransport. They verify literal HTML-like native names, explicit missing/over-bound names, customer-visible references, separate coverage, malformed/expired response clearing, A→B→A late responses, response loss without retry, disabled reads, session changes in flight/on focus, logout, expiry clearing and old/cancelled timer rejection. Expiry lifecycle is tested with an explicitly injected browser clock and captured timer callback; no production/source clock or deadline is changed. Each successful case makes exactly seven user-triggered provider read operations. No live provider calls.

Exploratory fixture failure: lost-response flag could be consumed by the preceding held response while its cloned JSON was still pending. Moved the fixture's delivered signal after clone parsing; final all-provider/bothDB browser cohort passes. This changed test ordering only, not application behavior.

Evidence `/workspace/inlet-evidence/20261008/native-targets-ui/`. Independent review/root integration pending. No hosted/deployment/production verification. This is an account inventory display, not a comprehensive planning product or execution capability. Remaining work belongs to reviewed comprehensive plan consumers/evidence/scenarios/briefs.
