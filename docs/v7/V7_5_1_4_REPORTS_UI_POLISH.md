# V7.5.1.4 Reports UI Polish

Saved Reports now presents compact trip, plan-adherence, and optional Google
Drive export state without adding a new dashboard surface. A report card shows
at most four short status badges so the list remains readable.

The completion dialog records the actual trip date, optional start and end
times, actual water and target species (with an Other option), and saved gear
references. These fields are optional where the existing completion service
permits them. If a trip did not occur, outcome-specific controls are disabled.

Reports remain SQLite-authoritative. Removing a report removes it from Saved
Reports and may remove generated local artifacts; its authoritative history is
soft-deleted rather than represented to the user as an irreversible hard
delete. Google Drive remains an optional secondary export target. A Drive
failure does not affect the local report, trip completion, or recommendation
adherence records.

Recommendation adherence remains a direct user choice only. It is never
inferred from catch records, and this release does not change live
recommendation ranking.
