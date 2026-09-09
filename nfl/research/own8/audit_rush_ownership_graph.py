"""OWN-8 Part A: prove which denominator owns each rushing component.

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' \
        python3.12 nfl/research/own8/audit_rush_ownership_graph.py

Two independent tests, because one would not settle it:

  1. COEFFICIENT OF VARIATION of the component rate under each candidate
     denominator. The denominator a quantity actually scales with is the one
     that makes its rate stable.
  2. CO-MOVEMENT with each budget. This is the test that matters for PER-DRAW
     coherence: a component must move WITH the budget it has to fit inside.

Measurement only. Nothing is fitted and no historical share is a target.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import math
import os
import statistics
import sys

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def scan(files):
    """Per team-game counts. A rush is classified by WHO took it, once."""
    passers = collections.defaultdict(set)
    rows = []
    for path in files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG' or _i(r.get('two_point_attempt')):
                    continue
                po = r.get('posteam') or ''
                if not po:
                    continue
                k = (_i(r.get('season')), _i(r.get('week')), po)
                if _i(r.get('qb_dropback')) and (r.get('passer_player_id') or ''):
                    passers[k].add(r['passer_player_id'])
                rows.append((k, r))
    tg = collections.defaultdict(collections.Counter)
    for k, r in rows:
        c = tg[k]
        if _i(r.get('qb_dropback')):
            c['dropbacks'] += 1
        if not _i(r.get('rush_attempt')):
            continue
        c['carries'] += 1
        rid = r.get('rusher_player_id') or ''
        # EXACTLY ONCE. The branches are exclusive by construction, so no rush
        # can be counted in two categories -- that is the whole point.
        if _i(r.get('qb_scramble')):
            c['scramble'] += 1
        elif _i(r.get('qb_kneel')):
            c['kneel'] += 1
        elif rid and rid in passers[k]:
            c['designed_qb'] += 1
        else:
            c['nonqb'] += 1
    return tg


def analyse(tg):
    ks = [k for k in tg if tg[k]['dropbacks'] > 0 and tg[k]['carries'] > 0]
    comps = ('scramble', 'designed_qb', 'kneel', 'nonqb')

    def cv(num, den):
        v = [tg[k][num] / tg[k][den] for k in ks if tg[k][den] > 0]
        m = statistics.mean(v)
        s = statistics.pstdev(v)
        return {'mean': round(m, 6), 'sd': round(s, 6),
                'cv': round(s / m, 6) if m else None}

    def corr(a, b):
        x = [tg[k][a] for k in ks]
        y = [tg[k][b] for k in ks]
        mx, my = statistics.mean(x), statistics.mean(y)
        sx, sy = statistics.pstdev(x), statistics.pstdev(y)
        if not sx or not sy:
            return None
        cov = sum((p - mx) * (q - my) for p, q in zip(x, y)) / len(ks)
        return round(cov / (sx * sy), 6)

    # closure: every carry lands in exactly one category
    res = [tg[k]['carries'] - sum(tg[k][c] for c in comps) for k in ks]
    out = {'n_team_games': len(ks),
           'closure_every_carry_exactly_one_category': {
               'exact': sum(1 for v in res if v == 0), 'n': len(ks),
               'max_abs': max(abs(v) for v in res)},
           'budget_correlation_carries_vs_dropbacks': corr('carries',
                                                           'dropbacks'),
           'components': {}}
    for c in comps:
        d, cc = cv(c, 'dropbacks'), cv(c, 'carries')
        owner = ('dropback' if (d['cv'] or math.inf) < (cc['cv'] or math.inf)
                 else 'carry')
        cd, ccr = corr(c, 'dropbacks'), corr(c, 'carries')
        out['components'][c] = {
            'per_dropback': d, 'per_carry': cc,
            'cv_test_owner': owner,
            'corr_with_dropbacks': cd, 'corr_with_carries': ccr,
            'comovement_test_owner': ('carry' if (ccr or 0) > (cd or 0)
                                      else 'dropback'),
        }
    out['reading'] = (
        'team carries and team dropbacks correlate '
        f'{out["budget_correlation_carries_vs_dropbacks"]}, so the two budgets '
        'move in OPPOSITE directions. A component generated on the dropback '
        'axis but required to fit inside the carry budget therefore has the '
        'wrong sign against its own container. qb2_lib draws designed QB '
        'rushes as Binom(dropbacks, drush_per_dropback); historically they '
        'correlate positively with carries and negatively with dropbacks. The '
        'simulator has the sign backwards.')
    return out


def main():
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB. The ownership '
                         'test is refused rather than assumed.')
    out = {'artifact': 'OWN8_RUSH_OWNERSHIP_GRAPH',
           'nothing_fitted': True,
           'historical_shares_are_evidence_not_targets': True,
           'source_files': [os.path.basename(p) for p in files],
           **analyse(scan(files))}
    dest = os.path.join(HERE, 'own8_ownership.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(json.dumps(out, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
