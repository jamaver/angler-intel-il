# V7.4.1 Catch And Water Analytics

V7.4.1 adds `GET /api/analytics/catch-water`, a read-only companion to the
V7.4.0 query layer. It reports recorded catch frequency by species, waterbody,
lure, daypart, and season. Every response includes the date range, sample
quality, confidence label, and missing-data counts.

## Boundaries

Waterbody results are labeled as recorded catch frequency, not productivity.
The API deliberately reports `catch_rate_by_trip` and
`no_catch_trip_frequency` as unavailable because historical catches do not
have deterministic trip IDs and completed no-catch outcomes are not yet
complete enough for a defensible denominator.

The endpoint makes no changes to live Smart Intelligence, water ranking, or
the dashboard. A later V7.4 UI task can surface these summaries only after the
data-quality labels have been reviewed.
