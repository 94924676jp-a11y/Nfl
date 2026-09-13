"""PRE_INACTIVES -> POST_INACTIVES_FINAL, per player and metric.

WHAT THIS IS FOR. The two stages exist so the information value of the official
inactive list can eventually be MEASURED rather than assumed. That requires
both forecasts to survive intact and to be comparable player by player, metric
by metric. This tool produces that comparison; it changes neither artifact.

WHY IT JOINS ON IDENTITY. A delta computed by row position would silently pair
one player's pre-inactives distribution with another's post-inactives
distribution -- the exact defect measured on 2026_01_ARI_LAC, where a
positional join put Justin Herbert's dropbacks on Gardner Minshew and made a
team split read 74.6/4.9 against a true 41.3/38.2. Every join here is by
`gsis_id` through the draw manifest's declared row identity.

WHAT A DELTA IS NOT. A large change between stages is not evidence that either
stage is right. It measures how much the official list moved the forecast, and
that is all it measures until both stages have been scored against outcomes.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research import board_select as BS                      # noqa: E402
from nfl.product import daily_board as PB                           # noqa: E402
from nfl.product import forecast_stage as FS                        # noqa: E402
from nfl.product import names as NM                                 # noqa: E402
from nfl.research import daily_board as RB                       # noqa: E402
from nfl.tools.market_comparison import (DrawIdentityError,         # noqa: E402
                                         draw_row_for)

SPEC_VERSION = 'stage-delta/1.0.0'
COLUMNS = ('game', 'player', 'gsis_id', 'team', 'position', 'metric',
           'pre_mean', 'post_mean', 'delta_mean', 'delta_mean_pct',
           'pre_median', 'post_median', 'pre_p90', 'post_p90',
           'pre_written_at', 'post_written_at', 'pre_run_id', 'post_run_id',
           'became_officially_inactive', 'status')


def _load(cfg_dir):
    bd, _ = BS.newest_board_dir(cfg_dir)
    if bd is None:
        return None
    board = json.load(open(bd / 'board.json'))
    draws = PB._load_draws(bd)
    mp = bd / 'player_draws_manifest.json'
    man = json.loads(mp.read_text()) if mp.exists() else None
    return {'dir': bd, 'board': board, 'draws': draws, 'manifest': man,
            'written_at': (board.get('freshness') or {}).get('written_at'),
            'run_id': board.get('run_id')}


def delta_for_game(gid, gdir, label, names):
    """Rows and a summary for one game's PRE/POST pair, or a named refusal."""
    pre = _load(gdir / f'pre_inactives_{label}')
    post = _load(gdir / f'post_inactives_{label}')
    if pre is None:
        return [], {'game': gid, 'status': 'NO_PRE_INACTIVES_BOARD'}
    if post is None:
        return [], {'game': gid, 'status': 'NO_POST_INACTIVES_BOARD',
                    'detail': 'stage 2 has not been sealed for this game yet, '
                              'so there is nothing to compare stage 1 against. '
                              'This is the expected state before the official '
                              'list publishes.'}
    if pre['run_id'] == post['run_id']:
        return [], {'game': gid, 'status': 'STAGES_SHARE_A_RUN_ID',
                    'detail': f'both stages report run_id {pre["run_id"]}. A '
                              f'stage-2 seal must be a NEW artifact, never a '
                              f'rewrite of stage 1.'}
    inact = set()
    own = (post['board'].get('qb_inactive_ownership') or {})
    for v in (own.get('inactive_qbs_excluded') or {}).values():
        inact.update(v)
    pre_p = {p['gsis_id']: p for p in (pre['board'].get('players') or [])}
    post_p = {p['gsis_id']: p for p in (post['board'].get('players') or [])}
    rows = []
    for pid in sorted(set(pre_p) | set(post_p)):
        a, b = pre_p.get(pid), post_p.get(pid)
        base = b or a
        metrics = sorted(set((a or {}).get('metrics') or {})
                         | set((b or {}).get('metrics') or {}))
        for metric in metrics:
            r = {'game': gid, 'gsis_id': pid,
                 'player': names.get(pid, pid), 'team': base.get('team'),
                 'position': base.get('position'), 'metric': metric,
                 'pre_run_id': pre['run_id'], 'post_run_id': post['run_id'],
                 'pre_written_at': pre['written_at'],
                 'post_written_at': post['written_at'],
                 'became_officially_inactive': pid in inact}
            vals = {}
            for tag, src, present in (('pre', pre, pre_p), ('post', post, post_p)):
                if (src['manifest'] is None or src['draws'] is None
                        or pid not in present):
                    vals[tag] = None
                    continue
                try:
                    vals[tag] = np.asarray(
                        draw_row_for(src['manifest'], src['draws'], metric,
                                     pid), float)
                except DrawIdentityError:
                    vals[tag] = None
            if vals['pre'] is None and vals['post'] is None:
                continue
            for tag in ('pre', 'post'):
                d = vals[tag]
                r[f'{tag}_mean'] = '' if d is None else round(float(d.mean()), 4)
                r[f'{tag}_median'] = ('' if d is None
                                      else round(float(np.median(d)), 4))
                r[f'{tag}_p90'] = ('' if d is None
                                   else round(float(np.quantile(d, 0.9)), 4))
            if vals['pre'] is None:
                r['status'] = 'ONLY_IN_POST'
                r['delta_mean'] = r['delta_mean_pct'] = ''
            elif vals['post'] is None:
                r['status'] = 'ONLY_IN_PRE'
                r['delta_mean'] = r['delta_mean_pct'] = ''
            else:
                pm, qm = float(vals['pre'].mean()), float(vals['post'].mean())
                r['delta_mean'] = round(qm - pm, 4)
                r['delta_mean_pct'] = (round((qm - pm) / pm * 100.0, 4)
                                       if pm else '')
                r['status'] = 'COMPARED'
            rows.append(r)
    moved = [r for r in rows if r['status'] == 'COMPARED'
             and abs(float(r['delta_mean'])) > 1e-9]
    return rows, {
        'game': gid, 'status': 'OK', 'n_rows': len(rows),
        'n_compared': sum(1 for r in rows if r['status'] == 'COMPARED'),
        'n_moved_by_the_official_list': len(moved),
        'n_only_in_pre': sum(1 for r in rows if r['status'] == 'ONLY_IN_PRE'),
        'n_only_in_post': sum(1 for r in rows if r['status'] == 'ONLY_IN_POST'),
        'n_players_ruled_officially_inactive': len(inact),
        'pre_run_id': pre['run_id'], 'post_run_id': post['run_id'],
        'pre_written_at': pre['written_at'],
        'post_written_at': post['written_at'],
        'stage_1_preserved': pre['run_id'] != post['run_id'],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='PRE -> POST forecast delta')
    ap.add_argument('--candidate', default='R8')
    ap.add_argument('--games', default=None)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    label = ('V1_CANDIDATE' if a.candidate == 'V1'
             else f'V1_CANDIDATE_{a.candidate}')
    want = set(a.games.split(',')) if a.games else None
    names = NM.lookup(None)
    rows, summaries = [], []
    for gdir in sorted(RB.LIVE.iterdir()):
        if not gdir.is_dir() or (want and gdir.name not in want):
            continue
        r, s = delta_for_game(gdir.name, gdir, label, names)
        rows += r
        summaries.append(s)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in COLUMNS})
    sp = out.with_suffix('.summary.json')
    sp.write_text(json.dumps(
        {'artifact': 'FORECAST_STAGE_DELTA', 'spec_version': SPEC_VERSION,
         'stages': [FS.PRE, FS.POST],
         'what_a_delta_is_not': (
             'a large change between stages is not evidence that either stage '
             'is right. It measures how much the official list moved the '
             'forecast, and nothing more until both stages are scored against '
             'outcomes.'),
         'join': 'gsis_id, through the draw manifest row identity. Never positional.',
         'games': summaries, 'n_rows': len(rows)}, indent=1) + '\n')
    print(f'{len(rows)} delta row(s) -> {out}')
    print(f'summary -> {sp}')
    for s in summaries:
        print(f'   {s["game"]}: {s["status"]}'
              + (f' n={s.get("n_rows")} moved='
                 f'{s.get("n_moved_by_the_official_list")}'
                 if s['status'] == 'OK' else f' {s.get("detail", "")[:90]}'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
