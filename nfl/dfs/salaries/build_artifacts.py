"""Emit the DK Week-2 universe, reconciliation and readiness artifacts.

    python3.12 nfl/dfs/salaries/build_artifacts.py --write

WHAT IT REFUSES TO EMIT

A projection. No board sealed for 2026 week 2 -- `artifact_sealing` blocks
every game on `current_season_input_freshness` -- so there is no forecast to
join a salary to. The join therefore carries COVERAGE (can this system project
this player at all) and leaves every distribution field null with
`DK_ELIGIBLE_MODEL_UNSUPPORTED` or `FORECAST_NOT_SEALED` as the reason.

Coverage is read from the rehearsal runs' draw manifests, which record
`row_ids` on a `gsis_id` row axis. That is a statement about the model's REACH
and it is not a forecast: the runs it comes from are REFUSED runs, and a number
taken out of a refused run and printed beside a salary would be exactly the
"absence read as success" defect this project exists downstream of.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import io
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.dfs.salaries import dk_universe as DK                 # noqa: E402
from nfl.dfs.salaries import identity as ID                    # noqa: E402

SPEC_VERSION = 'dk-week2-artifacts-1'
OUT_DIR = _REPO / 'nfl' / 'dfs' / 'salaries'

#: Where model coverage is read from. Declared rather than globbed blindly so
#: the artifact records which runs answered the question.
REHEARSAL_GLOB = '/tmp/claude-0/rehearsal_cand2/*/player_draws_manifest.json'

DISTRIBUTION_FIELDS = ('mean', 'median', 'p05', 'p10', 'p25', 'p50', 'p75',
                       'p90', 'p95', 'p_zero', 'mcse_mean', 'draws_ref')


def model_coverage(pattern=REHEARSAL_GLOB) -> dict:
    """gsis_id -> the run that modelled him, from the draw manifests."""
    per_game, by_id, digests = {}, {}, {}
    for m in sorted(glob.glob(pattern)):
        d = json.loads(pathlib.Path(m).read_text())
        gid, rid = d.get('game_id'), d.get('run_id')
        ids = set()
        for lname, l in (d.get('layers') or {}).items():
            if l.get('row_axis') == 'gsis_id':
                ids |= set(l.get('row_ids') or [])
        per_game[gid] = {'run_id': rid, 'n_modelled': len(ids),
                         'content_digest': d.get('content_digest'),
                         'n_draws': d.get('n_draws')}
        digests[gid] = d.get('content_digest')
        for i in ids:
            by_id[i] = {'game_id': gid, 'run_id': rid,
                        'content_digest': d.get('content_digest')}
    return {'per_game': per_game, 'by_gsis_id': by_id,
            'n_games': len(per_game), 'n_players': len(by_id)}


def governed_injuries(season=2026, week=2) -> dict:
    blobs = sorted(glob.glob(str(_REPO / 'nfl/vintage/injuries.*.csv.gz')))
    if not blobs:
        return {'state': 'ABSENT', 'rows': {}, 'blob': None}
    b = blobs[-1]
    txt = gzip.decompress(pathlib.Path(b).read_bytes()).decode(errors='replace')
    out = {}
    for r in csv.DictReader(io.StringIO(txt)):
        if (str(r.get('season')) == str(season)
                and str(r.get('week')) == str(week)):
            g = (r.get('gsis_id') or '').strip()
            if g:
                out[g] = r
    return {'state': 'PRESENT', 'rows': out,
            'blob': str(pathlib.Path(b).relative_to(_REPO)), 'n': len(out)}


def build() -> dict:
    load = DK.load()
    if load.state is not State.PASS:
        return {'fatal': f'{load.state.value}[{load.code}] {load.detail}'}
    dk_rows = load.value
    ros = ID.canonical_roster()
    if ros.state is not State.PASS:
        return {'fatal': f'{ros.state.value}[{ros.code}] {ros.detail}'}
    rec = ID.reconcile(dk_rows, ros.value)
    summ = ID.summarise(rec)
    cov = model_coverage()
    inj = governed_injuries()
    slate = DK.main_slate(dk_rows)

    # ---- the join, with coverage and WITHOUT projections -----------------
    join = []
    for r in rec['rows']:
        gid = r['gsis_id']
        c = cov['by_gsis_id'].get(gid) if gid else None
        ig = inj['rows'].get(gid) if gid else None
        row = {
            'gsis_id': gid, 'name': r['canonical_name'] or r['dk_name'],
            'dk_name': r['dk_name'], 'team': r['team'],
            'opponent': r['opponent'], 'is_home': r['is_home'],
            'position': r['dk_pos'],
            'canonical_position': r['canonical_position'],
            'dk_salary': r['salary'],
            'identity_status': r['status'],
            'match_method': r['match_method'],
            'roster_status': r['roster_status'],
            'dk_inj_flag': r['inj_flag'],
            'governed_report_status': (ig or {}).get('report_status') or None,
            'governed_practice_status': (
                (ig or {}).get('practice_status') or None),
            'governed_injury': ((ig or {}).get('report_primary_injury')
                                or (ig or {}).get('practice_primary_injury')
                                or None),
            'dk_depth': r['dk_depth'],
            'modeled_status': None,
            'simulation_reference': None,
            'slate_eligibility': 'UNRESOLVED_CONTEST_GAME_SET_NOT_SUPPLIED',
        }
        for f in DISTRIBUTION_FIELDS:
            row[f] = None
        if r['status'] == DK.STATUS_DST:
            row['modeled_status'] = 'DK_ELIGIBLE_MODEL_UNSUPPORTED'
            row['unsupported_reason'] = (
                'the engine produces no team-defence outputs at all '
                '(statline.NOT_SIMULATED). A DST cannot be scored from our '
                'simulation, so a Classic lineup -- which must field one -- '
                'cannot be built from it either.')
        elif r['status'] != DK.STATUS_MATCHED:
            row['modeled_status'] = 'DK_ELIGIBLE_IDENTITY_UNRESOLVED'
            row['unsupported_reason'] = r['note']
        elif c is None:
            row['modeled_status'] = 'DK_ELIGIBLE_MODEL_UNSUPPORTED'
            row['unsupported_reason'] = (
                'no modelled row in any rehearsal run for this player')
        else:
            row['modeled_status'] = 'MODEL_COVERED_FORECAST_NOT_SEALED'
            row['simulation_reference'] = c
            row['unsupported_reason'] = (
                'the model reaches this player, but no board sealed for 2026 '
                'week 2 -- artifact_sealing BLOCKS every game on '
                'current_season_input_freshness -- so there is no forecast to '
                'report. The distribution fields are null because the number '
                'does not exist, not because it was not looked up.')
        join.append(row)

    # ---- injury reconciliation ------------------------------------------
    flagged = [r for r in rec['rows'] if r['inj_flag']]
    inj_rec = []
    for r in flagged:
        ig = inj['rows'].get(r['gsis_id']) if r['gsis_id'] else None
        gov = (ig or {}).get('report_status') or None
        inj_rec.append({
            'dk_name': r['dk_name'], 'gsis_id': r['gsis_id'],
            'team': r['team'], 'position': r['dk_pos'],
            'dk_flag': r['inj_flag'],
            'governed_report_status': gov,
            'governed_practice_status': (
                (ig or {}).get('practice_status') or None),
            'governed_injury': ((ig or {}).get('report_primary_injury')
                                or (ig or {}).get('practice_primary_injury')
                                or None),
            'agreement': ('GOVERNED_CARRIES_A_DESIGNATION' if gov
                          else 'DK_FLAGS_WHERE_GOVERNED_HAS_NO_DESIGNATION'),
        })
    dk_ids = {r['gsis_id'] for r in rec['rows'] if r['gsis_id']}
    severe = [(g, i) for g, i in inj['rows'].items()
              if (i.get('report_status') or '') in ('Out', 'Doubtful')]
    severe_in_dk = [g for g, _ in severe if g in dk_ids]

    # ---- validation ------------------------------------------------------
    sal = [r['salary'] for r in dk_rows if r['salary'] is not None]
    teams_in_file = {r['team'] for r in dk_rows}
    bad_opp = [r['dk_name'] for r in dk_rows
               if r['team'] == r['opponent'] or not r['opponent']]
    unsupported = [r for r in join
                   if r['modeled_status'] != 'MODEL_COVERED_FORECAST_NOT_SEALED']
    inactive_with_opportunity = [
        r for r in join
        if r['governed_report_status'] in ('Out', 'Doubtful')
        and r['modeled_status'] == 'MODEL_COVERED_FORECAST_NOT_SEALED']

    return {
        'artifact': 'DK_WEEK2_SALARY_UNIVERSE',
        'spec_version': SPEC_VERSION,
        'generated_at_utc': dt.datetime.now(dt.timezone.utc)
                              .replace(microsecond=0).isoformat()
                              .replace('+00:00', 'Z'),
        'season': 2026, 'week': 2,
        'provenance': {
            'original_filename': 'draftkings_NFL_2026-week-2_players.csv',
            'sha256': load.evidence['sha256'],
            'sha256_matches_declared':
                load.evidence['sha256_matches_declared'],
            'blob': load.evidence['blob'],
            'acquisition': 'OWNER_SUPPLIED_DELIVERY',
            'role': 'DOWNSTREAM_SALARY_AND_UNIVERSE_ONLY',
            'predictive_use': 'NOT_AUTHORIZED',
        },
        'normalized_shape': {
            'n_rows': load.evidence['n_rows'],
            'n_columns': load.evidence['n_columns'],
            'header_row_index': load.evidence['header_row_index'],
            'columns_kept': load.evidence['columns_kept'],
            'columns_reconcile_only': load.evidence['columns_reconcile_only'],
            'columns_dropped': load.evidence['columns_dropped'],
            'n_columns_dropped': load.evidence['n_columns_dropped'],
            'team_code_crosswalk': load.evidence['team_code_crosswalk'],
        },
        'raw_universe': DK.raw_universe(dk_rows),
        'main_slate': {
            'state': slate.state.value, 'code': slate.code,
            'detail': slate.detail,
            'games_in_file': slate.evidence['games_in_file'],
            'excluded_already_played':
                slate.evidence['excluded_already_played'],
            'excluded_already_played_rows':
                slate.evidence['excluded_already_played_rows'],
        },
        'identity': {
            'canonical_source': ros.evidence,
            'summary': summ,
        },
        'model_coverage': {
            'source': 'rehearsal draw manifests (REFUSED runs; coverage only, '
                      'never a projection)',
            'per_game': cov['per_game'],
            'n_games': cov['n_games'],
            'n_modelled_players': cov['n_players'],
            'n_dk_matched': len(dk_ids),
            'n_dk_covered': len(dk_ids & set(cov['by_gsis_id'])),
            'n_dk_unsupported': len(dk_ids - set(cov['by_gsis_id'])),
            'n_modelled_absent_from_dk': len(
                set(cov['by_gsis_id']) - dk_ids),
        },
        'injury_reconciliation': {
            'governed_source': inj['blob'], 'n_governed_rows': inj.get('n'),
            'dk_flagged': inj_rec,
            'n_governed_out_or_doubtful': len(severe),
            'n_governed_out_or_doubtful_present_in_dk': len(severe_in_dk),
            'governed_out_or_doubtful_present_in_dk': severe_in_dk,
        },
        'validation': {
            'n_raw_rows': len(dk_rows),
            'n_main_slate_eligible': None,
            'n_matched': summ['by_status'].get(DK.STATUS_MATCHED, 0),
            'n_unmatched': summ['by_status'].get(DK.STATUS_UNMATCHED, 0),
            'n_ambiguous': summ['by_status'].get(DK.STATUS_AMBIGUOUS, 0),
            'n_dst': summ['by_status'].get(DK.STATUS_DST, 0),
            'n_unsupported': len(unsupported),
            'position_counts': dict(
                collections.Counter(r['position'] for r in join)),
            'n_teams': len(teams_in_file),
            'salary_min': min(sal), 'salary_max': max(sal),
            'n_salary_missing': sum(1 for r in dk_rows
                                    if r['salary'] is None),
            'malformed_salaries': load.evidence['malformed_salaries'],
            'duplicate_gsis_ids': summ['duplicate_gsis_ids'],
            'team_opponent_inconsistencies': bad_opp,
            'n_inactive_carrying_modelled_opportunity':
                len(inactive_with_opportunity),
            'inactive_carrying_modelled_opportunity': [
                {'name': r['name'], 'team': r['team'],
                 'governed_report_status': r['governed_report_status']}
                for r in inactive_with_opportunity],
        },
        'join': join,
    }


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    art = build()
    if 'fatal' in art:
        print('FATAL', art['fatal'])
        raise SystemExit(1)
    v = art['validation']
    print(f"rows {v['n_raw_rows']}  matched {v['n_matched']}  "
          f"unmatched {v['n_unmatched']}  ambiguous {v['n_ambiguous']}  "
          f"dst {v['n_dst']}  unsupported {v['n_unsupported']}")
    print(f"main slate: {art['main_slate']['state']}"
          f"[{art['main_slate']['code']}]")
    if a.write:
        p = OUT_DIR / 'DK_WEEK2_SALARY_UNIVERSE.json'
        p.write_text(json.dumps(art, indent=1, sort_keys=True) + '\n')
        print('wrote', p, p.stat().st_size, 'bytes')
