# V7.0 Validation

Validation is read-only and reports drift without repairing data.

## Expected statuses

- `exact`
- `missing_in_sqlite`
- `extra_in_sqlite`
- `changed`
- `invalid_source`
- `duplicate_source`
- `unmapped_reference`
- `orphan_reference`
- `generated_only`

## Checks

- JSON parsing
- Stable key comparison
- Canonical SHA-256 comparison
- Aggregate domain hashes
- Duplicate source IDs
- Duplicate normalized keys
- Unresolved water/species/gear/trip references
- SQLite integrity and foreign key checks

## Output

- Machine-readable JSON is written to the ignored exports area.
- Validation summaries and diffs may be recorded to SQLite after validation succeeds.

