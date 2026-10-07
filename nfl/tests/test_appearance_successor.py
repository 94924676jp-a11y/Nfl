"""Appearance successor (SC-APPEAR-1 rates + strict hurdle gate + field-specific pi): end-to-end guards. SHADOW_ONLY.

What is guarded here, and why each one matters:

  * DISABLED == PRODUCTION, BYTE FOR BYTE. With no gate key the hurdle module (production nfl/sim/game.py plus four
    in-memory substitutions) returns draws, stat lines and club worlds identical to production, on a synthetic game
    and through the whole end-to-end chain.
  * ALL pi = 1 IS DECLARED NOT IDENTICAL, and the test checks the declared truth: a gated field at pi = 1 has zero
    probability of 0 (zero-truncated), so the draws differ from production while P(0) = 0 exactly.
  * P(0) = 1 - pi PER FIELD IN END-TO-END WORLDS. On the full chain (spec -> simulate_game_centred -> efficiency
    worlds -> DST anchor -> DK points), every gated player-field's zero share is within 4 binomial SEs of 1 - pi
    (tolerance declared from the binomial SE sqrt(pi(1-pi)/n); 4 SE so the chance of any of ~30 units tripping by
    sampling alone is ~0.2%), AND world by world the count is 0 exactly when that world's gate is closed.
  * CLUB TOTALS CONSERVED AFTER EVERY STAGE: every gated allocation's players + ghost = the club total; per world the
    player counts + logged ghost = club_worlds; the efficiency step, DST step and DK scoring leave every count as drawn.
  * DK-ZERO TRACKS OPPORTUNITY ZERO: a gated player's DK score is 0 in exactly the worlds with no opportunity.
  * ELIGIBILITY SEPARATE: an INACTIVE row with volume never reaches the spec or the draws; pi = 0 never gets a count
    or a TD; UNKNOWN_ACTIVE_STATE stays in the pool, gated.
  * THE SEAL: refuses at/after kickoff, refuses an overwrite, the written week-5 seal verifies (hash, 444, before
    kickoff, every schedule game present). THE GRADER refuses a tampered seal, a post-kickoff seal, a prereg mismatch,
    a game not yet started, an empty panel; never scores an undressed player or a missing game as zero.
  * LEAKAGE: pi identical with 2025-2026 removed; a week-5 game record identical when week >= 5 rows are added and
    perturbed in the panel and in the football-points table.
  * NAMED REFUSALS on empty input.

Run standalone:  python3.12 nfl/tests/test_appearance_successor.py
Via the runner:  python3.12 nfl/tests/run_suite.py --modules test_appearance_successor
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import random
import stat
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load('appearance_successor', 'nfl/research/appearance/appearance_successor.py')
W = _load('seal_appearance_w5', 'nfl/prospective/appearance/seal_appearance_w5.py')
G = _load('grade_appearance_seal', 'nfl/research/appearance/grade_appearance_seal.py')
SIM = A.SIM

PASSED = FAILED = 0
_CACHE = {}
N_E2E = 3000
#: Monte Carlo tolerance multiple on the binomial SE (declared in the module docstring).
SE_MULT = 4.0


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')
    return bool(ok)


def _refused(fn, code):
    try:
        fn()
    except (A.SuccessorError, W.SealError, G.GradeError) as e:
        return e.code == code
    return False


def _model():
    if 'model' not in _CACHE:
        _CACHE['model'] = A.load_model()
    return _CACHE['model']


def _club(c):
    ps = [{'id': f'QB|{c}', 'position': 'QB', 'target_share': 0.0, 'carry_share': 0.08, 'pass_att_share': 0.97,
           'pass_td_share': 0.0, 'rush_td_share': 0.1, 'catch_rate': 0.65, 'slot': 'OTHER'}]
    sh = [('RB', 0.10, 0.55), ('RB', 0.04, 0.25), ('RB', 0.01, 0.07), ('WR', 0.25, 0.01), ('WR', 0.20, 0.01),
          ('WR', 0.12, 0.0), ('WR', 0.03, 0.0), ('TE', 0.15, 0.0), ('TE', 0.05, 0.0), ('TE', 0.02, 0.0)]
    for i, (p, t, ca) in enumerate(sh):
        # rush TD share only for RB, as showdown_draws._shares builds it
        ps.append({'id': f'{p}{i}|{c}', 'position': p, 'target_share': t, 'carry_share': ca, 'pass_att_share': 0.0,
                   'pass_td_share': t, 'rush_td_share': ca if p == 'RB' else 0.0, 'catch_rate': 0.7, 'slot': 'OTHER'})
    return {'club': c, 'players': ps, 'dst_id': f'DST|{c}'}


def _game():
    spec = {'total_line': 45.0, 'home_spread': -3.0, 'clubs': [_club('H'), _club('A')]}
    centre = {c: {'pass_attempts': 34.0, 'rush_attempts': 26.0, 'targets': 32.0} for c in 'HA'}
    return spec, centre


def _gates(spec, seed=1, pis=(0.2, 0.5, 0.8, 0.95), cpis=(0.3, 0.6, 0.9)):
    rng = random.Random(seed)
    out = {}
    for c in spec['clubs']:
        for p in c['players']:
            if p['position'] == 'QB':
                continue
            g = {'targets': rng.choice(pis)}
            if p['position'] == 'RB':
                g['carries'] = rng.choice(cpis)
            out[p['id']] = g
    return out


def _gate_uniforms(spec_gated, n, seed):
    """Replicates the gate stream: per world, per club in order, one uniform per gated player."""
    gr = random.Random(seed + A.GATE_SEED_OFFSET)
    U = {p['id']: [] for c in spec_gated['clubs'] for p in c['players'] if p.get('hurdle')}
    for _ in range(n):
        for c in spec_gated['clubs']:
            for p in c['players']:
                if p.get('hurdle'):
                    U[p['id']].append(gr.random())
    return {k: np.asarray(v) for k, v in U.items()}


def _e2e():
    if 'e2e' not in _CACHE:
        spec, centre = _game()
        gates = _gates(spec)
        A.ALLOC_LOG = []
        rbk = {p['id']: {'conditional_volume': {}} for c in spec['clubs'] for p in c['players']}
        e = A.end_to_end(_model(), spec, centre, rbk, 0.02, N_E2E, 7, gates=gates,
                         dst_targets={'DST|H': 6.0, 'DST|A': 5.0})
        log, A.ALLOC_LOG = A.ALLOC_LOG, None
        _CACHE['e2e'] = (spec, centre, gates, e, log)
    return _CACHE['e2e']


# --------------------------------------------------------------------------------------------- identity
def test_disabled_is_byte_identical_to_production():
    spec, centre = _game()
    m = _model()
    o = SIM.simulate_game_centred(m, spec, centre, n_sims=600, seed=11, n_calib=600)
    h = A.hurdle().simulate_game_centred(m, spec, centre, n_sims=600, seed=11, n_calib=600)
    check(o.state.value == 'PASS' and h.state.value == 'PASS', 'both simulators PASS')
    check(o.value['stat_draws'] == h.value['stat_draws'], 'stat lines byte-identical with no gate key')
    check(o.value['draws'] == h.value['draws'], 'DK draws byte-identical with no gate key')
    check(o.value['club_worlds'] == h.value['club_worlds'], 'club worlds byte-identical with no gate key')
    rbk = {p['id']: {'conditional_volume': {}} for c in spec['clubs'] for p in c['players']}
    e = A.end_to_end(m, spec, centre, rbk, 0.02, 600, 11, gates=None, dst_targets={'DST|H': 6.0, 'DST|A': 5.0})
    check(e['stat_draws'] == o.value['stat_draws'], 'end_to_end with the successor disabled = production simulator')
    check(A.hurdle().N_SUBSTITUTIONS == 4 and A.hurdle().SOURCE_SHA256 == A.sha_file(A.SIM_FILE),
          'hurdle module is the production source with exactly four substitutions')


def test_all_pi_one_is_declared_not_identical_and_zero_truncated():
    spec, centre = _game()
    m = _model()
    gates = {p['id']: ({'targets': 1.0, 'carries': 1.0} if p['position'] == 'RB' else {'targets': 1.0})
             for c in spec['clubs'] for p in c['players'] if p['position'] in ('RB', 'WR', 'TE')}
    o = SIM.simulate_game_centred(m, spec, centre, n_sims=600, seed=11, n_calib=600)
    e = A.end_to_end(m, spec, centre, {}, 0.02, 600, 11, gates=gates)
    check(e['stat_draws'] != o.value['stat_draws'], 'DECLARED: all pi = 1 is NOT byte-identical (zero-truncation)')
    p0 = []
    for k, g in gates.items():
        for f in g:
            p0.append(sum(1 for x in A.field_counts(e['stat_draws'][k], f) if x == 0))
    prod0 = sum(sum(1 for x in A.field_counts(o.value['stat_draws'][k], f) if x == 0) for k, g in gates.items() for f in g)
    check(max(p0) == 0, f'every gated field at pi = 1 has P(0) = 0 exactly (zero worlds {sum(p0)})')
    check(prod0 > 0, f'production draws do have zero worlds for the same players ({prod0}), so the difference is real')


# ----------------------------------------------------------------------------------- end-to-end zero mass
def test_zero_share_equals_one_minus_pi_end_to_end():
    spec, centre, gates, e, _log = _e2e()
    U = _gate_uniforms(e['spec'], N_E2E, 7)
    worst, n_units, mism = 0.0, 0, 0
    for k, g in gates.items():
        for f, pi in g.items():
            x = np.asarray(A.field_counts(e['stat_draws'][k], f))
            # stage after efficiency: the same counts
            xe = np.asarray(A.field_counts(e['stat_worlds_after_efficiency'][k], f))
            se = math.sqrt(pi * (1 - pi) / N_E2E)
            z = abs((x == 0).mean() - (1 - pi)) / se
            worst = max(worst, z)
            n_units += 1
            mism += int(((x == 0) != (U[k] >= pi)).sum()) + int((x != xe).sum())
    check(n_units >= 26, f'{n_units} gated player-fields in the end-to-end worlds')
    check(worst <= SE_MULT, f'every zero share within {SE_MULT} binomial SE of 1 - pi (worst {worst:.2f} SE)')
    check(mism == 0, 'world by world: count is 0 exactly when the gate is closed, identical after the efficiency step')
    c = e['counts']
    check(c.get('targets_gated_allocations', 0) > 0 and c.get('carries_gated_allocations', 0) > 0,
          f'the hurdle ran on both gated fields {dict((k, v) for k, v in c.items() if "allocations" in k)}')
    tot = c.get('targets_gated_allocations', 0) + c.get('carries_gated_allocations', 0)
    check(c.get('HURDLE_INFEASIBLE', 0) <= 0.001 * tot,
          f'infeasible worlds (club total < open gated players) are counted and rare ({c.get("HURDLE_INFEASIBLE", 0)} '
          f'of {tot} allocations)')


def test_club_totals_conserved_after_every_stage():
    spec, centre, gates, e, log = _e2e()
    check(bool(log) and all(t == s + g for _f, t, s, g, _n in log),
          f'every gated allocation: players + ghost == club total ({len(log)} allocations)')
    final = log[-N_E2E * 4:]       # final pass: per world, per club (home, away), targets then carries
    cw = e['sim']['club_worlds']
    ok = True
    for ci, c in enumerate(spec['clubs']):
        ids = [p['id'] for p in c['players']]
        tg = np.asarray([[w[A.SIM_IX['targets']] for w in e['stat_draws'][k]] for k in ids]).sum(0)
        ca = np.asarray([[w[A.SIM_IX['carries']] for w in e['stat_draws'][k]] for k in ids]).sum(0)
        gt = np.asarray([final[4 * si + 2 * ci][3] for si in range(N_E2E)])
        gc = np.asarray([final[4 * si + 2 * ci + 1][3] for si in range(N_E2E)])
        club = np.asarray(cw[c['club']])
        ok = ok and np.array_equal(tg + gt, club[:, 2]) and np.array_equal(ca + gc, club[:, 1])
        ok = ok and all(final[4 * si + 2 * ci][0] == 'targets' and final[4 * si + 2 * ci + 1][0] == 'carries'
                        for si in range(0, N_E2E, 97))
    check(ok, 'per world: player targets / carries + logged ghost == the club totals in club_worlds')
    cnt = [A.SIM_IX[f] for f in ('pass_att', 'pass_td', 'carries', 'rush_td', 'targets', 'receptions', 'rec_td')]
    same = all(np.array_equal(np.asarray(e['stat_draws'][k], float)[:, cnt],
                              np.asarray(e['stat_worlds_after_efficiency'][k], float)[:, cnt]) for k in e['stat_draws'])
    skill = set(e['dk_after_efficiency'])
    check(all(e['draws_final'][k] == e['dk_after_efficiency'][k] for k in skill),
          'DST step leaves every skill player\'s DK draws untouched')
    d = e['dst_anchor']
    check(d is not None and d['n_anchored'] == 2 and all(abs(np.mean(e['draws_final'][k]) - t) < 1e-9
                                                        for k, t in (('DST|H', 6.0), ('DST|A', 5.0))),
          'DST anchor step applied to DST only, means on target')
    rec = 0
    for k in skill:
        for w, dk in zip(e['stat_worlds_after_efficiency'][k], e['dk_after_efficiency'][k]):
            rec = max(rec, abs(A.CR.dk_from_stats(*w) - dk))
    check(rec < 1e-9, 'DK scoring recomputed from the post-efficiency stat line equals the drawn DK points')


#: Production splits club yards with a 1e-9 weight floor (nfl/sim/game.py split()), so a player with zero
#: opportunities can carry yard "dust" (measured <= 1e-3 yards, i.e. <= 1e-4 DK). A DK score below one hundredth of a
#: point is therefore read as zero. Declared here; it is a property of production, not of the gate.
DK_ZERO = 1e-2


def test_dk_zero_tracks_opportunity_zero():
    spec, centre, gates, e, _log = _e2e()
    bad, extra, n = 0, 0, 0
    for k in gates:
        st = np.asarray(e['stat_worlds_after_efficiency'][k], float)
        opp0 = ((st[:, A.SIM_IX['targets']] == 0) & (st[:, A.SIM_IX['carries']] == 0)
                & (st[:, A.SIM_IX['pass_att']] == 0) & (st[:, A.SIM_IX['rush_td']] == 0) & (st[:, A.SIM_IX['rec_td']] == 0))
        dk0 = np.asarray(e['draws_final'][k]) < DK_ZERO
        bad += int((opp0 & ~dk0).sum())
        extra += int((dk0 & ~opp0).sum())
        n += len(dk0)
    # Both directions are production properties, not gate leaks: split() can credit a zero-target player yards
    # (gamma with a ~1e-10 shape, measured 1 in 60,000 player-worlds) and an open player's one incomplete target can
    # carry < 0.1 yards (measured 0.4%). Bounds declared from those measurements.
    check(bad <= 0.001 * n, f'zero-opportunity worlds score DK < {DK_ZERO} (exceptions {bad} of {n}: production '
                            'yard dust, bound 0.1%)')
    check(extra <= 0.01 * n, f'DK < {DK_ZERO} with a positive opportunity is rare ({extra} of {n} player-worlds, '
                             'bound 1%)')
    rb = [k for k in gates if k.startswith('RB')]
    ok = True
    for k in rb:
        g = gates[k]
        dk0 = (np.asarray(e['draws_final'][k]) < DK_ZERO).mean()
        pm = max(g.values())
        ok = ok and abs(dk0 - (1 - pm)) <= SE_MULT * math.sqrt(pm * (1 - pm) / N_E2E) + 0.002
    check(ok, 'RB DK-zero share = 1 - max(pi_carries, pi_targets) within tolerance (comonotone gate, declared)')


def test_end_to_end_on_a_real_harness_game():
    """2026 week-4 ATL@NO through the seal's own pregame harness (no outcome read): P(0) = 1 - pi on real rows."""
    if 'atl' not in _CACHE:
        po = W.PP.load_panel()
        panel, pos_of = po.value, W.PP.position_index()
        ctx, pools = W.build_context(panel, pos_of, 2026, 4)
        fr, sc, depth, groups, ir = W.fitted_objects(panel, pos_of, ctx)
        rec = W.game_record(ctx, pools, fr, sc, depth, groups, ir, _model(),
                            {'game_id': '2026_04_ATL_NO', 'home': 'NO', 'away': 'ATL', 'kickoff_utc': 'n/a'},
                            123, W.football_table(), n_sims=1500, week=4)
        _CACHE['atl'] = rec
    rec = _CACHE['atl']
    check(rec['state'] == 'SEALED' and len(rec['units']) >= 20, f'harness game built ({len(rec["units"])} units)')
    worst = max(abs(u['P0_draws_successor'] - (1 - u['pi_candidate'])) / max(1e-9, math.sqrt(
        u['pi_candidate'] * (1 - u['pi_candidate']) / 1500)) for u in rec['units'])
    inf = rec['hurdle_counts'].get('HURDLE_INFEASIBLE', 0)
    check(worst <= SE_MULT + (1 if inf else 0), f'real rows: successor zero share within tolerance of 1 - pi '
                                                 f'(worst {worst:.2f} SE; infeasible worlds {inf})')
    check(rec['volume_centre_within_tol']['successor'] and rec['volume_centre_within_tol']['current'],
          'both arms reconcile to the projection volume centre (production tolerance)')
    check(all(sum(u['hist_successor'].values()) == 1500 and sum(u['hist_current'].values()) == 1500
              for u in rec['units']), 'count histograms hold every world for both arms')


# ------------------------------------------------------------------------------------------ eligibility
def test_inactive_gets_nothing_and_pi_zero_gets_nothing():
    rows = []
    for c in ('H', 'A'):
        rows.append({'name': f'QB|{c}', 'team': c, 'position': 'QB', 'dk_points': 1.0, 'pass_attempts': 34.0,
                     'carries': 3.0, 'targets': 0.0, 'td': {'rush_td': 0.2}})
        for i, (pos, tg, ca) in enumerate((('RB', 4.0, 15.0), ('WR', 8.0, 0.5), ('WR', 6.0, 0.0), ('TE', 4.0, 0.0))):
            rows.append({'name': f'{pos}{i}|{c}', 'team': c, 'position': pos, 'dk_points': 1.0, 'targets': tg,
                         'carries': ca, 'td': {'rec_td': tg, 'rush_td': ca}})
        rows.append({'name': f'OUT|{c}', 'team': c, 'position': 'WR', 'dk_points': 1.0, 'targets': 9.0,
                     'carries': 1.0, 'td': {'rec_td': 9.0}, 'eligibility': 'INACTIVE'})
        rows.append({'name': f'UNK|{c}', 'team': c, 'position': 'TE', 'dk_points': 1.0, 'targets': 2.0,
                     'carries': 0.0, 'td': {'rec_td': 2.0}, 'eligibility': A.AV.UNKNOWN_ACTIVE_STATE})
    fc = {'total': 44.0, 'home_margin': 2.0}
    spec = A.build_spec(rows, 'H', 'A', fc)
    ids = {p['id'] for c in spec['clubs'] for p in c['players']}
    check(not any(i.startswith('OUT|') for i in ids), 'INACTIVE rows (with volume) are not in the simulator pool')
    check(sum(1 for i in ids if i.startswith('UNK|')) == 2, 'UNKNOWN_ACTIVE_STATE stays in the pool (declared: eligible)')
    centre = {c: {'pass_attempts': 34.0, 'rush_attempts': 26.0, 'targets': 32.0} for c in 'HA'}
    gates = {p['id']: ({'targets': 0.0, 'carries': 0.0} if p['id'].startswith('WR1') else {'targets': 0.9})
             for c in spec['clubs'] for p in c['players'] if p['position'] in ('WR', 'TE')}
    rbk = {p['id']: {'conditional_volume': {}} for c in spec['clubs'] for p in c['players']}
    e = A.end_to_end(_model(), spec, centre, rbk, 0.02, 800, 3, gates=gates)
    check(not any(k.startswith('OUT|') for k in e['stat_draws']) and not any(k.startswith('OUT|') for k in e['draws_final']),
          'INACTIVE players have no draws at any stage')
    z = [k for k in gates if k.startswith('WR1')]
    tot = sum(sum(w[A.SIM_IX['targets']] + w[A.SIM_IX['rec_td']] for w in e['stat_draws'][k]) for k in z)
    check(len(z) == 2 and tot == 0, 'pi = 0 never receives a target or a receiving TD in any world')
    unk = [k for k in e['stat_draws'] if k.startswith('UNK|')]
    check(len(unk) == 2 and all(any(w[A.SIM_IX['targets']] > 0 for w in e['stat_draws'][k]) for k in unk),
          'UNKNOWN_ACTIVE_STATE players are gated and do receive volume')


# ------------------------------------------------------------------------------------------------ seal
def _fake_doc(first):
    return {'ARTIFACT': 'TEST', 'season': 2026, 'week': 5, 'first_kickoff_utc': first.isoformat(), 'games': {}}


def test_seal_refuses_after_kickoff_and_overwrite():
    sched = W.newest_schedule()
    games = W.week_games(sched)
    first = min(dt.datetime.fromisoformat(g['kickoff_utc']) for g in games)
    check(first == dt.datetime(2026, 10, 9, 0, 15, tzinfo=dt.timezone.utc) and games[0]['game_id'] == '2026_05_TB_DAL',
          f'first week-5 kickoff is 2026_05_TB_DAL at 2026-10-09T00:15Z ({first.isoformat()})')
    check(_refused(lambda: W.build(now_fn=lambda: first, schedule_path=sched), 'SEAL_AFTER_KICKOFF'),
          'build refuses AT the first kickoff')
    check(_refused(lambda: W.build(now_fn=lambda: first + dt.timedelta(hours=3), schedule_path=sched),
                   'SEAL_AFTER_KICKOFF'), 'build refuses after the first kickoff')
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / 'seal.json'
        check(_refused(lambda: W.write_seal(_fake_doc(first), out=out, now_fn=lambda: first + dt.timedelta(seconds=1)),
                       'SEAL_AFTER_KICKOFF') and not out.exists(), 'write_seal refuses after kickoff and writes nothing')
        early = lambda: first - dt.timedelta(days=1)  # noqa: E731
        p, d = W.write_seal(_fake_doc(first), out=out, now_fn=early)
        check(p.exists() and stat.S_IMODE(p.stat().st_mode) == 0o444, 'a seal is written read-only (444)')
        check(d['seal_sha256'] == W.seal_hash(json.loads(p.read_text())), 'seal_sha256 recomputes from the bytes')
        check(_refused(lambda: W.write_seal(_fake_doc(first), out=out, now_fn=early), 'SEAL_EXISTS_WRITE_ONCE'),
              'a second write to the same seal path is refused (write-once)')
        os.chmod(p, 0o644)


def test_week5_seal_on_disk():
    p = W.OUT
    if not check(p.exists(), f'{p.relative_to(_REPO)} exists'):
        return
    d = json.loads(p.read_text())
    check(stat.S_IMODE(p.stat().st_mode) == 0o444, 'seal is chmod 444')
    check(d.get('seal_sha256') == W.seal_hash(d), 'seal_sha256 matches the content')
    kick = dt.datetime(2026, 10, 9, 0, 15, tzinfo=dt.timezone.utc)
    check(dt.datetime.fromisoformat(d['first_kickoff_utc']) == kick
          and dt.datetime.fromisoformat(d['written_at']) < kick,
          f'written_at {d["written_at"]} is before the first week-5 kickoff {kick.isoformat()}')
    lock = json.loads(W.PREREG_LOCK.read_text())
    core = str(A._HERE.relative_to(_REPO) / 'appearance_successor.py')
    check(d['code_sha256'].get(core) == A.sha_file(_REPO / core),
          'the core library is byte-identical to the one the seal was built with (later seals need the same code)')
    check(d['prereg']['sha256'] == lock['prereg_sha256'] == A.sha_file(W.PREREG),
          'the seal carries the locked prereg hash, and the prereg file still matches it')
    check(dt.datetime.fromisoformat(lock['locked_at']) < dt.datetime.fromisoformat(d['written_at']),
          'the prereg was locked before the seal was written')
    games = W.week_games(W.newest_schedule())
    check(set(d['games']) == {g['game_id'] for g in games}, f'every week-5 schedule game has a record ({len(games)})')
    sealed = [g for g in d['games'].values() if g['state'] == 'SEALED']
    check(d['n_games_sealed'] == len(sealed) and d['n_units'] == sum(len(g['units']) for g in sealed) > 0,
          f'{len(sealed)} games sealed, {d["n_units"]} units, {d["n_players"]} players')
    keys = ('P0_projection_current', 'P0_draws_current', 'P0_projection_candidate', 'P0_draws_successor',
            'hist_current', 'hist_successor', 'pi_candidate', 'h_last3_present')
    check(all(all(k in u for k in keys) for g in sealed for u in g['units']), 'every unit carries the four P(0)s')
    check(d['weeks_missing_from_repo'] == [4] and d['panel_2026_weeks_present'] == [1, 2, 3],
          'week 4 recorded MISSING_FROM_REPO; the pool used weeks 1-3 only')
    check(all(u['P0_projection_candidate'] == round(1 - u['pi_candidate'], 6) for g in sealed for u in g['units']),
          'candidate projection P(0) is 1 - pi')


# ----------------------------------------------------------------------------------------------- grader
def _synthetic_seal(td, written, kick, games=1, tamper=False):
    lock = json.loads(W.PREREG_LOCK.read_text())
    g = {}
    for i in range(games):
        units = []
        for j, (gs, f, y_hist) in enumerate((('P1', 'targets', {'0': 100, '3': 900}), ('P2', 'targets', {'0': 800, '1': 200}),
                                             ('P3', 'carries', {'0': 50, '10': 950}))):
            units.append({'club': 'AAA', 'gsis': gs, 'position': 'WR' if f == 'targets' else 'RB', 'field': f,
                          'rank_table': j + 1, 'h_last3_present': 3, 'P0_draws_current': y_hist.get('0', 0) / 1000,
                          'P0_draws_successor': 0.3, 'P0_projection_current': 0.4, 'P0_projection_candidate': 0.3,
                          'P_dk_zero_successor': 0.3, 'hist_current': y_hist, 'hist_successor': {'0': 300, '2': 700}})
        g[f'2026_05_AAA_BBB{i}'] = {'state': 'SEALED', 'kickoff_utc': kick.isoformat(), 'units': units}
    doc = {'season': 2026, 'week': 5, 'n_sims': 1000, 'first_kickoff_utc': kick.isoformat(), 'games': g,
           'prereg': {'sha256': lock['prereg_sha256']}, 'written_at': written.isoformat()}
    doc['seal_sha256'] = W.seal_hash(doc)
    if tamper:
        doc['games'][f'2026_05_AAA_BBB0']['units'][0]['P0_draws_successor'] = 0.01
    p = pathlib.Path(td) / f'seal_{written.timestamp():.0f}_{tamper}.json'
    p.write_text(W.canonical(doc))
    sch = pathlib.Path(td) / 'sched.csv'
    k_et = kick.astimezone(W.ET)
    sch.write_text('game_id,season,game_type,week,gameday,gametime\n' + ''.join(
        f'2026_05_AAA_BBB{i},2026,REG,5,{k_et:%Y-%m-%d},{k_et:%H:%M}\n' for i in range(games)))
    return p, sch


def test_grader_refusals_and_rules():
    kick = dt.datetime(2026, 10, 9, 0, 15, tzinfo=dt.timezone.utc)
    after = kick + dt.timedelta(days=1)
    panel = {'players': {'P1': {'2026': {'5': {'team': 'AAA', 'targets': 4}}}, 'P3': {'2026': {'5': {'team': 'AAA'}}}},
             'teams': {'AAA': {'2026': {'5': {'plays': 60}}}}}
    dressed = {('AAA', 5): {'P1', 'P3'}}
    with tempfile.TemporaryDirectory() as td:
        good, sch = _synthetic_seal(td, kick - dt.timedelta(hours=5), kick)
        res = G.grade([good], panel, dressed, sch, now=after)
        c = list(res['seals'].values())[0]['counts']
        check(c.get('GRADED') == 2 and c.get('EXCLUDED_NOT_DRESSED') == 1,
              f'undressed sealed player excluded, never scored as zero ({c})')
        check(res['VERDICT'] == 'INSUFFICIENT_SAMPLE', 'one week is INSUFFICIENT_SAMPLE: no verdict')
        check(G.T975[3] == 3.182 and G.T975[14] == 2.145 and G.MIN_WEEKS == 4 and G.MIN_UNITS == 1500,
              'grader carries the pre-registered t quantiles and minimum sample')
        p3 = 'dressed player with no stat row is y = 0 (P3 carries)'
        check(res['PRIMARY_draw_zero_brier_current_minus_successor']['n_units'] == 2, p3)
        tam, _ = _synthetic_seal(td, kick - dt.timedelta(hours=5), kick, tamper=True)
        check(_refused(lambda: G.load_seal(tam), 'SEAL_TAMPERED'), 'a modified seal is refused (SEAL_TAMPERED)')
        late, sch2 = _synthetic_seal(td, kick + dt.timedelta(minutes=1), kick)
        check(_refused(lambda: G.grade([late], panel, dressed, sch2, now=after), 'SEAL_WRITTEN_AFTER_KICKOFF'),
              'a seal written after kickoff is refused, even with a valid hash')
        check(_refused(lambda: G.grade([good], panel, dressed, sch, now=kick - dt.timedelta(hours=1)),
                       'GAME_NOT_STARTED'), 'grading before the game is refused')
        moved = pathlib.Path(td) / 'sched_moved.csv'
        k2 = (kick - dt.timedelta(hours=6)).astimezone(W.ET)
        moved.write_text('game_id,season,game_type,week,gameday,gametime\n'
                         f'2026_05_AAA_BBB0,2026,REG,5,{k2:%Y-%m-%d},{k2:%H:%M}\n')
        check(_refused(lambda: G.grade([good], panel, dressed, moved, now=after), 'SEAL_WRITTEN_AFTER_KICKOFF'),
              'a schedule kickoff earlier than written_at refuses the seal (grader re-derives kickoffs)')
        nopanel = {'players': {'P1': {}}, 'teams': {'AAA': {'2026': {}}}}
        check(_refused(lambda: G.grade([good], nopanel, dressed, sch, now=after), 'NO_GRADED_UNITS'),
              'a game missing from the postgame panel is NOT_GRADABLE, never zero (nothing graded -> refusal)')
        check(_refused(lambda: G.grade([good], {}, dressed, sch, now=after), 'EMPTY_POSTGAME_PANEL'), 'empty panel refused')
        check(_refused(lambda: G.grade([good], panel, {}, sch, now=after), 'EMPTY_SNAPS'), 'empty dressed set refused')
        bad = pathlib.Path(td) / 'empty.json'
        bad.write_text('')
        check(_refused(lambda: G.load_seal(bad), 'SEAL_EMPTY'), 'empty seal file refused')
        d = json.loads(good.read_text())
        d['prereg']['sha256'] = '0' * 64
        d['seal_sha256'] = W.seal_hash(d)
        pm = pathlib.Path(td) / 'pm.json'
        pm.write_text(W.canonical(d))
        check(_refused(lambda: G.load_seal(pm), 'PREREG_MISMATCH'), 'a seal under a different prereg is refused')


def test_real_seal_passes_the_grader_integrity_checks():
    if not W.OUT.exists():
        check(False, 'week-5 seal absent')
        return
    d = G.load_seal(W.OUT)
    check(d['week'] == 5, 'the written week-5 seal passes the grader\'s hash / prereg / clock checks')


# ---------------------------------------------------------------------------------------------- leakage
def _panel():
    if 'panel' not in _CACHE:
        _CACHE['panel'] = (W.PP.load_panel().value, W.PP.position_index())
    return _CACHE['panel']


def test_fit_has_no_2025_or_2026():
    panel, pos_of = _panel()
    fr = A.fit_field_rates(panel, pos_of, A.F1._dressed(2024))
    cut = {**panel, 'players': {g: {s: v for s, v in ss.items() if int(s) <= 2024} for g, ss in panel['players'].items()},
           'teams': {c: {s: v for s, v in ss.items() if int(s) <= 2024} for c, ss in panel['teams'].items()}}
    fr2 = A.fit_field_rates(cut, pos_of, A.F1._dressed(2024))
    check(fr['rates'] == fr2['rates'] and fr['n'] == fr2['n'], 'pi identical with 2025-2026 removed from the panel')
    fit = A.P2.fit(panel, pos_of, A.F1._dressed(2024))
    check(all(fr['rates'][(p, f, 3)] == fit['rates'][(p, f)] for p, f in A.GATED_CELLS),
          'h = 3 cells are exactly the SC-APPEAR-1 rates')
    check(_refused(lambda: A.fit_field_rates(panel, pos_of, A.F1._dressed(2024), through=2025), 'FIT_SEASON_NOT_HELD_OUT'),
          'a fit through 2025 is refused')


def test_week5_record_ignores_week5_and_later_rows():
    panel, pos_of = _panel()
    pert = copy.deepcopy(panel)
    rng = random.Random(5)
    for g, ss in pert['players'].items():
        s26 = ss.get('2026')
        if s26 and '3' in s26:
            for w in ('5', '6'):
                s26[w] = {**s26['3'], 'targets': rng.randint(0, 12), 'carries': rng.randint(0, 20),
                          'team': rng.choice(['TB', 'DAL', s26['3'].get('team')])}
    for c, ss in pert['teams'].items():
        if ss.get('2026', {}).get('3'):
            ss['2026']['5'] = {**ss['2026']['3'], 'targets': 99, 'pass_attempts': 99}
    rows = W.FP._rows()
    prow = copy.deepcopy(rows) + [{'club': c, 'season': 2026, 'week': 5, 'points': 70.0} for c in ('TB', 'DAL')]
    out = []
    for pnl, tg in ((panel, rows), (pert, prow)):
        ctx, pools = W.build_context(pnl, pos_of)
        fr, sc, depth, groups, ir = W.fitted_objects(pnl, pos_of, ctx)
        g = {'game_id': '2026_05_TB_DAL', 'home': 'DAL', 'away': 'TB', 'kickoff_utc': 'n/a'}
        rec = W.game_record(ctx, pools, fr, sc, depth, groups, ir, _model(), g, 99, W.football_table(tg), n_sims=200)
        rec.pop('seconds', None)
        out.append((pools.get('TB'), pools.get('DAL'), W.canonical(rec)))
    check(out[0][0] == out[1][0] and out[0][1] == out[1][1], 'pregame pools identical with week >= 5 rows added')
    check(out[0][2] == out[1][2], 'week-5 game record byte-identical with week >= 5 panel and points rows perturbed')
    ctx, _ = W.build_context(pert, pos_of)
    check(all(int(w) < 5 for ss in ctx['panel']['players'].values() for w in (ss.get('2026') or {})),
          'the pregame panel holds no week >= 5 row')


# ------------------------------------------------------------------------------------------ refusals
def test_named_refusals_on_empty_input():
    m = _model()
    check(_refused(lambda: A.fit_field_rates({}, {}, {'x': 1}), 'EMPTY_PANEL'), 'empty panel -> EMPTY_PANEL')
    check(_refused(lambda: A.fit_field_rates({'players': {'a': {}}}, {}, {}), 'EMPTY_DRESSED_FIT'),
          'empty dressed set -> EMPTY_DRESSED_FIT')
    check(_refused(lambda: A.build_spec([], 'H', 'A', {'total': 40, 'home_margin': 0}), 'EMPTY_ROWS'), 'no rows -> EMPTY_ROWS')
    check(_refused(lambda: A.build_spec([{'name': 'x', 'team': 'A', 'position': 'WR', 'dk_points': 1.0}], 'H', 'A',
                                        {'total': 40, 'home_margin': 0}), 'EMPTY_CLUB_POOL'), 'empty club -> EMPTY_CLUB_POOL')
    check(_refused(lambda: A.end_to_end(m, {'clubs': []}, {}, {}, 0.02, 10, 1), 'EMPTY_GAME'), 'no clubs -> EMPTY_GAME')
    spec, centre = _game()
    gates = {spec['clubs'][0]['players'][1]['id']: {'targets': 1.5}}
    check(_refused(lambda: A.end_to_end(m, spec, centre, {}, 0.02, 20, 1, gates=gates), 'GATE_PROBABILITY_OUT_OF_RANGE'),
          'pi outside [0, 1] -> GATE_PROBABILITY_OUT_OF_RANGE')
    check(_refused(lambda: A.hurdle_simulator(src='def f():\n    pass\n'), 'HURDLE_ANCHOR_NOT_FOUND'),
          'production source moved -> HURDLE_ANCHOR_NOT_FOUND')
    check(_refused(lambda: A.pi_for({'rates': {}}, 'WR', 'targets', None), 'HISTORY_UNDEFINED'),
          'no 3-game history -> HISTORY_UNDEFINED')
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / 's.csv.gz'
        import gzip
        with gzip.open(p, 'wt') as fh:
            fh.write('game_id,season,game_type,week,gameday,gametime,away_team,home_team\n')
        check(_refused(lambda: W.week_games(p), 'NO_GAMES_IN_SCHEDULE'), 'schedule without the week -> NO_GAMES_IN_SCHEDULE')
    check(_refused(lambda: G.grade([], {'players': {1: 1}, 'teams': {1: 1}}, {1: 1}, 'x'), 'SEAL_ABSENT'),
          'grader with no seal -> SEAL_ABSENT')
    check(_refused(lambda: G.load_seal('/nonexistent/seal.json'), 'SEAL_ABSENT'), 'missing seal file -> SEAL_ABSENT')


def test_production_untouched_and_no_attribute_assignment():
    import ast
    before = A.production_hashes()
    for rel in ('nfl/research/appearance/appearance_successor.py', 'nfl/prospective/appearance/seal_appearance_w5.py',
                'nfl/research/appearance/grade_appearance_seal.py', 'nfl/research/appearance/appearance_successor_dev.py'):
        tree = ast.parse((_REPO / rel).read_text())
        bad = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AugAssign)) and any(
            isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
            and t.value.id in ('SIM', 'SD', 'CR', 'V', 'FP', 'AV', 'FC', 'PP', 'S')
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
        check(not bad, f'{rel}: assigns no attribute of a production module')
    check(before == A.production_hashes(), 'production files hash the same after the suite')


def test_dev_artifact_is_labelled_development():
    p = _REPO / 'nfl/research/appearance/APPEARANCE_SUCCESSOR_DEV_2025.json'
    if not p.exists():
        check(True, 'dev artifact not yet written (nothing to label)')
        return
    d = json.loads(p.read_text())
    check(d['EVIDENCE_CLASS'].startswith('DEVELOPMENT'), 'the 2025 artifact is labelled DEVELOPMENT')
    lock = json.loads(W.PREREG_LOCK.read_text())
    check(d['prereg_sha256'] == lock['prereg_sha256'] and d['scored_at'] > lock['locked_at'],
          'the 2025 development score was computed after the prereg lock')
    import re
    hits = re.findall(r'\b(validated|unbiased|correct)\b', p.read_text(), flags=re.I)
    check(not hits, f'no unmargined adequacy words in the dev artifact {hits}')


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            print(name)
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
