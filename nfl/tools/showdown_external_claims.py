#!/usr/bin/env python3.12
"""External strategy source (owner-supplied video transcript, Stochastic ATL @ NO show, 2026-10-05) as a
structured claims table beside OUR numbers. EXTERNAL_STRATEGY_AND_OWNERSHIP_BENCHMARK_ONLY.

    python3.12 nfl/tools/showdown_external_claims.py SCENARIO_DIR

Nothing here changes a projection, a role or a simulation. Each claim is typed (SIM_OUTPUT, OWNERSHIP,
HOST_OPINION, HARD_NUMBER, MARKET), tagged UNVERIFIED_EXTERNAL unless we checked it, and set beside our own
value computed from our worlds where one exists. Market figures are recorded as reported and never used.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_slate_run as CR  # noqa: E402

FIELDS = {f: i for i, f in enumerate(CR.WORLD_FIELDS)}

# (id, player, team, type, claim, timestamp, number, our_metric)
CLAIMS = [
    ('V01', 'Kendre Miller', 'NO', 'SIM_OUTPUT', '50+ rushing yards', '8:12', 0.15, ('rush_yards', 50)),
    ('V02', 'Kendre Miller', 'NO', 'SIM_OUTPUT', '15+ rushing attempts', '8:23', 0.04, ('carries', 15)),
    ('V03', 'Alvin Kamara', 'NO', 'SIM_OUTPUT', '15+ rushing attempts', '8:35', 0.21, ('carries', 15)),
    ('V04', 'Kendre Miller', 'NO', 'SIM_OUTPUT', 'rushing or receiving TD', '56:32', 0.31, ('td', 1)),
    ('V05', 'Alvin Kamara', 'NO', 'SIM_OUTPUT', 'rushing or receiving TD', '56:42', 0.39, ('td', 1)),
    ('V06', 'Drake London', 'ATL', 'HARD_NUMBER', 'with Penix: ~11 tgt/g, 35% share, >100 yds/g, 43% air, 40% RZ (13 games)',
     '15:38', None, ('verified', 'pbp 2024-26, 12 games Penix >=80% of attempts: 11.25 tgt/g, 35.6%, 103.1 yds/g, 41.1% air, 40.4% RZ; '
                     'other QBs 18 games: 7.89, 26.1%, 58.7, 33.6%, 40.0%. REPRODUCES. Our allocation is QB-agnostic.')),
    ('V07', 'Kyle Pitts Sr.', 'ATL', 'HARD_NUMBER', 'lower target share with Penix (~16%)', '16:39', 0.16,
     ('verified', 'pbp: 16.4% with Penix vs 18.8% without; 36.0 vs 47.3 yds/g. REPRODUCES.')),
    ('V08', 'Bijan Robinson', 'ATL', 'OWNERSHIP', 'CPT sim exposure ~29%', '18:57', 0.29, ('cpt_exposure', None)),
    ('V09', 'Alvin Kamara', 'NO', 'OWNERSHIP', 'projected ownership ~33% (CPT ~4%)', '45:18', 0.33, ('flex_exposure', None)),
    ('V10', 'Kendre Miller', 'NO', 'OWNERSHIP', 'projected ownership ~13% (CPT ~6%)', '45:18', 0.13, ('flex_exposure', None)),
    ('V11', 'Bryce Lance', 'NO', 'OWNERSHIP', 'projected ownership ~25%', '1:10:53', 0.25, ('flex_exposure', None)),
    ('V12', 'Jahan Dotson', 'ATL', 'OWNERSHIP', 'projected ownership ~18%', '1:10:53', 0.18, ('flex_exposure', None)),
    ('V13', 'Olamide Zaccheaus', 'ATL', 'OWNERSHIP', 'field ~10%, their exposure <3%', '26:57', 0.10, ('flex_exposure', None)),
    ('V14', 'Bijan Robinson', 'ATL', 'SIM_OUTPUT', 'optimal rate ~45%', '50:27', 0.45, ('optimal', None)),
    ('V15', 'Alvin Kamara', 'NO', 'SIM_OUTPUT', 'optimal rate ~35%', '50:27', 0.35, ('optimal', None)),
    ('V16', 'Tyler Shough', 'NO', 'MARKET', 'passing yards prop 257-261 (recorded, never used)', '38:17', 259, ('pass_yards_mean', None)),
    ('V17', 'Tyler Shough', 'NO', 'HARD_NUMBER', '132 pass attempts through 3 weeks', '32:49', 132,
     ('verified', 'nflverse pbp weeks 1-3: 133 attempts excl. sacks (57/34/42). REPRODUCES.')),
    ('V18', 'Alvin Kamara', 'NO', 'MARKET', 'rush attempts prop 11.5 (Miller 6.5) (recorded, never used)', '54:17', 11.5, ('carries_mean', None)),
    ('V19', 'Noah Fant', 'NO', 'HOST_OPINION', 'likely active; Oscar Delp the cheap TE path if out', '29:30', None, ('scenario', 'FANT_OUT staged')),
    ('V20', 'Saints/Falcons TE', 'NO', 'HARD_NUMBER', '9 of 20 NO red-zone targets to the tight ends', '30:18', 9,
     ('verified', 'our role review: Johnson 6 + Fant 3 = 9 of 19 NO RZ targets (yardline<=20, weeks 1-3). REPRODUCES (19 vs 20).')),
]


def run(sd):
    sd = pathlib.Path(sd)
    import glob
    worlds = next(sd.glob('SHOWDOWN_*_WORLDS.npz'))
    stats, _pts, meta = CR.load_worlds(worlds)
    keys = meta['keys']
    audit = json.loads(next(sd.glob('SHOWDOWN_*_AUDIT.json')).read_text())
    draws = json.loads(next(sd.glob('SHOWDOWN_*_DRAWS.json')).read_text())['draws']
    exp_flex, exp_cpt, n_all = {}, {}, 0
    fl = next(sd.glob('SHOWDOWN_*_FINAL_LINEUPS.csv'))
    for r in csv.DictReader(open(fl)):
        if r['contest_id'] != '196285137':
            continue
        n_all += 1
        exp_cpt[r['CPT']] = exp_cpt.get(r['CPT'], 0) + 1
        for k in ('CPT', 'FLEX1', 'FLEX2', 'FLEX3', 'FLEX4', 'FLEX5'):
            exp_flex[r[k]] = exp_flex.get(r[k], 0) + 1
    cptb = {r['player']: r for r in csv.DictReader(open(next(sd.glob('SHOWDOWN_*_CPT_BOARD.csv'))))}
    out = []
    for cid, pl, tm, typ, claim, ts, num, (metric, arg) in CLAIMS:
        key = f'{pl}|{tm}'
        ours, note = None, ''
        if key in keys and metric in ('rush_yards', 'carries'):
            a = stats[keys.index(key), :, FIELDS[metric]] / (meta['yard_scale'] if metric in meta['yard_fields'] else 1)
            ours = round(float((a >= arg).mean()), 3)
        elif key in keys and metric == 'td':
            i = keys.index(key)
            a = stats[i, :, FIELDS['rush_td']] + stats[i, :, FIELDS['rec_td']]
            ours = round(float((a >= 1).mean()), 3)
        elif metric == 'cpt_exposure':
            ours = round(exp_cpt.get(pl, 0) / max(1, n_all), 3)
            note = 'OUR 150-max CPT exposure (a portfolio choice, not a field ownership forecast)'
        elif metric == 'flex_exposure':
            ours = round(exp_flex.get(pl, 0) / max(1, n_all), 3)
            note = 'OUR 150-max total exposure; OUR FIELD OWNERSHIP FORECAST: UNAVAILABLE (no Showdown history)'
        elif metric == 'optimal':
            ours = float(cptb.get(pl, {}).get('p_world_optimal_captain') or 0) if pl in cptb else None
            note = 'ours is the CAPTAIN optimal rate over our worlds; theirs may count any slot'
        elif metric == 'pass_yards_mean' and key in keys:
            ours = round(float(stats[keys.index(key), :, FIELDS['pass_yards']].mean() / meta['yard_scale']), 1)
            note = 'market figure recorded only; our number was frozen before reading it'
        elif metric == 'carries_mean' and key in keys:
            ours = round(float(stats[keys.index(key), :, FIELDS['carries']].mean()), 2)
            m2 = 'Kendre Miller|NO'
            if m2 in keys:
                note = f"Miller ours {float(stats[keys.index(m2), :, FIELDS['carries']].mean()):.2f}; market recorded only"
        elif metric in ('verified', 'scenario'):
            note = arg
        status = ('VERIFIED_BY_US' if metric == 'verified' else
                  'MARKET_RECORDED_NOT_USED' if typ == 'MARKET' else 'UNVERIFIED_EXTERNAL')
        diff = (round(ours - num, 3) if isinstance(ours, (int, float)) and isinstance(num, (int, float))
                and typ != 'MARKET' else None)
        out.append({'claim_id': cid, 'player': pl, 'team': tm, 'type': typ, 'claim': claim, 'timestamp': ts,
                    'their_number': num, 'our_number': ours, 'ours_minus_theirs': diff, 'status': status, 'note': note})
    p = sd / 'SHOWDOWN_ATL_NO_EXTERNAL_VIDEO_CLAIMS.csv'
    with p.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    return p, out


if __name__ == '__main__':
    p, out = run(sys.argv[1])
    print(p)
    for r in out:
        print(r)
