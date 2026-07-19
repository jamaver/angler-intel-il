# V7 Gear Data Model

Before SQLite authority is introduced, the long-term gear model should be documented, validated, and backed up in JSON. The goal is to make gear relationships explicit before any authority flip.

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

Recommended fields:
- primary key id
- category / subtype
- brand / model / display_name
- owned status and retired metadata
- favorite flag
- source / source_name / source_url / provider metadata
- identifiers such as UPC, GTIN, SKU, ASIN, and MPN
- specifications and field_sources
- image / image_url / image_source / cached image state
- created_at / updated_at / retired_at
- maintenance dates and notes
- trip linkage and catch linkage references
- confidence fields for imported products

V7 should only flip authority after backup, export, and rollback gates are proven.
