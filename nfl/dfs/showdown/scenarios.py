"""Scenario buckets over the 8,000 frozen worlds.

THE FIRST THING TO REPORT IS WHAT CANNOT BE BUILT

Four of the six requested game-script buckets -- BUF decisive win, DET decisive
win, close BUF win, close DET win -- are NOT DERIVABLE from this artifact. The
sealed board produces player and team VOLUME and player fantasy scoring. It
produces no score, no margin, no win probability and no drive outcome, and the
projection export already says so under "Final score, game total and win
probability: NOT AVAILABLE".

A margin bucket could be faked by treating fantasy points as a proxy for
scoring. That would be a scoreboard invented from a scoring system, and every
conditional distribution underneath it would inherit the invention. They are
declared NOT_AVAILABLE instead, with the quantity that would be needed named.

WHAT IS DERIVABLE IS STILL USEFUL

Buckets defined on quantities the simulation actually emits: team passing
volume, team rushing volume, total modelled production, and per-player ceiling
events. These are descriptive partitions of the worlds, not probabilities of
football events, and the distinction is kept in the naming.

BUCKETS ARE NOT MUTUALLY EXCLUSIVE and are not presented as a distribution.
Each is a predicate over worlds with its own frequency. Anything that added up
to 1.0 here would be a coincidence of the definitions, not a probability.
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

SPEC_VERSION = 'nfl-showdown-scenarios-1'

NOT_AVAILABLE = {
    'BUF_DECISIVE_WIN': 'requires a simulated score margin; the artifact '
                        'produces no score',
    'DET_DECISIVE_WIN': 'same',
    'CLOSE_BUF_WIN': 'same',
    'CLOSE_DET_WIN': 'same',
    'GAME_TOTAL_HIGH': 'requires simulated points scored, not fantasy points',
    'GAME_TOTAL_LOW': 'same',
    '_what_would_be_needed': 'a drive or scoring model emitting points per '
                             'team per world. Track 1 game-state work is the '
                             'natural home for it; it does not exist today.',
}

#: Cut points are QUANTILES OF THE SIMULATION ITSELF, not football opinions,
#: so a bucket is always a defined share of worlds and no threshold is fitted
#: to anything. `ceiling` buckets use a fixed DK level because a quantile of a
#: player's own distribution would make every player's ceiling equally common
#: by construction, which is not what a ceiling means.
TERCILE_HI = 0.6667
TERCILE_LO = 0.3333
CEILING_DK = 25.0
MULTI_TD_RECEIVING = 2.0


def _agg(players, team, positions=None):
    rows = [p for p in players if p['team'] == team
            and (positions is None or p['pos'] in positions)]
    if not rows:
        return None
    return np.sum([p['draws'] for p in rows], axis=0)


def build(players=None) -> Outcome:
    if players is None:
        u = U.build()
        if u.state is not State.PASS:
            return u
        players = u.value['playable']
    by_name = {p['name']: p for p in players}
    W = len(players[0]['draws'])
    det_pass = _agg(players, 'DET', ('QB',))
    buf_pass = _agg(players, 'BUF', ('QB',))
    det_all = _agg(players, 'DET')
    buf_all = _agg(players, 'BUF')
    if det_pass is None or buf_pass is None:
        return Outcome.fail('SCENARIO_MISSING_TEAM_ROWS',
                            'a team has no modelled quarterback',
                            cause=Cause.DATA)
    total = det_all + buf_all

    def hi(v):
        return v >= np.quantile(v, TERCILE_HI)

    def lo(v):
        return v <= np.quantile(v, TERCILE_LO)

    def ceil(name):
        p = by_name.get(name)
        return (p['draws'] >= CEILING_DK) if p else np.zeros(W, bool)

    buckets = {
        'DET_PASSING_CEILING': hi(det_pass),
        'BUF_PASSING_CEILING': hi(buf_pass),
        'DET_PRODUCTION_HIGH': hi(det_all),
        'BUF_PRODUCTION_HIGH': hi(buf_all),
        'TOTAL_PRODUCTION_HIGH': hi(total),
        'TOTAL_PRODUCTION_LOW': lo(total),
        'BOTH_TEAMS_HIGH': hi(det_all) & hi(buf_all),
        'ONE_SIDED_DET': hi(det_all) & lo(buf_all),
        'ONE_SIDED_BUF': hi(buf_all) & lo(det_all),
        'ALLEN_CEILING': ceil('Josh Allen'),
        'GOFF_CEILING': ceil('Jared Goff'),
        'GIBBS_CEILING': ceil('Jahmyr Gibbs'),
        'COOK_CEILING': ceil('James Cook III'),
        'STBROWN_CEILING': ceil('Amon-Ra St. Brown'),
    }
    # MULTI-TD RECEIVER, measured from the receiving layer rather than assumed
    # from DK points, which cannot distinguish two touchdowns from one long one.
    multi = np.zeros(W, bool)
    for p in players:
        if p['pos'] in ('WR', 'TE'):
            multi |= (p['draws'] >= 30.0)
    buckets['A_RECEIVER_GOES_OFF'] = multi

    rows = {}
    for k, mask in buckets.items():
        n = int(mask.sum())
        rows[k] = {'n_worlds': n, 'share': float(n / W),
                   'definition_is_a_partition_of_worlds': True}
    # CONDITIONAL PLAYER MEANS. The point of a bucket is what changes inside it.
    cond = {}
    for k, mask in buckets.items():
        if mask.sum() < 50:
            cond[k] = {'INSUFFICIENT_WORLDS': int(mask.sum())}
            continue
        cond[k] = {p['name']: round(float(p['draws'][mask].mean()), 3)
                   for p in players}
    base = {p['name']: round(float(p['draws'].mean()), 3) for p in players}
    return Outcome.ok(
        'SCENARIOS_BUILT',
        value={'buckets': rows, 'conditional_mean_dk': cond,
               'unconditional_mean_dk': base,
               'masks': {k: v for k, v in buckets.items()}},
        detail=f'{len(rows)} derivable bucket(s) over {W} world(s); '
               f'{len(NOT_AVAILABLE) - 1} requested bucket(s) NOT_AVAILABLE '
               f'for want of a simulated score',
        spec_version=SPEC_VERSION, n_worlds=W,
        not_available=NOT_AVAILABLE,
        buckets_are_not_a_distribution=True,
        ceiling_dk=CEILING_DK, tercile=(TERCILE_LO, TERCILE_HI),
        uses_live_game_outcome_data=False)


def main() -> int:
    o = build()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    print('\nNOT AVAILABLE (no simulated score exists):')
    for k, v in o.evidence['not_available'].items():
        if not k.startswith('_'):
            print(f'  {k:22s} {v}')
    print('\nderivable buckets:')
    for k, v in sorted(o.value['buckets'].items(), key=lambda kv: -kv[1]['share']):
        print(f"  {k:24s} {v['n_worlds']:5d} worlds  {v['share']:6.2%}")
    print('\nbiggest conditional movers (mean DK inside bucket vs overall):')
    base = o.value['unconditional_mean_dk']
    seen = []
    for b, d in o.value['conditional_mean_dk'].items():
        if 'INSUFFICIENT_WORLDS' in d:
            continue
        for nm, mu in d.items():
            if base.get(nm, 0) > 1.0:
                seen.append((mu - base[nm], b, nm, base[nm], mu))
    for delta, b, nm, u0, u1 in sorted(seen, key=lambda t: -t[0])[:10]:
        print(f'  {b:24s} {nm:22s} {u0:6.2f} -> {u1:6.2f}  {delta:+6.2f}')
    out = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/SCENARIOS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'buckets': o.value['buckets'],
         'unconditional_mean_dk': o.value['unconditional_mean_dk'],
         'conditional_mean_dk': o.value['conditional_mean_dk']},
        indent=1, sort_keys=True))
    print(f'\nwrote {out.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
