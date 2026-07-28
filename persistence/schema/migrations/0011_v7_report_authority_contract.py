from __future__ import annotations

VERSION = "0011_v7_report_authority_contract"
DESCRIPTION = "Prepare report lifecycle and compatibility artifact metadata"

# V7.3.5a intentionally adds storage only.  Existing report creation, reads,
# and deletion continue through their JSON/HTML paths until a later explicit
# reports authority transition.
UP_SQL = """
ALTER TABLE trip_reports ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active', 'archived', 'deleted'));
ALTER TABLE trip_reports ADD COLUMN deleted_at TEXT;
ALTER TABLE trip_reports ADD COLUMN snapshot_payload_json TEXT;
ALTER TABLE trip_reports ADD COLUMN authoritative_payload_hash TEXT;
ALTER TABLE trip_reports ADD COLUMN compatibility_export_hash TEXT;
ALTER TABLE trip_reports ADD COLUMN compatibility_export_status TEXT NOT NULL DEFAULT 'not_applicable'
    CHECK(compatibility_export_status IN ('not_applicable', 'pending', 'ok', 'failed'));
ALTER TABLE trip_reports ADD COLUMN compatibility_exported_at TEXT;
ALTER TABLE trip_reports ADD COLUMN html_export_hash TEXT;
ALTER TABLE trip_reports ADD COLUMN html_export_status TEXT NOT NULL DEFAULT 'not_applicable'
    CHECK(html_export_status IN ('not_applicable', 'pending', 'ok', 'failed'));
ALTER TABLE trip_reports ADD COLUMN html_exported_at TEXT;
ALTER TABLE trip_reports ADD COLUMN artifact_error TEXT;

CREATE INDEX IF NOT EXISTS idx_trip_reports_status_created
ON trip_reports(status, created_at DESC);
"""
