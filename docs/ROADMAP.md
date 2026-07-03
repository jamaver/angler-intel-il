# Angler Intel Roadmap

## Current Direction

Angler Intel is moving toward a map-first, waterbody-centered fishing intelligence dashboard. The goal is to help decide where to fish, what species to target, what lure or rig to use, and why.

## Near-Term

- v4.9.2 Map usability and manual waters
- v4.9.3 Water Intel linkage and selected-water intelligence
- v4.9.4 Map filters and marker polish
- v4.9.5 Water Intel panel refinement
- v4.9.6 Icon and asset realism pass

## v5.0 Modern UI

- Map-first dashboard layout
- Target species selector in the main experience
- Selected water drives Smart Intelligence
- Better mobile behavior on map and detail panels
- Clear separation between user-facing product and App Health maintenance

## v5.1 SQLite Authority Migration

- Inspect JSON shapes and current waterbody records
- Design durable SQLite tables for waterbodies, catches, favorites, reports, and intelligence snapshots
- Add migration and rollback tooling
- Keep JSON export and validation in place
- Flip authority only after deliberate migration and backup coverage

## v5.2 Catch Learning

- Catch-history summaries by species and waterbody
- Confidence weighting that respects sample size
- Better local pattern learning from catch logs
- Optional waterbody context on catch entries

## v5.3 Target Species Profiles

- User-configurable target species
- Favorite species and current trip target
- Species-specific lure, rig, and seasonal guidance

## v5.4 Map Data Expansion

- More reliable coordinates
- Region, county, and access metadata
- Stocked and special-case waters
- Manual waterbody review and cleanup tools

## v5.5 Data Import and Export

- Import/export waterbody datasets
- Backup and restore coverage for structured data
- Portable snapshots for migration and recovery

## Future

- Better lure recommendation logic
- Optional offline-friendly tile strategy
- Weather and water-condition overlays where practical
- Expanded Midwest fishing logic as the dataset grows
