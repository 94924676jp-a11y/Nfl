"""Empirical fantasy-score correlation across the 8,000 frozen worlds.

MEASURE WHAT THIS SIMULATION IMPLIES, NOT WHAT DFS FOLKLORE SAYS

The conventional pairings -- quarterback with his own receiver, running back
against the opposing passing game, bring-back from the other side -- are
hypotheses here, not inputs. They are listed so their measured values can be
read, and several of them will be weaker than folklore expects for a reason
this project already knows: the draw generator seeds player rows INDEPENDENTLY.

THE CEILING ON WHAT THIS CAN SHOW, STATED FIRST

`player_draws_manifest.draw_index_semantics` says it plainly:

    across_rows: INDEPENDENT_STREAMS_COLUMN_ALIGNED
    "Rows are seeded independently, so a CROSS-ROW correlation read off the
     same axis measures the generator's lack of coupling, not a football
     quantity."

So a near-zero correlation between two players here is EVIDENCE ABOUT THE
GENERATOR, not evidence that the two are independent in football. Any non-zero
structure that does appear comes from shared team-level draws upstream. This
module reports the matrix and refuses to interpret a zero as a football fact.

It is portfolio information. It is never an input to the football model.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.showdown import universe as U                           # noqa: E402

SPEC_VERSION = 'nfl-showdown-correlation-1'

GENERATOR_CAVEAT = (
    'player rows are seeded INDEPENDENTLY in this artifact '
    '(draw_index_semantics.across_rows = INDEPENDENT_STREAMS_COLUMN_ALIGNED). '
    'A correlation near zero here is a fact about the generator, not about '
    'football, and must never be quoted as evidence that two players are '
    'independent on the field.')

#: Hypotheses to read off the matrix. Named, so the report cannot be mistaken
#: for a discovery when it is a lookup.
PAIR_CLASSES = {
    'QB_WITH_OWN_RECEIVER': lambda a, b: (a['pos'] == 'QB' and b['pos'] in
                                          ('WR', 'TE') and a['team'] == b['team']),
    'QB_WITH_OPPOSING_QB': lambda a, b: (a['pos'] == 'QB' and b['pos'] == 'QB'
                                         and a['team'] != b['team']),
    'RB_WITH_OPPOSING_PASSERS': lambda a, b: (a['pos'] == 'RB' and b['pos'] in
                                              ('QB', 'WR', 'TE')
                                              and a['team'] != b['team']),
    'SAME_TEAM_RECEIVERS': lambda a, b: (a['pos'] in ('WR', 'TE')
                                         and b['pos'] in ('WR', 'TE')
                                         and a['team'] == b['team']),
    'SAME_TEAM_BACKS': lambda a, b: (a['pos'] == 'RB' and b['pos'] == 'RB'
                                     and a['team'] == b['team']),
    'QB_WITH_OWN_BACK': lambda a, b: (a['pos'] == 'QB' and b['pos'] == 'RB'
                                      and a['team'] == b['team']),
}


def build(players=None) -> Outcome:
    if players is None:
        u = U.build()
        if u.state is not State.PASS:
            return u
        players = u.value['playable']
    M = np.vstack([p['draws'] for p in players])
    sd = M.std(axis=1)
    live = sd > 1e-12
    if not live.any():
        return Outcome.fail('CORRELATION_ALL_DEGENERATE',
                            'every player is constant across worlds',
                            cause=Cause.DATA)
    C = np.full((len(players), len(players)), np.nan)
    idx = np.where(live)[0]
    C[np.ix_(idx, idx)] = np.corrcoef(M[idx])
    names = [p['name'] for p in players]
    pairs = []
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            if not (live[i] and live[j]):
                continue
            a, b = players[i], players[j]
            cls = [k for k, f in PAIR_CLASSES.items() if f(a, b) or f(b, a)]
            pairs.append({'a': a['name'], 'b': b['name'],
                          'r': float(C[i, j]),
                          'same_team': a['team'] == b['team'],
                          'classes': cls,
                          'tags': [a['tag'], b['tag']]})
    pairs.sort(key=lambda p: -p['r'])
    by_class = {}
    for k in PAIR_CLASSES:
        v = [p['r'] for p in pairs if k in p['classes']]
        by_class[k] = ({'n': len(v), 'mean_r': float(np.mean(v)),
                        'min_r': float(np.min(v)), 'max_r': float(np.max(v))}
                       if v else {'n': 0})
    degenerate = [names[i] for i in range(len(players)) if not live[i]]
    allr = np.array([p['r'] for p in pairs])
    return Outcome.ok(
        'CORRELATION_BUILT',
        value={'names': names, 'matrix': C.tolist(), 'pairs': pairs,
               'by_class': by_class},
        detail=f'{len(pairs)} live pair(s); mean |r| {np.abs(allr).mean():.4f}, '
               f'max {allr.max():+.4f}, min {allr.min():+.4f}; '
               f'{len(degenerate)} degenerate player(s) excluded',
        spec_version=SPEC_VERSION, n_players=len(players),
        degenerate_players=degenerate,
        generator_caveat=GENERATOR_CAVEAT,
        mean_abs_r=float(np.abs(allr).mean()),
        is_portfolio_information_only=True,
        uses_live_game_outcome_data=False)


def main() -> int:
    o = build()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    print(f'\nCAVEAT: {o.evidence["generator_caveat"]}\n')
    print('by hypothesis class:')
    for k, v in o.value['by_class'].items():
        if v['n']:
            print(f"  {k:26s} n={v['n']:4d}  mean r {v['mean_r']:+.4f}  "
                  f"range [{v['min_r']:+.4f}, {v['max_r']:+.4f}]")
        else:
            print(f'  {k:26s} no live pair')
    print('\nstrongest positive:')
    for p in o.value['pairs'][:8]:
        print(f"  {p['a']:22s} {p['b']:22s} r {p['r']:+.4f}  "
              f"{','.join(p['classes']) or '-'}")
    print('\nstrongest negative:')
    for p in o.value['pairs'][-8:]:
        print(f"  {p['a']:22s} {p['b']:22s} r {p['r']:+.4f}  "
              f"{','.join(p['classes']) or '-'}")
    out = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/CORRELATION.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'names': o.value['names'], 'by_class': o.value['by_class'],
         'strongest_positive': o.value['pairs'][:25],
         'strongest_negative': o.value['pairs'][-25:]}, indent=1))
    # THE ARTIFACT IS CLAIMED BY VERIFYING IT, never by
    # printing a path. `dual_board.py | head -22` once died
    # on SIGPIPE after the table printed and before the
    # write, and the run was reported as successful.
    c = AC.claim(out, schema=['names', 'by_class'],
                 label=out.name)
    if c.state is not State.PASS:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
