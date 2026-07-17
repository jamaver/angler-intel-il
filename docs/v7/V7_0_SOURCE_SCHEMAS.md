# V7.0 Source Schemas

This document records the current JSON source shapes before the V7 SQLite foundation is activated.

## Catches

- File: `data/catches.json`
- Shape: list of dicts
- Common fields: `id`, `timestamp`, `zip`, `species`, `lure`, `waterbody`, `notes`
- Optional fields: gear refs/labels when present, trip notes, weather context

## Favorites

- File: `data/favorites.json`
- Shape: list of dicts
- Common fields: `name`, `zip`
- Optional fields: notes, city, county, state

## Gear inventory

- File: `data/gear_inventory.json`
- Shape: dict
- Top-level keys: `version`, `updated_at`, `items`, `maintenance`, `catalog_cache`
- Item keys include: `id`, `category`, `brand`, `model`, `display_name`, `status`, `favorite`, `notes`, `image`, `image_url`, `provider`, `provider_product_id`, `identifiers`, `specifications`
- Known gear categories: rod, reel, line, lure, terminal

## Gear settings

- File: `data/gear_settings.json`
- Shape: dict
- Key fields: search scope default, online lookup enable flag, enabled providers, remote image policy, cache policy

## Waters

- Files: `data/illinois_waters.json`, `data/manual_waters.json`
- Shape: list of dicts
- Common fields: `id`, `name`, `type`, `city`, `county`, `state`, `lat`, `lon`, `species`, `species_ids`, `access`, `habitat`, `notes`, `confidence`
- Manual waters additionally include: `manual`, `source`, `favorite`, `stocked_trout`, `catch_history_count`, `created_at`

## Reports

- File: `data/reports_index.json`
- Shape: list of dicts
- Common fields: `id`, `title`, `zip`, `created`, `json_file`, `html_file`, `json_url`, `html_url`, `view_url`, forecast metadata
- Per-report JSON files in `reports/*.json` store `meta`, `payload`, and `summary`
- HTML files in `reports/*.html` are generated presentation artifacts

## Species reference

- Files: `data/species_profiles_v43.json`, `data/species_settings_v431.json`
- Shapes: list and dict
- Key fields: `id`, `name`, `group`, `best_lures`, `habitat`, `quick_pattern`, `tier`, `enabled`

## Target profile

- File: `data/target_profile.json`
- Shape: dict
- Key fields: `default_target_species`, `current_trip_target`, `favorite_species`, `updated_at`

## Timestamp formats

- Current runtime data mixes local formatted timestamps and ISO-8601 values.
- V7 normalization should preserve the original timestamp payload while storing canonical UTC timestamps alongside it.

