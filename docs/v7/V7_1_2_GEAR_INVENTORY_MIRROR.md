# V7.1.2 Gear Inventory Mirror

V7.1.2 mirrors `data/gear_inventory.json` after its existing JSON write
succeeds. My Tackle Locker and Gear Intelligence continue to read JSON.

## Mirrored operations

- add and edit gear
- favorite and status changes, including retire/archive and restore
- guarded delete
- image, provider-source, and maintenance metadata changes
- new `record_item_usage()` calls

Each mirror replaces category specifications, tags, images, product-source
metadata, maintenance state, source provenance, and legacy payload hashes from
the complete saved inventory. Unknown/custom fields remain in
`legacy_payload_json`. Catalog-cache material is not treated as inventory data.

Existing `trips_used` and `catches_logged` counters remain legacy JSON values.
V7.1.2 does not fabricate historical usage events. New usage calls create one
SQLite `gear_usage` event after the JSON inventory save.

Use the operator reconciliation command after a recorded mirror failure:

```bash
./venv/bin/python tools/v7_1_reconcile.py --domain gear_inventory --json
```

SQLite failure does not undo or fail the JSON write. JSON remains authoritative.
