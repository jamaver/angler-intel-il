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
- Persisted target profile for dashboard and map
- Target-aware intelligence defaults and ranking prep

## v5.4 Map Data Expansion

- More reliable coordinates
- Region, county, and access metadata
- Stocked and special-case waters
- Manual waterbody review and cleanup tools
- Ranked waters for the selected target species

## v5.5 Realistic Icon System

- Waterbody markers with clearer visual categories
- More realistic fish and lure icon coverage
- Map and dashboard icon consistency
- Better fallback handling for missing icons

## v5.6 Waterbody Detail Panels

- Rich waterbody profile pages
- Target-fit context on selected waters
- Small map preview for mapped waters
- Clear action rail back to map and Smart Picks
- Cleaner presentation for species, habitat, access, and catch history

## v5.7 Waterbody Dataset Import/Export

- Export the editable manual waterbody dataset
- Import manual waters from JSON
- Keep starter waters untouched
- Refresh the local catalog after import

## v5.8 Structured Backup and Restore

- Restore structured data from app backups
- Pre-restore safety copy for JSON and SQLite data
- App Health restore controls for recent backups
- Path safety and backup naming checks

## v5.9 Modern UI Refresh

- Map-first dashboard shell
- More prominent target species and current conditions summary
- Nearby-water preview and faster map entry points
- Cleaner mobile layout and card hierarchy
- Stronger icon and action button presentation

## v6.1 Trip Plan Focus

- Selected waterbody steering on the dashboard
- Trip plan card with where, what, why, and next action
- Water-specific `/api/intel` requests from the main UI
- Focus-water persistence for faster repeat sessions
- Saved reports that can follow the selected waterbody
- Cleaner dashboard answers before the user opens the map

## v6.2 Dashboard Command Center

- Consolidated dashboard layout with a calmer primary flow
- Trip plan, Smart Intelligence, map brief, and supporting sections separated more clearly
- Secondary dashboard content collapsed into accordions
- Mobile-friendly command center structure

## v6.3 Smart Trip Forecast Date

- Smart Trip reports can focus on a selected 7-day forecast date
- Selected forecast day persists in saved report metadata
- Report conditions and outlook highlight the focused day

## v6.4 Report and Planning Polish

- Cleaner saved report cards with grouped trip-plan summaries
- Clearer report titles when users leave the title blank
- Compact report list previews for faster scanning
- Saved reports remain printable and PDF-friendly

## v6.5 Ranking and Explanation Tuning

- Clearer confidence labels and trust signals
- Grouped explanation sections for target fit, water fit, catch history, and presentation
- Less repeated reasoning between the dashboard and saved reports
- Stronger emphasis on why a recommendation is ranked where it is

## Follow-On

- Import/export waterbody datasets
- Backup and restore coverage for structured data
- Portable snapshots for migration and recovery

## Future

- Better lure recommendation logic
- Optional offline-friendly tile strategy
- Weather and water-condition overlays where practical
- Expanded Midwest fishing logic as the dataset grows
