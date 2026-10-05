#!/usr/bin/env python3.12
"""ATL@NO Hard Rock player-prop comparison: DOWNSTREAM, SHADOW / NOT_VALIDATED. Never an input to anything upstream.

    python3.12 nfl/market/atl_no_prop_shadow.py seal                 # freeze our per-world stat distributions
    python3.12 nfl/market/atl_no_prop_shadow.py compare BOARD.csv    # score a captured Hard Rock board against the seal
    python3.12 nfl/market/atl_no_prop_shadow.py grade ACTUALS.json   # post-game: score every sealed comparison

ORDER (nfl/market/price_history.comparable): the forecast is SEALED first, the price captured after the seal and
before kickoff; any other order is refused by name. Hard Rock lines, prices, implied probabilities, spreads, totals
and props never travel back into the football model, the simulation or any DFS lineup -- this module has no code
path that writes anywhere upstream, and the DFS portfolio is not read here at all.

SOURCE OF OUR NUMBERS: the frozen v2 production worlds (RW_INACTIVES_CHARTFIX, official inactives), per-world stat
lines after the efficiency step -- not DK points.

TARGET-SPECIFIC VALIDATION RULE (owner, 2026-10-05). A good fantasy-point model validates no prop market. Each target
is judged on its own process, and every target below is SHADOW / NOT_VALIDATED: no held-out calibration of these
per-player stat distributions exists in this repository (the receiving zero-mass debt DEBT-RECV-CALIB is still open).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_slate_run as CR  # noqa: E402
from nfl.market import price_history as PH  # noqa: E402

SD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
OUT = _REPO / 'nfl/market/atl_no_2026W4'
KICKOFF_UTC = '2026-10-06T00:15:00+00:00'
LABEL = 'SHADOW / NOT_VALIDATED'
#: Hard Rock market name -> (our simulated variable, how to read it). Priority order from the owner directive.
MARKETS = {
    'player_receptions': ('receptions', 'COUNT'),
    'player_receiving_yards': ('rec_yards', 'YARDS'),
    'player_rushing_yards': ('rush_yards', 'YARDS'),
    'player_passing_yards': ('pass_yards', 'YARDS'),
    'player_passing_touchdowns': ('pass_td', 'COUNT'),
    'player_anytime_touchdown': ('anytime_td', 'TD'),
    'player_to_score_a_touchdown': ('anytime_td', 'TD'),
    'anytime_touchdown_scorer': ('anytime_td', 'TD'),
}
VALIDATION = {
    'receptions': ('NOT_VALIDATED', 'must be judged on the RECEPTION PROCESS: routes x targets/route x catch rate, '
                   'and the zero-reception mass (DEBT-RECV-CALIB open); a fantasy-point fit says nothing about it'),
    'rec_yards': ('NOT_VALIDATED', 'volume (targets) x efficiency (yards/target) AND tail behaviour; needs PIT and '
                  'upper-tail coverage on held-out games'),
    'rush_yards': ('NOT_VALIDATED', 'carries x yards/carry AND tail; rushing efficiency is barely sticky (SumerSports)'),
    'pass_yards': ('NOT_VALIDATED', 'attempts x yards/attempt AND tail; game-script dependence'),
    'pass_td': ('NOT_VALIDATED', 'TD-incidence calibration (P(0), P(1), P(2+)) on held-out games'),
    'anytime_td': ('NOT_VALIDATED', 'TD-incidence calibration per player role; the TD pool share is the weakest-'
                   'identified piece (B6 TD recoverability experiment pending)'),
}


def _worlds():
    stats, _pts, meta = CR.load_worlds(next(SD.glob('SHOWDOWN_*_WORLDS.npz')))
    F = {f: i for i, f in enumerate(meta['fields'])}
    keys = list(meta['keys'])
    out = {}
    for i, k in enumerate(keys):
        g = lambda f: stats[i, :, F[f]] / (meta['yard_scale'] if f in meta['yard_fields'] else 1)
        out[k] = {'receptions': g('receptions'), 'rec_yards': g('rec_yards'), 'rush_yards': g('rush_yards'),
                  'pass_yards': g('pass_yards'), 'pass_td': g('pass_td'),
                  'anytime_td': g('rush_td') + g('rec_td')}
    return out, meta


def seal():
    W, meta = _worlds()
    OUT.mkdir(parents=True, exist_ok=True)
    players = {}
    for k, d in W.items():
        players[k] = {}
        for var, a in d.items():
            a = np.asarray(a, dtype=float)
            if not np.any(a):
                continue
            players[k][var] = {'mean': round(float(a.mean()), 3), 'median': float(np.median(a)),
                               'p10': float(np.percentile(a, 10)), 'p90': float(np.percentile(a, 90)),
                               'p_zero': round(float((a == 0).mean()), 4),
                               'worlds': [round(float(x), 2) for x in a]}
    if not players:
        raise SystemExit('PROP_SEAL_EMPTY')
    body = {'ARTIFACT': 'ATL_NO_PROP_FORECAST_SEAL', 'label': LABEL, 'source_dir': str(SD.relative_to(_REPO)),
            'worlds_projection_sha256': meta.get('projection_sha256'), 'n_worlds': len(next(iter(W.values()))['receptions']),
            'kickoff_utc': KICKOFF_UTC, 'validation': {k: {'status': v[0], 'rule': v[1]} for k, v in VALIDATION.items()},
            'players': players}
    blob = json.dumps(body, sort_keys=True).encode()
    body['seal_sha256'] = hashlib.sha256(blob).hexdigest()
    body['written_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    p = OUT / 'PROP_FORECAST_SEAL.json'
    if p.exists():
        raise SystemExit(f'PROP_SEAL_EXISTS {p} -- a seal is never overwritten')
    p.write_text(json.dumps(body))
    p.chmod(0o444)
    return p, body


def _devig(po, pu):
    imp = lambda a: (100.0 / (a + 100.0)) if a > 0 else (-a / (-a + 100.0))
    if po is None or pu is None:
        return None, None
    io, iu = imp(po), imp(pu)
    return io / (io + iu), io + iu - 1.0


def compare(board_csv):
    seal_doc = json.loads((OUT / 'PROP_FORECAST_SEAL.json').read_text())
    rows = list(csv.DictReader(open(board_csv, newline='', encoding='utf-8-sig')))
    if not rows:
        raise SystemExit('HR_BOARD_EMPTY')
    names = {k.split('|')[0]: k for k in seal_doc['players']}
    out, refused = [], []
    for r in rows:
        mk = r.get('market', '')
        if mk not in MARKETS:
            continue
        var, kind = MARKETS[mk]
        key = names.get((r.get('selection') or '').strip())
        if key is None or var not in seal_doc['players'].get(key, {}):
            refused.append({'market': mk, 'selection': r.get('selection'), 'why': 'NO_SIMULATED_VARIABLE_FOR_THIS_PLAYER'})
            continue
        ok = PH.comparable(seal_doc, {'ts_utc': r.get('ts_utc')})
        if ok.state.value != 'PASS':
            refused.append({'market': mk, 'selection': r.get('selection'), 'why': ok.code})
            continue
        a = np.asarray(seal_doc['players'][key][var]['worlds'])
        line = float(r['points']) if r.get('points') not in (None, '') else (0.5 if kind == 'TD' else None)
        if line is None:
            refused.append({'market': mk, 'selection': r.get('selection'), 'why': 'NO_LINE'})
            continue
        p_over = float((a > line).mean())
        po = float(r['over']) if r.get('over') not in (None, '') else (float(r['price']) if r.get('price') else None)
        pu = float(r['under']) if r.get('under') not in (None, '') else None
        mkt, hold = _devig(po, pu)
        n = len(a)
        se = (p_over * (1 - p_over) / n) ** 0.5
        warn = []
        if min(p_over, 1 - p_over) < 0.05:
            warn.append('EXTREME_TAIL: fewer than 5% of worlds on one side')
        if kind == 'TD' and pu is None:
            warn.append('ONE_SIDED_PRICE: no vig removal possible, raw implied probability shown')
        out.append({'player': key.split('|')[0], 'team': key.split('|')[1], 'prop_type': mk, 'our_variable': var,
                    'line': line, 'over_price': po, 'under_price': pu, 'timestamp': r.get('ts_utc'),
                    'market_id': r.get('over_id') or r.get('price_id') or None,
                    'our_mean': seal_doc['players'][key][var]['mean'], 'our_median': seal_doc['players'][key][var]['median'],
                    'our_p_over': round(p_over, 4), 'our_p_under': round(1 - p_over, 4), 'mc_se': round(se, 4),
                    'market_p_over_novig': (round(mkt, 4) if mkt is not None else
                                            (round(100 / (po + 100) if po and po > 0 else (-po / (-po + 100)), 4) if po else None)),
                    'hold': round(hold, 4) if hold is not None else None,
                    'gap_ours_minus_market': (round(p_over - mkt, 4) if mkt is not None else None),
                    'uncertainty_warning': warn or ['MODEL_UNVALIDATED_FOR_THIS_TARGET'],
                    'validation_status': VALIDATION[var][0], 'validation_rule': VALIDATION[var][1], 'label': LABEL,
                    'NOT_A_WAGER_RECOMMENDATION': True, 'DFS_EFFECT': 'NONE (downstream comparison only)'})
    order = {v: i for i, v in enumerate(['receptions', 'rec_yards', 'rush_yards', 'pass_yards', 'pass_td', 'anytime_td'])}
    out.sort(key=lambda x: (order[x['our_variable']], x['player'], x['line']))
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%MZ')
    res = {'ARTIFACT': 'ATL_NO_PROP_COMPARISON', 'label': LABEL, 'seal_sha256': seal_doc['seal_sha256'],
           'seal_written_at': seal_doc['written_at'], 'board': str(board_csv),
           'board_sha256': hashlib.sha256(pathlib.Path(board_csv).read_bytes()).hexdigest(),
           'n_compared': len(out), 'n_refused': len(refused), 'refused': refused, 'rows': out}
    (OUT / f'PROP_COMPARISON_{stamp}.json').write_text(json.dumps(res, indent=1))
    with (OUT / f'PROP_COMPARISON_{stamp}.csv').open('w', newline='') as fh:
        if out:
            w = csv.DictWriter(fh, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
    # PROSPECTIVE GRADING LEDGER: one row per compared price, outcome fields empty until the game is final
    with (OUT / 'PROP_GRADING_LEDGER.jsonl').open('a') as fh:
        for x in out:
            fh.write(json.dumps({**{k: x[k] for k in ('player', 'team', 'prop_type', 'our_variable', 'line', 'over_price',
                                                     'under_price', 'timestamp', 'market_id', 'our_p_over',
                                                     'market_p_over_novig')},
                                 'seal_sha256': seal_doc['seal_sha256'], 'actual': None, 'graded': False}) + '\n')
    return res


def grade(actuals_json):
    """Post-game: actuals {player|team: {receptions, rec_yards, rush_yards, pass_yards, pass_td, anytime_td}} from the
    official box score. Scores every ledger row (Brier and log loss for ours and for the no-vig market), plus the
    PIT of the realised value inside our sealed world distribution. Rows are appended graded, never overwritten."""
    act = json.loads(pathlib.Path(actuals_json).read_text())
    seal_doc = json.loads((OUT / 'PROP_FORECAST_SEAL.json').read_text())
    led = [json.loads(l) for l in (OUT / 'PROP_GRADING_LEDGER.jsonl').read_text().splitlines() if l.strip()]
    graded = []
    for r in led:
        if r.get('graded'):
            continue
        k = f"{r['player']}|{r['team']}"
        if k not in act or r['our_variable'] not in act[k]:
            continue
        y = float(act[k][r['our_variable']])
        hit = 1.0 if y > r['line'] else 0.0
        a = np.asarray(seal_doc['players'][k][r['our_variable']]['worlds'])
        pit = float((a < y).mean() + 0.5 * (a == y).mean())
        ll = lambda p: -np.log(max(1e-6, p if hit else 1 - p))
        g = {**r, 'actual': y, 'over_hit': hit, 'graded': True, 'pit': round(pit, 4),
             'brier_ours': round((r['our_p_over'] - hit) ** 2, 4), 'logloss_ours': round(float(ll(r['our_p_over'])), 4)}
        if r.get('market_p_over_novig') is not None:
            g.update({'brier_market': round((r['market_p_over_novig'] - hit) ** 2, 4),
                      'logloss_market': round(float(ll(r['market_p_over_novig'])), 4)})
        graded.append(g)
    with (OUT / 'PROP_GRADING_LEDGER_GRADED.jsonl').open('a') as fh:
        for g in graded:
            fh.write(json.dumps(g) + '\n')
    return {'graded': len(graded), 'NOTE': 'one game is one observation; nothing is promoted on it'}


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'seal':
        p, b = seal()
        print(p, b['seal_sha256'], b['written_at'], len(b['players']), 'players')
    elif cmd == 'compare':
        r = compare(sys.argv[2])
        print(r['n_compared'], 'compared,', r['n_refused'], 'refused')
    elif cmd == 'grade':
        print(grade(sys.argv[2]))
    else:
        raise SystemExit(__doc__)
