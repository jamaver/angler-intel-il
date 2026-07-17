# V7.0 Migration Runbook

## Read-only audit

```bash
./venv/bin/python tools/v7_0_data_audit.py --json
```

## Dry-run migration

```bash
./venv/bin/python tools/v7_0_migrate.py --dry-run --all --json
```

## Apply to a caller-supplied database

```bash
./venv/bin/python tools/v7_0_migrate.py --apply --db /tmp/angler-v7-preview.sqlite3 --all --backup-manifest backups/latest_v7_runtime_backup_manifest.json --json
```

## Validation

```bash
./venv/bin/python tools/v7_0_validate.py --db data/angler_intel.sqlite3 --json
```

## Backup

```bash
./venv/bin/python tools/v7_0_backup.py --label pre_v7_0 --json
```

## Restore rehearsal

```bash
./venv/bin/python tools/v7_0_restore_rehearsal.py backups/angler_intel_v7_runtime_backup_YYYYMMDD_HHMMSS.zip --json
```

## Gates

- JSON hashes must remain unchanged.
- Migration checksums must not drift.
- Validation must be exact for clean fixtures.
- Backup verification must pass before any operator apply step.

