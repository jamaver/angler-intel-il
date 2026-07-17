# V7.0 Backup and Rollback

## Backup requirements

- Use `sqlite3.Connection.backup()` for the database copy.
- Do not rely on copying a live WAL database file as the only backup method.
- Include authoritative JSON runtime data, report JSON files, gear uploads, and the SQLite copy.
- Keep caches and generated HTML optional, not authoritative.

## Restore rehearsal

- Restore only to a temporary directory.
- Validate manifest hashes.
- Validate JSON parsing.
- Verify SQLite integrity and foreign keys.
- Compare restored exports against the restored source data.

## Rollback rule

- Live rollback is an operator action.
- V7.0 does not automate production rollback.

