# V7.1.3 Manual Water Mirror

V7.1.3 mirrors the complete `data/manual_waters.json` document after its
existing JSON write succeeds. The map, Water Intel, and all production readers
continue to use the existing JSON water registry.

The mirror retains manual records with missing or invalid coordinates in SQLite
and marks them as invalid source records for validation. The existing map keeps
its current behavior of excluding records without valid coordinates from map
display. No coordinates are invented.

Manual-water source provenance, legacy payload hashes, names, coordinates,
location, type, notes, source, confidence, favorite state, and custom fields
are retained. Unknown or incomplete records remain in the JSON source; SQLite
diagnostics report their validation state separately.

To repair a non-fatal mirror failure after the JSON write:

```bash
./venv/bin/python tools/v7_1_reconcile.py --domain manual_waters --json
```

SQLite failure does not undo or fail a JSON write. JSON remains authoritative.

The reconciliation command deliberately records a new mirror operation even if
the current JSON hash was mirrored earlier. This repairs a stale SQLite copy
after a restore or an out-of-band diagnostic repair without changing JSON.
