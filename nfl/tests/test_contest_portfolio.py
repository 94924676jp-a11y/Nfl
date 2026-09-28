#!/usr/bin/env python3.12
"""Contest-aware selection must beat independent selection, and must refuse rather than fake.

Two things are worth guarding here. The objective is a set property, so a portfolio chosen for it
must actually differ from the 48 highest projections -- if it does not, the objective is not doing
anything and the whole gap is decoration. And a lineup containing a player the simulator cannot
model must make the lineup unscorable, never a lineup scored on eight players.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import contest  # noqa: E402
from nfl.sim import dst as dst_mod  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

ART = _REPO / 'nfl/dfs/salaries/CONTEST_PORTFOLIO.json'
RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the defence tier table is DK\'s, and a shutout is worth more than a blowout allowed')
def t_tier():
    assert dst_mod.tier(0) == 10.0
    assert dst_mod.tier(3) == 7.0
    assert dst_mod.tier(10) == 4.0
    assert dst_mod.tier(17) == 1.0
    assert dst_mod.tier(24) == 0.0
    assert dst_mod.tier(30) == -1.0
    assert dst_mod.tier(42) == -4.0
    prev = None
    for pa in range(0, 60):
        v = dst_mod.tier(pa)
        if prev is not None:
            assert v <= prev, f'the tier rose from {prev} to {v} at {pa} points allowed'
        prev = v
    return 'monotone decreasing from 10 at a shutout to -4 beyond 35 allowed'


@check('a defence is short the opposing offence, and says it excludes defensive touchdowns')
def t_dst_model():
    o = dst_mod.DstModel.load()
    assert o.state is State.PASS, o
    art = json.loads(dst_mod.OUT.read_text())
    tail = art['scoring_tail']
    assert tail['state'] == 'MEASURED_FROM_PLAY_BY_PLAY', tail
    assert tail['closes'] == 'OUT-041'
    assert tail['seasons_read'], 'no play-by-play season was read'
    assert tail['known_omission'], 'the rare omission must stay named, not absorbed'
    # sacks and takeaways must fall as points allowed rise, or the conditioning is inverted
    means = [b['mean_sacks'] for b in art['bands'].values()]
    assert means == sorted(means, reverse=True), means
    takes = [b['mean_takeaways'] for b in art['bands'].values()]
    assert takes == sorted(takes, reverse=True), takes
    # THE TOURNAMENT TAIL. A defence that holds a club down also scores more often, so the good
    # outcomes must arrive together rather than being sprinkled on independently.
    tds = [b['mean_defensive_td'] for b in art['bands'].values()]
    assert tds[0] > tds[-1], (
        f'defensive scores do not fall as points allowed rise: {tds}. Either the conditioning is '
        f'inverted or the tail is being drawn independently of the tier.')
    assert tds[0] > 0.15, tds[0]
    import random
    rng = random.Random(3)
    m = o.value
    lo_s = sorted(m.draw(3, rng) for _ in range(6000))
    hi_s = sorted(m.draw(38, rng) for _ in range(6000))
    lo = sum(lo_s) / len(lo_s)
    hi = sum(hi_s) / len(hi_s)
    assert lo > hi + 5, f'holding a club to 3 scored {lo:.2f} against {hi:.2f} allowing 38'
    # THE CLAIM IS ABOUT THE TAIL, so it is tested against the same model WITHOUT the tail rather
    # than against an absolute number -- an absolute threshold silently encodes which tier was used
    # to pick it, and the first version of this check did exactly that.
    def _no_tail(pa, n=6000):
        r2 = random.Random(11)
        out = []
        for _ in range(n):
            pool = next((t for lo, hi, t in m.bands if lo <= pa < hi), m.bands[-1][2])
            sk, tk, _td, _sf = pool[r2.randrange(len(pool))]
            out.append(dst_mod.tier(pa) + m.sack_pts * sk + m.take_pts * tk)
        return sorted(out)
    for pa in (3, 20, 38):
        with_tail = sorted(m.draw(pa, rng) for _ in range(6000))
        without = _no_tail(pa)
        q = lambda x, f: x[int(f * len(x))]
        assert q(with_tail, 0.99) > q(without, 0.99), (
            f'at {pa} points allowed the 99th percentile did not rise when the scoring tail was '
            f'included ({q(without, 0.99)} -> {q(with_tail, 0.99)}), so the tail is not reaching '
            f'the distribution where a tournament looks')
        assert max(with_tail) > max(without), pa
    gain = (q(sorted(m.draw(38, rng) for _ in range(6000)), 0.99)
            - q(_no_tail(38), 0.99))
    return (f'sacks {means[0]:.2f} down to {means[-1]:.2f}; holding 3 averages {lo:.2f} against '
            f'{hi:.2f} allowing 38; the scoring tail lifts the 99th percentile at every tier, by '
            f'{gain:.0f} points even for a defence allowing 38')


@check('LOAD-BEARING: a lineup with an unmodelled player is unscorable, never scored on the rest')
def t_unscorable():
    draws = {'a': [1.0, 2.0], 'b': [3.0, 4.0]}
    assert contest._score(['a', 'b'], draws, 2) == [4.0, 6.0]
    assert contest._score(['a', 'b', 'missing'], draws, 2) is None, (
        'a lineup containing a player with no draws was scored anyway, which silently ranks it on '
        'fewer players than it has')
    return 'a missing player makes the lineup unscorable rather than cheaper'


@check('the field threshold is recomputed per world, not fixed once')
def t_threshold():
    import random
    draws = {f'p{i}': [float(i), float(20 - i)] for i in range(12)}
    field = [tuple(f'p{j}' for j in range(i, i + 3)) for i in range(9)] * 40
    th, n = _safe_threshold(field, draws, 2, 0.2, random.Random(1), 5000)
    assert th is not None, f'only {n} usable'
    assert len(th) == 2
    assert th[0] != th[1], (
        'the two worlds were deliberately built as mirror images, so an identical threshold in '
        'both means it is not being recomputed per world')
    return f'thresholds {round(th[0], 2)} and {round(th[1], 2)} in two mirrored worlds'


def _safe_threshold(*a, **k):
    return contest._threshold_per_sim(*a, **k)


@check('contest-aware selection beats independent selection, and gives up projection to do it')
def t_arms():
    if not ART.exists():
        return 'CONTEST_PORTFOLIO absent; skipped'
    a = json.loads(ART.read_text())
    indep = next(x for x in a['arms'] if x['label'].startswith('INDEPENDENT'))
    joint = next(x for x in a['arms'] if x['label'].startswith('CONTEST_AWARE'))
    assert joint['p_at_least_one_in_top_1pct'] > indep['p_at_least_one_in_top_1pct'], (indep, joint)
    assert joint['n_distinct_players'] > indep['n_distinct_players'], (
        'the joint portfolio is no more diverse than the independent one, which means the '
        'objective is not actually selecting differently')
    assert joint['mean_projected'] <= indep['mean_projected'] + 1e-9, (
        'the joint portfolio has a HIGHER mean projection than the 48 highest projections, which '
        'is impossible')
    assert a['n_candidates_unscorable'] == 0
    return (f"P(top 1%) {indep['p_at_least_one_in_top_1pct']} -> "
            f"{joint['p_at_least_one_in_top_1pct']}, distinct players "
            f"{indep['n_distinct_players']} -> {joint['n_distinct_players']}, giving up "
            f"{a['improvement']['mean_projection_given_up']} projected points per entry")


@check('marginal contribution is non-increasing, as a set-cover objective requires')
def t_marginal():
    if not ART.exists():
        return 'CONTEST_PORTFOLIO absent; skipped'
    h = json.loads(ART.read_text())['marginal_history']
    gains = [x['marginal_worlds_added'] for x in h]
    assert gains == sorted(gains, reverse=True), (
        'greedy marginal gains rose at some point, which cannot happen when each pick covers '
        'worlds that stay covered')
    ps = [x['p_at_least_one'] for x in h]
    assert ps == sorted(ps), 'the objective fell as entries were added'
    return (f'{len(gains)} picks, first adds {gains[0]} worlds and last adds {gains[-1]}, '
            f'objective rising throughout to {ps[-1]}')


@check('the conclusion survives the uncalibrated field range even where the selection does not')
def t_sensitivity():
    if not ART.exists():
        return 'CONTEST_PORTFOLIO absent; skipped'
    ds = json.loads(ART.read_text())['decision_sensitivity']
    tested = [x for x in ds['settings'] if 'p_joint' in x]
    assert len(tested) >= 3, ds['settings']
    assert ds['joint_beats_independent_at_every_setting'], tested
    assert ds['VERDICT'].startswith('METHOD_ROBUST')
    g = json.loads(ART.read_text())['GOVERNANCE']
    assert g['sim_optimal'] == 'NOT_CLAIMED'
    assert 'NONE' in g['entries_submitted']
    assert 'NOT_DETERMINED' in g['refined_state']['the_specific_48_entries']
    return (f"{len(tested)} settings, joint wins at all of them, lowest portfolio overlap "
            f"{ds['lowest_portfolio_overlap_with_base']} -- method usable, entries not determined")


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
