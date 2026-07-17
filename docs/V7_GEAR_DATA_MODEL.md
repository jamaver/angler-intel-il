# V7 Gear Data Model

Before SQLite authority is introduced, the long-term gear model should be documented and backed up in JSON.

Proposed core entities:
- gear_items
- rods
- reels
- lines
- lures
- terminal_tackle
- gear_setups
- trip_gear
- catch_gear
- gear_maintenance
- product_sources
- gear_images
- gear_usage
- trip_packing
- catch_gear_links

Relationships:
- one setup contains rod / reel / line / leader / lure / terminal items
- one trip can use multiple setups
- one catch can reference the gear used
- one gear item can be reused across many trips and catches
- one gear item can track last_used, trips_used, catches_logged, and maintenance metadata

V7 should only flip authority after backup, export, and rollback gates are proven.
