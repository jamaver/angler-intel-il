# Runtime Data Policy

Angler Intel uses a mix of repository defaults, local runtime JSON, generated cache, uploads, and backups. Before V7, the codebase should keep these responsibilities explicit so user data stays safe and predictable.

## Current repository defaults

These are app-managed defaults or seeded content that should remain available in the repo:
- `data/illinois_waters.json`
- `data/species_profiles_v43.json`
- `data/lure_rig_setups_v43.json`
- version marker files in `data/version_*.json`
- template/static code and fixed reference assets

## Current runtime user data

These are user-owned or session-owned files that should not be treated as source-controlled defaults:
- `data/gear_inventory.json`
- `data/manual_waters.json`
- `data/target_profile.json`
- `data/gear_settings.json`
- `data/catches.json`
- `data/favorites.json`
- `data/saved_reports.json`

The repository ignores these files. A missing gear inventory initializes as an
empty locker, a missing target profile uses the species defaults, and a missing
manual-water file is treated as an empty personal-water collection. This keeps
fresh installs functional without shipping another user's history.

## Generated cache and artifacts

These are derived from app activity and should stay out of source control unless intentionally captured:
- `data/gear_catalog_cache.json`
- `data/exports/`
- backup archives under `backups/`
- generated reports under `reports/`

## Local gear images and uploads

User-uploaded or imported gear images are runtime media and should be managed separately from code:
- `data/gear_uploads/`

The app should keep fallback images in `static/gear/fallback/` so missing uploads never break the UI.

## Backup behavior

Backups should include:
- gear inventory
- manual waters
- target profile
- gear settings
- catches and favorites
- saved reports when present
- local gear uploads / images

Backups should exclude:
- generated exports
- transient caches
- build artifacts
- private credentials

## Recommended future `instance/` layout

For V7 and beyond, the runtime policy should migrate toward Flask's `instance/` directory while preserving JSON compatibility during transition:

```text
instance/
  gear_inventory.json
  manual_waters.json
  target_profile.json
  gear_settings.json
  catches.json
  favorites.json
  saved_reports.json
  exports/
  uploads/
  cache/
```

## Compatibility notes

- Existing `data/*.json` files should continue to load until a deliberate migration step copies them into `instance/`.
- A future migration should support rollback to the current JSON layout.
- Authority should not flip until backup, export, validation, and rollback gates are proven.
- Runtime data should stay human-readable until the relational layer is explicitly adopted.
