# Google Budget Observation In The Customer Application

The saved execution view has an explicit **Read Budget Observation** action. It calls
only the owned CSRF-protected envelope-observation POST. Opening the page, changing runs
or refreshing execution status never starts a native budget read automatically.

The display separates original native campaign total, current observed native total and
recorded reservation. Unknown amounts display “Unavailable”, never zero. Matching settings
are explicitly not financial qualification, execution approval, settlement or permission
to release a reservation. Current saved-run metadata does not identify the exact supported
Google total variant, so the action is clearly named Google Budget Observation and handles
unsupported 409/default-unavailable 503 responses without guessing eligibility.

The independent controller accepts only the frozen response schema, exact run/environment,
known reason codes, bounded amounts, valid dates and fresh expiry. It renders fixed labels
and text content, never raw provider identifiers or arbitrary response fields. Results
clear on run/workspace/session/logout changes; a local timer also clears expired results
and detects session-cookie changes during delayed responses. It performs no network polling.
Workspace/run/session changes followed by a return to the earlier value cannot resurrect
the in-flight observation when the change was observed by the page's state fences.

Verification uses genuine configured total creation/capture followed by actual HTTPS
browser login, saved owned run recovery, vault/native inventory MockHTTP and the real
endpoint. The browser reads matching settings, explicitly rereads changed settings, handles
the disabled runtime, and logs out. Retained reservations and provider mutation counts are
unchanged. No runtime getter overrides or seeded execution records are used.

This is customer access to nonauthorizing observed configuration evidence. It does not
complete financial source qualification or a live autonomous optimization pilot.

Validation: final new DOM + actual SQLite/PostgreSQL HTTPS cohort **3 passed in 9.45s**
(`/tmp/inlet-envelope-ui-final.log`, `--durations=20`; browser calls 2.70s/4.30s). It asserts
exactly fourteen native/OAuth requests for two explicit observations, zero reads from page
load or disabled action, and unchanged mutations/reservations. Earlier initial run passed
3 in 12.33s before tightening the exact request-count assertion. Existing configured
Google/Meta/TikTok creation and separate-activation HTTPS happy paths **6 passed,
30 deselected in 123.53s** (`/tmp/inlet-envelope-ui-compat.log`, `--durations=20`). Whole
Ruff, configured mypy **869 files**, Node syntax checks and diff checks pass. No Full,
remote actions, live account calls or demo artifacts.
