# V7.3.5b SQLite-First Report Creation

## Scope

V7.3.5b implements and tests the SQLite-first save service. Production report
routes remain JSON-authoritative until the explicit V7.3.5e transition.

## Transaction boundary

The authoritative SQLite transaction upserts the deterministic trip and the
active `trip_reports` row. It stores complete wrapped snapshot JSON, selected
forecast metadata, compatibility paths, and the authoritative snapshot hash.

JSON snapshots, the reports index, and printable HTML are not part of the
SQLite transaction. They are compatibility/generated artifacts created after
the commit and tracked independently as `ok`, `pending`, or `failed`.

## Failure behavior

- SQLite failure: report creation fails and no authoritative report exists.
- JSON/index export failure: SQLite report remains saved; the result carries a
  repair warning and the database records the failed compatibility export.
- HTML generation failure: SQLite report and any JSON export remain saved; the
  printable artifact is marked failed for later regeneration.

The service does not write recommendation-history tables. Full intelligence is
retained in the authoritative report snapshot for later V7.3.6 work.
