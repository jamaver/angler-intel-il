# V7.0 Runtime Paths

V7.0 documents a future `instance/` layout but does not activate it.

## Future layout

```text
instance/
  gear_inventory.json
  manual_waters.json
  target_profile.json
  gear_settings.json
  exports/
  uploads/
  cache/
```

## Current rule

- Production still reads and writes the legacy JSON locations.
- The migration foundation uses the runtime path resolver only in tools and validation.
- When both legacy and `instance/` paths exist and differ, the tool should stop and require operator action.

