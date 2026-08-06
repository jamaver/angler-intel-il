# V7.5.1.2 Verified App Health Backups

App Health creates only `tools.v7_0_backup.create_backup` archives. Each listed
V7 archive has a verified manifest, SHA-256, SQLite integrity result, and
foreign-key result. The UI supports archive/manifest download, temporary
restore rehearsal, and local deletion. Legacy archives remain download/delete
only and are clearly labeled as not verified for SQLite authority.

Live directory-replacement restore is deliberately disabled. A live recovery
requires the V7 maintenance runbook and an operator-controlled restore flow.
