"""Captain-relevant features, measured from the 8,000 frozen worlds.

WHAT WENT WRONG THAT THIS REPLACES

The 2026-09-17 portfolio chose captains by mean DK points and then spread them
with a counter: `capct[ck] >= 6` against 40 lineups is 15.0%, and it bound for
six different captains at once, which is why six captains sat at exactly 15.0%.
That is a counting rule wearing the costume of a football judgement.

Eight thousand simulated worlds were sitting in the same file. A captain is the
single largest bet a lineup makes -- 1.5x points on 1.5x salary -- and the
quantity that decides it is not the mean. It is how often the player is the
one who goes off.

WHAT THIS MODULE DOES AND DOES NOT PRODUCE

It produces FEATURES. It does not produce exposure percentages, and it must
not be extended to until the layers that would justify one exist: optimality
frequency, ownership, duplication, scenario allocation, payout structure. The
whole failure was a number being turned into an allocation by a mechanism that
had no standing to do it.

`p_top1` is P(this player is the highest RAW DK scorer in the game). It is NOT
an ownership projection, NOT a win probability, and NOT P(optimal captain) --
that last one lives in `optimal_worlds.py` and is a different quantity, because
the optimal captain is constrained by salary and by the five flex slots that
have to fit underneath him.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.showdown import universe as U                           # noqa: E402

SPEC_VERSION = 'nfl-showdown-captain-metrics-1'

#: Reported thresholds. Declared, round, and not fitted to anything.
DK_THRESHOLDS = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0)

PCTILES = (50, 75, 90, 95, 99)


def metrics(players=None, thresholds=DK_THRESHOLDS) -> Outcome:
    if players is None:
        u = U.build()
        if u.state is not State.PASS:
            return u
        players = u.value['playable']
    if not players:
        return Outcome.fail('CAPTAIN_METRICS_NO_PLAYERS', 'empty universe',
                            cause=Cause.DATA)
    M = np.vstack([p['draws'] for p in players])          # (n_players, n_draws)
    n_p, n_d = M.shape
    # RANK WITHIN EACH WORLD. Ties are resolved explicitly below rather than by
    # whatever argsort happens to do with equal values.
    order = np.argsort(-M, axis=0, kind='stable')
    top1 = order[0]
    top2 = order[1]
    # A TIE FOR FIRST IS A TIE, NOT A WIN. Zero is the common case here: on a
    # slate where many players score exactly 0.0 DK, argsort would hand "the
    # highest scorer" to whichever row sorts first, which is an artefact of row
    # order and not football.
    best = M.max(axis=0)
    n_at_best = (M == best[None, :]).sum(axis=0)
    unique_top = n_at_best == 1
    rows = []
    for i, p in enumerate(players):
        v = p['draws']
        q = {f'p{k}': float(np.percentile(v, k)) for k in PCTILES}
        t1 = float(((top1 == i) & unique_top).mean())
        t2 = float((((top1 == i) | (top2 == i)) & unique_top).mean())
        rows.append({
            'name': p['name'], 'team': p['team'], 'pos': p['pos'],
            'dk_id': p['dk_id'], 'cpt_dk_id': p['cpt_dk_id'],
            'salary': p['salary'], 'cpt_salary': p['cpt_salary'],
            'tag': p['tag'],
            'mean': float(v.mean()), **q,
            'p_zero': float((v == 0).mean()),
            'p_top1_unique': t1, 'p_top2_unique': t2,
            'p_tied_for_top': float(((M[i] == best) & ~unique_top).mean()),
            # THE CAPTAIN TRANSFORM, APPLIED MECHANICALLY. 1.5x the score and
            # 1.5x the salary; nothing else about the player changes.
            'cpt_mean': float(v.mean() * U.CPT_MULTIPLIER),
            'cpt_p90': float(np.percentile(v, 90) * U.CPT_MULTIPLIER),
            'cpt_p99': float(np.percentile(v, 99) * U.CPT_MULTIPLIER),
            'flex_pts_per_1k': float(v.mean() / (p['salary'] / 1000.0)),
            'cpt_pts_per_1k': float(v.mean() * U.CPT_MULTIPLIER
                                    / (p['cpt_salary'] / 1000.0)),
            'p_over': {str(t): float((v > t).mean()) for t in thresholds},
        })
    rows.sort(key=lambda r: -r['p_top1_unique'])
    ties = float((~unique_top).mean())
    return Outcome.ok(
        'CAPTAIN_METRICS', value=rows,
        detail=f'{n_p} player(s) over {n_d} world(s); '
               f'{ties:.2%} of worlds have a tie for highest raw scorer, '
               f'excluded from p_top1 rather than broken arbitrarily',
        spec_version=SPEC_VERSION, n_players=n_p, n_draws=n_d,
        share_of_worlds_with_tied_top=ties,
        thresholds=list(thresholds), percentiles=list(PCTILES),
        is_not='p_top1 is NOT ownership, NOT a win probability, and NOT '
               'P(optimal captain) -- see optimal_worlds.py for that',
        exposure_percentages_produced=False,
        uses_live_game_outcome_data=False)


def main() -> int:
    o = metrics()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    print(f"{'player':22s} {'tm':3s} {'tag':20s} {'sal':>6s} {'mean':>6s} "
          f"{'p90':>6s} {'p99':>6s} {'P(top1)':>8s} {'P(top2)':>8s} {'P(0)':>6s}")
    for r in o.value:
        print(f"{r['name']:22s} {r['team']:3s} {r['tag']:20s} {r['salary']:6d} "
              f"{r['mean']:6.2f} {r['p90']:6.1f} {r['p99']:6.1f} "
              f"{r['p_top1_unique']:8.4f} {r['p_top2_unique']:8.4f} "
              f"{r['p_zero']:6.3f}")
    out = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/CAPTAIN_METRICS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'code': o.code, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'rows': o.value}, indent=1, sort_keys=True))
    print(f'\nwrote {out.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
