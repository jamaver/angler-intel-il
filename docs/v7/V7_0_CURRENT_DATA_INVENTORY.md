# V7.0 Current Data Inventory

Angler Intel V7.0 keeps JSON authoritative. This inventory is the source map for the migration foundation.

## Core runtime sources

| Domain | Path | Status | Shape | Writer | Reader | Authority |
| --- | --- | --- | --- | --- | --- | --- |
| Catches | `data/catches.json` | runtime user data | list of catch dicts | catch logging UI, catch tools | dashboard, reports, catch learning | JSON |
| Favorites | `data/favorites.json` | runtime user data | list of favorite location dicts | favorites UI | waters, app health | JSON |
| Gear inventory | `data/gear_inventory.json` | runtime user data | dict with `items`, `maintenance`, `catalog_cache` | My Tackle Locker | gear intelligence, packing, reports | JSON |
| Gear settings | `data/gear_settings.json` | runtime config | dict of search/provider preferences | gear settings UI | gear search/import | JSON |
| Illinois waters | `data/illinois_waters.json` | repository reference | list of waterbody dicts | repository default | map, waters, reports | JSON |
| Manual waters | `data/manual_waters.json` | runtime user data | list of waterbody dicts | manual water UI | map, waters, reports | JSON |
| Reports index | `data/reports_index.json` | runtime generated index | list of saved report refs | report save flow | /reports, App Health | JSON |
| Species profiles | `data/species_profiles_v43.json` | repository reference | list of species dicts | versioned seed data | dashboard, rig guidance | JSON |
| Species settings | `data/species_settings_v431.json` | repository reference | dict of species settings | versioned seed data | species UI | JSON |
| Target profile | `data/target_profile.json` | runtime user data | dict of target species preferences | target selector UI | dashboard, Smart Intelligence | JSON |
| SQLite mirror | `data/angler_intel.sqlite3` | runtime mirror/foundation | SQLite database | mirror tools only | App Health, QC, migration foundation | JSON source of truth remains |

## Generated and derived sources

| Domain | Path | Notes |
| --- | --- | --- |
| Reports | `reports/*.json` | generated saved trip payloads |
| Report HTML | `reports/*.html` | generated printable views |
| Gear uploads | `data/gear_uploads/` | runtime user-uploaded media |
| Gear catalog cache | `data/gear_catalog_cache.json` | cache, not authority |

## Stable keys and duplicates

- Catches use a saved `id`.
- Waters use a saved `id`.
- Target profile uses a single current profile key.
- Gear items use a saved `id`.
- Reports use the report `id` from the report index and saved payload.
- Duplicate risk is highest in gear imports and manual waters; V7 validation should flag duplicates instead of merging them.

## Mirror coverage today

- SQLite still mirrors JSON and does not replace JSON production reads or writes.
- Existing v4.5 mirror tables remain intact.
- V7 adds migration metadata, provenance, and validation tables without changing authority.

