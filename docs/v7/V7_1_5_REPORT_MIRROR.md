# V7.1.5 Report Mirror

Saved report JSON/index writes mirror into normalized trip/report tables only
after the existing filesystem and JSON writes succeed. Existing report views and
printable output remain JSON/filesystem based. Reconcile with:

```bash
./venv/bin/python tools/v7_1_reconcile.py --domain reports --json
```
