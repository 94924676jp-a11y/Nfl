"""Score a sealed forecast against a completed game and append to the ledger.

    python3.12 nfl/tools/score_game.py --forecast-dir <dir> \
        --pbp <play_by_play.csv.gz> --pbp-sha256 <hash>

The outcome hash is REQUIRED and checked. A scorer that will read any file it
is handed cannot tell you which outcome it scored against.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import evaluator as EV                          # noqa: E402
from nfl.research.shadow import actuals as ACT                   # noqa: E402


def actuals_from_pbp(pbp, game_id, roster=None) -> dict:
    """Map the play-by-play into the model's own metric vocabulary.

    The definitions come from `research.shadow.actuals`, which read them out of
    the panel builder the model was fitted on rather than from a box score.
    """
    rows = ACT.load(pathlib.Path(pbp), game_id)
    qb = ACT.qb_actuals(rows)
    skill = ACT.receiving_rushing_actuals(rows)
    out = {}
    for pid, q in qb.items():
        out.setdefault(pid, {}).update({
            'qb/att': q['att'], 'qb/cmp': q['cmp'], 'qb/db': q['db'],
            'qb/pyds': q['pyds'], 'qb/ptd': q['ptd'], 'qb/int': q['int'],
            'qb/sacks': q['sacks'], 'qb/scr': q['scr'],
            'qb/rush_opp': q['rush_opp'], 'qb/ryds': q['ryds'],
            'qb/rtd': q['rtd'], '_position': 'QB'})
    for pid, v in skill.items():
        d = out.setdefault(pid, {})
        d.update({'receiving/targets': v['targets'],
                  'receiving/receptions': v['receptions'],
                  'receiving/receiving_yards': v['rec_yds'],
                  'receiving/receiving_td': v['rec_td'],
                  'rushing/carries': v['carries'],
                  'rushing/rushing_td': v['rush_td']})
        d.setdefault('_team', v.get('team'))
    for pid, v in skill.items():
        out[pid].setdefault('_team', v.get('team'))
    if roster:
        for pid, d in out.items():
            info = roster.get(pid) or {}
            if info.get('position'):
                d['_position'] = info['position']
            if info.get('team'):
                d['_team'] = info['team']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--forecast-dir', required=True)
    ap.add_argument('--pbp', required=True)
    ap.add_argument('--pbp-sha256', required=True)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--out')
    ap.add_argument('--no-append', action='store_true')
    ap.add_argument('--ledger')
    a = ap.parse_args()

    got = hashlib.sha256(pathlib.Path(a.pbp).read_bytes()).hexdigest()
    if got != a.pbp_sha256:
        raise SystemExit(f'OUTCOME_HASH_MISMATCH: {got} != {a.pbp_sha256}')

    art = json.loads((pathlib.Path(a.forecast_dir)
                      / 'forecast_artifact.json').read_text())
    gid = art['game_id']
    from nfl.product import board as B
    roster = B.roster_identity(a.season, a.week, art.get('team_ids') or [])
    acts = actuals_from_pbp(a.pbp, gid, roster)

    ev = EV.score(a.forecast_dir, acts)
    ev['outcome_sha256'] = a.pbp_sha256
    if a.out:
        pathlib.Path(a.out).write_text(
            json.dumps(ev, indent=1, sort_keys=True, default=str))
    print('game', gid, '| scored rows', ev['n_scored'])
    o = ev['summary']['overall']
    if o:
        print('  mean CRPS %.3f  median |err| %.2f  bias %+.3f'
              % (o['mean_crps'], o['median_abs_error'], o['bias_mean_error']))
        print('  coverage', o['coverage_pct'])
        print('  miss classes', o['miss_classes'])
    if not a.no_append:
        n = EV.append(ev, a.ledger)
        print('  appended', n, 'row(s) to the evaluation ledger')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
