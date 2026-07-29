# V7.4.0 Analytics Query Layer

V7.4.0 introduces a read-only, SQLite-backed personal analytics query layer.
It reads only the SQLite-authoritative `catches` domain and does not alter live
Smart Intelligence, ranking, dashboard layout, or catch writes.

## API

`GET /api/analytics/personal` accepts optional `date_from`, `date_to`,
`species`, `waterbody`, and `limit` query parameters. Results are bounded to
5,000 matching catches and include top species, waters, lures, dayparts,
missing-data counts, a date range, and a sample-quality label.

The layer reports frequency, not catch rate. It intentionally does not claim
productivity or no-catch performance until trips and outcomes are sufficiently
complete for a denominator. It uses built-in SQLite and Python collections;
no dataframe or external analytics dependency is introduced.

## Safety

The endpoint is available only while the catches authority resolves to healthy
SQLite. It is read-only and writes no cached source data. If the authoritative
store is unavailable or its authority markers conflict, the endpoint returns a
clear unavailable response rather than falling back silently to legacy JSON.

## Next

V7.4.1 can add carefully labeled catch and water analytics surfaces after the
query output has been reviewed. Any recommendation tuning remains a later,
separate step.
