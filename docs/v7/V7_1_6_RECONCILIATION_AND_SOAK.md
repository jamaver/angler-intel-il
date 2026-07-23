# V7.1.6 Reconciliation and Soak Gate

V7.1.6 keeps JSON authoritative while all supported production write domains
mirror into SQLite. Operators can reconcile one domain or all domains:

```bash
./venv/bin/python tools/v7_1_reconcile.py --domain reports --json
./venv/bin/python tools/v7_1_reconcile.py --all --json
```

An exact reconciliation resolves pending mirror recovery requests for that
domain. App Health displays pending recovery work and stale running operations.
It does not run imports or change authority.

This is a soak gate, not a read cutover. V7.2 remains blocked until normal
use, service restarts, and deliberate SQLite failure recovery show zero
unexplained drift for every mirrored domain.
