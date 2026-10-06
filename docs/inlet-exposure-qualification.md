# Portfolio Exposure Composition

This server-only reader composes a complete set of owned account facts with current
separate consent, connection generations and the shared durable reservation ledger.
It does not create provider cap guarantees or enable a runtime. No API accepts these
facts or profiles from customers, and there is no default live facts reader/profile.

A server-selected qualification profile must independently establish native or
portfolio bound semantics, including reporting delay and all unchanged campaigns.
Daily budget values alone do not establish that bound. The supplied cached source
must cover the exact approved account set, currency, period, plan digest and current
connection generations. Its unchanged future component excludes precisely the
proposed owner's future component. Missing, incomplete, regressed or unknown-profile
facts return unqualified evidence with no numeric portfolio bound; stale or foreign
lineage is rejected. A fresh clock after source read prevents expired facts being
accepted after a wait. Facts readers must not release the transaction or perform
provider mutations. Coordinator post-claim checks remain required.

Creation counts all held workspace/environment reservations, including unresolved
holds from previous periods, matching the coordinator inventory. Activation may exclude only its
exact owned/environment/ledger held reservation, whose owner key and amount match
the proposed bound, and includes that amount once as the proposed owner component.
No reservation is released or changed by this reader. Expired periods or aggressiveness
settings grant no additional authority.

Focused actual SQLite/PostgreSQL coordinator fixtures:24 passed. Tests cover retained
reservation accounting, unknown profile/bounds, incomplete data, regressed spend,
foreign/duplicate accounts, currency/plan mismatch and expiry during read. Initial
fixture incorrectly expected create_run to allocate a reservation; corrected to use
the actual durable claim. Ruff and configured mypy412 pass. Independent review found and repaired two
composition defects: emitted evidence now expires by the qualification profile
lifetime, and previous-period holds are counted conservatively while never eligible
for activation exclusion. Downstream expiry and retained-history regressions pass. No Full/live qualification.

Concrete provider portfolio completeness/native cap/reporting-delay sources remain
an engineering and live-qualification gap; an injected contract scenario is not a
production proof. This module supplies validated composition, not those missing facts.
