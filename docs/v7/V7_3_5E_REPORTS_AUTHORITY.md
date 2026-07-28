# V7.3.5e Reports and Trips Authority Transition

This transition changes only `reports` authority. SQLite becomes authoritative
for report identity, metadata, trip relationships, lifecycle state, and the
complete saved snapshot. `reports_index.json` and report JSON/HTML files become
compatibility/generated artifacts.

Before transition, run `tools/v7_3_5_report_reconcile.py --apply` to hydrate
complete legacy snapshots, create a verified runtime backup, run drift and
integrity validation, and run the restore rehearsal. Then run the explicit
`tools/v7_authority.py transition --domain reports ... --confirm-domain reports
--execute` command.

The command activates SQLite, regenerates and verifies compatibility artifacts,
then atomically updates the external authority manifest. If artifact export or
manifest update fails, it leaves a fail-closed recovery-required state rather
than resuming legacy JSON writes.
