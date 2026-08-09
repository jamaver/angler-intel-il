# V7.5.1.5 Compatibility Reconciliation

This maintenance release regenerates legacy JSON compatibility exports from
the existing SQLite-authoritative records for target profiles, gear inventory,
manual waters, and catches. SQLite authority is unchanged.

Drift validation now compares only active `trip_reports` rows with the active
report index. Rows soft-deleted for audit and rollback purposes remain in
SQLite but are intentionally not represented as active compatibility exports.

The repair is performed through `tools/v7_regenerate_compatibility_export.py`
with an explicit `--domain` and matching `--confirm-domain`. A verified V7
runtime backup is required before a live reconciliation. No historical record
is imported from a legacy export by this release.
