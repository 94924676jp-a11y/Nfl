#!/usr/bin/env python3.12
"""Event-linked football worlds and the invariant checker (SHADOW_ONLY research).

    python3.12 nfl/tests/test_event_linked_world.py
    python3.12 nfl/tests/run_suite.py --modules test_event_linked_world

  A  every registered invariant holds on generated event-linked worlds at EVERY stage (raw, efficiency, DST,
     scoring), every invariant is actually CHECKED there, and the incumbent's breaks are COUNTED, not hidden
  B  a planted violation of each invariant is caught by the checker (one fixture per invariant)
  C  the per-event efficiency step moves passer and receiver yards identically (and production's does not)
  D  an interception is one event: once for the passer, once for the opposing DST
  E  DST DK recomputes exactly from its components and DK_PA_v1 points allowed (and the anchor breaks it)
  F  team points == 6 TD + XP + 2 x 2pt + 3 FG + 2 x safeties exactly, integral, in every world
  G  no market field is reachable: injected total_line / spread_line / odds / moneyline are refused by name
  H  deterministic under seed: byte-identical arrays on two runs
  I  refusal on empty or partial input with named errors
  J  official-stat conventions and history-only exceptions (laterals, trick-play passer, sack yards, 2pt, fumble TD)
  K  pre-registration enforcement (changed prereg / frozen, no lock, confirmation re-read, code change, off-design)
  L  shared constants agree with production (tier table, kicker bands, MIN_SIM_OPPORTUNITIES, DK classic)
  M  DST event-rate step: thinning / superposition behave as declared
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.research.coherence import event_linked_world as E  # noqa: E402
from nfl.research.coherence import invariants as INV  # noqa: E402
from nfl.research.coherence import sc_coh_1_clean_eval as CE  # noqa: E402

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _raises(fn, code, exc=(E.ELError, INV.InvariantError)):
    try:
        fn()
    except exc as e:
        return e.code == code, e.code
    except Exception as e:  # noqa: BLE001
        return False, f'{type(e).__name__}: {e}'
    return False, 'no error'


# --------------------------------------------------------------------------------------------- fixtures
N = 80
SEED = 20261011


def _toy_model():
    from nfl.sim import game as G, dst as D
    rng = np.random.default_rng(3)
    shared = {'environment': {'total_residual': {'sd': 13.0}, 'margin_residual': {'sd': 13.0}},
              'empirical_residuals': {'total': sorted(rng.normal(0, 13, 400).round(2).tolist()),
                                      'margin': sorted(rng.normal(2, 13, 400).round(2).tolist())},
              'volume_response_to_realised_game': {
                  'pass_attempts': {'intercept': 33.0, 'per_own_point': 0.0, 'per_margin_point': -0.26, 'residual_sd': 6.0},
                  'rush_attempts': {'intercept': 25.0, 'per_own_point': 0.2, 'per_margin_point': 0.23, 'residual_sd': 5.0}},
              'volume_response_plays_and_pass_share': {
                  'plays': {'intercept': 57.6, 'per_own_point': 0.2, 'per_margin_point': -0.035, 'residual_sd': 8.0},
                  'pass_share': {'intercept': 0.56, 'per_own_point': 0.0009, 'per_margin_point': -0.004, 'residual_sd': 0.09}},
              'scoring': {'points_per_offensive_td': 6.36, 'points_not_from_offensive_td': 7.4, 'residual_sd': 4.5}}
    eff = {'yards_per_pass_attempt': {'empirical': sorted(rng.normal(6.7, 1.5, 300).clip(2).round(3).tolist())},
           'yards_per_carry': {'empirical': sorted(rng.normal(4.4, 1.2, 300).clip(1).round(3).tolist())}}
    vc = {'receiving': {'state': 'ESTIMATED', 'concentration': 15.9}, 'rushing': {'state': 'ESTIMATED', 'concentration': 12.9},
          'share_dispersion_targets': {'state': 'ESTIMATED', 'concentration': 142.0},
          'share_dispersion_carries': {'state': 'ESTIMATED', 'concentration': 12.9}}
    m = G.Model(shared, eff).attach_concentration(vc)
    tup = lambda lo: [[float(a), float(b), float(c), float(d)] for a, b, c, d in
                      zip(rng.poisson(2.5 - lo / 30, 80), rng.poisson(1.6 - lo / 40, 80),
                          (rng.random(80) < 0.15).astype(int), (rng.random(80) < 0.05).astype(int))]
    bands = {f'{lo}-{hi}': {'n': 80, 'empirical_tuples': tup(lo)} for lo, hi in ((0, 10), (10, 17), (17, 24), (24, 31),
                                                                                   (31, 1000000))}
    m.dst = D.DstModel({'bands': bands, 'sack_points': 1.0, 'takeaway_points': 2.0, 'defensive_td_points': 6.0,
                        'safety_points': 2.0})
    m.attach_usage(None)
    return m, {'dst_bands': {'bands': bands}, 'int_rate': {'int_per_attempt': 0.023}}


def _spec():
    def club(t):
        ps = [('QB', 0.0, 0.08, 1.0, 0.6, 0.0), ('WR', 0.40, 0.0, 0.0, 0.62, 0.0), ('WR', 0.25, 0.0, 0.0, 0.62, 0.0),
              ('TE', 0.15, 0.0, 0.0, 0.70, 0.0), ('RB', 0.15, 0.70, 0.0, 0.78, 0.8), ('RB', 0.05, 0.22, 0.0, 0.75, 0.2)]
        out = []
        for i, (pos, ts, cs, pas, cr, rts) in enumerate(ps):
            pid = f'{t}{pos}{i}'
            out.append({'id': CE.player_key(pid, t), 'pid': pid, 'position': pos, 'target_share': ts, 'carry_share': cs,
                        'pass_att_share': pas, 'pass_td_share': ts, 'rush_td_share': rts if pos == 'RB' else 0.0,
                        'catch_rate': cr, 'slot': 'OTHER'})
        return {'club': t, 'players': out, 'dst_id': f'DST|{t}'}
    return {'total_line': 45.0, 'home_spread': 2.5, 'fc_total': 45.0, 'fc_margin': 2.5,
            'scoring_basis': 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND', 'clubs': [club('H'), club('A')]}


VOL = {'H': {'pass_attempts': 34.0, 'rush_attempts': 26.0, 'targets': 32.0},
       'A': {'pass_attempts': 35.0, 'rush_attempts': 24.0, 'targets': 33.0}}


def _rates():
    return {'p_int_of_takeaway': 0.63, 'fumble_location_share': {'carry': 0.38, 'reception': 0.28, 'sack': 0.34},
            'sack_yards_lost_empirical': [0, 3, 5, 6, 7, 8, 9, 11], 'p_dst_td_is_takeaway_return': 0.84,
            'kicker': {'try_rate_2pt_per_td': 0.1, 'two_pt_success': 0.48, 'pat_make_rate': 0.95, 'fg_share': 0.84,
                       'made_band_mix': {'fg_0_39': 0.57, 'fg_40_49': 0.26, 'fg_50_plus': 0.17},
                       'band_make_rate': {'fg_0_39': 0.95, 'fg_40_49': 0.79, 'fg_50_plus': 0.69}}}


def _pools(spec):
    out = {}
    for c in spec['clubs']:
        ps = []
        for p in c['players']:
            ypt = {'WR': 8.6, 'TE': 7.2, 'RB': 5.8}.get(p['position'], 0.0)
            ps.append({'pid': p['pid'], 'pos': p['position'],
                       'eff': {'targets': 60.0, 'rec_yards': 60.0 * ypt, 'carries': 80.0, 'rush_yards': 80 * 4.6,
                               'pass_attempts': 300.0, 'pass_yards': 2050.0}})
        out[c['club']] = {'players': ps, 'roles': {}}
    return out


_CACHE = {}


def _worlds():
    """(spec, inc0, ELState after S2, {stage: bundle}) on the toy model; built once."""
    if 'w' not in _CACHE:
        model, fits = _toy_model()
        spec = _spec()
        inc0 = E.simulate_incumbent(model, spec, VOL, N, SEED)
        st = E.ELState(spec, inc0, _rates(), SEED + 7)
        eb = {'S0_raw': st.bundle('S0_raw')}
        st.apply_efficiency(_pools(spec))
        eb['S1_after_efficiency'] = st.bundle('S1_after_efficiency')
        edges, means = E.band_table(fits)
        st.apply_dst_rates({'H': {'sacks': 1.3, 'ints': 0.7, 'fumbles': 1.0, 'dst_td': 1.5, 'safeties': 0.5},
                            'A': {'sacks': 0.8, 'ints': 1.4, 'fumbles': 0.9, 'dst_td': 0.6, 'safeties': 1.0}},
                           means, edges, SEED + 11)
        eb['S2_after_dst'] = st.bundle('S2_after_dst')
        eb['S3_after_scoring'] = st.bundle('S3_after_scoring', scored=True)
        _CACHE['w'] = (spec, inc0, st, eb, model, fits)
    return _CACHE['w']


def _viol(b, inv, **kw):
    return INV.check_bundle(b, **kw)[inv]['violations']


# --------------------------------------------------------------------------------------------- A
def test_a_every_invariant_holds_at_every_stage():
    print('\nA. every invariant holds on event-linked worlds at every stage, and is checked')
    spec, inc0, st, eb, model, fits = _worlds()
    for s_, b in eb.items():
        r = INV.check_bundle(b)
        bad = {k: v['violations'] for k, v in r.items() if v['state'] == 'CHECKED' and v['violations']}
        unchecked = [k for k in E.required_invariants(s_) if r[k]['state'] != 'CHECKED']
        check(not bad, f'{s_}: zero violations ({bad})')
        check(not unchecked, f'{s_}: every required invariant CHECKED ({unchecked})')
    r3 = INV.check_bundle(eb['S3_after_scoring'])
    check(all(r3[k]['state'] == 'CHECKED' for k in INV.INVARIANTS), 'S3: all registered invariants checked')
    check(r3['E05']['units'] > 0 and r3['D02']['units'] == 2 * N, 'ledger and DST-sack identities ran on every world')
    # the incumbent on the SAME raw worlds: breaks are counted, and unrepresented ones are None, never 0
    kick = {t: E.incumbent_kicker(inc0['club_points'][t], inc0['club_td'][t], _rates()['kicker'], 5) for t in ('H', 'A')}
    ib = E.incumbent_bundle(inc0, spec, 'S0_raw', kick, 'raw')
    ri = INV.check_bundle(ib)
    check(ri['C07']['violations'] > 0 and ri['C06']['violations'] > 0, 'incumbent raw: non-integer points counted')
    check(ri['P02']['violations'] > 0, 'incumbent raw: receiving yards without a reception counted')
    check(ri['D02']['state'] == 'NOT_REPRESENTED' and ri['D02']['violations'] is None,
          'incumbent: DST sacks vs offence sacks NOT_REPRESENTED (None), not 0')


# --------------------------------------------------------------------------------------------- B
def _first(mask):
    ix = np.argwhere(mask)
    return tuple(ix[0]) if len(ix) else None


def _plant(b, inv):
    """Return a copy of a clean S3 bundle with exactly one planted violation of `inv` (or None if impossible)."""
    b = copy.deepcopy(b)
    H, A = b['order']
    cb, ob = b['clubs'][H], b['clubs'][A]
    S, T, K, D = cb['S'], cb['team'], cb['kicker'], cb['dst']
    X = INV.PX
    pos = np.array(cb['pos'])
    qb = int(np.flatnonzero(pos == 'QB')[0])
    wr = int(np.flatnonzero(pos == 'WR')[0])
    L = b['ledger'][H]
    if inv == 'P01':
        S[wr, 0, X['receptions']] = S[wr, 0, X['targets']] + 1
    elif inv == 'P02':
        i = _first(S[..., X['rec_yards']] > 1.0); S[i[0], i[1], X['receptions']] = 0
    elif inv == 'P03':
        S[wr, 0, X['rec_td']] = S[wr, 0, X['receptions']] + 1
    elif inv == 'P04':
        S[wr, 0, X['rush_td']] = S[wr, 0, X['carries']] + 1
    elif inv == 'P05':
        i = _first(S[..., X['rush_yards']] > 1.0); S[i[0], i[1], X['carries']] = 0
    elif inv == 'P06':
        w = _first(S[qb, :, X['pass_yards']] > 1.0)[0]; S[qb, w, X['completions']] = 0
    elif inv == 'P06W':
        w = _first(S[qb, :, X['pass_yards']] > 1.0)[0]; S[qb, w, X['pass_att']] = 0
    elif inv == 'P07':
        S[qb, 0, X['pass_td']] = S[qb, 0, X['completions']] + 1
    elif inv == 'P07W':
        S[qb, 0, X['pass_td']] = S[qb, 0, X['pass_att']] + 1
    elif inv == 'P08':
        S[qb, 0, X['completions']] = S[qb, 0, X['pass_att']] + 1
    elif inv == 'P09':
        S[qb, 0, X['ints']] = S[qb, 0, X['pass_att']] - S[qb, 0, X['completions']] + 1
    elif inv == 'P09W':
        S[qb, 0, X['ints']] = S[qb, 0, X['pass_att']] + 1
    elif inv == 'P10':
        S[wr, 0, X['targets']] += 0.5
    elif inv == 'P11':
        S[wr, 0, X['fumbles_lost']] = S[wr, 0, X['carries']] + S[wr, 0, X['receptions']] + S[wr, 0, X['sacks_taken']] + 1
    elif inv == 'P12':
        S[wr, 0, X['sacks_taken']] = 1
    elif inv == 'C01':
        S[wr, 0, X['rec_yards']] += 5.0
    elif inv == 'C02':
        S[qb, 0, X['pass_td']] += 1; S[qb, 0, X['completions']] += 1; S[qb, 0, X['pass_att']] += 1
    elif inv == 'C03':
        S[qb, 0, X['completions']] += 1; S[qb, 0, X['pass_att']] += 1
    elif inv == 'C04':
        T['throwaways'] = T['throwaways'] + 1
    elif inv == 'C05':
        T['off_td'] = T['off_td'] + 1
    elif inv == 'C06':
        T['points'] = T['points'] + 1
    elif inv == 'C07':
        T['points'] = T['points'] + 0.5
    elif inv == 'C08':
        K['xp_att'] = K['xp_att'] + 1
    elif inv == 'C09':
        K['fg_made'] = K['fg_made'] + 1
    elif inv == 'C10':
        K['dk'] = K['dk'] + 1
    elif inv == 'C11':
        T['net_pass_yards'] = T['net_pass_yards'] + 3
    elif inv == 'C12':
        T['pass_att'] = T['pass_att'] + 1
    elif inv == 'D01':
        D['ints'] = D['ints'] + 1
    elif inv == 'D01W':
        D['takeaways'] = D['takeaways'] - 99
    elif inv == 'D02':
        D['sacks'] = D['sacks'] + 1
    elif inv == 'D03':
        D['fum_rec'] = D['fum_rec'] + 1
    elif inv == 'D04':
        D['takeaways'] = D['takeaways'] + 1
    elif inv == 'D05':
        D['def_td'] = D['def_td'] + 1
    elif inv == 'D06':
        D['safeties'] = D['safeties'] + 1
    elif inv == 'D07':
        D['def_td'] = D['takeaways'] + 1
    elif inv == 'D08':
        D['pa'] = D['pa'] + 7
    elif inv == 'D09':
        D['tier'] = D['tier'] + 3
    elif inv == 'D10':
        D['dk'] = D['dk'] * 1.1 + 1   # the anchor's kind of change
    elif inv == 'S01':
        cb['dk']['core'][wr, 0] += 0.5
    elif inv == 'S02':
        cb['dk']['classic'][wr, 0] += 0.5
    elif inv == 'E01':
        i = np.flatnonzero((L['kind'] == INV.KIND_PASS) & ~L['complete'] & ~L['int'])[0]; L['td'][i] = True
    elif inv == 'E02':
        i = np.flatnonzero((L['kind'] == INV.KIND_PASS) & L['complete'] & ~L['td'] & ~L['fumble'])[0]; L['int'][i] = True
    elif inv == 'E03':
        i = np.flatnonzero((L['kind'] == INV.KIND_RUSH) & L['td'])[0]; L['fumble'][i] = True
        L['fumbler'][i] = L['rusher'][i]
    elif inv == 'E04':
        i = np.flatnonzero((L['kind'] == INV.KIND_PASS) & ~L['complete'])[0]; L['yards'][i] = 5.0
    elif inv == 'E05':
        S[wr, 0, X['rec_yards']] += 2.0
    elif inv == 'E06':
        i = np.flatnonzero(L['kind'] == INV.KIND_PASS)[0]; L['passer'][i] = wr
    else:
        return None
    _ = ob
    return b


def test_b_planted_violation_caught_for_every_invariant():
    print('\nB. one planted violation per invariant is caught')
    spec, inc0, st, eb, model, fits = _worlds()
    base = eb['S3_after_scoring']
    clean = INV.check_bundle(base)
    check(INV.total_violations(clean) == 0, 'the base bundle is clean')
    missed = []
    for inv in INV.INVARIANTS:
        b = _plant(base, inv)
        if b is None:
            missed.append((inv, 'no fixture'))
            continue
        v = _viol(b, inv)
        if not v:
            missed.append((inv, v))
    check(not missed, f'all {len(INV.INVARIANTS)} invariants catch their planted violation ({missed})')
    check(len(INV.INVARIANTS) >= 40, f'{len(INV.INVARIANTS)} invariants registered')


# --------------------------------------------------------------------------------------------- C
def test_c_efficiency_moves_passer_and_receiver_identically():
    print('\nC. per-event efficiency: passer and receiver yards move by the same amount')
    model, fits = _toy_model()
    spec = _spec()
    inc0 = E.simulate_incumbent(model, spec, VOL, N, SEED)
    st = E.ELState(spec, inc0, _rates(), SEED + 7)
    b0 = st.bundle('S0_raw')
    fac = st.apply_efficiency(_pools(spec))
    b1 = st.bundle('S1_after_efficiency')
    X = INV.PX
    worst, moved = 0.0, 0.0
    for t in b0['order']:
        d_pass = (b1['clubs'][t]['S'][..., X['pass_yards']].sum(0) - b0['clubs'][t]['S'][..., X['pass_yards']].sum(0))
        d_rec = (b1['clubs'][t]['S'][..., X['rec_yards']].sum(0) - b0['clubs'][t]['S'][..., X['rec_yards']].sum(0))
        worst = max(worst, float(np.abs(d_pass - d_rec).max()))
        moved = max(moved, float(np.abs(d_pass).max()))
    check(moved > 1.0, f'the efficiency step does move yards (max club change {moved:.1f})')
    check(worst < 1e-6, f'passer change == receiver change in every club-world (max gap {worst:.2e})')
    check(any(abs(f - 1.0) > 1e-3 for t in fac for f in fac[t]['rec']), 'non-unit receiver factors applied')
    # one completion carries one yardage, credited to both ends
    L = b1['ledger'][b1['order'][0]]
    c = (L['kind'] == INV.KIND_PASS) & L['complete']
    check(c.sum() > 0 and 'pyards' not in L and 'ryards' not in L, 'a single yards column per event (no per-side copy)')
    # production's step on the same raw worlds breaks it
    inc1 = CE.stage_efficiency(inc0, _pools(spec), 0.023, SEED + 99)
    inc1['club_worlds'] = inc0['club_worlds']
    kick = {t: E.incumbent_kicker(inc0['club_points'][t], inc0['club_td'][t], _rates()['kicker'], 5) for t in ('H', 'A')}
    r = INV.check_bundle(E.incumbent_bundle(inc1, spec, 'S1_after_efficiency', kick, 'classic'))
    r0 = INV.check_bundle(E.incumbent_bundle(inc0, spec, 'S0_raw', kick, 'raw'))
    check(r0['C01']['violations'] == 0 and r['C01']['violations'] > 0,
          f"production efficiency_worlds breaks C01 ({r0['C01']['violations']} -> {r['C01']['violations']} of 2x{N})")


# --------------------------------------------------------------------------------------------- D
def test_d_interception_counted_once_each_side():
    print('\nD. an interception is ONE event: once for the passer, once for the opposing DST')
    spec, inc0, st, eb, model, fits = _worlds()
    b = eb['S3_after_scoring']
    X = INV.PX
    ok, n_int = True, 0
    for t in b['order']:
        o = b['order'][1] if t == b['order'][0] else b['order'][0]
        L = b['ledger'][o]
        ev = np.bincount(L['world'][L['int']], minlength=b['n'])
        qb = b['clubs'][o]['S'][..., X['ints']].sum(0)
        dst = b['clubs'][t]['dst']['ints']
        ok &= bool(np.array_equal(ev, qb) and np.array_equal(qb, dst))
        n_int += int(ev.sum())
    check(ok and n_int > 0, f'ledger INT events == opposing passers\' INTs == DST INTs in every world ({n_int} INTs)')
    # a single-INT world
    for t in b['order']:
        o = b['order'][1] if t == b['order'][0] else b['order'][0]
        w = np.flatnonzero(b['clubs'][t]['dst']['ints'] == 1)
        if len(w):
            w = int(w[0])
            check(b['clubs'][o]['S'][:, w, X['ints']].sum() == 1 and b['clubs'][t]['dst']['ints'][w] == 1
                  and b['clubs'][t]['dst']['takeaways'][w] >= 1, f'world {w}: one INT -> QB 1, DST 1')
            break
    # interceptions sit on incomplete attempts only
    L = b['ledger'][b['order'][0]]
    check(not np.any(L['int'] & L['complete']), 'no interception on a completed pass')


# --------------------------------------------------------------------------------------------- E
def test_e_dst_points_recompute_exactly():
    print('\nE. DST DK recomputes exactly from components and DK_PA_v1')
    spec, inc0, st, eb, model, fits = _worlds()
    b = eb['S3_after_scoring']
    ok, any_def_td = True, False
    for t in b['order']:
        o = b['order'][1] if t == b['order'][0] else b['order'][0]
        d, To = b['clubs'][t]['dst'], b['clubs'][o]['team']
        pa = To['points'] - 6 * To['def_td'] - To['def_td_conv_points'] - 2 * To['safeties']
        want = (INV.dk_tier(pa) + d['sacks'] + 2 * d['ints'] + 2 * d['fum_rec'] + 6 * (d['def_td'] + d['st_td'])
                + 2 * d['safeties'])
        ok &= bool(np.array_equal(d['pa'], pa) and np.array_equal(d['dk'], want))
        any_def_td |= bool((To['def_td'] > 0).any())
    check(ok, 'DST DK == tier(PA) + components; PA excludes the opponent\'s takeaway-return TDs, tries and safeties')
    check(any_def_td, 'the fixture contains worlds with an opponent takeaway-return TD (the DK_PA_v1 branch ran)')
    from nfl.sim import dst as D
    check(all(INV.dk_tier(np.array([x]))[0] == D.tier(x) for x in range(0, 61)), 'tier table == nfl/sim/dst.tier')
    # production's anchor breaks it on the same worlds
    inc2 = CE.stage_dst_anchor(dict(inc0), {'H': 9.0, 'A': 4.0})
    kick = {t: E.incumbent_kicker(inc0['club_points'][t], inc0['club_td'][t], _rates()['kicker'], 5) for t in ('H', 'A')}
    r0 = INV.check_bundle(E.incumbent_bundle(inc0, spec, 'S0_raw', kick, 'raw'))
    r2 = INV.check_bundle(E.incumbent_bundle(inc2, spec, 'S2_after_dst', kick, None))
    check(r0['D10']['violations'] == 0 and r2['D10']['violations'] > 0,
          f"anchor_means breaks D10 ({r0['D10']['violations']} -> {r2['D10']['violations']})")


# --------------------------------------------------------------------------------------------- F
def test_f_points_identity_exact():
    print('\nF. team points identity is exact and integral')
    spec, inc0, st, eb, model, fits = _worlds()
    for s_, b in eb.items():
        ok = True
        for t in b['order']:
            T, K = b['clubs'][t]['team'], b['clubs'][t]['kicker']
            want = 6 * (T['off_td'] + T['def_td'] + T['st_td']) + K['xp_made'] + 2 * K['tp_made'] + 3 * K['fg_made'] \
                + 2 * T['safeties']
            ok &= bool(np.array_equal(T['points'], want) and np.all(T['points'] == np.round(T['points']))
                       and np.all(T['points'] >= 0))
            ok &= bool(np.array_equal(K['xp_att'] + K['tp_att'], T['off_td'] + T['def_td'] + T['st_td']))
        check(ok, f'{s_}: points == 6 TD + XP + 2 x 2pt + 3 FG + 2 x safety; tries == TDs')
    b = eb['S3_after_scoring']
    pts = np.concatenate([b['clubs'][t]['team']['points'] for t in b['order']])
    check(pts.std() > 3 and pts.mean() > 10, f'points vary across worlds (mean {pts.mean():.1f}, sd {pts.std():.1f})')


# --------------------------------------------------------------------------------------------- G
def test_g_no_market_field_reachable():
    print('\nG. no market field reachable')
    check(not any(CE.is_market_name(c) for c in E.EL_PBP_COLS), 'the play-by-play whitelist holds no market column')
    import pandas as pd
    df = pd.DataFrame({'game_id': ['g'], 'total_line': [44.5]})
    ok, code = _raises(lambda: E.guard_no_market(df, 'pbp'), 'EL_MARKET_INPUT')
    check(ok, f'pbp frame carrying total_line refused ({code})')
    rows = [{'game_id': 'g', 'club': 'H', 'points': 21, 'spread_line_raw': 3.0}]
    ok, code = _raises(lambda: E.guard_no_market(rows, 'TEAM_GAME'), 'EL_MARKET_INPUT')
    check(ok, f'TEAM_GAME rows carrying spread_line_raw refused ({code})')
    check('spread_line_raw' not in CE.whitelist_rows(rows, CE.TG_FIELDS)[0], 'the TEAM_GAME whitelist drops it')
    model, fits = _toy_model()
    spec = _spec()
    inc0 = E.simulate_incumbent(model, spec, VOL, 10, SEED)
    bad = copy.deepcopy(spec)
    bad['clubs'][0]['players'][1]['implied_total'] = 24.0
    ok, code = _raises(lambda: E.ELState(bad, inc0, _rates(), 1), 'EL_MARKET_INPUT')
    check(ok, f'a spec player carrying implied_total refused by the event-linked stage ({code})')
    r = _rates()
    r['odds_adjustment'] = 1.0
    ok, code = _raises(lambda: E.ELState(spec, inc0, r, 1), 'EL_MARKET_INPUT')
    check(ok, f'event rates carrying an odds field refused ({code})')
    bad2 = copy.deepcopy(spec)
    bad2['moneyline'] = -150
    ok, code = _raises(lambda: E.simulate_incumbent(model, bad2, VOL, 10, SEED), 'EL_MARKET_INPUT')
    check(ok, f'a game spec carrying moneyline refused before simulation ({code})')
    bad3 = copy.deepcopy(spec)
    bad3['total_line'] = 51.0
    ok, code = _raises(lambda: E.simulate_incumbent(model, bad3, VOL, 10, SEED), 'EL_SPEC_NOT_FOOTBALL')
    check(ok, f'a simulator centre that differs from the football centre refused ({code})')
    df24 = E.load_pbp(2024)
    check(not any(CE.is_market_name(c) for c in df24.columns) and len(df24) > 10000,
          'committed 2024 play-by-play loads without total_line / spread_line / vegas_wp')


# --------------------------------------------------------------------------------------------- H
def _digest(b):
    h = hashlib.sha256()
    for t in b['order']:
        cb = b['clubs'][t]
        h.update(np.ascontiguousarray(cb['S']).tobytes())
        for blk in ('team', 'dst', 'kicker'):
            for k in sorted(cb[blk]):
                h.update(k.encode())
                h.update(np.ascontiguousarray(np.asarray(cb[blk][k], float)).tobytes())
        for k in sorted(b['ledger'][t]):
            h.update(np.ascontiguousarray(b['ledger'][t][k]).tobytes())
    return h.hexdigest()


def test_h_deterministic_under_seed():
    print('\nH. deterministic under seed')
    model, fits = _toy_model()
    spec = _spec()
    d = []
    for _ in range(2):
        inc0 = E.simulate_incumbent(model, spec, VOL, 40, SEED)
        st = E.ELState(spec, inc0, _rates(), 99)
        st.apply_efficiency(_pools(spec))
        edges, means = E.band_table(fits)
        st.apply_dst_rates({'H': {'sacks': 1.2}, 'A': {'ints': 0.5}}, means, edges, 5)
        d.append(_digest(st.bundle('S3', scored=True)))
    check(d[0] == d[1], f'byte-identical bundles on two runs ({d[0][:12]})')
    inc0 = E.simulate_incumbent(model, spec, VOL, 40, SEED)
    st2 = E.ELState(spec, inc0, _rates(), 100)
    check(_digest(st2.bundle('S0')) != _digest(E.ELState(spec, inc0, _rates(), 99).bundle('S0')),
          'a different seed gives a different ledger')
    a = E.simulate_incumbent(model, spec, VOL, 40, SEED)
    c = CE.simulate_incumbent(model, spec, VOL, 40, SEED)
    check(all(np.array_equal(a['players'][k], c['players'][k]) for k in c['players'])
          and all(np.array_equal(a['dst_comp'][k], c['dst_comp'][k]) for k in c['dst_comp']),
          'the incumbent call is the clean harness\'s call (identical draws)')


# --------------------------------------------------------------------------------------------- I
def test_i_refusal_on_empty_input():
    print('\nI. refusal on empty or partial input, by name')
    model, fits = _toy_model()
    spec = _spec()
    ok, code = _raises(lambda: E.ELState(spec, {}, _rates(), 1), 'EL_EMPTY_INPUT')
    check(ok, f'empty incumbent world ({code})')
    empty = copy.deepcopy(spec)
    empty['clubs'][1]['players'] = []
    ok, code = _raises(lambda: E.simulate_incumbent(model, empty, VOL, 10, SEED), 'EL_EMPTY_INPUT')
    check(ok, f'a club with no players ({code})')
    ok, code = _raises(lambda: E.simulate_incumbent(model, spec, VOL, 0, SEED), 'EL_EMPTY_INPUT')
    check(ok, f'zero worlds ({code})')
    ok, code = _raises(lambda: INV.check_bundle({'n': 0, 'clubs': {}, 'order': []}), 'INV_EMPTY_BUNDLE')
    check(ok, f'checker: empty bundle ({code})')
    spec_, inc0, st, eb, model_, fits_ = _worlds()
    b = copy.deepcopy(eb['S0_raw'])
    b['clubs']['H']['S'] = np.zeros((0, b['n'], len(INV.PF)))
    b['clubs']['H']['ids'], b['clubs']['H']['pos'] = [], []
    ok, code = _raises(lambda: INV.check_bundle(b), 'INV_EMPTY_BUNDLE')
    check(ok, f'checker: a club with no player rows ({code})')
    bad = copy.deepcopy(inc0)
    bad['club_worlds']['H'][0, 0] += 3
    ok, code = _raises(lambda: E.ELState(spec_, bad, _rates(), 1), 'EL_INCUMBENT_VOLUME_NOT_RECONCILED')
    check(ok, f'partial / unreconciled incumbent volume ({code})')
    ok, code = _raises(lambda: E.load_pbp(2025), 'EL_SEASON_LOCKED')
    check(ok, f'2025 unreadable with the gate closed ({code})')
    ok, code = _raises(lambda: E.load_pbp(2026), 'EL_SEASON_LOCKED')
    check(ok, f'2026 unreadable with the gate closed ({code})')
    check(all(int(r['season']) <= E.CUTOFF for r in E.load_team_game()), 'TEAM_GAME rows after 2024 are closed')
    ok, code = _raises(lambda: E.measure_event_rates((2024, 2025)), 'EL_HELDOUT_LEAK')
    check(ok, f'an event-rate fit including 2025 refused ({code})')


# --------------------------------------------------------------------------------------------- J
def _history_bundle(n=1):
    """A two-club HISTORY bundle with every field represented (n club-games)."""
    def club(name):
        P_ = 3
        S = np.zeros((P_, n, len(INV.PF)))
        X = INV.PX
        S[0, :, X['pass_att']] = 10; S[0, :, X['completions']] = 6; S[0, :, X['pass_yards']] = 70
        S[1, :, X['targets']] = 7; S[1, :, X['receptions']] = 5; S[1, :, X['rec_yards']] = 60
        S[2, :, X['targets']] = 2; S[2, :, X['receptions']] = 1; S[2, :, X['rec_yards']] = 10
        S[2, :, X['carries']] = 12; S[2, :, X['rush_yards']] = 50
        z = np.zeros(n)
        team = {'points': z + 3, 'off_td': z, 'def_td': z, 'st_td': z, 'dst_td': z, 'safeties': z,
                'def_td_conv_points': z, 'throwaways': z + 1, 'pass_att': z + 10, 'rush_att': z + 12,
                'sacks_taken': z, 'sack_yards': z, 'net_pass_yards': z + 70}
        kick = {'xp_att': z, 'xp_made': z, 'tp_att': z, 'tp_made': z, 'fg_made': z + 1, 'fg_0_39': z + 1,
                'fg_40_49': z, 'fg_50_plus': z, 'dk': z + 3}
        dst = {'sacks': z, 'ints': z, 'fum_rec': z, 'takeaways': z, 'def_td': z, 'st_td': z, 'dst_td': z,
               'safeties': z, 'pa': z + 3, 'tier': INV.dk_tier(z + 3), 'dk': INV.dk_tier(z + 3)}
        return {'ids': ['qb', 'wr', 'rb'], 'pos': ['QB', 'WR', 'RB'], 'S': S, 'team': team, 'kicker': kick, 'dst': dst,
                'dk': None}
    return {'provider': 'HISTORY', 'stage': 'actual', 'n': n, 'order': ['H', 'A'],
            'clubs': {'H': club('H'), 'A': club('A')}, 'ledger': None}


def test_j_official_stat_conventions_and_exceptions():
    print('\nJ. official-stat conventions and history-only exceptions')
    b = _history_bundle()
    check(INV.total_violations(INV.check_bundle(b)) == 0, 'the history fixture is clean')
    X = INV.PX
    lat = copy.deepcopy(b)
    lat['clubs']['H']['S'][2, 0, X['rec_yards']] += 8          # lateral receiving yards to the RB, no reception
    lat['clubs']['H']['S'][2, 0, X['receptions']] = 0
    lat['clubs']['H']['S'][2, 0, X['targets']] = 0
    lat['clubs']['H']['S'][1, 0, X['rec_yards']] -= 0          # QB yards still 70: lateral yards are extra
    r = INV.check_bundle(lat)
    check(r['P02']['violations'] == 1 and r['C01']['violations'] == 1, 'a lateral breaks P02 and C01 when unflagged')
    ex = {'H': {'LATERAL': np.array([True])}}
    r = INV.check_bundle(lat, exceptions=ex)
    check(r['P02']['violations'] == 0 and r['C01']['violations'] == 0, 'LATERAL excuses P02 / C01 in that club-game')
    check(INV.check_bundle(lat, exceptions={'H': {'LATERAL': np.array([False])}})['P02']['violations'] == 1,
          'the exception excuses only flagged club-games')
    sim = copy.deepcopy(lat)
    sim['provider'] = 'EVENT_LINKED'
    ok, code = _raises(lambda: INV.check_bundle(sim, exceptions=ex), 'INV_EXCEPTION_NOT_ALLOWED_FOR_SIMULATION')
    check(ok, f'a simulated world may not claim the lateral exception ({code})')
    ok, code = _raises(lambda: INV.check_bundle(lat, exceptions={'H': {'GOOD_VIBES': np.array([True])}}),
                       'INV_UNKNOWN_EXCEPTION')
    check(ok, f'an undeclared exception kind is refused ({code})')
    # ALL_PASSERS: a WR throws a 20-yard completion to the RB
    tp = copy.deepcopy(b)
    S = tp['clubs']['H']['S']
    S[1, 0, X['pass_att']] = 1; S[1, 0, X['completions']] = 1; S[1, 0, X['pass_yards']] = 20
    S[2, 0, X['targets']] += 1; S[2, 0, X['receptions']] += 1; S[2, 0, X['rec_yards']] += 20
    tp['clubs']['H']['team']['pass_att'] = tp['clubs']['H']['team']['pass_att'] + 1
    tp['clubs']['H']['team']['net_pass_yards'] = tp['clubs']['H']['team']['net_pass_yards'] + 20
    r = INV.check_bundle(tp)
    check(r['C01']['violations'] == 0 and r['C03']['violations'] == 0, 'trick-play pass: identities over ALL passers hold')
    # SACK_YARDS: a 7-yard sack leaves gross passing yards alone and reduces team net
    sk = copy.deepcopy(b)
    sk['clubs']['H']['S'][0, 0, X['sacks_taken']] = 1
    sk['clubs']['H']['S'][0, 0, X['sack_yards']] = 7
    sk['clubs']['H']['team']['sacks_taken'] = np.array([1.0])
    sk['clubs']['H']['team']['sack_yards'] = np.array([7.0])
    sk['clubs']['H']['team']['net_pass_yards'] = np.array([63.0])
    sk['clubs']['A']['dst']['sacks'] = np.array([1.0])
    sk['clubs']['A']['dst']['dk'] = sk['clubs']['A']['dst']['dk'] + 1
    check(INV.total_violations(INV.check_bundle(sk)) == 0, 'SACK_YARDS: gross unchanged, net = gross - sack yards')
    wrong = copy.deepcopy(sk)
    wrong['clubs']['H']['S'][0, 0, X['pass_yards']] -= 7          # the wrong convention
    check(INV.check_bundle(wrong)['C01']['violations'] == 1, 'subtracting sack yards from the passer breaks C01')
    # TWO_POINT: a successful 2pt try is a try, not a TD / reception
    t2 = copy.deepcopy(b)
    T, K = t2['clubs']['H']['team'], t2['clubs']['H']['kicker']
    T['off_td'] = np.array([1.0]); T['points'] = np.array([11.0])
    S = t2['clubs']['H']['S']
    S[2, 0, X['rush_td']] = 1
    K['tp_att'] = np.array([1.0]); K['tp_made'] = np.array([1.0])
    t2['clubs']['A']['dst']['pa'] = np.array([11.0])
    t2['clubs']['A']['dst']['tier'] = INV.dk_tier(np.array([11.0]))
    t2['clubs']['A']['dst']['dk'] = t2['clubs']['A']['dst']['tier'].copy()
    check(INV.total_violations(INV.check_bundle(t2)) == 0, 'TWO_POINT: TD + successful 2pt = 8 points, no extra TD')
    # OFFENSIVE_FUMBLE_RECOVERY_TD (history only)
    fr = copy.deepcopy(t2)
    fr['clubs']['H']['S'][2, 0, X['rush_td']] = 0
    check(INV.check_bundle(fr)['C05']['violations'] == 1, 'an offensive TD that is neither pass nor rush breaks C05')
    check(INV.check_bundle(fr, exceptions={'H': {'OFFENSIVE_FUMBLE_RECOVERY_TD': np.array([True])}})['C05']['violations']
          == 0, 'OFFENSIVE_FUMBLE_RECOVERY_TD excuses C05 for history')
    # DK_PA_v1: the opponent's pick-six is excluded from points allowed
    pk = copy.deepcopy(b)
    TA = pk['clubs']['A']['team']
    TA['def_td'] = np.array([1.0]); TA['dst_td'] = np.array([1.0]); TA['points'] = np.array([10.0])
    TA['def_td_conv_points'] = np.array([1.0])
    pk['clubs']['A']['kicker']['xp_att'] = np.array([1.0]); pk['clubs']['A']['kicker']['xp_made'] = np.array([1.0])
    pk['clubs']['A']['kicker']['dk'] = np.array([4.0])
    pk['clubs']['H']['S'][0, 0, X['ints']] = 1
    pk['clubs']['A']['dst'].update({'ints': np.array([1.0]), 'takeaways': np.array([1.0]), 'def_td': np.array([1.0]),
                                    'dst_td': np.array([1.0])})
    pk['clubs']['A']['dst']['dk'] = pk['clubs']['A']['dst']['tier'] + 2 + 6
    pk['clubs']['H']['dst']['pa'] = np.array([3.0])            # 10 - 6 - 1
    pk['clubs']['H']['dst']['tier'] = INV.dk_tier(np.array([3.0]))
    pk['clubs']['H']['dst']['dk'] = pk['clubs']['H']['dst']['tier'].copy()
    check(INV.total_violations(INV.check_bundle(pk)) == 0, 'DK_PA_v1: opponent 10 incl. a pick-six + XP -> PA 3')
    wrong = copy.deepcopy(pk)
    wrong['clubs']['H']['dst']['pa'] = np.array([10.0])          # the full-score grader rule
    check(INV.check_bundle(wrong)['D08']['violations'] == 1, 'PA = full opponent score breaks D08')


# --------------------------------------------------------------------------------------------- K
def test_k_prereg_enforced():
    print('\nK. pre-registration enforcement')
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        pre, fz, lk = d / 'pre.md', d / 'frozen.json', d / 'lock.json'
        pre.write_text('registration v1\n')
        fz.write_text('{}')
        ok, code = _raises(lambda: E.verify_prereg(pre, lk, fz), 'EL_PREREG_NOT_LOCKED')
        check(ok, f'no lock -> refused ({code})')
        lk.write_text(json.dumps({'prereg_sha256': E._sha(pre), 'frozen_sha256': E._sha(fz),
                                  'clean_frozen_sha256': E._sha(CE.FROZEN)}))
        check(E.verify_prereg(pre, lk, fz)['prereg_sha256'] == E._sha(pre), 'matching files verify')
        pre.write_text('registration v1, edited after the lock\n')
        ok, code = _raises(lambda: E.verify_prereg(pre, lk, fz), 'EL_PREREG_CHANGED')
        check(ok, f'changed pre-registration refused ({code})')
        pre.write_text('registration v1\n')
        fz.write_text('{"x": 1}')
        ok, code = _raises(lambda: E.verify_prereg(pre, lk, fz), 'EL_FROZEN_CHANGED')
        check(ok, f'changed frozen file refused ({code})')
    dev = {'development': {'code_sha256': 'abc'}}
    ok, code = _raises(lambda: E.check_phase_preconditions('confirmation', {}, 'abc', E.N_WORLDS, None),
                       'EL_NO_DEVELOPMENT_RUN')
    check(ok, f'confirmation before development refused ({code})')
    ok, code = _raises(lambda: E.check_phase_preconditions('confirmation', dev, 'def', E.N_WORLDS, None),
                       'EL_CODE_CHANGED_SINCE_DEVELOPMENT')
    check(ok, f'code changed since development refused ({code})')
    ok, code = _raises(lambda: E.check_phase_preconditions('confirmation', dev, 'abc', 100, None),
                       'EL_CONFIRMATION_NOT_AS_REGISTERED')
    check(ok, f'off-design confirmation refused ({code})')
    ok, code = _raises(lambda: E.check_phase_preconditions('development', {**dev, 'confirmation': {}}, 'abc',
                                                           E.N_WORLDS, None), 'EL_CONFIRMATION_ALREADY_READ')
    check(ok, f'any scoring after the confirmation read refused ({code})')
    check(E.check_phase_preconditions('confirmation', dev, 'abc', E.N_WORLDS, None), 'the registered path is allowed')
    if E.LOCK.exists():
        lk_ = json.loads(E.LOCK.read_text())
        check(lk_['prereg_sha256'] == E._sha(E.PREREG) and lk_['frozen_sha256'] == E._sha(E.FROZEN),
              'the committed registration and frozen file match their lock')


# --------------------------------------------------------------------------------------------- L
def test_l_constants_agree_with_production():
    print('\nL. shared constants agree with production')
    from nfl.tools import classic_slate_run as CR, kicker_world as KW
    from nfl.sim import dst as D
    check(E.MIN_SIM_OPPORTUNITIES == CR.MIN_SIM_OPPORTUNITIES, 'MIN_SIM_OPPORTUNITIES == classic_slate_run')
    check(INV.FG_BAND_POINTS == KW.BAND_POINTS, 'kicker band points == kicker_world.BAND_POINTS')
    check([b[:2] for b in INV.POINTS_BANDS[:-1]] == [b[:2] for b in D.POINTS_BANDS[:-1]]
          and [b[2] for b in INV.POINTS_BANDS] == [b[2] for b in D.POINTS_BANDS], 'tier bands == dst.POINTS_BANDS')
    check(tuple(INV.PF[:0]) == () and set(CE.STAT_FIELDS) <= set(INV.PF), 'every simulator stat field is a PF field')
    rng = np.random.default_rng(1)
    S = np.zeros((40, 1, len(INV.PF)))
    for f in INV.PF:
        S[:, 0, INV.PX[f]] = rng.integers(0, 6, 40) if f in INV.COUNT_FIELDS else rng.uniform(-5, 360, 40)
    S[:, 0, INV.PX['fumbles_lost']] = 0
    mine = INV.dk_classic(S)[:, 0]
    X = lambda f: S[:, 0, INV.PX[f]]
    prod = np.array([CR.dk_from_stats(*(X(f)[i] for f in CE.STAT_FIELDS), X('ints')[i]) for i in range(40)])
    check(np.allclose(mine, prod), 'DK classic == classic_slate_run.dk_from_stats (fumbles 0)')


# --------------------------------------------------------------------------------------------- M
def test_m_dst_rate_step():
    print('\nM. DST event-rate step: thinning and superposition')
    model, fits = _toy_model()
    spec = _spec()
    inc0 = E.simulate_incumbent(model, spec, VOL, 200, SEED)
    edges, means = E.band_table(fits)
    st = E.ELState(spec, inc0, _rates(), 3)
    before = {t: {k: v.copy() for k, v in st.counts[t].items()} for t in st.order}
    st.apply_dst_rates({'H': {'sacks': 0.0}, 'A': {}}, means, edges, 4)
    check(int(st.counts['H']['sacks'].sum()) == 0, 'm = 0 removes every sack event of that DST')
    check(all(np.array_equal(st.counts['A'][k], before['A'][k]) for k in before['A']), 'm = 1 leaves counts unchanged')
    b = st.bundle('S2', scored=True)
    check(INV.total_violations(INV.check_bundle(b)) == 0, 'after re-placement every invariant still holds')
    st2 = E.ELState(spec, inc0, _rates(), 3)
    base = st2.counts['H']['sacks'].astype(float).mean()
    st2.apply_dst_rates({'H': {'sacks': 2.0}}, means, edges, 4)
    check(st2.counts['H']['sacks'].mean() > base + 0.5, f'm = 2 adds sack events (mean {base:.2f} -> '
          f'{st2.counts["H"]["sacks"].mean():.2f})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in dict(globals()).items() if k.startswith('test_') and callable(v)):
        if name != 'test_zz_every_check_passed':
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)
