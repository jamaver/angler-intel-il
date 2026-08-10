# V7.6.1 Runtime Hardening

V7.6.1 retains the V7.6 `instance/` layout and does not change authority.
SQLite relocation verification uses canonical table content hashes, row counts,
integrity checks, and foreign-key checks rather than file-page hashes.

`tools/v7_6_runtime_transition.py` journals each object as `pending`, `copied`,
`verified`, `parked`, `linked`, `complete`, or `failed`. Operators must use an
explicit confirmation to resume or roll back. Rollback refuses to overwrite a
runtime target that has diverged from its parked legacy copy.

The canonical database environment variable is `AI_SQLITE_DB_PATH`.
`AI_SQLITE_PATH` remains a compatibility alias only. ZIP extraction uses
filesystem containment checks, rejects absolute and traversal entries, and is
shared by backup verification and restore rehearsal.
