from __future__ import annotations

VERSION = "0003_v7_gear"
DESCRIPTION = "Gear inventory and gear intelligence tables"

UP_SQL = """
CREATE TABLE IF NOT EXISTS gear_items (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    subtype TEXT,
    brand TEXT,
    model TEXT,
    display_name TEXT,
    status TEXT NOT NULL DEFAULT 'owned',
    favorite INTEGER NOT NULL DEFAULT 0,
    retired_at TEXT,
    notes TEXT,
    source_kind TEXT,
    source_name TEXT,
    source_url TEXT,
    provider TEXT,
    provider_product_id TEXT,
    confidence TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    legacy_payload_json TEXT NOT NULL,
    field_sources_json TEXT,
    specifications_json TEXT,
    identifiers_json TEXT,
    image_path TEXT,
    image_url TEXT,
    image_source TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS rod_specs (
    gear_item_id TEXT PRIMARY KEY,
    length_ft REAL,
    length_label TEXT,
    power TEXT,
    action TEXT,
    pieces INTEGER,
    lure_weight_min_oz REAL,
    lure_weight_max_oz REAL,
    line_rating_min_lb REAL,
    line_rating_max_lb REAL,
    technique_tags_json TEXT,
    species_tags_json TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reel_specs (
    gear_item_id TEXT PRIMARY KEY,
    reel_type TEXT,
    gear_ratio REAL,
    max_drag_lb REAL,
    line_capacity TEXT,
    weight_oz REAL,
    handedness TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS line_specs (
    gear_item_id TEXT PRIMARY KEY,
    line_type TEXT,
    strength_lb REAL,
    diameter_equivalent TEXT,
    color TEXT,
    length_yd REAL,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lure_specs (
    gear_item_id TEXT PRIMARY KEY,
    lure_type TEXT,
    color TEXT,
    weight_oz REAL,
    hook_size TEXT,
    depth_min_ft REAL,
    depth_max_ft REAL,
    quantity INTEGER,
    technique_tags_json TEXT,
    species_tags_json TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS terminal_tackle_specs (
    gear_item_id TEXT PRIMARY KEY,
    subtype TEXT,
    size TEXT,
    weight_oz REAL,
    hook_size TEXT,
    quantity INTEGER,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gear_item_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gear_item_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    source_path TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS product_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gear_item_id TEXT,
    provider TEXT,
    source_name TEXT,
    source_url TEXT,
    provider_product_id TEXT,
    retrieved_at TEXT,
    confidence TEXT,
    price REAL,
    availability TEXT,
    raw_provider_data_json TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS gear_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gear_item_id TEXT NOT NULL,
    image_path TEXT,
    image_url TEXT,
    image_source TEXT,
    locally_cached INTEGER NOT NULL DEFAULT 0,
    retrieved_at TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gear_maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gear_item_id TEXT NOT NULL,
    maintenance_type TEXT,
    due_at TEXT,
    last_done_at TEXT,
    notes TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gear_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gear_item_id TEXT NOT NULL,
    trip_id TEXT,
    catch_id TEXT,
    used_at TEXT,
    notes TEXT,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gear_setups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    species_id TEXT,
    notes TEXT,
    legacy_payload_json TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS gear_setup_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gear_setup_id TEXT NOT NULL,
    gear_item_id TEXT NOT NULL,
    role TEXT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(gear_setup_id) REFERENCES gear_setups(id) ON DELETE CASCADE,
    FOREIGN KEY(gear_item_id) REFERENCES gear_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gear_items_category ON gear_items(category);
CREATE INDEX IF NOT EXISTS idx_gear_items_status ON gear_items(status);
CREATE INDEX IF NOT EXISTS idx_gear_items_favorite ON gear_items(favorite);
CREATE INDEX IF NOT EXISTS idx_gear_item_tags_tag ON gear_item_tags(tag);
"""

