# R02 Q09 Single Observer Result

Exactly one authorized PostgreSQL complete-case probe on clean application source
`0b6fd7954bc6380417593593c22ee9f42caf2c60`. Reviewed external observer SHA256
`7a5bd4ca025fbcfdf322bb7f78823ad43025de71a0d20afd0e7a0171c8b41a38`.
No retries, guard changes, artificial delay or clock replacement. Sole test slot
released after terminal verification.

Probe04 passed one case, zero failures/errors/skips, 21.668 seconds, exit0.
Its explicit generation replay accounts for the second service invocation.

| Observed interval | Wall seconds | CPU seconds | SQL count | SQL seconds |
| --- | ---: | ---: | ---: | ---: |
| Initial generate | 9.233794 | 7.867542 | 8628 | 2.349233 |
| Save generation, inclusive | 3.042459 | 2.709975 | 3146 | 0.656306 |
| Exact replay generate | 0.093005 | 0.085950 | 26 | 0.009630 |

Maximum final authority age was bracketed3.042561..3.042576seconds at
`repository.save_generation:640`; minimum observed session remaining was
28782.495827seconds across both invocations. Every final check returned. Maximum
replay fact age0.086879seconds. No event/report truncation occurred. SQL failed-call
durations are excluded by the observer; stage totals overlap and must not be added.

These are observations of a passing probe, not measurements of the original failed
run. R02 remains unresolved; a five-second-age cause or session-expiry cause of
both03 is not established. The original both03 matrix remains2passed/1failed with
its fourth case not run. Neither the single probe nor SQLite successes complete
that matrix. Exact Q09 social selected-event/attribution producers remain separate
gaps regardless of performance diagnosis.

Evidence retained locally under
`/workspace/inlet-evidence/20261011/creative-q09-baseline/`:
`probe04.log`, `.xml`, `.exitcode`, `-report.json`, `-source.json`, and
`probe04-manifest.json`; PostgreSQL document/export and their manifest copied into
`probe04-artifacts`. Preflight workspace1577MiB, scratch4501MiB, cgroup memory
headroom2104623104bytes. No external sharing or provider access.

## Recommended Next Step (Source Inspection Only)

Map the3146SQL save interval to the current source call graph: input receipt
revalidation, selected/image/selected checks, retained witness capture and final
persistence/authority calls. Identify repeated ownership/manifest loads *inside*
one already bounded validation pass separately from the mandatory independent
fresh passes. Record expected query multiplicities and exact source locations;
existing observer counters do not identify SQL shapes or prove which work is
redundant. A later bounded query-shape observer, if needed, requires a separate
reviewed payload-free contract. No implementation/cache/authority-window change is
justified yet. Preserve full copied-model and original-session validation.
