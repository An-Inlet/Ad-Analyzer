# Plan Review Authorization And Ceiling Repair

Independent review of the fresh-brand customer journey found two pre-existing
simulation API gaps exposed by the new Plan Review page: a pending approval could
commit after its original session was revoked or owner membership was downgraded,
and a saved simulation could exceed its confirmed goal budget.

Every customer simulation mutation now locks workspace, user, original persisted
session and membership before mandate/action locks. The canonical guard refreshes
these rows and provider authority; locks remain held through the mutation commit.
Server-selected role sets preserve analyst drafting, owner-only approval/dispatch,
and owner/admin stopping. Existing guard callers retain the owner/admin default;
no client field can select authorization roles.

The shared simulation validator rejects a total cap above the current confirmed
goal budget at creation, revision and approval, including historical saved drafts.
Zero budgets and caps exactly at the goal ceiling remain valid. Existing exact
goal-revision/baseline/currency checks remain in place. This repair does not impose
a new timezone/period policy on older valid simulations or change production
spending authority.

## Evidence

A real PostgreSQL transaction held the workspace row while the original request
completed authentication and blocked on that row. The holding transaction then
revoked the session or downgraded the owner and committed. Baseline943ce8 returned
HTTP200 for both approvals; repaired requests return401/403 with the fresh draft
still unapproved. No test attempts an impossible revocation behind the repaired
session lock.

The focused matrix also exercises create/edit/approve at above/zero/exact ceiling,
all existing customer role permissions and unchanged default guard behavior on
SQLite and PostgreSQL. The broader identity/mandate/context/fresh HTTPS customer
suite passed90 tests; its two skips are the SQLite variants of PostgreSQL lock
races. No live providers, pushes, PR operations, hosted CI, or frozen Full changes.
