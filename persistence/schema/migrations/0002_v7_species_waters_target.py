from __future__ import annotations

VERSION = "0002_v7_species_waters_target"
DESCRIPTION = "Species, waters, saved locations, and target profile tables"

UP_SQL = """
CREATE TABLE IF NOT EXISTS species (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    group_name TEXT,
    tier TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    legacy_payload_json TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    source_key TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS species_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    source_path TEXT,
    FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS waterbodies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    water_type TEXT,
    city TEXT,
    county TEXT,
    state TEXT,
    lat REAL,
    lon REAL,
    source_kind TEXT NOT NULL DEFAULT 'json',
    source_path TEXT,
    source_hash TEXT,
    source_key TEXT,
    manual INTEGER NOT NULL DEFAULT 0,
    favorite INTEGER NOT NULL DEFAULT 0,
    stocked_trout INTEGER NOT NULL DEFAULT 0,
    catch_history_count INTEGER NOT NULL DEFAULT 0,
    confidence TEXT,
    access_json TEXT,
    habitat_json TEXT,
    species_json TEXT,
    species_ids_json TEXT,
    notes TEXT,
    legacy_payload_json TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS waterbody_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waterbody_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    source_path TEXT,
    FOREIGN KEY(waterbody_id) REFERENCES waterbodies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS waterbody_species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waterbody_id TEXT NOT NULL,
    species_id TEXT NOT NULL,
    confidence TEXT,
    source_path TEXT,
    FOREIGN KEY(waterbody_id) REFERENCES waterbodies(id) ON DELETE CASCADE,
    FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS waterbody_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waterbody_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    source_path TEXT,
    FOREIGN KEY(waterbody_id) REFERENCES waterbodies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS saved_locations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    zip TEXT,
    city TEXT,
    county TEXT,
    state TEXT,
    notes TEXT,
    legacy_payload_json TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    source_key TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS target_profiles (
    id TEXT PRIMARY KEY,
    default_target_species TEXT,
    current_trip_target TEXT,
    favorite_species_json TEXT,
    legacy_payload_json TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    source_key TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS target_profile_species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_profile_id TEXT NOT NULL,
    species_id TEXT NOT NULL,
    preference TEXT,
    source_path TEXT,
    FOREIGN KEY(target_profile_id) REFERENCES target_profiles(id) ON DELETE CASCADE,
    FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_species_name ON species(name);
CREATE INDEX IF NOT EXISTS idx_waterbodies_type ON waterbodies(water_type);
CREATE INDEX IF NOT EXISTS idx_waterbodies_favorite ON waterbodies(favorite);
CREATE INDEX IF NOT EXISTS idx_waterbody_species_species ON waterbody_species(species_id);
CREATE INDEX IF NOT EXISTS idx_saved_locations_zip ON saved_locations(zip);
"""

