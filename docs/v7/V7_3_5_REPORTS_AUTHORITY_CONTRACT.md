# V7.3.5 Reports and Trips Authority Contract

## V7.3.5a status

This contract prepares report authority work only. `reports` and `reports_index`
remain JSON-authoritative, and generated printable HTML remains derived from the
JSON snapshot. Existing report creation, list, view, download, and deletion
routes are unchanged by this subtask.

## Authoritative model after transition

SQLite will own report identity, report metadata, report status, deterministic
trip relationships, and the complete saved snapshot payload. The report row will
use `status` values of `active`, `archived`, or `deleted`; deletion is a soft
state with `deleted_at` rather than an immediate row removal.

A report maps to a trip by `trip_id`. Legacy and first-generation reports use a
deterministic same-ID trip. Reports never automatically delete a trip: a trip
may retain catches, gear, outcomes, feedback, or future report revisions.

## Future V7.3.5b save transaction

1. Build and validate the complete wrapped report snapshot.
2. Begin one SQLite transaction.
3. Upsert the deterministic trip and active report metadata.
4. Store the complete snapshot and its authoritative canonical hash.
5. Commit SQLite.
6. Export the compatibility JSON snapshot.
7. Generate printable HTML from the committed snapshot.
8. Record JSON and HTML artifact status and hashes separately.

A SQLite transaction failure fails report creation. JSON or HTML artifact
failure does not erase the committed report; it records a repairable artifact
failure for App Health and the later repair command.

## Read and repair behavior

V7.3.5c will list and open active reports from SQLite snapshots. Missing JSON
or HTML artifacts will be regenerated from the authoritative snapshot. A
temporary JSON fallback is limited to unimported legacy reports and must be
visible in diagnostics.

## Delete behavior

V7.3.5d will mark the report `deleted` in SQLite first. JSON and HTML cleanup
occurs only after that authoritative operation succeeds. Cleanup failure is an
artifact error, not a reason to restore the report. The trip remains intact.

## Transition guard

Once `reports` is explicitly SQLite-authoritative, the old JSON-to-SQLite
mirror is rejected. V7.3.5a does not set report authority to SQLite.
