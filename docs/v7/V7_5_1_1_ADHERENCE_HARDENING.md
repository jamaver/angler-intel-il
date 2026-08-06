# V7.5.1.1 Adherence Integrity Hardening

Trip completion remains a reports-authority operation. Before recording a
linked recommendation-adherence row, the service resolves the external
recommendations manifest and SQLite authority marker. A conflict, missing or
malformed manifest, or unavailable database records the trip completion but
returns an explicit unavailable adherence result.

The first completion sets `completed_at` and `updated_at`; later edits preserve
`completed_at` and update only `updated_at`. The schema adds `actual_trip_date`
and SQLite triggers enforcing supported outcome and adherence values, boolean
trip occurrence, nonnegative catch counts, and satisfaction from one through
five. No table rebuild is used.
