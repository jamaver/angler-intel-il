# V7.3.6 Persisted Recommendation Authority

V7.3.6 transitions only persisted intelligence snapshots, recommendation
records, explanations, and feedback to SQLite authority. Live Smart
Intelligence and `/api/recommendations` remain application-computed.

Active SQLite-authoritative report snapshots are reconciled into deterministic
`<report-id>-intel` and `<report-id>-best-bet` records before cutover. The
report JSON snapshot remains a compatibility artifact owned by the reports
domain; no separate recommendation JSON file is introduced.

Use `tools/v7_3_6_recommendation_reconcile.py --apply`, create a verified V7
runtime backup, then run `tools/v7_authority.py transition --domain
recommendations ... --confirm-domain recommendations --execute`. If either
authority marker disagrees after activation, writes fail closed. The only
write endpoint added by this release records user feedback against an existing
SQLite recommendation; it never alters live recommendation calculation.
