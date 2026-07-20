from __future__ import annotations

VERSION = "0007_v7_json_authority_defaults"
DESCRIPTION = "Persist explicit JSON authority defaults for every V7 domain"

UP_SQL = """
INSERT OR IGNORE INTO data_authority(domain, authority, note, updated_at) VALUES
('species', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('waters', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('target_profile', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('saved_locations', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('gear_inventory', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('gear_settings', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('gear_catalog_cache', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('catches', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('favorites', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('reports', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('reports_index', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('forecast', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP),
('intelligence', 'json', 'JSON remains authoritative during V7.1 mirror preparation.', CURRENT_TIMESTAMP);
"""
