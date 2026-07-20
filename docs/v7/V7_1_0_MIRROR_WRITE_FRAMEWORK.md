# V7.1.0 Mirror-Write Framework

V7.1.0 adds shared infrastructure for future JSON-first SQLite mirror writes.
It does not enable a mirror for any production domain and does not change any
production reader or writer.

## Contract

1. A domain completes its existing JSON write first.
2. It may then call `mirror_after_json_write()` with a stable operation ID.
3. The SQLite callback runs in its own transaction.
4. SQLite errors are returned as `MirrorResult` values, logged, and recorded
   for App Health when the database is available.
5. A successful operation ID is idempotent. Retrying it does not rerun the
   callback or create duplicate rows.
6. Failure queues a reconciliation request; it never triggers an import or
   changes JSON automatically.

## Operational status

The `mirror_operations`, `mirror_domain_status`, and
`mirror_reconciliation_requests` tables are diagnostics and control records.
The authority-default migration records `data_authority = json` for every V7
domain. App Health only displays their status and never initiates a migration,
import, mirror, or authority transition.

Domain-specific mirror hooks begin in V7.1.1, beginning with target profiles.
