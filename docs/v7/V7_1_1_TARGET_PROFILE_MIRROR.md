# V7.1.1 Target Profile Mirror

V7.1.1 mirrors `data/target_profile.json` after its existing JSON write has
succeeded. JSON remains authoritative for all target-profile reads and writes.

## Mirrored operations

- default target changes
- current-trip target changes and resets
- favorite-species additions, removals, membership, and order

Each saved complete profile has a deterministic operation ID derived from its
canonical payload. A retry of the same profile snapshot is idempotent.

## Operational behavior

The mirror replaces the normalized `current` profile in a separate SQLite
transaction. A SQLite failure does not fail or roll back the JSON API request.
It is recorded for App Health and can be retried with:

```bash
./venv/bin/python tools/v7_1_reconcile.py --domain target_profile --json
```

`favorite_species_json` preserves the complete ordered list even if the V7
species reference table has not yet been reconciled. Relationship rows are
created only for normalized species already present, so V7.1.1 never invents
or guesses species reference data.
