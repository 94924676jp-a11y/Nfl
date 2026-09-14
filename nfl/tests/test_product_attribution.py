"""`nfl.product.attribution`: the low-projection mechanism diagnostic.

NAMING. This is `test_product_attribution.py` and not `test_attribution.py`
because that name is TAKEN, by a live test guarding the retirement of
`nfl.capture.attribution`'s post-hoc claims path (Directive 7 section 6).
Overwriting it would have deleted a guard whose whole job is to notice a
retired mechanism coming back, and "the file name I was given was already in
use" is not a reason to delete somebody else's guard.

WHAT IS ACTUALLY BEING TESTED. Three different kinds of thing, and they are
kept apart on purpose:

  *  ARITHMETIC that must close exactly -- the gap identity, and the partition
     of the zero mass. These are not opinions and are checked to 1e-9.
  *  ACCEPTANCE against the case worked by hand on 2026-09-14 -- Mahomes must
     come out ROLE_STATE and Nix must not be flagged. A method that cannot
     reproduce the case it was designed from is wrong, whatever else it does.
  *  REFUSALS -- the things the module must decline to say. Two identification
     strategies were tried and failed, and a test that lets them back in
     quietly is how a rejected method returns.

Run standalone:  python3.12 nfl/tests/test_product_attribution.py
"""
import json
import pathlib
import shutil
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import attribution as A                          # noqa: E402
from nfl.product.distributions import Forecast                    # noqa: E402
from sportsplatform.governance.outcome import State               # noqa: E402

RUN = (_REPO / 'nfl' / 'research' / 'live' / '2026_01_DEN_KC'
       / 'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8' / 'f91342d6787a66a1')

MAHOMES = '00-0033873'      # KC QB1
NIX = '00-0039732'          # DEN QB1, the on-board control
RB1 = '00-0038134'          # KC RB1
RBS = ('00-0038134', '00-0040078', '00-0041013')

PASSED = FAILED = BLOCKED = 0
_V = None


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def board():
    """The sealed run, attributed once. Read, never rebuilt."""
    global _V
    if _V is None:
        o = A.attribute_run(RUN)
        if o.state is not State.PASS:
            return None
        _V = o.unwrap()
    return _V


def metric(pid, key):
    return (board()['players'][pid]['metrics'] or {}).get(key)


# ---------------------------------------------------------------- arithmetic
def test_a_the_gap_identity_is_an_identity():
    """C - U = p0*C, and C/U = 1/(1-p0). Checked, not assumed."""
    print('\nA. the gap identity')
    v = board()
    if v is None:
        blocked('sealed run readable', f'{RUN} did not attribute')
        return
    n = 0
    worst = 0.0
    for p in v['players'].values():
        for rec in p['metrics'].values():
            g = rec.get('gap') or {}
            if g.get('conditional') is None:
                continue
            n += 1
            lhs = g['conditional'] - g['unconditional']
            rhs = g['p0'] * g['conditional']
            worst = max(worst, abs(lhs - rhs))
            if g['unconditional'] > 0:
                worst = max(worst, abs(g['gap_ratio'] - 1.0 / (1 - g['p0'])))
    check('every metric closes C - U == p0*C and C/U == 1/(1-p0)',
          n > 0 and worst < 1e-9, f'n={n} worst={worst!r}')
    check('the board carries metrics to check at all', n >= 100, f'n={n}')


def test_b_the_zero_mass_partitions_exactly():
    """The mechanism masses sum to p0 for EVERY metric, with no slack."""
    print('\nB. the partition closes')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    worst, n, negatives = 0.0, 0, []
    for pid, p in v['players'].items():
        for key, rec in p['metrics'].items():
            zm = rec.get('zero_mass')
            if not zm:
                continue
            n += 1
            worst = max(worst, abs(sum(zm['mass'].values()) - zm['p0']))
            negatives += [(pid, key, k) for k, x in zm['mass'].items()
                          if x < -1e-12]
    check('masses sum to p0 on every metric', n > 0 and worst < 1e-9,
          f'n={n} worst={worst!r}')
    check('no mechanism carries a negative mass', not negatives,
          f'{negatives[:4]}')
    check('every metric reports `closes` true',
          all(r['zero_mass']['closes'] for p in v['players'].values()
              for r in p['metrics'].values() if r.get('zero_mass')))


def test_c_contributions_sum_to_the_gap():
    """Mechanism contributions are in the metric's own units and sum to G."""
    print('\nC. contributions sum to the gap')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    worst, n = 0.0, 0
    for p in v['players'].values():
        for rec in p['metrics'].values():
            if 'contribution_to_gap' not in rec:
                continue
            n += 1
            worst = max(worst, abs(sum(rec['contribution_to_gap'].values())
                                   - rec['gap']['gap']))
    check('sum of contributions == C - U, in the metric\'s units',
          n > 0 and worst < 1e-8, f'n={n} worst={worst!r}')


# ---------------------------------------------------------------- acceptance
def test_d_mahomes_is_role_state():
    """The worked case. ROLE_STATE dominant and near the whole zero mass."""
    print('\nD. acceptance: Mahomes')
    if board() is None:
        blocked('sealed run readable', 'no attribution')
        return
    rec = metric(MAHOMES, 'qb/pyds')
    if rec is None:
        blocked('Mahomes qb/pyds present', 'metric absent from the board')
        return
    g = rec['gap']
    check('unconditional is 144.02', abs(g['unconditional'] - 144.02) < 0.01,
          g['unconditional'])
    check('P(zero) is 0.413', abs(g['p0'] - 0.413) < 0.001, g['p0'])
    check('conditional is 245.3', abs(g['conditional'] - 245.34) < 0.05,
          g['conditional'])
    check('the gap is material', rec['material'] is True)
    check('dominant mechanism is ROLE_STATE',
          rec['dominant']['mechanism'] == 'ROLE_STATE', rec['dominant'])
    check('ROLE_STATE holds ~all of the zero mass',
          rec['dominant']['share'] > 0.99, rec['dominant']['share'])
    check('ROLE_STATE carries ~all of the 101.3-yard gap',
          abs(rec['contribution_to_gap']['ROLE_STATE'] - g['gap'])
          < 0.01 * g['gap'], rec['contribution_to_gap'])
    check('a team-mate held a dropback majority in EVERY zero draw',
          rec['zero_mass']['room']['p_other_holds_majority_given_zero'] == 1.0,
          rec['zero_mass']['room'])


def test_e_nix_is_not_flagged():
    """The control. Same code, same slate, same seed, a clean room."""
    print('\nE. acceptance: Nix is not flagged')
    if board() is None:
        blocked('sealed run readable', 'no attribution')
        return
    for key in ('qb/pyds', 'qb/att', 'qb/db'):
        rec = metric(NIX, key)
        if rec is None:
            blocked(f'Nix {key} present', 'metric absent')
            continue
        check(f'{key} is NOT material', rec['material'] is False,
              rec['gap'].get('gap_ratio'))
    n = metric(NIX, 'qb/pyds')['gap']['p0']
    m = metric(MAHOMES, 'qb/pyds')['gap']['p0']
    check('the on-board control separates the two rooms by ~8x',
          m / n > 7.0, f'KC {m} against DEN {n}')
    check('the mechanism is the same for both; only the magnitude differs',
          metric(NIX, 'qb/pyds')['dominant']['mechanism'] == 'ROLE_STATE',
          'this is the point: the gate is materiality, not a different label')


def test_f_rb1_is_participation():
    """An established back who sometimes does not take the field."""
    print('\nF. acceptance: RB1 carries are PARTICIPATION')
    if board() is None:
        blocked('sealed run readable', 'no attribution')
        return
    rec = metric(RB1, 'rushing/carries')
    if rec is None:
        blocked('RB1 rushing/carries present', 'metric absent')
        return
    check('P(zero carries) is 0.150', abs(rec['gap']['p0'] - 0.150) < 0.001,
          rec['gap']['p0'])
    check('dominant mechanism is PARTICIPATION',
          rec['dominant']['mechanism'] == 'PARTICIPATION', rec['dominant'])
    check('PARTICIPATION holds most of the zero mass',
          rec['dominant']['share'] > 0.9, rec['dominant']['share'])
    check('it was IDENTIFIED, not assumed',
          rec['zero_mass']['participation_state'] == 'IDENTIFIED',
          rec['zero_mass']['participation_state'])
    check('ROLE_STATE did NOT take this zero mass',
          rec['zero_mass']['mass'].get('ROLE_STATE', 0.0) < 0.01,
          'displacement is entailed by absence and must not be read as a '
          'competing role contest')


def test_g_the_dual_room_estimator_is_bounded_and_falsifiable():
    """a must lie in [0, min(p_a,p_b)]. It could fail here. It does not."""
    print('\nG. the dual-room estimator')
    fc = Forecast(RUN)
    n = 0
    for pid in RBS:
        c = fc.vector('rushing', 'carries', pid)
        t = fc.vector('receiving', 'targets', pid)
        if c is None or t is None:
            continue
        n += 1
        pa, pb = float((c == 0).mean()), float((t == 0).mean())
        pj = float(((c == 0) & (t == 0)).mean())
        r = A.participation_mass(pa, pb, pj)
        check(f'{pid}: identified', r['state'] == 'IDENTIFIED', r)
        if r['state'] == 'IDENTIFIED':
            check(f'{pid}: 0 <= a <= min(p_a,p_b)',
                  0.0 <= r['estimate'] <= min(pa, pb) + 1e-12,
                  (r['estimate'], pa, pb))
            # The closed form must reproduce the system it solves.
            a = r['estimate']
            u = (pa - a) / (1 - a)
            vv = (pb - a) / (1 - a)
            check(f'{pid}: recovers p_joint = a + (1-a)uv',
                  abs(a + (1 - a) * u * vv - pj) < 1e-9,
                  (a, u, vv, pj))
    check('all three backs were reachable', n == 3, n)


def test_h_the_two_rejected_identifications_stay_rejected():
    """Both were tried on this board and both fail. Keep them failing."""
    print('\nH. rejected identification strategies')
    fc = Forecast(RUN)
    tt = fc.team_vector('team_targets', 'KC')
    # (1) VOLUME-LIMIT. If thinness vanished with volume, p0 would fall
    #     across terciles. It does not, because the allocator draws a SHARE.
    wr6 = fc.vector('receiving', 'targets', '00-0038519')
    if wr6 is None or tt is None:
        blocked('WR6 targets and team targets present', 'vectors absent')
    else:
        q = np.quantile(tt, [1 / 3, 2 / 3])
        band = np.digitize(tt, q)
        p0s = [float((wr6[band == k] == 0).mean()) for k in range(3)]
        check('p0 does not fall across team-volume terciles, so the '
              'volume-limit estimator is not available',
              abs(p0s[0] - p0s[2]) < 0.05, p0s)
    # (2) BINOMIAL THINNESS BOUND. It would claim RB2 is absent in >=16% of
    #     draws; the identified value is under 1%. The bound is refuted
    #     because a p4c share can be exactly zero.
    c = fc.vector('rushing', 'carries', '00-0041013')
    t = fc.vector('receiving', 'targets', '00-0041013')
    if c is None or t is None:
        blocked('RB2 vectors present', 'vectors absent')
        return
    est = A.participation_mass(float((c == 0).mean()), float((t == 0).mean()),
                              float(((c == 0) & (t == 0)).mean()))
    check('RB2 identified participation mass is under 2%',
          est['state'] == 'IDENTIFIED' and est['estimate'] < 0.02, est)
    room = np.asarray([fc.vector('rushing', 'carries', g) for g in RBS], float)
    tot = room.sum(axis=0)
    pres = c > 0
    share = float((c[pres] / np.maximum(tot[pres], 1e-9)).mean())
    budget = float(tot.mean())
    binom_bound = float((1 - share) ** budget)
    check('the binomial bound would claim >= 16% and is therefore refuted',
          float((c == 0).mean()) - binom_bound > 0.16,
          f'p0={float((c == 0).mean())} bound_term={binom_bound}')


# ----------------------------------------------------------------- refusals
def test_i_unmodelled_mechanisms_carry_none_not_zero():
    """A measured zero and an absent layer are different facts."""
    print('\nI. mechanisms with no layer')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    nm = v['not_modelled']
    for k in ('GAME_STATE', 'INJURY_LIMITATION'):
        check(f'{k} is declared not modelled', k in nm and bool(nm[k]), nm)
        check(f'{k} is in the vocabulary', k in A.MECHANISMS)
        check(f'{k} never receives mass',
              all(k not in (r['zero_mass']['mass'] if r.get('zero_mass')
                            else {})
                  for p in v['players'].values()
                  for r in p['metrics'].values()))
    check('residual has its own named bucket instead',
          'OTHER_RESIDUAL' in A.ZERO_MECHANISMS)


def test_j_a_quarterback_zero_is_never_participation():
    """No quarterback has an appearance draw, so the channel does not exist."""
    print('\nJ. the channel map')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    qb = [(pid, k, r) for pid, p in v['players'].items()
          for k, r in p['metrics'].items()
          if k.startswith('qb/') and r.get('zero_mass')]
    check('there are quarterback metrics to check', len(qb) >= 30, len(qb))
    check('no quarterback metric is attributed PARTICIPATION',
          all(r['zero_mass']['mass'].get('PARTICIPATION', 0.0) == 0.0
              for _p, _k, r in qb))
    check('and each says WHY, rather than being silently absent',
          all(r['zero_mass']['participation_state']
              == 'NOT_MODELLED_FOR_THIS_LAYER' for _p, _k, r in qb))
    check('the qb layer is declared rivalrous and the receiving layer is not',
          A.LAYER_CHANNELS['qb-v1-aggregate-then-allocate-1']['rivalrous_room']
          and not A.LAYER_CHANNELS['nfl-nonqb-receiving-1']['rivalrous_room'])


def test_k_an_unmapped_engine_version_is_refused():
    """Which mechanisms can fire is a fact about the engine version."""
    print('\nK. an unmapped layer spec is refused, not guessed')
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td) / 'run'
        shutil.copytree(RUN, d)
        man = json.loads((d / 'player_draws_manifest.json').read_text())
        man['layers']['qb']['spec_version'] = 'qb-v9-something-nobody-mapped'
        (d / 'player_draws_manifest.json').write_text(json.dumps(man))
        o = A.attribute_run(d)
    check('state is BLOCKED', o.state is State.BLOCKED, o.state)
    check('code names the problem', o.code == 'LAYER_SPEC_UNKNOWN', o.code)
    check('a cause is declared', o.evidence.get('cause') == 'GOVERNANCE',
          o.evidence.get('cause'))


def test_l_a_missing_run_blocks_with_a_cause():
    print('\nL. an unreadable run')
    o = A.attribute_run(_REPO / 'nfl' / 'research' / 'live' / 'no_such_run')
    check('state is BLOCKED', o.state is State.BLOCKED, o.state)
    check('code is SEALED_RUN_UNREADABLE', o.code == 'SEALED_RUN_UNREADABLE',
          o.code)
    check('a cause is declared', o.evidence.get('cause') == 'DATA',
          o.evidence.get('cause'))


def test_m_rows_are_addressed_by_gsis_id():
    """The artifact's draws_ref and the manifest's row_ids must agree.

    If they ever disagree, every number above belongs to the wrong player and
    nothing else in this file means anything. Positional reads are how that
    happens, so the agreement is asserted rather than trusted.
    """
    print('\nM. row addressing')
    fc = Forecast(RUN)
    man = fc.manifest['layers']
    n = 0
    for layer, blk in man.items():
        if layer == 'team_volume':
            continue
        ids = blk['row_ids']
        for key in blk['metrics']:
            arr = fc.arrays.get(f'{layer}__{key}')
            if arr is None:
                continue
            for i, pid in enumerate(ids):
                ref = fc.row_index(layer, key, pid)
                if ref is None:
                    continue
                n += 1
                if ref != i:
                    check(f'{layer}/{key} row for {pid}', False,
                          f'draws_ref says {ref}, manifest says {i}')
                    return
    check('artifact draws_ref agrees with manifest row_ids everywhere', n > 0,
          f'n={n}')
    check('enough rows were compared to mean something', n >= 100, n)


def test_n_the_role_prior_screen_reports_without_claiming():
    """D4's mechanism gets a screen and an explicit non-claim."""
    print('\nN. the ROLE_PRIOR screen')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    sc = v['role_prior_screen']
    check('screens exist for the non-rivalrous rooms', len(sc) >= 3, len(sc))
    check('no screen is built for the quarterback room, which is ROLE_STATE\'s',
          not any('|QB|' in k for k in sc), list(sc))
    ok = [r for r in sc.values() if r.get('state') == 'OK']
    check('every screen states what it cannot say',
          all(r.get('what_it_cannot_say') for r in ok))
    check('severity is one of the three declared values',
          all(r['severity'] in ('SEVERE_SIGNATURE_PRESENT',
                                'MILD_ADJACENT_INVERSIONS',
                                'CHART_AND_MODEL_AGREE') for r in ok))
    inv = sum(r.get('n_inversions', 0) for r in ok)
    check('the screen actually ran on this board and found its inversions',
          inv >= 1, inv)
    check('any swap-equivalent delta is labelled as a restatement',
          all(mm['swap_equivalent']['basis'].startswith('arithmetic')
              for r in ok for mm in r['members'] if 'swap_equivalent' in mm))
    check('the missing label is named rather than stretched onto an old one',
          v['taxonomy_gap']['missing_label'] == 'ROLE_PRIOR'
          and 'ROLE_PRIOR' not in A.MECHANISMS,
          v['taxonomy_gap']['missing_label'])


def test_o_the_participation_caveat_travels_with_the_number():
    print('\nO. the appearance-level caveat')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    cav = v['participation_caveat']
    check('the caveat is carried on the run', bool(cav) and len(cav) > 200)
    check('it names the boundary inversion', '0.2778' in cav and '0.5079' in cav)
    check('it does not claim to correct anything',
          'changes nothing' in cav, cav[-80:])


def test_p_structurally_absent_rows_get_eligibility_and_no_arithmetic():
    print('\nP. rows with no draws at all')
    v = board()
    if v is None:
        blocked('sealed run readable', 'no attribution')
        return
    sa = v['structurally_absent']
    check('the mechanism is ELIGIBILITY', sa['mechanism'] == 'ELIGIBILITY')
    check('there are absent rows on this board', sa['n_absent'] > 0,
          sa['n_absent'])
    check('no gap arithmetic is invented for them',
          sa['gap_arithmetic'].startswith('NONE'))
    check('the per-row limitation is stated',
          'UNATTRIBUTABLE' in sa['limitation'].upper()
          or 'cannot say which' in sa['limitation'], sa['limitation'][:80])
    check('DEN is recorded as the deferred team',
          'DEN' in (v['deferred_teams'] or []), v['deferred_teams'])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and name != 'test_zz_every_check_passed':
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    sys.exit(1 if FAILED else 0)
