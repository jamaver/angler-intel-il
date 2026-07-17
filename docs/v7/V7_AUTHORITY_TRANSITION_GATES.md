# V7 Authority Transition Gates

SQLite authority must not be enabled in V7.0.

## Mandatory gates before any future transition

- Full JSON backup and verification
- Full SQLite backup and verification
- Import idempotency
- Drift validation on clean fixtures
- Rollback rehearsal
- Dual-write design
- Staged read-path switch
- Explicit authority marker change
- Operator confirmation

## V7.0 state

- Authority remains `json`.
- Existing mirror tables remain intact.
- No production path may read from SQLite as the primary source.

