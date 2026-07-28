# V7.3.3 Manual Waters SQLite Authority

Only user-managed `data/manual_waters.json` transitions in V7.3.3. The base
Illinois water catalog remains JSON reference data, and map reads merge that
base catalog with SQLite-authoritative manual waters.

Manual-water create, import, and update operations commit the complete custom
water payload to SQLite first, then atomically write a compatibility export to
`data/manual_waters.json`. The prior JSON mirror refuses to run after this
transition. Invalid-coordinate historical records remain persisted and are
handled as map-validation state rather than silently deleted.

No web page can change authority. Use the verified-backup preflight and
operator-only command in `tools/v7_authority.py` for transition.
