# Gear Catalog Sources

My Tackle Locker uses a layered search flow:

1. Local gear inventory
2. Cached catalog products
3. Optional online providers
4. Manual entry
5. Product URL import

Phase 1 intentionally keeps online search optional. Local and manual workflows must always work offline.

Supported source classes:

- Local locker items in `data/gear_inventory.json`
- Cached catalog products in `data/gear_catalog_cache.json`
- Structured product pages from user-pasted URLs
- Stubbed provider entries for future official integrations

Rules:

- Do not auto-import online results into the locker.
- Do not overwrite user edits.
- Prefer manufacturer specifications when they are available and trustworthy.
- Treat pricing and availability as lookup data, not durable specifications.
- Keep provider failures isolated so local gear search remains usable.

