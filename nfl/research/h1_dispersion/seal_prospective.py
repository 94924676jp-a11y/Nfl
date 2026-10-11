"""H1 prospective seal (research chain): project 2026 weeks 5 and 6 with data through 2026 week 4 only.

    cd /home/user/nfl && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/user/p0work/pylib:. \
        python3.12 seal_prospective.py DEV_rows.csv.gz CHECKA_rows.csv.gz OUT.csv

Incumbent = production arm (blend 1.0, cap 2.0). Candidate = PREREG section 4 with c fitted on every earlier chain
week (2022-2025 rows, top-quartile players who played), per position, capped at 1. Writes only OUT.csv.
"""
import csv, gzip, sys, statistics as st, hashlib, json
from nfl.tools import forward_chain as FC, player_prior
from nfl.tools import proj_v1 as V, td_rates as R

def rows_of(path):
    with gzip.open(path, 'rt') as fh:
        return [r for r in csv.DictReader(fh) if r['arm'] == '1.0|2.0']

hist = rows_of(sys.argv[1]) + rows_of(sys.argv[2])
# top quartile per (season, week, pos) by projection, then c per position over all of it
from collections import defaultdict
g = defaultdict(list)
for r in hist:
    g[(r['season'], r['week'], r['pos'])].append(r)
num, den = defaultdict(float), defaultdict(float)
for (s, w, pos), v in g.items():
    q75 = sorted(float(r['proj']) for r in v)[int(0.75 * len(v))]
    for r in v:
        if float(r['proj']) >= q75 and r['appeared'] == '1':
            num[pos] += float(r['actual_dk']); den[pos] += float(r['proj'])
C = {pos: min(1.0, num[pos] / den[pos]) for pos in den}
n_weeks = len({(r['season'], r['week']) for r in hist})
print('c', {k: round(v, 4) for k, v in C.items()}, 'from', n_weeks, 'earlier chain weeks')

po = player_prior.load_panel(); assert po.state.name == 'PASS'
panel = po.value; pos_of = player_prior.position_index()
season = 2026; through = season - 1
pos_map, inferred = FC.positions_for_chain(panel, pos_of)
season_pos = FC._SeasonPos(pos_map, season, pos_of)
FC.PRATES[0] = R.positional_rates(panel, pos_of)
depth = V.depth_shares(panel, pos_of, through=through)
groups = V.group_shares(panel, pos_of, through=through)
bonus = V.bonus_rates(panel, pos_of, through=through)
ip = V.int_rate(panel, pos_of)['int_per_attempt']
gl = [x for x in panel['players'] if season_pos.get(x) in FC.SKILL]
priors = FC.season_priors(panel, season_pos, season, gl)
FC.TRANSITION[0] = set()
out = []
for week in (5, 6):
    inc = FC.project_week(panel, season_pos, season, week, priors, depth, groups, bonus, ip, 1.0, prior_cap=2.0)
    pool = set(FC.POOL[0]); club = dict(FC.POOL_CLUB[0])
    by = defaultdict(list)
    for x, p in inc.items():
        if p is not None and x in pool and season_pos.get(x) in FC.SKILL:
            by[season_pos.get(x)].append((x, p))
    for pos, v in by.items():
        q75 = sorted(p for _, p in v)[int(0.75 * len(v))]
        for x, p in v:
            cand = min(p, max(q75, C[pos] * p)) if p >= q75 else p
            out.append({'season': season, 'week': week, 'gsis': x, 'pos': pos, 'club': club.get(x),
                        'incumbent': round(p, 4), 'candidate': round(cand, 4), 'top_quartile': int(p >= q75),
                        'q75': round(q75, 4), 'c': round(C[pos], 4)})
with open(sys.argv[3], 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0]))
    w.writeheader(); w.writerows(out)
print('rows', len(out), {wk: sum(r['week'] == wk for r in out) for wk in (5, 6)},
      'sha256', hashlib.sha256(open(sys.argv[3], 'rb').read()).hexdigest())
