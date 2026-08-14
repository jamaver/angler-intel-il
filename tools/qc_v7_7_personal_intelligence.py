#!/usr/bin/env python3
"""Focused regression QC for V7.7 shadow-only personal intelligence."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.personal_evidence import build_contextual_personal_evidence, build_forecast_calibration, contextual_shadow_adjustment
from intelligence.species_condition_scoring import explainable_components, species_condition_components, weather_trend_intelligence
from persistence.connection import connect
from persistence.migrations import migrate


def seed(db: Path) -> None:
    with connect(db) as conn:
        migrate(conn, db_path=str(db))
        conn.execute("INSERT INTO trips(id, title, legacy_payload_json) VALUES ('t', 'QC trip', '{}')")
        conn.execute("INSERT INTO intelligence_snapshots(id, summary_json, legacy_payload_json) VALUES ('s', '{}', '{}')")
        conn.execute("INSERT INTO recommendations(id, intelligence_snapshot_id, target_species, lure_type, score, reasons_json, caution_json, legacy_payload_json) VALUES ('r', 's', 'Largemouth Bass', 'jig', 82, '[]', '[]', '{}')")
        for index, (catch_count, adherence, water, species) in enumerate(((1, 'exact', 'Lake A', 'Largemouth Bass'), (0, 'partial', 'Lake A', 'Largemouth Bass'), (1, 'changed_water', 'Lake B', 'Largemouth Bass'), (0, 'did_not_fish', 'Lake A', 'Largemouth Bass')), 1):
            rid = f'report-{index}'
            conn.execute("INSERT INTO trip_reports(id, trip_id, status, legacy_payload_json) VALUES (?, 't', 'active', '{}')", (rid,))
            occurred = 0 if adherence == 'did_not_fish' else 1
            conn.execute("""INSERT INTO trip_outcomes(trip_id, report_id, outcome, notes, legacy_payload_json, trip_occurred,
                         catch_count, actual_waterbody, actual_target_species, completed_at, updated_at)
                         VALUES ('t', ?, 'completed', '', '{}', ?, ?, ?, ?, ?, ?)""",
                         (rid, occurred, catch_count, water, species, f'2026-07-0{index}T09:00:00+00:00', f'2026-07-0{index}T09:00:00+00:00'))
            outcome_id = conn.execute("SELECT id FROM trip_outcomes WHERE report_id=?", (rid,)).fetchone()[0]
            conn.execute("""INSERT INTO recommendation_adherence(recommendation_id, trip_outcome_id, trip_id, report_id, adherence,
                         trip_occurred, outcome, catch_count, created_at, updated_at) VALUES ('r', ?, 't', ?, ?, ?, 'completed', ?, '2026-07-01T00:00:00+00:00', '2026-07-01T00:00:00+00:00')""",
                         (outcome_id, rid, adherence, occurred, catch_count))
        conn.commit()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='angler-v7-7-qc-') as folder:
        db = Path(folder) / 'analytics.sqlite3'
        seed(db)
        context = build_contextual_personal_evidence(db, species='Largemouth Bass', waterbody='Lake A', season='summer', lure_family='jig')
        assert context['comparable_trips'] == 2 and context['successes'] == 1
        assert context['match_level'].startswith('species+')
        assert context['quality'] == 'none'
        shadow = contextual_shadow_adjustment(context)
        assert shadow['proposed_adjustment'] == 0 and shadow['live_applied'] is False
        calibration = build_forecast_calibration(db)
        band = next(row for row in calibration['buckets'] if row['band'] == '80-89')
        assert band['followed_trips'] == 2 and band['catch_positive_trips'] == 1
        bass = species_condition_components('Largemouth Bass', temp_f=68, wind_mph=9, pressure_inhg=29.9, cloud_cover=60, season='summer', water_type='lake')
        trout = species_condition_components('Rainbow Trout', temp_f=68, wind_mph=9, pressure_inhg=29.9, cloud_cover=60, season='summer', water_type='lake')
        assert bass['score'] != trout['score']
        assert 0 <= explainable_components(bass)['score'] <= 100
        trend = weather_trend_intelligence([{'pressure':30.1, 'temp':68}, {'pressure':29.9, 'temp':72}])
        assert 'falling-pressure pattern' in trend['signals']
        assert weather_trend_intelligence([])['available'] is False
        with connect(db, read_only=True) as conn:
            assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert list(conn.execute('PRAGMA foreign_key_check')) == []
    source = (ROOT / 'intelligence' / 'personal_evidence.py').read_text(encoding='utf-8')
    assert 'live_applied' in source and "changed-plan" in source
    print('PASS: V7.7 personal intelligence QC')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
