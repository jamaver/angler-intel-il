# V7.2.2 Gear Inventory Reads

The gear mirror now retains a complete inventory envelope in SQLite alongside
the normalized gear tables. This allows canonical comparison without losing
legacy fields such as maintenance and catalog-cache metadata.

The live locker still returns JSON. `AI_GEAR_INVENTORY_READ_SOURCE` follows the
same guarded modes as target profiles; SQLite or fallback reads additionally
require `AI_ENABLE_V7_STAGED_READS=1`.

SQLite authority remains disabled.
