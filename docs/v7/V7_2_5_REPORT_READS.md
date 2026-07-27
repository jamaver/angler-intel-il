# V7.2.5 Report Reads

The JSON report index is mirrored as a SQLite comparison envelope. Report lists,
snapshot loading, and printable output remain JSON/filesystem based. Controlled
SQLite fallback testing requires `AI_ENABLE_V7_STAGED_READS=1`.
