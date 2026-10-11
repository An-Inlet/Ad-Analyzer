# Normal PostgreSQL save measurement01

Source7db9768 (application/tests unchanged from9fd75ab). Exactly one authorized normal postgres-owner generation/history/export/replay case passed; no retry, repair or additional qualification run. Original exit0; testcase26.446s, XMLsuite28.221s, process30.779793s. This is instrumented measurement, not acceptance or R01–R03 closure.

Evidence: `/workspace/inlet-evidence/20261011/v6-normal-save-subphases/`. Frozen manifest01133047, plugin13b6df5d, runnerf78eee22. Report7016c6e4 was201112bytes, with no observer error or restoration failure. All1787 source hashes and clean Git state remained unchanged.

The observer reached its512-frame and128-final-record caps:375 flush frames and128 authority frames exhausted useful capacity. The operation called final222times; detailed authority records were consumed before save. The report correctly declares truncation/accounting incomplete. Retained-capture, storage and final guard details are absent. Exclusive residuals therefore contain omitted work; a zero arithmetic partition error does not establish complete attribution.

Recorded outer envelopes remain observations: generation9.713393s; save4.282553s (process-wideCPU3.728630s),2385 SQL executions/0.858256s SQL. Save age brackets0.001296→4.283829s are observer samples, not predicate samples. Captured entry0.168355s, actual bindings0.002364s and owner bindings0.286330s each recorded zero SQL. Final-sources span2.610634s is inclusive, not additive to save; incomplete nested coverage prevents a complete cost partition. No dominant-cause or removable-cost conclusion follows.

Initial external Ruff findings were formatting and explicit diagnostic-only suppression annotations; corrected Ruff and compilation passed. Collection was separately authorized and observer-free. A manifest-preparation script initially resolved relative source paths from the wrong working directory; it failed before writing the final manifest and was corrected without executing tests. No production files changed.

Next authorized work is source-only observer correction: remove per-call flush spans and restrict detailed authority brackets to active save, retaining bounded records and all original calls. This is a concrete observer-capacity defect, not a production repair. Any changed observer and subsequent measurement require separate review and authorization. No caps, deadlines, authorization, privacy or rollback behavior have been relaxed.
