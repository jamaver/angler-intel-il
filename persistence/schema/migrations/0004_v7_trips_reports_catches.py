from __future__ import annotations

VERSION = "0004_v7_trips_reports_catches"
DESCRIPTION = "Trips, reports, forecasts, catches, and catch gear tables"

UP_SQL = """
CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    zip TEXT,
    target_species TEXT,
    focus_waterbody_id TEXT,
    selected_forecast_date TEXT,
    selected_forecast_label TEXT,
    forecast_day_index INTEGER,
    started_at TEXT,
    updated_at TEXT,
    legacy_payload_json TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    source_key TEXT
);

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    id TEXT PRIMARY KEY,
    trip_id TEXT,
    source_path TEXT,
    source_hash TEXT,
    forecast_date TEXT,
    pretty_date TEXT,
    summary_json TEXT NOT NULL,
    legacy_payload_json TEXT NOT NULL,
    created_at TEXT,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS forecast_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT,
    forecast_snapshot_id TEXT,
    forecast_date TEXT NOT NULL,
    rating TEXT,
    score REAL,
    high_temp REAL,
    low_temp REAL,
    wind_mph REAL,
    cloud_cover REAL,
    legacy_payload_json TEXT NOT NULL,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY(forecast_snapshot_id) REFERENCES forecast_snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trip_reports (
    id TEXT PRIMARY KEY,
    trip_id TEXT,
    report_title TEXT,
    zip TEXT,
    selected_forecast_date TEXT,
    selected_forecast_label TEXT,
    forecast_day_index INTEGER,
    json_path TEXT,
    html_path TEXT,
    view_url TEXT,
    legacy_payload_json TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trip_gear (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT,
    report_id TEXT,
    gear_item_id TEXT,
    role TEXT NOT NULL,
    notes TEXT,
    legacy_label TEXT,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY(report_id) REFERENCES trip_reports(id) ON DELETE CASCADE,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trip_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT,
    report_id TEXT,
    outcome TEXT,
    notes TEXT,
    legacy_payload_json TEXT NOT NULL,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY(report_id) REFERENCES trip_reports(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catches (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    species TEXT,
    waterbody TEXT,
    lure TEXT,
    rig TEXT,
    notes TEXT,
    zip TEXT,
    gear_refs_json TEXT,
    gear_labels_json TEXT,
    legacy_payload_json TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    source_key TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS catch_gear (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catch_id TEXT NOT NULL,
    gear_item_id TEXT,
    gear_role TEXT,
    legacy_label TEXT,
    FOREIGN KEY(catch_id) REFERENCES catches(id) ON DELETE CASCADE,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_trips_zip ON trips(zip);
CREATE INDEX IF NOT EXISTS idx_trips_target_species ON trips(target_species);
CREATE INDEX IF NOT EXISTS idx_catches_species ON catches(species);
CREATE INDEX IF NOT EXISTS idx_catches_waterbody ON catches(waterbody);
CREATE INDEX IF NOT EXISTS idx_trip_reports_zip ON trip_reports(zip);
"""

