# Qualified Exposure Settlement

The reservation shared by creation and activation remains held after paused creation,
activation status readback, cancellation, closure, and period end. These events alone
cannot establish that spending exposure or an original network operation has ended.

`publication.settlement` adds two explicit, audited paths using the existing protected
reservation/ledger records. Neither path mutates a provider or resets action counters.

- `settle_unemitted`: all related runs are canceled and no original attempt was ever
  committed. The workspace lock serializes this proof against any future claim. It
  writes the canceled-run snapshot and local no-attempt evidence before release.
- `settle`: all related runs are canceled and every committed original attempt has a
  current scoped verified receipt. A server-owned read-only source must additionally
  prove every original request is terminal or incapable of a later effect, the exact
  budget owner's remaining future upper bound is zero, and reporting is complete for
  every portfolio account. The source binds the complete immutable snapshot. Locks
  are released around source IO and reacquired to validate the same latest receipt
  set, ownership, ledger, reservation and fresh proof before release.

A verified target state is not proof that a delayed original mutation has finished.
`SettlementObservation.closed_attempt_ids` must cover exactly every original attempt
in the snapshot, under authoritative terminal semantics. Missing readback, old paused
status, elapsed time, a provider acknowledgement alone, or a single no-effect step do
not provide this proof. An earlier created resource remains part of the exposure.
Terminal evidence must cover the latest observation time of every original receipt.

The original reservation amount and evidence remain intact. The settled evidence is
written separately and the period ledger's spend high-water can only increase. A
final report that reveals spend above the cap is retained honestly; it does not reset
accounting or grant new spending authority. New unknown evidence arriving during the
source read prevents settlement. The completed terminal snapshot remains auditable.

## Server Interface And Remaining Work

`SettlementReader(snapshot: SettlementSnapshot, now: datetime) -> SettlementObservation`
is a server-only port. No customer API accepts an observation object as proof. The
snapshot includes workspace/reservation/ledger/environment, original exposure, all
canceled sharing runs, current ledger high-water and each latest owned normalized
receipt. The observation carries a bound snapshot digest, explicit qualification
profile/proof kind, closed original-attempt set, terminal upper bound, reporting
watermark, complete account set, final portfolio spend and zero future upper bound.

The default runtime factory returns `None`. Contract scenarios cannot qualify live
settlement. Concrete live native-terminal/request-closure and final-reporting sources
remain missing implementation; a disabled factory does not stand in for those sources.
No live provider reads or mutations, deployment, workflow dispatch, or Full suite were
performed for this package. Existing lifecycle/export policy retains these protected
financial/audit records; no new table or migration is introduced.

## Verification

**25 tests passed** on SQLite and disposable PostgreSQL. Covered full mocked Google
creation→separate activation→cancellation of both runs→qualified settlement; unknown
original attempts after period end; later no-effect with an earlier created resource;
missing terminal request closure; changed account coverage/snapshot/high-water;
qualification expiry during source IO; newer unknown receipts during source IO; local
zero-attempt release; preserved reservation amount/spend/action accounting; and default
disabled runtime. Whole repository Ruff passed; mypy passed for 386 source files;
`git diff --check` passed. Logs: `/tmp/inlet-settlement-complete.log`,
`/tmp/inlet-settlement-ruff.log`, `/tmp/inlet-settlement-mypy.log`.
