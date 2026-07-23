# V7.1.4 Catch Mirror

V7.1.4 mirrors `data/catches.json` only after its JSON write succeeds. Catch
lists and catch-learning continue to read JSON. Catch IDs, labels, raw payloads,
gear references, and unresolved gear labels are retained without guessing links.

New catch-linked gear usage events mirror in the same SQLite transaction as the
catch mirror. JSON gear usage counters remain authoritative. Reconcile with:

```bash
./venv/bin/python tools/v7_1_reconcile.py --domain catches --json
```
