# Runtime Data Policy

Angler Intel uses a mix of repository defaults, local runtime JSON compatibility exports, generated cache, uploads, backups, and SQLite-authoritative data. V7.6 keeps these responsibilities explicit so user data stays safe and predictable.

## Current repository defaults

These are app-managed defaults or seeded content that should remain available in the repo:
- `data/illinois_waters.json`
- `data/species_profiles_v43.json`
- `data/lure_rig_setups_v43.json`
- version marker files in `data/version_*.json`
- template/static code and fixed reference assets

## Current runtime user data

These are user-owned or session-owned files that should not be treated as source-controlled defaults:
- `instance/angler_intel.sqlite3`
- `instance/authority.json`
- `instance/compatibility/*.json`
- `instance/reports/`
- `instance/uploads/`
- `instance/backups/`
- `instance/exports/`
- `instance/cache/`

The repository ignores these paths. Legacy `data/*.json`, `reports/`, and
`backups/` names are compatibility symlinks into `instance/`; they are not a
second source of truth. The original pre-transition copies are parked under
`instance/legacy_pre_v7_6/` for operator-led recovery.

## Generated cache and artifacts

These are derived from app activity and should stay out of source control unless intentionally captured:
- `instance/cache/gear_catalog_cache.json`
- `instance/exports/`
- backup archives under `instance/backups/`
- generated reports under `instance/reports/`

## Local gear images and uploads

User-uploaded or imported gear images are runtime media and should be managed separately from code:
- `instance/uploads/`

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

## Active V7.6 `instance/` layout

For V7 and beyond, the runtime policy should migrate toward Flask's `instance/` directory while preserving JSON compatibility during transition:

```text
instance/
  angler_intel.sqlite3
  authority.json
  compatibility/
  exports/
  uploads/
  cache/
  reports/
  backups/
```

## Compatibility notes

- The V7.6 transition copies and validates each legacy runtime item before it
  activates a compatibility symlink.
- The systemd service declares `AI_INSTANCE_DIR`, `AI_SQLITE_DB_PATH`, and
  `AI_AUTHORITY_MANIFEST`; service startup must retain those values.
- Live rollback is a deliberate maintenance operation: stop the service, use a
  verified backup or parked legacy copy, validate it, then start the service.
- SQLite authority is explicit per domain. Compatibility JSON is an export for
  transitioned domains, not an authority fallback.
