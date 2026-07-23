from __future__ import annotations

VERSION = "0008_v7_manual_water_mirror_authority"
DESCRIPTION = "Register JSON-authoritative manual water mirror domain"

UP_SQL = """
INSERT OR IGNORE INTO data_authority(domain, authority, note, updated_at)
VALUES('manual_waters', 'json', 'JSON remains authoritative during V7.1 manual-water mirroring.', CURRENT_TIMESTAMP);
"""
