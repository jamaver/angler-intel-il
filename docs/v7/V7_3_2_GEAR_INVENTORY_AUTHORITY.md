# V7.3.2 Gear Inventory SQLite Authority

## Scope

V7.3.2 transitions only `gear_inventory` after an operator preflight. The
already-transitioned `target_profile` remains SQLite-authoritative. Every
other domain remains JSON-authoritative.

## Write contract

My Tackle Locker writes the complete reviewed inventory envelope to SQLite in a
transaction, records a pending compatibility export, then atomically refreshes
`data/gear_inventory.json`. Existing item IDs, category-specific specifications,
images, source data, favorites, archive state, and user-entered unknown fields
remain in the legacy payload and compatibility export.

If SQLite fails, the locker update fails. If the post-commit compatibility
export fails, SQLite remains authoritative and App Health can surface the
failed export state. The old JSON-to-SQLite mirror refuses to run after this
transition.

## Transition gate

Use a fresh verified V7 runtime backup and clean validation:

```bash
./venv/bin/python tools/v7_authority.py transition \
  --domain gear_inventory \
  --backup-manifest backups/<verified-runtime-manifest>.manifest.json \
  --confirm-domain gear_inventory \
  --execute
```

No web UI changes domain authority. `data/gear_inventory.json` remains a
compatibility export for legacy consumers and recovery tooling.
