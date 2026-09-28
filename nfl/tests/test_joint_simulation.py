#!/usr/bin/env python3.12
"""The joint simulator's identities must be exact, and its correlations must not be hand-added.

The seven reconciliation identities are the whole justification for this module existing, so most
of these checks try to BREAK them and require a refusal. A simulator that reports an identity
violation as a warning has no identities.

The other half is about provenance of correlation. If a correlation can be produced by editing a
constant, it is a bonus wearing a simulator's clothes. So one check confirms the correlation
between two same-club players comes from the shared draw: freeze the shared state and the
correlation must collapse.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import game as sim_game  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _model():
    o = sim_game.Model.load()
    assert o.state is State.PASS, o
    return o.value


def _spec(total=45.0, spread=0.0):
    def club(tag):
        return {'club': tag, 'players': [
            {'id': f'{tag}_QB', 'position': 'QB', 'target_share': 0.0, 'carry_share': 0.05,
             'pass_att_share': 1.0, 'pass_td_share': 0.0, 'rush_td_share': 0.05},
            {'id': f'{tag}_RB1', 'position': 'RB', 'target_share': 0.12, 'carry_share': 0.60,
             'pass_att_share': 0.0, 'pass_td_share': 0.08, 'rush_td_share': 0.60},
            {'id': f'{tag}_RB2', 'position': 'RB', 'target_share': 0.06, 'carry_share': 0.30,
             'pass_att_share': 0.0, 'pass_td_share': 0.04, 'rush_td_share': 0.30},
            {'id': f'{tag}_WR1', 'position': 'WR', 'target_share': 0.27, 'carry_share': 0.02,
             'pass_att_share': 0.0, 'pass_td_share': 0.30, 'rush_td_share': 0.02},
            {'id': f'{tag}_WR2', 'position': 'WR', 'target_share': 0.19, 'carry_share': 0.0,
             'pass_att_share': 0.0, 'pass_td_share': 0.22, 'rush_td_share': 0.0},
            {'id': f'{tag}_TE1', 'position': 'TE', 'target_share': 0.16, 'carry_share': 0.0,
             'pass_att_share': 0.0, 'pass_td_share': 0.18, 'rush_td_share': 0.0},
        ]}
    return {'total_line': total, 'home_spread': spread, 'clubs': [club('HOME'), club('AWAY')]}


def _corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = sum((x - ma) ** 2 for x in a)
    sb = sum((y - mb) ** 2 for y in b)
    if sa <= 0 or sb <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sa * sb)


@check('the simulator runs and every reconciliation identity holds')
def t_runs():
    o = sim_game.simulate_game(_model(), _spec(), n_sims=400, seed=5)
    assert o.state is State.PASS, o
    assert set(o.value['IDENTITIES_HELD']) >= {'total', 'margin', 'volume', 'yards',
                                               'touchdowns'}
    assert o.value['club_checks']['club_games_checked'] == 800
    return f"400 sims, {o.value['club_checks']['club_games_checked']} club-games all reconciled"


@check('LOAD-BEARING: a broken allocation is caught -- identity checking is not decorative')
def t_identity_enforced():
    real = sim_game._multinomial

    def leaky(n, weights, rng):
        got = real(n, weights, rng)
        if got and n > 3:
            got[0] = max(0, got[0] - 1)   # one unit vanishes
        return got
    try:
        sim_game._multinomial = leaky
        o = sim_game.simulate_game(_model(), _spec(), n_sims=20, seed=6)
        assert o.state is State.FAIL and o.code == 'SIM_IDENTITY_VIOLATED', (
            f'got {o.state}/{o.code}: an allocation that loses a target went unnoticed, so the '
            f'identity checks are not actually checking')
        assert 'VOLUME' in o.evidence['violations_by_kind']
    finally:
        sim_game._multinomial = real
    return 'losing one target per club-game is detected and refused'


@check('unallocated club volume is reported, not renormalised onto the players present')
def t_unallocated():
    spec = _spec()
    # drop the receivers: their targets belong to nobody in the pool now
    for c in spec['clubs']:
        c['players'] = [p for p in c['players'] if p['position'] not in ('WR', 'TE')]
    o = sim_game.simulate_game(_model(), spec, n_sims=200, seed=7)
    assert o.state is State.PASS, o
    frac = o.value['unallocated_fraction']
    assert frac['targets'] > 0.5, frac
    full = sim_game.simulate_game(_model(), _spec(), n_sims=200, seed=7)
    rb_thin = sum(o.value['draws']['HOME_RB1']) / 200
    rb_full = sum(full.value['draws']['HOME_RB1']) / 200
    assert rb_thin < rb_full * 1.35, (
        f'the back scored {rb_thin:.2f} with the receivers removed against {rb_full:.2f} with '
        f'them present. Removing other players should not hand him their work.')
    return (f"{frac['targets']:.1%} of targets unallocated and reported; the back's mean moved "
            f"{rb_full:.2f} -> {rb_thin:.2f}, not inflated")


@check('LOAD-BEARING: same-club correlation comes from the shared draw, not from a constant')
def t_correlation_is_earned():
    m = _model()
    o = sim_game.simulate_game(m, _spec(), n_sims=1500, seed=11)
    live = _corr(o.value['draws']['HOME_QB'], o.value['draws']['HOME_WR1'])
    # freeze the shared world: same total and margin every simulation
    import copy
    frozen = copy.copy(m)
    frozen.total_res = [0.0]
    frozen.margin_res = [0.0]
    # freeze the volume draw too. This froze pass_v/rush_v until the volume model was
    # reparameterised to plays and pass share; the stale freeze left the volume noise running and
    # the test correctly refused to call the correlation earned.
    frozen.plays_v = dict(m.plays_v, residual_sd=0.0)
    frozen.share_v = dict(m.share_v, residual_sd=0.0)
    f = sim_game.simulate_game(frozen, _spec(), n_sims=1500, seed=11)
    held = _corr(f.value['draws']['HOME_QB'], f.value['draws']['HOME_WR1'])
    assert live is not None and held is not None
    assert live > held + 0.05, (
        f'freezing the shared game state barely changed the quarterback-receiver correlation '
        f'({live:.3f} -> {held:.3f}). That would mean the correlation is coming from somewhere '
        f'other than the shared draw, which is the one thing this design is for.')
    return (f'correlation {live:.3f} with the shared world drawn, {held:.3f} with it frozen -- '
            f'it comes from the shared draw')


@check('game script moves passing and rushing in opposite directions, as measured')
def t_script():
    m = _model()
    assert m.pass_v['per_margin_point'] < 0, m.pass_v
    assert m.rush_v['per_margin_point'] > 0, m.rush_v
    big_fav = sim_game.simulate_game(m, _spec(spread=13.0), n_sims=800, seed=13)
    big_dog = sim_game.simulate_game(m, _spec(spread=-13.0), n_sims=800, seed=13)
    qb_fav = sum(big_fav.value['draws']['HOME_QB']) / 800
    qb_dog = sum(big_dog.value['draws']['HOME_QB']) / 800
    rb_fav = sum(big_fav.value['draws']['HOME_RB1']) / 800
    rb_dog = sum(big_dog.value['draws']['HOME_RB1']) / 800
    assert rb_fav > rb_dog, f'the favoured back should see more work: {rb_fav:.2f} vs {rb_dog:.2f}'
    return (f'13-point favourite vs underdog: back {rb_fav:.2f} vs {rb_dog:.2f}, '
            f'quarterback {qb_fav:.2f} vs {qb_dog:.2f}')


@check('a higher total lifts both clubs, which is why opposing players correlate at all')
def t_total():
    m = _model()
    lo = sim_game.simulate_game(m, _spec(total=38.0), n_sims=800, seed=17)
    hi = sim_game.simulate_game(m, _spec(total=54.0), n_sims=800, seed=17)
    for pid in ('HOME_WR1', 'AWAY_WR1'):
        a = sum(lo.value['draws'][pid]) / 800
        b = sum(hi.value['draws'][pid]) / 800
        assert b > a, f'{pid} scored {b:.2f} in the 54 game against {a:.2f} in the 38 game'
    return (f"both sides rise with the total: home receiver "
            f"{sum(lo.value['draws']['HOME_WR1'])/800:.2f} -> "
            f"{sum(hi.value['draws']['HOME_WR1'])/800:.2f}")


@check('the measured correlation targets exist and carry game-blocked intervals')
def t_targets_exist():
    f = _REPO / 'nfl/sim/PAIR_CORRELATIONS.json'
    if not f.exists():
        return 'PAIR_CORRELATIONS absent; skipped'
    a = json.loads(f.read_text())
    est = [k for k, v in {**a['same_club'], **a['cross_club']}.items() if v.get('SIGN_ESTABLISHED')]
    assert len(est) >= 8, est
    qb_wr = a['same_club']['QB1~WR1']
    assert qb_wr['ci95_game_blocked']['lo'] > 0.3, qb_wr
    assert 'RANKS_ARE_PREGAME' in a
    # the two results worth not losing
    assert a['same_club']['WR1~WR2']['r'] > 0, (
        'same-club receivers measured positive, not cannibalising -- if this flips, the '
        'measurement changed and the simulator target changed with it')
    assert a['cross_club']['QB1~QB1']['r'] > 0, 'opposing quarterbacks measured positive'
    return (f"{len(est)} pair types with an established sign; QB1~WR1 "
            f"{qb_wr['r']} ci{[qb_wr['ci95_game_blocked']['lo'], qb_wr['ci95_game_blocked']['hi']]}")


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
