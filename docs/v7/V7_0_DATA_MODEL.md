# V7.0 Data Model

V7.0 adds the relational foundation only. JSON remains the authoritative production contract.

## Entity groups

- Reference: `species`, `species_aliases`, `waterbodies`, `waterbody_aliases`, `waterbody_species`, `waterbody_tags`, `saved_locations`
- Preferences: `target_profiles`, `target_profile_species`, `app_settings`, `data_authority`
- Gear: `gear_items`, `rod_specs`, `reel_specs`, `line_specs`, `lure_specs`, `terminal_tackle_specs`, `gear_item_tags`, `product_sources`, `gear_images`, `gear_maintenance`, `gear_usage`, `gear_setups`, `gear_setup_items`
- Trips and reports: `trips`, `forecast_snapshots`, `forecast_days`, `trip_reports`, `trip_gear`, `trip_outcomes`
- Catches: `catches`, `catch_gear`
- Intelligence: `intelligence_snapshots`, `recommendations`, `recommendation_explanations`, `recommendation_feedback`
- Governance: `schema_migrations`, `migration_runs`, `source_files`, `legacy_record_map`, `validation_runs`, `validation_diffs`

## Key design rules

- User-facing entities use stable text IDs.
- Provenance is retained with `legacy_payload_json`, source paths, source hashes, and record maps.
- Archive/status fields are preferred over destructive deletes.
- Historical catches and reports keep their original labels.
- Favorites are not modeled with a polymorphic foreign-key design.
- Usage counters are descriptive only and not treated as authority.

## Source-of-truth rules

- Every domain authority row remains `json`.
- SQLite rows are migration/validation/diagnostic structures only in V7.0.
- No production read or write path is allowed to switch to SQLite in V7.0.

