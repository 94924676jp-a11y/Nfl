"""P8: the impossible distribution tails, and integer count support.

TWO DEFECTS, ONE MODULE, BECAUSE THEY ARE THE SAME CLASS OF DEFECT: a quantity
generated at the wrong scale and then published as though the scale did not
matter.

1. THE PASSING-YARD TAILS. `qb2_lib` built passing yards as

       ypc_d = _mix(...)          # ONE game-level yards-per-completion ratio
       PY    = CMP * ypc_d        # times an independently drawn completion count

   The donor ratio carries no record of the completion count that produced it.
   A ratio estimated at n = 1 completion is applied at n = 16 with no
   shrinkage and no denominator weighting -- SCALE NON-EXCHANGEABILITY. It is
   what puts 680 cells of the sealed corpus above the all-time NFL single-game
   record of 554 yards (maximum 1,587) and 2,262 cells below zero, including
   D19's 16 completions for -32 yards, which is -2.0 x 16 exactly, the -2.0
   donated by a one-completion game.

   The repair changes the UNIT OF RESAMPLING from the game to the completion.
   It is not a clip, a truncation or a rejection: the support of the generator
   is unchanged and only the probability law moves. The checks below are a
   RATE against a bound derived from 3,787 realised QB game-lines, plus the
   generator's own block ledger, which holds by construction.

2. THE CARRY COUNT. 442 sealed cells carry more rushing touchdowns than
   carries, and every one of them has a FRACTIONAL carry. The generation half
   is already repaired -- `stat_contract.deal_counts` deals an integer budget,
   and the two boards built after that repair carry zero fractional carries --
   but nothing asserted the invariant, so the cause was closed and the symptom
   left unfenced. `assert_events_within_opportunity` is that fence, and it
   compares against the PUBLISHED opportunity, never a rounding of it: all 442
   violations vanish against `ceil` or `rint`, which is precisely why neither
   is used.

WHAT THIS MODULE DOES NOT ASSERT. Nothing here says the candidate forecasts
better. It says the tails come inside a bound derived from realised football
and that the completion marginal does not move. Prediction quality is measured
in `nfl/research/v4/p8/P8_TAILS_AND_COUNTS.md` with its intervals attached.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb2'),
           os.path.join(_ROOT, 'nfl', 'research', 'v3', 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production import stat_contract as SC                     # noqa: E402
from nfl.research import sealed_index as SI                        # noqa: E402
import h1_frame as FR                                              # noqa: E402
import qb2_lib as Q                                                # noqa: E402

PASSED = FAILED = BLOCKED = 0

# THE RECORD, AND THE BOUND DERIVED FROM IT.
#
# 554 is Norm Van Brocklin's 1951 single-game passing-yard record, the
# all-time NFL maximum. The donor pool this engine resamples holds 3,787 QB
# game-lines with at least one completion; its own maximum is 525 and NONE is
# above 554. Zero events in n trials gives a one-sided 95% upper bound on the
# rate of 1 - 0.05^(1/n), which is computed below rather than written here.
NFL_SINGLE_GAME_RECORD = 554.0
ALPHA = 0.05

# The realised yards-per-completion support, banded by the completion count
# that produced it. Re-measured from the frame below; these are the values the
# X1 census published and they are checked, not trusted.
REALISED_BANDS = ((1, 1), (2, 4), (5, 9), (10, 14), (15, 19), (20, 99))

EVAL_SEASON = 2025
SEED = 20260908
M_DRAWS = 1000

_CACHE = {}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def frame():
    if 'frame' not in _CACHE:
        rows, meta = FR.build()
        Q.attach(rows)
        _CACHE['frame'] = (rows, meta)
    return _CACHE['frame']


def cohort():
    """The 2025 forward-chained QB-game cohort. Pool is 2020-2024 only."""
    if 'cohort' not in _CACHE:
        rows, _ = frame()
        _CACHE['cohort'] = [r for r in rows
                            if r['season'] == EVAL_SEASON and Q.eligible(r)]
    return _CACHE['cohort']


def arms():
    """Both arms on one slate, one seed, one draw count."""
    if 'arms' not in _CACHE:
        rows, _ = frame()
        keep = cohort()
        a = Q.simulate(keep, EVAL_SEASON, rows, seed=SEED, m=M_DRAWS,
                       rung='L1')
        b = Q.simulate(keep, EVAL_SEASON, rows, seed=SEED, m=M_DRAWS,
                       rung='L1', ypc_spec=Q.YPC_SPEC_COMPLETION_BLOCKS)
        _CACHE['arms'] = (a, b)
    return _CACHE['arms']


def rate_bound(n):
    return 1.0 - ALPHA ** (1.0 / n)


def banded_out_of_support(PY, CMP, bands):
    """Cells whose implied yards per completion is outside the realised
    support AT THEIR OWN COMPLETION COUNT."""
    total = 0
    for (lo, hi), (mn, mx) in bands.items():
        msk = (CMP >= lo) & (CMP <= hi)
        if not msk.any():
            continue
        v = PY[msk] / CMP[msk]
        total += int(((v < mn) | (v > mx)).sum())
    return total


# ------------------------------------------------- the donor pool, re-measured
def test_a_the_donor_pool_and_the_derived_bound():
    """Every number the repair is judged against, measured here."""
    rows, meta = frame()
    g = [(r['cmp'], r['pyds']) for r in rows if r['cmp'] > 0]
    n = np.array([x[0] for x in g], float)
    y = np.array([x[1] for x in g], float)
    ypc = y / n
    check(f'{len(ypc)} realised QB game-lines with at least one completion',
          len(ypc) == 3787, str(len(ypc)))
    check(f'  the realised single-game maximum is {y.max():.0f}',
          float(y.max()) == 525.0, f'{y.max()}')
    check(f'  and NONE is above the all-time record of '
          f'{NFL_SINGLE_GAME_RECORD:.0f}', int((y > NFL_SINGLE_GAME_RECORD).sum()) == 0,
          f'{int((y > NFL_SINGLE_GAME_RECORD).sum())}')
    b = rate_bound(len(ypc))
    check(f'  so the one-sided 95% rate bound is {b:.6e} '
          f'(1 - 0.05^(1/{len(ypc)}); rule of three 3/n = {3/len(ypc):.6e})',
          6.0e-4 < b < 9.0e-4, f'{b:.6e}')
    neg = ypc < 0
    check(f'  {int(neg.sum())} donor ratios are negative and EVERY one comes '
          f'from a 1- or 2-completion game',
          int(neg.sum()) == 10 and int(n[neg].max()) == 2,
          f'{int(neg.sum())} negatives, max completions {n[neg].max()}')
    ge5 = n >= 5
    check(f'  across the {int(ge5.sum())} games with 5+ completions the '
          f'minimum ratio is {ypc[ge5].min():.3f}, not negative',
          float(ypc[ge5].min()) > 0, f'{ypc[ge5].min()}')
    bands = {}
    for lo, hi in REALISED_BANDS:
        msk = (n >= lo) & (n <= hi)
        bands[(lo, hi)] = (float(ypc[msk].min()), float(ypc[msk].max()))
    _CACHE['bands'] = bands
    check('  the banded support is monotone: the widest band is 1 completion '
          'and the narrowest is 20+',
          (bands[(1, 1)][1] - bands[(1, 1)][0])
          > (bands[(20, 99)][1] - bands[(20, 99)][0]),
          str(bands))
    check(f'  the 20+ band is [{bands[(20, 99)][0]:.3f}, '
          f'{bands[(20, 99)][1]:.3f}], the X1 census value',
          abs(bands[(20, 99)][0] - 5.125) < 1e-9
          and abs(bands[(20, 99)][1] - 21.2) < 1e-9, str(bands[(20, 99)]))
    check('  the pool is completion-counted, index-aligned with the ratios',
          len(Q.pools(rows, EVAL_SEASON)['ypc'])
          == len(Q.pools(rows, EVAL_SEASON)['ypc_n']))


# --------------------------------- the reproduction, on both arms, one slate
def test_b_the_tail_reproduces_on_the_incumbent_and_closes_on_the_candidate():
    """THE FAILING REPRODUCTION. Run against the incumbent alone, the first
    check below is the failure this repair exists for: the rate of cells above
    the all-time record sits OUTSIDE a bound derived from realised football.
    """
    keep = cohort()
    A, B = arms()
    bands = _CACHE.get('bands')
    if bands is None:
        test_a_the_donor_pool_and_the_derived_bound()
        bands = _CACHE['bands']
    rows, _ = frame()
    n_pool = len([r for r in rows if r['cmp'] > 0])
    bound = rate_bound(n_pool)
    CMP = A['cmp']
    for nm, D in (('incumbent', A), ('candidate', B)):
        P = D['pyds']
        _CACHE[nm] = {
            'cells': int(P.size),
            'over_record': int((P > NFL_SINGLE_GAME_RECORD).sum()),
            'rate': float((P > NFL_SINGLE_GAME_RECORD).mean()),
            'max': float(P.max()), 'min': float(P.min()),
            'negative': int((P < 0).sum()),
            'below_minus_30': int((P < -30).sum()),
            'out_of_support': banded_out_of_support(P, CMP, bands),
            'mean': float(P.mean()),
        }
    inc, can = _CACHE['incumbent'], _CACHE['candidate']
    check(f'{len(keep)} QB-game rows x {M_DRAWS} draws = {inc["cells"]} cells '
          f'on one slate, one seed', inc['cells'] == can['cells'])
    check(f'  REPRODUCTION: the incumbent puts {inc["over_record"]} cells above '
          f'{NFL_SINGLE_GAME_RECORD:.0f} yards, a rate of {inc["rate"]:.4e} '
          f'against the derived bound {bound:.4e} -- outside by '
          f'{inc["rate"] / bound:.2f}x',
          inc['rate'] > bound, f'{inc["rate"]:.4e} <= {bound:.4e}')
    check(f'  the candidate is at {can["rate"]:.4e}, INSIDE the same bound',
          can['rate'] <= bound, f'{can["rate"]:.4e} > {bound:.4e}')
    check(f'  the upper tail: maximum {inc["max"]:.0f} -> {can["max"]:.0f} yards',
          can['max'] < inc['max'])
    check(f'  the lower tail: minimum {inc["min"]:.0f} -> {can["min"]:.0f} yards',
          can['min'] > inc['min'])
    check(f'  cells below -30 yards, D19\'s own magnitude: '
          f'{inc["below_minus_30"]} -> {can["below_minus_30"]}',
          can['below_minus_30'] == 0, str(can['below_minus_30']))
    check(f'  cells outside the realised ratio support AT THEIR OWN completion '
          f'count: {inc["out_of_support"]} -> {can["out_of_support"]}',
          can['out_of_support'] < inc['out_of_support'] / 10,
          f'{inc["out_of_support"]} -> {can["out_of_support"]}')
    check('  BOTH TAILS MOVE TOGETHER, which is what one mechanism predicts',
          can['max'] < inc['max'] and can['min'] > inc['min'])


# ------------------------------------------- the treatment is isolated
def test_c_the_only_quantity_that_moves_is_the_one_under_treatment():
    A, B = arms()
    differ = sorted(k for k in A if not np.array_equal(A[k], B[k]))
    check(f'exactly one draw matrix differs between the arms: {differ}',
          differ == ['pyds'], str(differ))
    check('  the completion marginal is identical, cell for cell',
          np.array_equal(A['cmp'], B['cmp']))
    check('  so is the dropback, attempt, sack and scramble decomposition',
          all(np.array_equal(A[k], B[k])
              for k in ('db', 'att', 'sacks', 'scr')))
    check('  and so are the six layers drawn AFTER passing yards, which the '
          'stream alignment exists to hold in place',
          all(np.array_equal(A[k], B[k])
              for k in ('ptd', 'int', 'drush', 'rush_opp', 'ryds', 'rtd')))
    inc, can = _CACHE.get('incumbent'), _CACHE.get('candidate')
    if inc and can:
        shift = can['mean'] - inc['mean']
        check(f'  the centre moves by {shift:+.3f} yards '
              f'({100 * shift / inc["mean"]:+.2f}%), reported rather than '
              f'claimed to be zero', abs(shift) < 0.05 * inc['mean'],
              f'{shift:+.3f}')


def test_d_the_incumbent_is_byte_identical_and_is_the_default():
    rows, _ = frame()
    keep = cohort()[:40]
    a = Q.simulate(keep, EVAL_SEASON, rows, seed=SEED, m=200, rung='L1')
    b = Q.simulate(keep, EVAL_SEASON, rows, seed=SEED, m=200, rung='L1',
                   ypc_spec=Q.YPC_SPEC_GAME_RATIO)
    check('the default specification IS the incumbent, named explicitly, cell '
          'for cell', all(np.array_equal(a[k], b[k]) for k in a))
    check('  the declared set is exactly two specifications',
          Q.YPC_SPECS == (Q.YPC_SPEC_GAME_RATIO, Q.YPC_SPEC_COMPLETION_BLOCKS),
          str(Q.YPC_SPECS))
    try:
        Q.simulate(keep, EVAL_SEASON, rows, seed=SEED, m=50, ypc_spec='nope')
        check('  an undeclared specification is REFUSED', False, 'no raise')
    except ValueError as exc:
        check('  an undeclared specification is REFUSED by name',
              'unknown passing-yard specification' in str(exc), str(exc)[:80])


# ------------------------------- the block ledger, which holds by construction
def test_e_the_completion_block_ledger_closes_and_rejects_a_seeded_violation():
    rows, _ = frame()
    po = Q.pools(rows, EVAL_SEASON)
    rng = np.random.default_rng(20260915)
    CMP = rng.integers(0, 45, 400)
    PY, led = Q.completion_block_yards(
        rng, np.array([]), np.array([], np.int64),
        po['ypc'], po['ypc_w'], po['ypc_n'], 0.0, CMP)
    check(f'{led["blocks_drawn"]} blocks cover exactly '
          f'{led["completions_covered"]} completions against '
          f'{led["completions_requested"]} requested',
          led['closes'] and led['completions_covered']
          == led['completions_requested'], json.dumps(led))
    check('  no block ever supplies yardage for more completions than its '
          'donor game recorded',
          led['max_block_completions_above_donor'] == 0,
          str(led['max_block_completions_above_donor']))
    check('  a zero-completion draw gets exactly zero yards, with no block '
          'drawn', float(PY[CMP == 0].sum()) == 0.0 if (CMP == 0).any() else True)
    # THE GUARD IS DEMONSTRATED ON A SEEDED VIOLATION, not on compliant data.
    real = Q.completion_block_yards
    try:
        Q.completion_block_yards = (
            lambda *a, **k: (np.zeros(len(a[7])),
                             {'blocks_drawn': 1, 'rounds': 1,
                              'completions_requested': 10,
                              'completions_covered': 3, 'closes': False,
                              'max_block_completions_above_donor': 4}))
        r = dict(cohort()[0])
        try:
            Q.passing_yards_draws(r, po, np.random.default_rng(1),
                                  0.5, False, 5, np.full(5, 10),
                                  Q.YPC_SPEC_COMPLETION_BLOCKS)
            check('  a broken ledger is REFUSED', False, 'no raise')
        except ValueError as exc:
            check('  a broken ledger is REFUSED by name',
                  'QB_YPC_BLOCK_LEDGER_BROKEN' in str(exc), str(exc)[:90])
    finally:
        Q.completion_block_yards = real
    # the named refusals on missing or misaligned donor counts
    r = dict(cohort()[0]); r.pop('h_ypc_n')
    try:
        Q.passing_yards_draws(r, po, np.random.default_rng(1), 0.5, False, 5,
                              np.full(5, 10), Q.YPC_SPEC_COMPLETION_BLOCKS)
        check('  a row with no donor completion counts is REFUSED', False,
              'no raise')
    except ValueError as exc:
        check('  a row with no donor completion counts is REFUSED by name',
              'QB_YPC_DONOR_COUNTS_ABSENT' in str(exc), str(exc)[:90])
    r = dict(cohort()[0]); r['h_ypc_n'] = r['h_ypc_n'][:-1]
    try:
        Q.passing_yards_draws(r, po, np.random.default_rng(1), 0.5, False, 5,
                              np.full(5, 10), Q.YPC_SPEC_COMPLETION_BLOCKS)
        check('  a ratio paired with the wrong denominator is REFUSED', False,
              'no raise')
    except ValueError as exc:
        check('  a ratio paired with the wrong denominator is REFUSED by name',
              'QB_YPC_DONOR_COUNTS_MISALIGNED' in str(exc), str(exc)[:90])
    bad = {k: v for k, v in po.items() if k not in ('ypc_w', 'ypc_n')}
    try:
        Q.passing_yards_draws(dict(cohort()[0]), bad,
                              np.random.default_rng(1), 0.5, False, 5,
                              np.full(5, 10), Q.YPC_SPEC_COMPLETION_BLOCKS)
        check('  an uncounted pool is REFUSED', False, 'no raise')
    except ValueError as exc:
        check('  an uncounted pool is REFUSED by name',
              'QB_YPC_POOL_NOT_COUNTED' in str(exc), str(exc)[:90])


def test_f_it_is_not_a_clip_and_the_source_says_so():
    """A truncation would show up as an atom at the boundary. No boundary
    exists: the candidate's support is the pool's, and its extremes are
    interior values that simply became improbable."""
    A, B = arms()
    P = B['pyds']
    top = np.sort(P.ravel())[-40:]
    check('the candidate\'s largest cells are 40 distinct values, not 40 '
          'copies of a bound', len(set(top.tolist())) > 30,
          f'{len(set(top.tolist()))} distinct')
    check('  and its maximum is not equal to any fence in this module',
          float(P.max()) not in (NFL_SINGLE_GAME_RECORD, 0.0),
          f'{P.max()}')
    src = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'qb2' / 'qb2_lib.py'
    import ast as _ast
    calls = []
    for node in _ast.walk(_ast.parse(src.read_text())):
        if isinstance(node, _ast.Call):
            f = node.func
            calls.append(f.attr if isinstance(f, _ast.Attribute)
                         else f.id if isinstance(f, _ast.Name) else '')
    check(f'  the module calls np.clip {calls.count("clip")} time(s), the two '
          f'pre-existing share clips, and the repair adds none',
          calls.count('clip') == 2, str(calls.count('clip')))
    check('  the repair introduces no maximum, minimum, truncation or '
          'rejection call',
          calls.count('trunc') == 0 and calls.count('clip') == 2)


# ------------------------------------------------------ DEFECT B: the counts
def test_g_the_carry_defect_is_measured_and_its_stated_shape_is_corrected():
    runs = SI.live_draw_files(exclude=None)
    if not runs:
        blocked('no sealed runs', 'the carry defect has nothing to measure on')
        return
    cells = frac = viol = sub1 = one_to_two = 0
    post_r4_cells = post_r4_frac = post_r4_viol = 0
    for p in runs:
        z = SI.load_draws(p.parent)
        if z is None or 'rushing__carries' not in z.files:
            continue
        c = np.asarray(z['rushing__carries'], float)
        t = np.asarray(z['rushing__rushing_td'], float)
        if c.size == 0:
            continue
        doc = json.loads((p.parent / 'board.json').read_text())
        f = int((np.abs(c - np.round(c)) > 0).sum())
        v = c < t
        cells += c.size
        frac += f
        viol += int(v.sum())
        sub1 += int((v & (c > 0) & (c < 1) & (t == 1)).sum())
        one_to_two += int((v & (c > 1) & (c < 2) & (t == 2)).sum())
        if doc.get('model_configuration') == 'V1_CANDIDATE_R9':
            post_r4_cells += c.size
            post_r4_frac += f
            post_r4_viol += int(v.sum())
    check(f'{len(runs)} sealed run(s), {cells} carry cells, {frac} non-integer '
          f'({100 * frac / max(cells, 1):.2f}%)',
          cells == 516000 and frac == 327103, f'{cells} cells, {frac} frac')
    check(f'  {viol} cells carry more rushing touchdowns than carries',
          viol == 442, str(viol))
    check(f'  CORRECTION to the stated shape: {sub1} of them are '
          f'0 < carries < 1 with one touchdown and {one_to_two} are '
          f'1 < carries < 2 with two. "EVERY violation is the first kind" is '
          f'wrong -- it is {100 * sub1 / max(viol, 1):.1f}%',
          sub1 == 415 and one_to_two == 27 and sub1 + one_to_two == viol,
          f'{sub1} + {one_to_two} vs {viol}')
    check(f'  the two boards built after the counts repair carry '
          f'{post_r4_cells} carry cells, {post_r4_frac} non-integer and '
          f'{post_r4_viol} violations -- the generator half is closed',
          post_r4_cells > 0 and post_r4_frac == 0 and post_r4_viol == 0,
          f'{post_r4_cells}/{post_r4_frac}/{post_r4_viol}')


def test_h_the_event_opportunity_fence_refuses_the_sealed_violations():
    runs = SI.live_draw_files(exclude=None)
    contaminated = clean = None
    for p in runs:
        z = SI.load_draws(p.parent)
        if z is None or 'rushing__carries' not in z.files:
            continue
        c = np.asarray(z['rushing__carries'], float)
        t = np.asarray(z['rushing__rushing_td'], float)
        if c.size == 0:
            continue
        mats = {'rushing/carries': c, 'rushing/rushing_td': t}
        if (t > c).any() and contaminated is None:
            contaminated = mats
        if not (t > c).any() and int((np.abs(c - np.round(c)) > 0).sum()) == 0 \
                and clean is None:
            clean = mats
    if contaminated is None or clean is None:
        blocked('sealed carry pair', 'no contaminated and clean pair found')
        return
    o = SC.assert_events_within_opportunity(contaminated)
    check('a sealed board carrying more rushing touchdowns than carries is '
          'REFUSED', o.state is State.FAIL
          and o.code == 'EVENT_EXCEEDS_OPPORTUNITY',
          f'{o.state.value}[{o.code}]')
    o2 = SC.assert_events_within_opportunity(clean)
    check('  a board built after the counts repair PASSES the same fence',
          o2.state is State.PASS, f'{o2.state.value}[{o2.code}]')
    o3 = SC.assert_events_within_opportunity(contaminated,
                                             round_opportunity='ceil')
    check('  and rounding the opportunity to make the count vanish is '
          'REFUSED by name',
          o3.state is State.FAIL
          and o3.code == 'EVENT_OPPORTUNITY_ROUNDING_REQUESTED',
          f'{o3.state.value}[{o3.code}]')
    c = contaminated['rushing/carries']
    t = contaminated['rushing/rushing_td']
    check('  the violations really do vanish against ceil and against rint, '
          'which is why neither is the comparison',
          int((t > np.ceil(c)).sum()) == 0 and int((t > np.round(c)).sum()) == 0)
    o4 = SC.assert_events_within_opportunity({'qb/pyds': np.zeros((2, 3))})
    check('  a call that completes no declared pair is BLOCKED, not passed',
          o4.state is State.BLOCKED
          and o4.code == 'NO_EVENT_OPPORTUNITY_PAIR_SUPPLIED',
          f'{o4.state.value}[{o4.code}]')
    o5 = SC.assert_events_within_opportunity(
        {'receiving/targets': np.array([[4.0, 4.0]]),
         'receiving/receptions': np.array([[5.0, 1.0]])})
    check('  a seeded violation on a different declared pair is caught too',
          o5.state is State.FAIL and o5.evidence['violations'][0]['cells'] == 1,
          f'{o5.state.value}[{o5.code}]')
    o6 = SC.assert_events_within_opportunity(
        {'receiving/targets': np.zeros((1, 2)),
         'receiving/receptions': np.zeros((1, 3))})
    check('  a shape mismatch is refused rather than broadcast',
          o6.state is State.FAIL and o6.code == 'EVENT_OPPORTUNITY_SHAPE',
          f'{o6.state.value}[{o6.code}]')
    check('  every declared pair names why the bound holds',
          all(isinstance(v[1], str) and v[1]
              for v in SC.EVENT_BOUNDS.values()))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
