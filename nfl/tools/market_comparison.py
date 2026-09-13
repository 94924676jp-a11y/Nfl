#!/usr/bin/env python3.12
r"""The governed model-vs-market table, from stored draws and a frozen price.

    python3.12 nfl/tools/market_comparison.py --date 2026-09-13 \
        --candidate R8 --market /path/to/snapshot.csv --out TABLE.csv

WHAT IT EMITS AND WHAT IT REFUSES

A row appears only if ALL of the following hold, and the reason any row is
missing is written to the refusal file beside the table rather than being
silently absent:

  * the board is POST-INACTIVES for that game
  * `qb_inactive_ownership_enforced` is true on the board
  * the metric carries no defect flagged as contaminating FOR THAT METRIC
  * the player maps to a team and a gsis_id
  * the metric has stored draws, so the probability is counted and not fitted
  * a frozen quote exists for that player and market

It ranks nothing, recommends nothing, and sizes nothing. `edge` below is the
model probability minus the de-vigged market probability on the chosen side --
a disagreement, which is not an edge estimate and not advice.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.product import daily_board as PB                        # noqa: E402
from nfl.product import market_cdf as MC                         # noqa: E402
from nfl.product import market_names as MN                       # noqa: E402
from nfl.research import board_select as BS                      # noqa: E402
from nfl.research import daily_board as RB                       # noqa: E402

COLUMNS = ('game', 'player', 'market', 'metric', 'line', 'over_price',
           'under_price',
           'r8_mean', 'r8_median', 'r8_p_over', 'r8_p_under', 'r8_p_push',
           'no_vig_p_over', 'no_vig_p_under', 'edge_over', 'edge_under',
           'completeness', 'defects', 'information_timestamp',
           'market_timestamp', 'sportsbook', 'n_draws', 'n_over', 'n_under',
           'n_push', 'probability_method', 'cutoff',
           'qb_inactive_ownership_enforced')



SNAPSHOT_COLUMNS = ('player', 'team', 'opponent', 'market', 'line',
                    'over_price', 'under_price', 'sportsbook',
                    'retrieval_time_utc', 'availability', 'source_url')
REQUIRED_AVAILABILITY = 'TWO_SIDED_OPEN'


def load_frozen_snapshot(path):
    """A frozen book snapshot, keyed by (player, team, market).

    THE TEAM IS PART OF THE KEY AND THAT IS NOT PEDANTRY. Two different
    players share a name across clubs in this very week: the Vikings' Justin
    Jefferson is a receiver and the Browns listed a linebacker of the same
    name on their inactive report. A (player, market) key would have joined a
    receiving line onto whichever one it met first.

    NOTHING IS REFRESHED AND NOTHING IS RESTAMPED. The file is read, its
    digest is recorded, and every clock in it is carried through exactly as
    written.
    """
    p = pathlib.Path(path)
    raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode().splitlines()))
    if not rows:
        raise ValueError('MARKET_SNAPSHOT_EMPTY: an empty snapshot is an '
                         'error, not an absence of quotes')
    missing = [c for c in SNAPSHOT_COLUMNS if c not in rows[0]]
    if missing:
        raise ValueError(f'MARKET_SNAPSHOT_SCHEMA: missing {missing}')
    by, skipped = {}, []
    for r in rows:
        if (r.get('availability') or '').strip() != REQUIRED_AVAILABILITY:
            skipped.append({'player': r.get('player'),
                            'market': r.get('market'),
                            'reason': 'NOT_TWO_SIDED_OPEN',
                            'detail': r.get('availability')})
            continue
        try:
            line = float(r['line'])
        except (TypeError, ValueError):
            skipped.append({'player': r.get('player'),
                            'market': r.get('market'),
                            'reason': 'UNPARSEABLE_LINE',
                            'detail': r.get('line')})
            continue
        key = (r['player'].strip(), r['team'].strip(), r['market'].strip())
        if key in by:
            raise ValueError(f'MARKET_SNAPSHOT_DUPLICATE: {key} appears more '
                             f'than once; a duplicate quote is an ambiguity, '
                             f'not a choice this tool may make')
        by[key] = {'line': line, 'over_price': r['over_price'],
                   'under_price': r['under_price'],
                   'sportsbook': r['sportsbook'],
                   'timestamp': r['retrieval_time_utc'],
                   'source_url': r['source_url'],
                   'opponent': r['opponent']}
    return {'quotes': by, 'sha256': digest, 'n_rows': len(rows),
            'n_quotes': len(by), 'skipped': skipped, 'path': str(p)}


def _draw_key(metric):
    return str(metric).replace('/', '__')


def rows_for_game(gid, cfg_dir, quotes, names):
    """(rows, refusals) for one sealed board against the frozen snapshot."""
    rows, refused = [], []
    bd, how = BS.newest_board_dir(cfg_dir)
    if bd is None:
        return rows, [{'game': gid, 'reason': 'NO_SEALED_BOARD'}]
    board = json.load(open(bd / 'board.json'))
    cutoff = 'post_inactives' if 'post_inactives' in cfg_dir.name else \
        'pre_inactives'
    if cutoff != 'post_inactives':
        return rows, [{'game': gid, 'reason': 'NOT_POST_INACTIVES',
                       'detail': cfg_dir.name}]
    enforced = bool(board.get('qb_inactive_ownership_enforced'))
    if not enforced:
        own = board.get('qb_inactive_ownership') or {}
        return rows, [{'game': gid,
                       'reason': 'QB_INACTIVE_OWNERSHIP_NOT_ENFORCED',
                       'detail': ','.join(own.get('failed_conditions') or
                                          ['no ownership block on the board'])}]
    draws = PB._load_draws(bd)
    if draws is None:
        return rows, [{'game': gid, 'reason': 'NO_STORED_DRAWS'}]
    fresh = board.get('freshness') or {}
    info_ts = max((s.get('retrieved_at') or '')
                  for s in (fresh.get('sources') or [])) or None
    for i, p in enumerate(board.get('players') or []):
        pid, team = p.get('gsis_id'), p.get('team')
        nm = names.get(pid, pid)
        if not pid or not team:
            refused.append({'game': gid, 'player': nm,
                            'reason': 'PLAYER_MAPPING_INVALID'})
            continue
        for (qn, qt, qmarket), q in quotes.items():
            if qn != nm or qt != team:
                continue
            metric, basis = MN.metric_for(qmarket, p.get('position'))
            if metric is None:
                refused.append({'game': gid, 'player': nm,
                                'market': qmarket,
                                'reason': 'MARKET_NOT_MAPPED',
                                'detail': basis[:200]})
                continue
            if metric not in (p.get('metrics') or {}):
                refused.append({'game': gid, 'player': nm, 'market': qmarket,
                                'reason': 'METRIC_NOT_ON_THIS_BOARD',
                                'detail': metric})
                continue
            flags = PB._defect_flags(board, metric)
            bad = [f['id'] for f in flags if f.get('contaminates_this_metric')]
            if bad:
                refused.append({'game': gid, 'player': nm, 'market': metric,
                                'reason': 'CONTAMINATING_DEFECT',
                                'detail': ','.join(bad)})
                continue
            k = _draw_key(metric)
            if k not in draws.files:
                refused.append({'game': gid, 'player': nm, 'market': metric,
                                'reason': 'METRIC_HAS_NO_STORED_DRAWS',
                                'detail': k})
                continue
            arr = draws[k]
            d = arr[i] if arr.ndim == 2 else arr
            quote = {'line': q['line'], 'over_price': q.get('over_price'),
                     'under_price': q.get('under_price'),
                     'retrieved_at': q.get('timestamp'),
                     'source': q.get('sportsbook'),
                     'market_timestamp': q.get('timestamp')}
            try:
                c = MC.compare(d, metric, quote)
            except (ValueError, MC.MarketLeak) as e:
                refused.append({'game': gid, 'player': nm, 'market': metric,
                                'reason': type(e).__name__,
                                'detail': str(e)[:160]})
                continue
            e = c['exact_probability']
            nv = c['no_vig']
            rows.append({
                'game': gid, 'player': nm, 'market': qmarket,
                'metric': metric, 'line': q['line'], 'over_price': q.get('over_price'),
                'under_price': q.get('under_price'),
                'r8_mean': round(c['model']['mean'], 4),
                'r8_median': round(c['model']['median'], 4),
                'r8_p_over': round(e['p_over'], 6),
                'r8_p_under': round(e['p_under'], 6),
                'r8_p_push': round(e['p_push'], 6),
                'no_vig_p_over': (round(nv['no_vig_over'], 6)
                                  if nv['no_vig_over'] is not None else ''),
                'no_vig_p_under': (round(nv['no_vig_under'], 6)
                                   if nv['no_vig_under'] is not None else ''),
                'edge_over': (round(c['disagreement_over'], 6)
                              if c['disagreement_over'] is not None else ''),
                'edge_under': (round(c['disagreement_under'], 6)
                               if c['disagreement_under'] is not None else ''),
                'completeness': board.get('completeness'),
                'defects': ','.join(f['id'] for f in flags) or '',
                'information_timestamp': info_ts,
                'market_timestamp': q.get('timestamp'),
                'sportsbook': q.get('sportsbook'),
                'n_draws': e['n_draws'], 'n_over': e['n_over'],
                'n_under': e['n_under'], 'n_push': e['n_push'],
                'probability_method': e['method'], 'cutoff': cutoff,
                'qb_inactive_ownership_enforced': enforced,
            })
    return rows, refused


def main(argv=None):
    ap = argparse.ArgumentParser(description='exact model-vs-market table')
    ap.add_argument('--date', required=True)
    ap.add_argument('--candidate', default='R8')
    ap.add_argument('--market', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--games', default=None)
    a = ap.parse_args(argv)

    snap = load_frozen_snapshot(a.market)
    quotes = snap['quotes']
    print(f'frozen snapshot {snap["path"]}')
    print(f'  sha256 {snap["sha256"]}')
    print(f'  {snap["n_rows"]} row(s), {snap["n_quotes"]} '
          f'(player, team, market) quote(s), {len(snap["skipped"])} skipped')

    want = set(a.games.split(',')) if a.games else None
    label = ('V1_CANDIDATE' if a.candidate == 'V1'
             else f'V1_CANDIDATE_{a.candidate}')
    from nfl.product import names as NM
    names = NM.lookup(None) if hasattr(NM, 'lookup') else {}
    rows, refused = [], []
    for gdir in sorted((RB.LIVE).iterdir()):
        if not gdir.is_dir() or (want and gdir.name not in want):
            continue
        for cut in ('post_inactives', 'pre_inactives'):
            d = gdir / f'{cut}_{label}'
            if d.exists():
                r, x = rows_for_game(gdir.name, d, quotes, names)
                rows += r
                refused += x
                break
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    ref = out.with_suffix('.refusals.json')
    ref.write_text(json.dumps(
        {'n_rows': len(rows), 'n_refused': len(refused),
         'market_snapshot_sha256': snap['sha256'],
         'market_snapshot_path': snap['path'],
         'market_rows_skipped': snap['skipped'],
         'by_reason': dict(collections.Counter(
             x['reason'] for x in refused)),
         'refusals': refused}, indent=1) + '\n')
    print(f'{len(rows)} row(s) -> {out}')
    print(f'{len(refused)} refusal(s) -> {ref}')
    for k, v in collections.Counter(x['reason'] for x in refused).items():
        print(f'   {k}: {v}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
