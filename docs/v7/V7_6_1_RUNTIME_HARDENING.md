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

If an already-parked V7.6 database differs from the active authoritative
database, do not merge or overwrite either copy. Use
`tools/v7_6_1_rebaseline_runtime.py --inspect` to document the difference, then
record a fresh verified active-backup baseline with explicit confirmation. The
parked copy remains historical and is deliberately excluded from automatic
rollback.
