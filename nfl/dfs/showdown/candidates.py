"""The candidate lineup data model, and the cheap-punt failure mode measured.

A LINEUP IS NOT SIX PLAYER IDS

The 2026-09-17 generator emitted six ids and a projected mean. Nothing
downstream could ask what the lineup depended on, how concentrated its risk
was, or whether any of its players carried a recorded defect -- because the
lineup did not carry the answers. Every one of those questions had to be
reconstructed afterwards from a CSV.

SALARY_RELIEF_DEPENDENCE

Frank Gore Jr. reached 55% exposure at $400 for 4.24 projected points: 10.6
points per $1,000 against 1.8 for Jahmyr Gibbs. Under a pure mean objective
that trade is accepted every time it is offered. The quantity that was never
computed is how much of the lineup's FEASIBILITY rested on him -- whether the
other five players could still be afforded without the punt.

`salary_relief_dependence` answers exactly that: remove the cheapest player,
and ask what the best available replacement costs relative to the room left.
A lineup that collapses without its $400 player is a lineup betting on the
$400 player, whatever its projected mean says.

NO THRESHOLD IS SET HERE. The diagnostic is reported; no rule is fitted from
one slate's outcome, and a cap derived from tonight would be the postmortem's
own mistake repeated.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.showdown import universe as U                           # noqa: E402
from nfl.production.dfs import projection_confidence as PC           # noqa: E402

SPEC_VERSION = 'nfl-showdown-candidate-1'

#: A player at or under this salary is CHEAP for the purposes of the
#: dependence diagnostic. Declared, not fitted: it is the bottom of the DK
#: salary ladder on a Showdown slate, where a roster spot costs about 1% of
#: the cap.
CHEAP_SALARY = 1000


def describe(captain, flex, players, *, optimal=None, scenarios=None,
             corr=None, lineup_id=None) -> Outcome:
    """One candidate, fully described. `captain` and `flex` are player names."""
    by = {p['name']: p for p in players}
    missing = [n for n in [captain] + list(flex) if n not in by]
    if missing:
        return Outcome.fail(
            'CANDIDATE_UNKNOWN_PLAYER', f'{missing} are not in the universe',
            cause=Cause.DATA)
    if len(set([captain] + list(flex))) != len(flex) + 1:
        return Outcome.fail('CANDIDATE_DUPLICATE_PLAYER',
                            f'{captain} / {flex} repeats a player',
                            cause=Cause.DATA)
    c = by[captain]
    fl = [by[n] for n in flex]
    salary = c['cpt_salary'] + sum(p['salary'] for p in fl)
    score = c['draws'] * U.CPT_MULTIPLIER + np.sum(
        [p['draws'] for p in fl], axis=0)
    tags = {n: by[n]['tag'] for n in [captain] + list(flex)}
    concern = [n for n, t in tags.items() if t != PC.MODEL_SUPPORTED]
    cheap = sorted([p for p in fl if p['salary'] <= CHEAP_SALARY],
                   key=lambda p: p['salary'])
    # SALARY RELIEF DEPENDENCE. Drop the cheapest player and ask what could be
    # afforded in his place out of the room that frees up.
    dep = None
    if cheap:
        drop = cheap[0]
        room = U.SALARY_CAP - (salary - drop['salary'])
        pool = [p for p in players
                if p['name'] not in tags and p['salary'] <= room]
        best = max((p['draws'].mean() for p in pool), default=0.0)
        dep = {
            'cheapest_player': drop['name'],
            'cheapest_salary': drop['salary'],
            'cheapest_mean_dk': float(drop['draws'].mean()),
            'cheapest_pts_per_1k': float(drop['draws'].mean()
                                         / (drop['salary'] / 1000.0)),
            'room_if_dropped': int(room),
            'best_affordable_replacement_mean': float(best),
            'mean_lost_by_swapping': float(drop['draws'].mean() - best),
            'n_cheap_players_in_lineup': len(cheap),
        }
    teams = {p['team'] for p in [c] + fl}
    pair_r = None
    if corr is not None:
        names = corr['names']
        idx = {n: i for i, n in enumerate(names)}
        rs = []
        for a, b in itertools.combinations([captain] + list(flex), 2):
            if a in idx and b in idx:
                r = corr['matrix'][idx[a]][idx[b]]
                if r == r:
                    rs.append(r)
        if rs:
            pair_r = {'mean_pairwise_r': float(np.mean(rs)),
                      'max_pairwise_r': float(np.max(rs)),
                      'min_pairwise_r': float(np.min(rs)),
                      'n_negative_pairs': int(sum(1 for r in rs if r < 0))}
    row = {
        'lineup_id': lineup_id,
        'captain': captain, 'flex': list(flex),
        'captain_dk_id': c['cpt_dk_id'],
        'flex_dk_ids': [p['dk_id'] for p in fl],
        'salary': int(salary), 'salary_remaining': int(U.SALARY_CAP - salary),
        'legal_salary': bool(salary <= U.SALARY_CAP),
        'both_teams': len(teams) >= 2,
        'projected_mean': float(score.mean()),
        'median': float(np.median(score)),
        'p90': float(np.percentile(score, 90)),
        'p95': float(np.percentile(score, 95)),
        'confidence_tags': tags,
        'n_concern_tagged': len(concern),
        'concern_players': sorted(concern),
        'blocked_players': sorted(n for n, t in tags.items()
                                  if PC.POLICY[t]['blocked']),
        'salary_relief_dependence': dep,
        'pairwise_correlation': pair_r,
        'scenario_source': scenarios,
    }
    if optimal is not None:
        po = {r['name']: r for r in optimal}
        row['player_optimality'] = {
            n: round(po.get(n, {}).get('p_optimal', 0.0), 4)
            for n in [captain] + list(flex)}
        row['captain_optimality'] = round(
            po.get(captain, {}).get('p_optimal_captain', 0.0), 4)
    return Outcome.ok(
        'CANDIDATE_DESCRIBED', value=row,
        detail=f'{captain} + {len(flex)} flex, ${salary}, '
               f'mean {score.mean():.2f}, {len(concern)} concern-tagged',
        spec_version=SPEC_VERSION, uses_live_game_outcome_data=False)
