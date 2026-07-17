# V7 Migration Plan

This plan documents the shape of the long-term relational model without flipping SQLite authority yet.

## Goals

- Preserve current JSON behavior.
- Make gear, trips, catches, and reports explicitly relational.
- Require backup, export, validation, and rollback gates before authority changes.
- Keep the app Raspberry Pi friendly and locally recoverable.

## Proposed entity order

1. waterbodies
2. target_profiles
3. trips
4. trip_reports
5. forecast_snapshots
6. catches
7. gear_items
8. gear_setups
9. trip_gear
10. catch_gear
11. gear_maintenance
12. recommendations
13. product_sources
14. favorites

## Suggested identifiers

- Use stable string IDs for imported or user-created records.
- Keep existing gear IDs and catch IDs stable during migration.
- Preserve the current JSON record IDs as the source for seed mapping.

## Suggested relationships

- `trips` -> one target profile, one waterbody, many gear references
- `trip_reports` -> one trip, one selected forecast day, many recommendation blocks
- `forecast_snapshots` -> one trip date or one report date
- `catches` -> one trip or report, optional gear references
- `gear_items` -> many trip_gear / catch_gear links
- `gear_setups` -> many gear items, one setup profile
- `product_sources` -> one or more gear items

## Provenance and confidence

Keep provenance explicit where possible:
- source name
- source URL
- retrieved timestamp
- confidence level
- field sources for imported specs
- manual vs imported vs cached origin

## Migration gates

Do not flip authority until all of these are true:

- JSON backup is created successfully.
- JSON export from the current app is successful.
- SQLite export/import path is validated.
- Row counts match between JSON and SQLite staging tables.
- Existing reports and catches render after import.
- Rollback from SQLite back to JSON is proven.
- Gear images and other runtime media remain accessible.
- QC passes on the migration branch.

## Validation order

1. waterbodies
2. target profiles
3. trips and reports
4. catches
5. gear items
6. gear setups and trip gear
7. maintenance and recommendations

## Rollback rule

If any migrated entity fails validation, restore the JSON snapshot and keep SQLite in mirror mode. No partial authority flip.
