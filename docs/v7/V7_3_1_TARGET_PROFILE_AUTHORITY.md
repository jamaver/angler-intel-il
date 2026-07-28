# V7.3.1 Target Profile SQLite Authority

## Scope

V7.3.1 transitions only the `target_profile` domain after an operator runs the
explicit authority command. All other V7 domains remain JSON-authoritative.

## Write contract

After transition, target-profile updates use this order:

1. Validate and write the complete profile in one SQLite transaction.
2. Mark the SQLite compatibility-export state as pending.
3. Atomically replace `data/target_profile.json` with a compatibility export.
4. Mark the export state as successful.

SQLite failure fails the update. A JSON export failure leaves SQLite
authoritative and records a failed export state for operator recovery; it never
reverts authority or writes independent JSON state.

## Safety rules

- The normal JSON-to-SQLite target-profile mirror refuses to run after this
  domain becomes SQLite-authoritative.
- `target_profile.json` remains a compatibility export for legacy tools.
- The transition command requires a verified runtime backup, clean canonical
  validation, integrity checks, foreign-key checks, `--confirm-domain
  target_profile`, and `--execute`.
- No web route can change authority.
- Any other domain remains `json`.

## Operator command

```bash
./venv/bin/python tools/v7_authority.py transition \
  --domain target_profile \
  --backup-manifest backups/<verified-runtime-manifest>.manifest.json \
  --confirm-domain target_profile \
  --execute
```

Before transition, run the same command with `preflight` and inspect its JSON
output. After transition, confirm `data_authority.target_profile = sqlite`,
load `/api/target-profile`, and inspect the App Health V7 diagnostics.

## Rollback

Live rollback remains an operator action. Restore the verified runtime backup,
validate it in temporary paths, then explicitly reset authority only through a
future documented rollback command. V7.3.1 does not provide an automatic web
rollback control.
