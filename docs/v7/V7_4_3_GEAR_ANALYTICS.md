# V7.4.3 Gear Analytics

V7.4.3 adds `GET /api/analytics/gear`, a read-only SQLite summary of owned
gear, recorded usage events, catch-linked gear, underused items, and dated
maintenance records.

The endpoint distinguishes logged catch links from success or effectiveness.
It does not infer catch outcomes by saved setup because historical catches do
not yet carry deterministic setup IDs. Underused gear simply has no recorded
usage event or catch link; it is not judged unsuitable.

Gear Intelligence and its recommendations are unchanged. V7.4.3 only makes
the stored gear history available for later, restrained UI use.
