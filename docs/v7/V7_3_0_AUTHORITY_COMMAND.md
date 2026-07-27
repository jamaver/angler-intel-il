# V7.3.0 Authority Command

`tools/v7_authority.py` provides an operator-only preflight for one requested
domain. It checks a verified JSON backup manifest, canonical validation,
integrity, foreign keys, and current JSON authority.

V7.3.0 intentionally refuses `transition --execute`: a later V7.3.x task must
register exactly one proven domain writer/read contract before authority can
change. No web authority toggle exists.
