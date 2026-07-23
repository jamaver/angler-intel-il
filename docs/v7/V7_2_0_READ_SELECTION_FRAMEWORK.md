# V7.2.0 Read-Selection Framework

V7.2.0 introduces reusable JSON and SQLite repository interfaces without
changing production readers. Supported modes are:

- `json`: current production behavior.
- `sqlite`: strict SQLite result, with no hidden fallback.
- `sqlite_with_json_fallback`: SQLite first, then JSON only on an error.
- `compare_json`: reads both, returns JSON, and records canonical differences.

The framework currently includes target-profile reference repositories for QC
and later V7.2.1 adoption. Flask routes do not call them in V7.2.0.

SQLite authority remains disabled. V7.2.1 requires V7.1 soak evidence and a
domain-specific production read change with JSON fallback diagnostics.
