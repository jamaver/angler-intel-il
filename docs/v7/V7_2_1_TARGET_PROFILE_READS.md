# V7.2.1 Target-Profile Reads

The target-profile reader now defaults to `compare_json`: it reads JSON for
the application response and compares the SQLite mirror for diagnostics.
JSON remains authoritative.

An operator may opt into staged fallback testing only through systemd or the
process environment:

```text
AI_TARGET_PROFILE_READ_SOURCE=sqlite_with_json_fallback
AI_ENABLE_V7_STAGED_READS=1
```

There is no web authority control. `sqlite` strict mode and fallback mode are
for controlled validation only; any failed SQLite read falls back only in the
explicit fallback mode. App Health shows the most recent comparison result.
