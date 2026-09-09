"""NFL-V1-R1: run the whole upcoming slate through the production entrypoint.

REHEARSAL ONLY. Every artifact this produces is tagged dry_run and
prospective_eligible=false, and publication stays refused while G0A is
incomplete. This does not forecast for money and cannot.
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb2'),
           os.path.join(_ROOT, 'nfl', 'research', 'rc1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from nfl.capture import coverage as C                             # noqa: E402
from nfl.production import run_forecast as RUN                    # noqa: E402

# Failure taxonomy, per s.D. Every failure gets one of these; "error" is not a
# category.
CATS = ('DATA_MISSING', 'ID_RECONCILIATION', 'ACCOUNTING', 'MODEL_INTERFACE',
        'AUTHORIZATION', 'CHRONOLOGY', 'PRODUCTION_ENTRYPOINT', 'OTHER_NAMED')

CODE_CAT = {
    'QB_SLATE_EMPTY': 'MODEL_INTERFACE',
    'QB_FRAME_MISSING': 'DATA_MISSING',
    'STAGE_NOT_IMPLEMENTED': 'MODEL_INTERFACE',
    'MODEL_ARTIFACT_MISSING': 'DATA_MISSING',
    'MODEL_HASH_MISMATCH': 'DATA_MISSING',
    'IDENTITY_UNRESOLVED': 'ID_RECONCILIATION',
    'REQUIRED_GAME_MISSING': 'DATA_MISSING',
    'INCOMPLETE_PLAYER_ACCOUNTING': 'ACCOUNTING',
    'JOINT_RECONCILIATION_FAILURE': 'ACCOUNTING',
    'QB_DRAW_ACCOUNTING_VIOLATED': 'ACCOUNTING',
    'SOURCE_MISSING': 'DATA_MISSING',
    'UNAUTHORIZED_INPUT': 'DATA_MISSING',
    'SOURCE_TOO_LATE': 'CHRONOLOGY',
    'SOURCE_CHRONOLOGY_FAILURE': 'CHRONOLOGY',
    'RAW_HASH_MISMATCH': 'DATA_MISSING',
    'SCHEMA_DRIFT': 'DATA_MISSING',
    'ARM_RULE_VIOLATION': 'CHRONOLOGY',
    'COLD_START_VIOLATION': 'CHRONOLOGY',
    'NFL1_NOT_AUTHORIZED': 'AUTHORIZATION',
    'ARTIFACT_SEALING_FAILURE': 'PRODUCTION_ENTRYPOINT',
    'STAGE_RAISED': 'PRODUCTION_ENTRYPOINT',
    'STAGE_NOT_REACHED': 'PRODUCTION_ENTRYPOINT',
}


def roster(season, week):
    """The player set for an UPCOMING week comes from the roster, not history.

    This is the whole point: a live forecast must be able to name players for a
    season that has not been played. Sourcing the player set from a historical
    panel can only ever 'forecast' the past.
    """
    best, rows = None, []
    for f in sorted(glob.glob(os.path.join(
            _ROOT, 'nfl', 'vintage', 'weekly_rosters.*.reduced.csv.gz'))):
        r = [x for x in csv.DictReader(gzip.open(f, 'rt'))
             if x['season'] == str(season) and x['week'] == str(week)]
        if len(r) > len(rows):
            best, rows = f, r
    return os.path.basename(best) if best else None, rows


def build(season, week, out_dir, written_at,
          model_configuration=None):
    plan = C.load_week_plan(season, week)
    if plan.state.name != 'PASS':
        return {'fatal': f'{plan.code}: {plan.detail}'}
    games = sorted({c.game_id: c for c in plan.value}.items())
    ko = {c.game_id: c.kickoff_utc for c in plan.value}
    src_file, rrows = roster(season, week)
    by_team = collections.defaultdict(list)
    for r in rrows:
        by_team[r['team']].append(r)

    results = []
    for gid, _ in games:
        parts = gid.split('_')
        away, home = parts[2], parts[3]
        players = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                    'team': r['team']}
                   for t in (away, home) for r in by_team.get(t, [])]
        fx = {'kickoff_utc': ko[gid].isoformat().replace('+00:00', 'Z'),
              'source_hashes': {'schedules': {
                  'sha256': 'b' * 64, 'retrieved_at': '2026-09-08T12:00:00Z'}},
              'players': players, 'team_ids': [away, home],
              'qb_slate': {'prospective': True}, 'qb_draws': 200,
              'team_volume': True,
              'distributions': {}}
        a = argparse.Namespace(season=season, week=week, game_id=gid, arm='A',
                               written_at=written_at, out_dir=out_dir,
                               seed=20260908, dry_run=True, fixtures=None,
                               model_configuration=model_configuration)
        s = RUN.build(a, fx)
        fails = []
        for st in s['stages']:
            if st['state'] not in ('PASS', 'NOT_APPLICABLE'):
                fails.append({'stage': st['stage'], 'code': st['code'],
                              'category': CODE_CAT.get(st['code'],
                                                       'OTHER_NAMED'),
                              'detail': st['detail'][:200]})
        results.append({'game_id': gid, 'status': s['status'],
                        'n_players': len(players), 'failures': fails,
                        # Additive: the full per-stage outcome, so a consumer
                        # need not infer PASS from absence-of-failure. Absence
                        # read as success is the defect this project pays for
                        # most often, and inferring it here would be that.
                        'stages': [{'stage': st['stage'],
                                    'state': st['state'], 'code': st['code']}
                                   for st in s['stages']],
                        'publication': s['publication']['code'],
                        'run_id': s['run_id']})
    return {'season': season, 'week': week, 'n_games': len(games),
            'model_configuration': model_configuration or 'PRODUCTION_BASELINE',
            'roster_source': src_file, 'n_roster_rows': len(rrows),
            'results': results}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--out-dir', default='/tmp/v1r1')
    ap.add_argument('--written-at', default='2026-09-08T23:00:00Z')
    ap.add_argument('--model-configuration',
                    dest='model_configuration', default=None)
    a = ap.parse_args()
    r = build(a.season, a.week, a.out_dir, a.written_at,
              a.model_configuration)
    if 'fatal' in r:
        print('FATAL', r['fatal']); sys.exit(1)
    print(f"slate {r['season']} wk{r['week']}: {r['n_games']} games, roster "
          f"{r['roster_source']} ({r['n_roster_rows']} rows)")
    cat = collections.Counter(); st = collections.Counter()
    for g in r['results']:
        st[g['status']] += 1
        for f in g['failures']:
            cat[(f['category'], f['code'], f['stage'])] += 1
    print('\nSTATUS:', dict(st))
    print('\nFAILURE INVENTORY (category / code / stage -> games):')
    for (c, code, stg), n in cat.most_common():
        print(f'  {c:24s} {code:32s} {stg:22s} {n}')
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'slate_inventory.json'), 'w'), indent=1)
    print('\nwrote slate_inventory.json')
