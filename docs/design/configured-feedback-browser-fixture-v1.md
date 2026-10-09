# Configured Feedback Browser — Exact Two-Case Fixture Interface

Proposal only after d0371f4 configured API8 and7a90f74 configured runtime10. Root
review precedes implementation. No browser or other test executed for this proposal.

## Scope

Exactly the original failed identities:

```text
tests/test_reported_feedback_configured_browser.py::test_configured_v2_browser[sqlite]
tests/test_reported_feedback_configured_browser.py::test_configured_v2_browser[postgres]
```

Only this Python test harness changes; the shared JavaScript driver, application,
legacy helper, current configured helper and producers remain untouched. No aggregate,
provider network, writes, production clock/TTL changes or runtime/policy overrides.

## Fixture And Rotation Seam

Apply the same reviewed import/fixture/pass-origin adaptation as current API8:
file-backed customer_engine wrapper plus base fixture, planning_origin/PlanningOrigin,
configured_journey from configured_planning_read_fixture and origin=planning_origin.
Keep the whole-test strict original/PlanningConsent financial guard through browser
shutdown. The actual relative original effect precedes current real configured API
acquisition, scheduler, V2 baseline and normal same-actor login.

Preserve the actual TestClient cookie transfer into the local TLS browser at
/__fixture__/start. No replacement session, job or cookie value is fabricated. Keep
all existing browser driver slicing: remove its initial synthetic-login/acquisition
portion because the configured helper already ran the actual chain; retain refresh,
comparison, feedback and late-response operations. Existing USD47→USD45.75 and label
substitutions remain exactly unchanged, matching this real configured policy.

The sole driver-token change is the known test identity assumption. Replace the
literal `'reported-browser:rotated'` in the loaded driver with a JSON-quoted literal
for `planning_origin.ids.actor_id + ':rotated'`, rather than hardcoded
configured-planning:rotated. Assert exactly one expected token occurrence before the
replacement. This fake identity-provider token represents the same retained subject
used by the actual ordinary helper login; it is not a real credential. Do not mutate
CustomerUser.subject or extend session TTL. No global/namespace clock substitution.

Supplement with DB evidence if straightforward: capture actual helper session and
user ID; after browser finishes, new session rows from its actual rotation must belong
to that same actor, use ordinary TTL and be revoked by its actual logout. Do not assume
there were no authentic historical sessions, compare the before/after session set.
If observed API session behavior differs, preserve the failure before choosing a
new assertion; no manual session insertion/revocation or counterfeit browser result.

## Preserved Actual Assertions

Keep the existing JavaScript body and Python result/timeout/cleanup assertions:
actual comparison wording and before/after CPA5/2.5; real changed preview USD45.75;
no-compounding explanation and unavailable financial handoff; held actual POST response
discarded after workspace change; original session history/comparison restored; second
held actual response discarded after real same-owner session rotation; refreshed
replacement session and actual logout clear values. Responses remain genuine API
results, not substituted payloads.

Retain existing Chromium executable selection, local TLS certificate, isolated user
profile, external DNS blocked, same harness path allowlist,90sec completion bound and
all finally cleanup. No timeout, native expiry or300sec configured preview extension.
Underlying replicas DB/FakeProvider dependencies are disclosed and distinct from
prohibited runtime/policy dependency overrides. Current native MockHTTP is GET-only,
strict finalizer preserves original financial graph; no live browser/provider claim.

## Qualification

First SQLite browser gate, then exact two on both databases; preserve any real browser
stage timeout/source expiry traces rather than retrying with weakened deadlines.
Retain structured browser result in evidence alongside stdout/log/XML where supported.
Original node identity and driver-transformation assertion proof accompany final code.
Bounded compatibility is current configured API session-mode2 and runtime positive2,
not all previously closed cohorts. Whole Ruff, bare mypy with /tmp cache, Node syntax
check of unchanged shared driver and diff check before freeze. Overlapping gate and
compatibility results add no original failure credit. No additional feature expansion.
