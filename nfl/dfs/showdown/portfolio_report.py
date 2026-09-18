"""Portfolio audit. Report the mismatches; do not quietly fix them.

An elite optimizer is not what is missing. What was missing on 2026-09-17 was
the ability to LOOK at a finished portfolio and see that Ray Davis was at 72.5%
while the model's own worlds put him in the optimal lineup 29.0% of the time
and carried a recorded defect against exactly that number.

So this is built before any optimizer. It reports; `portfolio_guard.authorize`
is the thing that refuses. Keeping them apart matters: an audit that silently
repaired what it found would destroy the evidence that the generator needed
changing.
"""
from __future__ import annotations

import collections
import itertools
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.showdown import universe as U                           # noqa: E402
from nfl.dfs.showdown import candidates as CD                        # noqa: E402
from nfl.production.dfs import projection_confidence as PC           # noqa: E402

SPEC_VERSION = 'nfl-showdown-portfolio-report-1'

#: A mismatch this large between exposure and simulated optimality is
#: HIGHLIGHTED, not corrected. Declared, round, not fitted.
MISMATCH_FLAG = 0.20


def report(lineups, players, *, optimal=None, corr=None,
           label='portfolio') -> Outcome:
    """`lineups` is a sequence of {'captain': name, 'flex': [names]}."""
    if not lineups:
        return Outcome.fail('PORTFOLIO_EMPTY', 'no lineups', cause=Cause.DATA)
    n = len(lineups)
    rows, errs = [], []
    for i, lu in enumerate(lineups):
        d = CD.describe(lu['captain'], lu['flex'], players, optimal=optimal,
                        corr=corr, lineup_id=i)
        if d.state is not State.PASS:
            errs.append({'lineup': i, 'code': d.code, 'detail': d.detail})
            continue
        rows.append(d.value)
    if errs:
        return Outcome.fail(
            'PORTFOLIO_CONTAINS_UNDESCRIBABLE_LINEUP',
            f'{len(errs)} lineup(s) could not be described: {errs[:3]}',
            cause=Cause.DATA, errors=errs)
    any_, cpt = collections.Counter(), collections.Counter()
    for r in rows:
        cpt[r['captain']] += 1
        for nm in [r['captain']] + r['flex']:
            any_[nm] += 1
    po = {x['name']: x for x in (optimal or [])}
    exposure = []
    for nm, c in sorted(any_.items(), key=lambda kv: -kv[1]):
        tag = next(p['tag'] for p in players if p['name'] == nm)
        e = c / n
        ce = cpt.get(nm, 0) / n
        opt = po.get(nm, {}).get('p_optimal')
        optc = po.get(nm, {}).get('p_optimal_captain')
        exposure.append({
            'player': nm, 'tag': tag, 'exposure': round(e, 4),
            'captain_exposure': round(ce, 4),
            'p_optimal': (round(opt, 4) if opt is not None else None),
            'p_optimal_captain': (round(optc, 4) if optc is not None else None),
            'exposure_minus_optimality': (round(e - opt, 4)
                                          if opt is not None else None),
            'captain_exposure_minus_optimality': (
                round(ce - optc, 4) if optc is not None else None),
            'salary': next(p['salary'] for p in players if p['name'] == nm),
        })
    mismatches = [e for e in exposure
                  if e['exposure_minus_optimality'] is not None
                  and abs(e['exposure_minus_optimality']) >= MISMATCH_FLAG]
    cpt_mismatches = [e for e in exposure
                      if e['captain_exposure_minus_optimality'] is not None
                      and abs(e['captain_exposure_minus_optimality'])
                      >= MISMATCH_FLAG / 2]
    sal = np.array([r['salary'] for r in rows])
    left = np.array([r['salary_remaining'] for r in rows])
    cores = collections.Counter(
        tuple(sorted([r['captain']] + r['flex'])) for r in rows)
    dup_cores = {' + '.join(k): v for k, v in cores.items() if v > 1}
    # UNIQUENESS DISTANCE: how many players two lineups differ by, pairwise.
    sets = [set([r['captain']] + r['flex']) for r in rows]
    dists = [6 - len(a & b) for a, b in itertools.combinations(sets, 2)]
    tag_exposure = collections.Counter()
    for r in rows:
        for t in r['confidence_tags'].values():
            tag_exposure[t] += 1
    cheap_exposed = collections.Counter()
    for r in rows:
        d = r['salary_relief_dependence']
        if d:
            cheap_exposed[d['cheapest_player']] += 1
    ev = {
        'spec_version': SPEC_VERSION, 'label': label, 'n_lineups': n,
        'exposure': exposure,
        'exposure_vs_optimality_mismatches': mismatches,
        'captain_exposure_vs_optimality_mismatches': cpt_mismatches,
        'salary': {'min': int(sal.min()), 'max': int(sal.max()),
                   'mean': float(sal.mean())},
        'salary_remaining': {'min': int(left.min()), 'max': int(left.max()),
                             'mean': float(left.mean())},
        'duplicated_cores': dup_cores,
        'n_unique_lineups': len(set(tuple(sorted(s)) for s in sets)),
        'uniqueness_distance': ({'min': int(min(dists)),
                                 'mean': float(np.mean(dists)),
                                 'max': int(max(dists))} if dists else None),
        'confidence_tag_slot_share': {k: round(v / (6 * n), 4)
                                      for k, v in tag_exposure.items()},
        'concern_slots_per_lineup': float(
            np.mean([r['n_concern_tagged'] for r in rows])),
        'cheap_punt_reliance': {k: round(v / n, 4)
                                for k, v in cheap_exposed.most_common()},
        'mismatch_flag': MISMATCH_FLAG,
        'this_module_does_not_repair': True,
        'uses_live_game_outcome_data': False,
    }
    return Outcome.ok(
        'PORTFOLIO_REPORTED', value={'lineups': rows, 'exposure': exposure},
        detail=f'{label}: {n} lineup(s), {ev["n_unique_lineups"]} unique, '
               f'{len(mismatches)} exposure/optimality mismatch(es) at or '
               f'beyond {MISMATCH_FLAG:.0%}',
        **ev)
