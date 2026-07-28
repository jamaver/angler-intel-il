# V7.3.5d Transactional Report Deletion and Restore

Authoritative report deletion is a soft lifecycle change: `trip_reports.status`
becomes `deleted` and `deleted_at` is recorded before any generated JSON or
HTML is removed. Artifact cleanup failure is reported in SQLite and App Health;
it never reactivates the report.

Trips are never deleted as a report side effect. They can later carry catches,
gear, outcomes, and report revisions.

`tools/v7_3_5_report_lifecycle.py` requires `--confirm` for delete, delete-all,
or restore. Restore marks the report active and regenerates compatibility JSON,
the report index, and printable HTML from the saved SQLite snapshot.

Production delete routes remain JSON-authoritative until V7.3.5e.
