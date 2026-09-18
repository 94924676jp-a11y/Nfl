"""The optimal lineup in every one of the 8,000 frozen worlds.

WHY THIS IS THE HIGHER-PRIORITY MEASUREMENT

A mean says what a player scores on average. It does not say how often he
belongs in the best possible lineup, and those diverge hard under a salary cap:
a cheap player with a modest mean can appear in the optimal lineup constantly
because he buys the room for two expensive ones, and an expensive player with a
high mean can be absent from it constantly for the same reason.

The 2026-09-17 portfolio had no measurement of this at all. It ranked by mean,
spread captains with a counter, and took cheap points-per-dollar wherever it
was offered.

WHY THE SOLVE IS EXACT AND NOT GREEDY

Measured on this slate: taking the top five scorers under each captain fits the
salary cap in only 57.3% of worlds. In the other 42.7% the cap genuinely binds,
so a greedy answer would be wrong four times in ten and wrong in a direction
that systematically favours expensive players. This is a full dynamic program
over (flex slots used, captain used, salary spent), per world.

TIES ARE BROKEN DETERMINISTICALLY AND THE RATE IS REPORTED. Where two lineups
score identically the one whose player indices sort first is taken, indices
being assigned by name so the order does not depend on dictionary iteration.
The share of worlds where a tie occurred is carried in the evidence, because a
high tie rate would mean the frequencies are partly an artefact of that rule.

WHAT THESE NUMBERS ARE NOT

`p_optimal` and `p_optimal_captain` are SIMULATED_OPTIMAL_LINEUP_FREQUENCY.
They are not ownership, not projected ownership, not leverage, and not a
recommendation. They say how often a player belongs in the best lineup of a
world drawn from this model -- including all of that model's known defects.
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

SPEC_VERSION = 'nfl-showdown-optimal-worlds-1'

RAW_FANTASY_PROJECTION = 'RAW_FANTASY_PROJECTION'
SIMULATED_OPTIMAL_LINEUP_FREQUENCY = 'SIMULATED_OPTIMAL_LINEUP_FREQUENCY'

NEG = -1e18


def solve(players, cap: int = U.SALARY_CAP, n_flex: int = U.N_FLEX,
          unit: int = 100, chunk_report: int = 2000) -> Outcome:
    """Exact optimal lineup per world. O(worlds x players x slots x budget)."""
    n = len(players)
    if n < n_flex + 1:
        return Outcome.fail('OPTIMAL_UNIVERSE_TOO_SMALL',
                            f'{n} player(s) cannot fill {n_flex + 1} slots',
                            cause=Cause.DATA)
    # INDEX ORDER IS BY NAME, so the tie-break below is reproducible and does
    # not depend on how the universe happened to be built.
    order = sorted(range(n), key=lambda i: players[i]['name'])
    P = [players[i] for i in order]
    M = np.vstack([p['draws'] for p in P]).astype(np.float64)
    fs = np.array([p['salary'] // unit for p in P], dtype=np.int32)
    cs = np.array([p['cpt_salary'] // unit for p in P], dtype=np.int32)
    B = cap // unit
    W = M.shape[1]
    S = n_flex + 1
    in_opt = np.zeros(n, dtype=np.int64)
    as_cpt = np.zeros(n, dtype=np.int64)
    infeasible = 0
    ties = 0
    best_scores = np.zeros(W)
    lineups = []
    # dp[k, c, b] = best flex-score-with-captain using the first j players
    for w in range(W):
        sc = M[:, w]
        dp = np.full((S, 2, B + 1), NEG)
        dp[0, 0, 0] = 0.0
        ch = np.zeros((n, S, 2, B + 1), dtype=np.int8)   # 0 skip 1 flex 2 cpt
        for j in range(n):
            f, c, v = fs[j], cs[j], sc[j]
            nd = dp.copy()
            # take as FLEX: k-1 -> k, same captain state, budget + f
            if f <= B:
                src = dp[:S - 1, :, :B + 1 - f]
                cand = src + v
                tgt = nd[1:, :, f:]
                take = cand > tgt
                nd[1:, :, f:] = np.where(take, cand, tgt)
                ch[j, 1:, :, f:] = np.where(take, 1, ch[j, 1:, :, f:])
            # take as CAPTAIN: captain state 0 -> 1, budget + c
            if c <= B:
                src = dp[:, 0, :B + 1 - c]
                cand = src + v * U.CPT_MULTIPLIER
                tgt = nd[:, 1, c:]
                take = cand > tgt
                nd[:, 1, c:] = np.where(take, cand, tgt)
                ch[j, :, 1, c:] = np.where(take, 2, ch[j, :, 1, c:])
            dp = nd
        row = dp[n_flex, 1]
        b = int(np.argmax(row))
        if row[b] <= NEG / 2:
            infeasible += 1
            lineups.append(None)
            continue
        if int((row == row[b]).sum()) > 1:
            ties += 1
        best_scores[w] = row[b]
        # BACKTRACK. `ch` was written only where the candidate strictly beat
        # the incumbent, so following it reproduces the lineup that the
        # name-ordered scan found first among equals.
        k, cu, bb = n_flex, 1, b
        cpt_i, flex_i = None, []
        for j in range(n - 1, -1, -1):
            d = ch[j, k, cu, bb]
            if d == 1:
                flex_i.append(j)
                k -= 1
                bb -= int(fs[j])
            elif d == 2:
                cpt_i = j
                cu = 0
                bb -= int(cs[j])
        if cpt_i is None or len(flex_i) != n_flex:
            infeasible += 1
            lineups.append(None)
            continue
        as_cpt[cpt_i] += 1
        in_opt[cpt_i] += 1
        for i in flex_i:
            in_opt[i] += 1
        lineups.append((cpt_i, sorted(flex_i)))
        if chunk_report and (w + 1) % chunk_report == 0:
            print(f'  ... {w + 1}/{W} worlds solved', flush=True)
    solved = W - infeasible
    if not solved:
        return Outcome.fail('OPTIMAL_NO_FEASIBLE_WORLD',
                            'no world produced a feasible lineup',
                            cause=Cause.DATA)
    rows = []
    for i, p in enumerate(P):
        rows.append({
            'name': p['name'], 'team': p['team'], 'pos': p['pos'],
            'tag': p['tag'], 'salary': p['salary'],
            'cpt_salary': p['cpt_salary'],
            'mean_dk': float(M[i].mean()),
            'p_optimal': float(in_opt[i] / solved),
            'p_optimal_captain': float(as_cpt[i] / solved),
            'quantity': SIMULATED_OPTIMAL_LINEUP_FREQUENCY,
        })
    rows.sort(key=lambda r: -r['p_optimal'])
    return Outcome.ok(
        'OPTIMAL_WORLDS', value={'rows': rows, 'lineups': lineups,
                                 'names': [p['name'] for p in P]},
        detail=f'{solved}/{W} world(s) solved exactly; {ties} tie(s) broken by '
               f'name order ({ties / max(solved, 1):.2%}); {infeasible} '
               f'infeasible',
        spec_version=SPEC_VERSION, n_worlds=W, n_solved=solved,
        n_infeasible=infeasible, n_ties=ties,
        tie_share=float(ties / max(solved, 1)),
        tie_break='lowest player index, indices assigned by name',
        mean_optimal_score=float(best_scores[best_scores > 0].mean()),
        quantity=SIMULATED_OPTIMAL_LINEUP_FREQUENCY,
        is_not='NOT ownership, NOT projected ownership, NOT leverage',
        uses_live_game_outcome_data=False)


def main() -> int:
    u = U.build()
    if u.state is not State.PASS:
        print(f'{u.state.value}[{u.code}] {u.detail}')
        return 1
    o = solve(u.value['playable'])
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    print(f"{'player':22s} {'tag':20s} {'sal':>6s} {'mean':>6s} "
          f"{'P(opt)':>8s} {'P(optCPT)':>10s}")
    for r in o.value['rows']:
        print(f"{r['name']:22s} {r['tag']:20s} {r['salary']:6d} "
              f"{r['mean_dk']:6.2f} {r['p_optimal']:8.4f} "
              f"{r['p_optimal_captain']:10.4f}")
    out = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/OPTIMAL_WORLDS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'rows': o.value['rows']}, indent=1, sort_keys=True))
    print(f'\nwrote {out.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
