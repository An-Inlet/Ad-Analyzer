# Decision Needed: Separately Consented Pause-Only Containment

Current behavior is deliberately conservative: every provider operation requires a
fresh complete exposure bound within the approved total cap. That also blocks an
otherwise risk-reducing pause when exposure is unknown or already over cap. The
existing production policy has no emergency or post-period mutation authority.
B07's approved stop semantics distinguish stopping Inlet from stopping the platform;
pausing/revoking Inlet never promises an immediate platform stop.

Recommended owner decision: authorize implementing a **separate optional customer
containment consent**, explicitly reviewed alongside the spending mandate. It would
permit only PAUSED/DISABLE on an exact approved advertiser/budget-owner/target set.
It would have its own finite validity window, including any explicitly selected
post-spending-period grace window. Unknown/over-cap exposure may satisfy only this
pause-only admission exception. Normal workspace/account ownership, current generation,
customer revocation, entitlement policy, runtime gates, durable original-attempt fencing
and audit checks still apply. No resume, activation, budget/creative/targeting changes,
new resources, implicit target discovery, or replacement attempt after uncertainty.
Pausing retains residual exposure and does not establish a treatment instant or release
reservations. This would be software behavior only; the present assignment still does
not authorize live provider calls or spending.

Alternative: retain the present fail-closed policy and ask customers to pause the
platform themselves when exposure cannot be bounded. This avoids a new consent model
but limits automatic containment precisely when reporting or bounds are unavailable.

Until an explicit owner decision, no containment exception is implemented. Period end
is neither pause authority nor settlement evidence. Authoritative terminal exposure
and complete reporting are required before any reservation can be released; an
unresolved original attempt cannot be retired based on age or missing readback.
