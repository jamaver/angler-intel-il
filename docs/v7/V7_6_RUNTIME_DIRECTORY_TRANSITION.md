# V7.6 Runtime Directory Transition

V7.6 moves mutable runtime state into `instance/` while retaining legacy paths
as compatibility symlinks. The transition tool first copies and hashes every
runtime item, validates JSON and SQLite integrity, parks the original source
under `instance/legacy_pre_v7_6/`, and only then activates each symlink.

The app is configured through a systemd drop-in with `AI_INSTANCE_DIR`,
`AI_SQLITE_DB_PATH`, and `AI_AUTHORITY_MANIFEST`. Reference datasets remain in
the repository. Runtime data, uploads, reports, backups, caches, and exports
remain ignored by Git.

Run only with the service stopped and a verified V7 backup available:

```bash
./venv/bin/python tools/v7_6_runtime_transition.py --dry-run --json
sudo systemctl stop angler-intel
./venv/bin/python tools/v7_6_runtime_transition.py --apply --confirm MOVE_RUNTIME_DATA --json
sudo install -D -m 0644 deploy/systemd/angler-intel-runtime.conf /etc/systemd/system/angler-intel.service.d/runtime.conf
sudo systemctl daemon-reload
sudo systemctl start angler-intel
```

The preserved `legacy_pre_v7_6` copy and verified runtime backup are rollback
inputs. Do not restore either over a running service.
