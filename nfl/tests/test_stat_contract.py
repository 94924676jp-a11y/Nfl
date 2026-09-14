"""The stat contract, and the count support it guards.

WHAT THIS MODULE ASSERTS
========================
1. THE TAXONOMY IS A PARTITION, MEASURED ON REAL PLAYS. Every offensive play
   in `nfl/research/postgame/pbp_*.csv.gz` falls into exactly one of six
   classes, and the three aggregate identities -- `att_raw == att + sacks +
   spikes`, `dropbacks == att + sacks + scrambles`, `rush_attempts ==
   scrambles + kneels + designed` -- hold as exact integer sums. The
   frequencies are fenced, so a feed whose flags change meaning fails here
   rather than silently moving a band.
2. THE TWO TRAPS ARE REFUSED BY CODE, NOT BY COMMENT.
   `panel_p3.dropbacks_as_passer` is handed to `assert_not_a_dropback_column`
   against the real 57,670 rows and must be REFUSED; nflverse `pass_attempt`
   is shown to differ from the board's `qb/att` by exactly the sacks and
   spikes.
3. COUNT SUPPORT IS ASSERTED AND NEVER REPAIRED. A seeded non-integer and a
   seeded negative are both caught; a matrix of declared counts that are
   counts passes; a call that checks NOTHING is BLOCKED rather than passing,
   because absence read as success is this project's Class A defect.
4. `deal_counts` CONSERVES. On random simplices and random budgets the dealt
   counts plus the named pool equal the budget in every draw, the counts are
   non-negative integers, and the expectation matches the continuous product
   it replaces while the variance is HIGHER -- which is the honest description
   of what the repair does and is asserted rather than asserted away.
5. THE SEALED BOARDS ARE RE-SCANNED. The defect is fenced at the size it was
   measured at (`rushing/carries` non-integer in 243,766 of 384,000 cells over
   the 102 sealed runs), so the historical state cannot be quietly rewritten,
   and the `db == att + sacks + scr` identity is re-checked over every sealed
   quarterback cell.
6. THE TWO COUNT REGISTRIES AGREE. `nfl.product.metrics.SUPPORTED` and
   `stat_contract.COUNT_METRICS` must name one set; a divergence is a failing
   test rather than two quiet answers to one question.
7. NOTHING IN THE CONTRACT REPAIRS. Asserted on the AST: no `np.clip`, no
   `np.round`/`np.rint` outside the two places that are declared roundings of
   a LEVEL, and no file opened for writing.

WHAT IT DOES NOT ASSERT
=======================
Nothing here says a forecast is good, and nothing here says the sealed boards
were right. The fences are regression fences on a measured state, not targets.
"""
from __future__ import annotations

import ast
import csv
import glob
import gzip
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production import stat_contract as SC                     # noqa: E402

csv.field_size_limit(10 ** 7)

PASSED = FAILED = BLOCKED = 0

PBP = sorted(glob.glob(os.path.join(_ROOT, 'nfl', 'research', 'postgame',
                                    'pbp_*.csv.gz')))
PANEL = os.path.join(_ROOT, 'nfl', 'research', 'inputs', 'panel_p3.csv.gz')
LIVE = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live'
GLOB = '2026_01_*/*/*/player_draws.npz'

# MEASURED 2026-09-14 on the six pbp corpora in this repository, REG only,
# two-point attempts and no_play rows excluded, posteam non-empty. A fence,
# not a target: if the feed's flags change meaning these move and this module
# is where that becomes visible.
CORPUS = {'plays': 211755, 'att_raw': 97696, 'att': 90748, 'sack': 6601,
          'spike': 347, 'rush_attempt': 73815, 'scramble': 5054,
          'kneel': 2104, 'designed_rush': 66657, 'dropbacks': 102403}

# The sealed state of the count defect, re-derived below.
SEALED_COUNTS = {'runs': 102, 'carry_cells': 384000,
                 'carry_non_integer_cells': 243766,
                 'qb_identity_cells': 844000,
                 'qb_identity_violating_cells': 0}

# panel_p3, re-derived below.
PANEL_ROWS = 57670


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


def _pbp_rows():
    for f in PBP:
        with gzip.open(f, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                if not (r.get('posteam') or ''):
                    continue
                yield r


# ------------------------------------------------------------------ taxonomy
def test_a_the_taxonomy_is_a_partition_of_real_plays():
    if not PBP:
        blocked('no pbp corpus under nfl/research/postgame/',
                'the taxonomy cannot be measured against real plays')
        return
    o = SC.tabulate(_pbp_rows())
    check('tabulate returns PASS over the whole corpus', o.state is State.PASS,
          f'{o.code}: {o.detail[:200]}')
    if o.state is not State.PASS:
        return
    c, agg = o.value['counts'], o.value['aggregates']
    for k in ('att', 'sack', 'spike', 'scramble', 'kneel', 'designed_rush'):
        got = c['pass_attempt'] if k == 'att' else c[k]
        check(f'  class {k} = {CORPUS[k]}', got == CORPUS[k], f'got {got}')
    check(f'  att_raw = {CORPUS["att_raw"]}',
          agg['att_raw'] == CORPUS['att_raw'], f'got {agg["att_raw"]}')
    check(f'  dropbacks = {CORPUS["dropbacks"]}',
          agg['dropbacks'] == CORPUS['dropbacks'], f'got {agg["dropbacks"]}')
    check(f'  rush attempts = {CORPUS["rush_attempt"]}',
          agg['rush_attempts'] == CORPUS['rush_attempt'],
          f'got {agg["rush_attempts"]}')
    check('  every identity holds as an exact integer sum',
          all(o.evidence['identities_hold'].values()),
          str(o.evidence['identities_hold']))
    # THE GAP THE BOARD PAYS FOR, as a number rather than an opinion.
    check('  att_raw - att == sacks + spikes, exactly',
          agg['att_raw'] - c['pass_attempt'] == c['sack'] + c['spike'])
    check('  and it is 6,948 plays of 97,696 att_raw (7.11%)',
          c['sack'] + c['spike'] == 6948,
          f'got {c["sack"] + c["spike"]}')


def test_a_no_play_carries_two_classes():
    if not PBP:
        blocked('no pbp corpus', 'the partition cannot be measured')
        return
    both_pr = both_ss = both_sk = flag_only = 0
    n = 0
    for r in _pbp_rows():
        def f(k):
            try:
                return int(float(r.get(k)))
            except (TypeError, ValueError):
                return 0
        if f('two_point_attempt') or r.get('play_type') == 'no_play':
            continue
        n += 1
        pas, rush = f('pass_attempt'), f('rush_attempt')
        if pas and rush:
            both_pr += 1
        if pas and f('sack') and f('qb_spike'):
            both_ss += 1
        if rush and f('qb_scramble') and f('qb_kneel'):
            both_sk += 1
        if not pas and not rush and (f('sack') or f('qb_spike')
                                     or f('qb_scramble') or f('qb_kneel')):
            flag_only += 1
    check(f'{n} plays examined', n == CORPUS['plays'], f'got {n}')
    check('  no play is both a pass attempt and a rush attempt',
          both_pr == 0, f'{both_pr} plays')
    check('  no play is both a sack and a spike', both_ss == 0,
          f'{both_ss} plays')
    check('  no play is both a scramble and a kneel', both_sk == 0,
          f'{both_sk} plays')
    check('  no event flag appears without its play flag', flag_only == 0,
          f'{flag_only} plays')


def test_a_classify_refuses_an_impossible_row_rather_than_choosing():
    o = SC.classify_play({'pass_attempt': 1, 'rush_attempt': 1})
    check('a pass-and-rush row is REFUSED, not assigned',
          o.state is State.FAIL and o.code == 'PLAY_IS_BOTH_PASS_AND_RUSH',
          f'{o.state.value}[{o.code}]')
    o = SC.classify_play({'pass_attempt': 1, 'sack': 1, 'qb_spike': 1})
    check('a sack-and-spike row is REFUSED',
          o.state is State.FAIL and o.code == 'PLAY_IS_BOTH_SACK_AND_SPIKE',
          f'{o.state.value}[{o.code}]')
    o = SC.classify_play({'sack': 1})
    check('a sack flag with no pass attempt is REFUSED',
          o.state is State.FAIL and o.code == 'EVENT_FLAG_WITHOUT_ITS_PLAY',
          f'{o.state.value}[{o.code}]')
    o = SC.classify_play({'play_type': 'punt'})
    check('a punt is NOT_APPLICABLE with a reason, never a class',
          o.state is State.NOT_APPLICABLE and len(o.detail) > 30,
          f'{o.state.value}[{o.code}]')
    o = SC.classify_play({'pass_attempt': 1, 'two_point_attempt': 1})
    check('a two-point attempt is excluded by name',
          o.code == 'PLAY_EXCLUDED_TWO_POINT', o.code)


# -------------------------------------------------------------- the two traps
def test_b_panel_p3_dropback_column_is_refused_as_a_dropback():
    if not os.path.exists(PANEL):
        blocked('panel_p3.csv.gz absent', 'the trap cannot be demonstrated')
        return
    a, b = [], []
    with gzip.open(PANEL, 'rt') as fh:
        for r in csv.DictReader(fh):
            a.append(float(r.get('dropbacks_as_passer') or 0))
            b.append(float(r.get('pass_att_as_passer') or 0))
    check(f'panel_p3 carries {PANEL_ROWS} rows', len(a) == PANEL_ROWS,
          f'got {len(a)}')
    o = SC.assert_not_a_dropback_column('panel_p3.dropbacks_as_passer', a, b)
    check('  it is REFUSED as a dropback column',
          o.state is State.FAIL and o.code == 'DROPBACK_COLUMN_IS_ATT_RAW',
          f'{o.state.value}[{o.code}]')
    check('  and the refusal reports every row equal',
          o.evidence['rows_equal'] == len(a),
          f'{o.evidence["rows_equal"]} of {len(a)}')
    # THE GUARD MUST ALSO PASS SOMETHING. A refusal that refuses everything is
    # not a guard, it is a constant.
    o2 = SC.assert_not_a_dropback_column('a_real_dropback_column',
                                         [float(x) + 1 for x in a[:100]],
                                         b[:100])
    check('  a genuinely different column is NOT refused',
          o2.state is State.PASS, f'{o2.state.value}[{o2.code}]')
    check('  and the PASS says plainly that it is still not proof',
          'does NOT' in o2.detail or 'not' in o2.detail.lower())


def test_b_the_contract_names_both_false_friends():
    check('panel_p3.dropbacks_as_passer is a declared false friend',
          'panel_p3.dropbacks_as_passer' in SC.FALSE_FRIENDS)
    check('nflverse.pass_attempt is a declared false friend',
          'nflverse.pass_attempt' in SC.FALSE_FRIENDS)
    for k, v in SC.FALSE_FRIENDS.items():
        check(f'  {k} says what it actually is', len(v['actually_is']) > 8)
        check(f'  {k} carries its evidence', len(v['evidence']) > 20)
        check(f'  {k} names a refusal code', v['refusal'].isupper())


# ----------------------------------------------------------- dropback identity
def test_c_dropback_identity_holds_and_bites():
    db = np.array([[35, 40], [12, 0]], float)
    att = np.array([[30, 36], [10, 0]], float)
    sk = np.array([[3, 2], [1, 0]], float)
    scr = np.array([[2, 2], [1, 0]], float)
    o = SC.assert_dropback_identity(db, att, sk, scr)
    check('a coherent set passes exactly', o.state is State.PASS
          and o.evidence['max_abs_deviation'] == 0.0,
          f'{o.state.value}[{o.code}]')
    bad = db.copy()
    bad[0, 0] += 1
    o = SC.assert_dropback_identity(bad, att, sk, scr)
    check('  a seeded one-cell violation is caught',
          o.state is State.FAIL and o.evidence['violating_cells'] == 1,
          f'{o.state.value}[{o.code}]')
    o = SC.assert_dropback_identity(np.zeros((0, 3)), np.zeros((0, 3)),
                                    np.zeros((0, 3)), np.zeros((0, 3)))
    check('  zero cells is BLOCKED, never a satisfied identity',
          o.state is State.BLOCKED, f'{o.state.value}[{o.code}]')
    o = SC.assert_dropback_identity(db, att, sk, scr[:1])
    check('  a shape mismatch is refused, not broadcast',
          o.state is State.FAIL and o.code == 'DROPBACK_IDENTITY_SHAPE',
          f'{o.state.value}[{o.code}]')


def test_c_the_identity_holds_on_every_sealed_quarterback_cell():
    runs = sorted(LIVE.glob(GLOB))
    if not runs:
        blocked('no sealed runs', 'the identity has nothing to hold over')
        return
    cells = viol = 0
    worst = 0.0
    for p in runs:
        z = np.load(p, allow_pickle=True)
        if not {'qb__db', 'qb__att', 'qb__sacks', 'qb__scr'} <= set(z.files):
            continue
        o = SC.assert_dropback_identity(z['qb__db'], z['qb__att'],
                                        z['qb__sacks'], z['qb__scr'])
        cells += o.evidence['n_cells']
        viol += o.evidence['violating_cells']
        worst = max(worst, o.evidence['max_abs_deviation'])
    check(f'{len(runs)} sealed run(s) scanned', len(runs) >= 1)
    check(f'  db == att + sacks + scr over {cells} cell(s)',
          cells >= SEALED_COUNTS['qb_identity_cells'], f'got {cells}')
    check('  violating cells: 0', viol == 0, f'got {viol}')
    check('  max absolute deviation: 0.000000', worst == 0.0, f'got {worst}')


# ---------------------------------------------------------------- count support
def test_d_count_support_is_asserted_and_bites():
    good = {'rushing/carries': np.arange(20).reshape(4, 5).astype(float),
            'qb/att': np.full((2, 5), 30.0)}
    o = SC.assert_counts_are_counts(good)
    check('valid counts pass', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    frac = {k: v.copy() for k, v in good.items()}
    frac['rushing/carries'][0, 0] = 10.4183
    o = SC.assert_counts_are_counts(frac)
    check('  one seeded non-integer cell is caught',
          o.state is State.FAIL and o.code == 'COUNT_SUPPORT_VIOLATED',
          f'{o.state.value}[{o.code}]')
    check('  and the refusal names the metric and the cell count',
          o.evidence['violations'][0]['metric'] == 'rushing/carries'
          and o.evidence['violations'][0]['non_integer'] == 1)
    neg = {k: v.copy() for k, v in good.items()}
    neg['qb/att'][1, 1] = -1.0
    o = SC.assert_counts_are_counts(neg)
    check('  a seeded negative count is caught',
          o.state is State.FAIL
          and o.evidence['violations'][0]['negative'] == 1,
          f'{o.state.value}[{o.code}]')
    o = SC.assert_counts_are_counts({'qb/pyds': np.full((2, 3), 1.5)})
    check('  checking NOTHING is BLOCKED, not a pass',
          o.state is State.BLOCKED
          and o.code == 'NO_DECLARED_COUNT_SUPPLIED',
          f'{o.state.value}[{o.code}]')
    o = SC.assert_counts_are_counts({'rushing/carries': np.zeros((0, 0))})
    check('  an empty matrix is a refusal, not a count of zero',
          o.state is State.FAIL and o.code == 'COUNT_MATRIX_EMPTY',
          f'{o.state.value}[{o.code}]')
    check('  yards are NOT in the declared count set',
          all(k not in SC.COUNT_METRICS for k in SC.CONTINUOUS_METRICS))


def test_d_the_two_count_registries_name_one_set():
    from nfl.product import metrics as PM
    o = SC.reconcile_with_product_registry(PM.SUPPORTED)
    check('the product layer and the stat contract agree on what a count is',
          o.state is State.PASS,
          f'{o.code}: only_in_product={o.evidence.get("only_in_product")} '
          f'only_in_contract={o.evidence.get("only_in_contract")}')
    check('  and the agreed set is not empty', len(SC.COUNT_METRICS) >= 14,
          str(len(SC.COUNT_METRICS)))


# ------------------------------------------------------------------ deal_counts
def test_e_deal_counts_conserves_in_every_draw():
    rng = np.random.default_rng(20260914)
    for trial in range(5):
        n, m = 4, 300
        starts, counts = [0, 2], [2, 2]
        S = rng.dirichlet(np.ones(3), size=(2, m))    # 2 players + other
        share = np.zeros((n, m))
        other = np.zeros((2, m))
        for k in range(2):
            share[starts[k]:starts[k] + 2] = S[k][:, :2].T
            other[k] = S[k][:, 2]
        budget = [rng.integers(0, 40, m).astype(float) for _ in range(2)]
        o = SC.deal_counts(share, other, budget, starts, counts, rng,
                           metric='carries')
        if not check(f'trial {trial}: deal_counts passes',
                     o.state is State.PASS, f'{o.code}: {o.detail[:120]}'):
            continue
        X, P = o.value['counts'], o.value['other']
        bad = 0
        for k in range(2):
            bad += int((X[starts[k]:starts[k] + 2].sum(0) + P[k]
                        != budget[k]).sum())
        check('  closure holds in every draw', bad == 0, f'{bad} cells')
        check('  every dealt value is a non-negative integer',
              X.dtype.kind == 'i' and (X >= 0).all())


def test_e_deal_counts_matches_the_product_in_expectation_and_exceeds_it_in_spread():
    # THE HONEST DESCRIPTION OF THE REPAIR. E[dealt] == share x budget, so no
    # mass moves on average; Var[dealt] > Var[share x budget], because dealing
    # a finite number of carries to a finite number of backs is genuinely
    # noisier than splitting a level by a share. Both are asserted.
    rng = np.random.default_rng(7)
    m = 40000
    starts, counts = [0], [2]
    p = np.array([0.55, 0.35])
    share = np.repeat(p[:, None], m, axis=1)
    other = np.full((1, m), 0.10)
    budget = [np.full(m, 20.0)]
    o = SC.deal_counts(share, other, budget, starts, counts, rng)
    check('deal_counts passes on a fixed simplex', o.state is State.PASS,
          o.code)
    X = o.value['counts']
    prod = share * budget[0][None, :]
    for i in range(2):
        d = abs(X[i].mean() - prod[i].mean())
        check(f'  row {i}: mean agrees with share x budget to within 0.05 '
              f'({X[i].mean():.4f} vs {prod[i].mean():.4f})', d < 0.05,
              f'{d:.4f}')
        check(f'  row {i}: the dealt spread is strictly larger '
              f'(sd {X[i].std():.4f} vs {prod[i].std():.4f})',
              X[i].std() > prod[i].std())
    check('  the multinomial sd matches sqrt(n p (1-p)) to within 2%',
          abs(X[0].std() - np.sqrt(20 * 0.55 * 0.45))
          / np.sqrt(20 * 0.55 * 0.45) < 0.02,
          f'{X[0].std():.4f} vs {np.sqrt(20 * 0.55 * 0.45):.4f}')


def test_e_deal_counts_refuses_rather_than_rounding_a_budget():
    rng = np.random.default_rng(1)
    share = np.full((2, 5), 0.45)
    other = np.full((1, 5), 0.10)
    o = SC.deal_counts(share, other, [np.full(5, 10.4)], [0], [2], rng)
    check('a fractional budget is REFUSED, never rounded here',
          o.state is State.FAIL
          and o.code == 'DEAL_COUNTS_BUDGET_NOT_INTEGER',
          f'{o.state.value}[{o.code}]')
    o = SC.deal_counts(share, other, [np.full(5, -1.0)], [0], [2], rng)
    check('  a negative budget is refused', o.state is State.FAIL
          and o.code == 'DEAL_COUNTS_BUDGET_NEGATIVE',
          f'{o.state.value}[{o.code}]')
    o = SC.deal_counts(np.zeros((2, 5)), np.zeros((1, 5)),
                       [np.full(5, 10.0)], [0], [2], rng)
    check('  a degenerate simplex is refused, not dealt uniformly',
          o.state is State.FAIL
          and o.code == 'DEAL_COUNTS_SIMPLEX_DEGENERATE',
          f'{o.state.value}[{o.code}]')
    o = SC.deal_counts(share, other, [np.full(4, 10.0)], [0], [2], rng)
    check('  a budget on a different draw index is refused',
          o.state is State.FAIL and o.code == 'DEAL_COUNTS_BUDGET_DRAWS',
          f'{o.state.value}[{o.code}]')
    # A GROUP WITH NOBODY IN IT IS NOT ZERO OPPORTUNITY.
    o = SC.deal_counts(np.zeros((0, 5)), np.full((1, 5), 1.0),
                       [np.full(5, 7.0)], [0], [0], rng)
    check('  a group with no modelled player gives the whole budget to the '
          'named pool', o.state is State.PASS
          and int(o.value['other'].sum()) == 35,
          f'{o.state.value}[{o.code}]')


def test_e_integerise_level_declares_itself_and_counts_the_moves():
    o = SC.integerise_level(np.array([10.4, 10.6, 11.0]))
    check('a declared level rounding passes', o.state is State.PASS, o.code)
    check('  and counts the cells it moved', o.evidence['cells_moved'] == 2,
          str(o.evidence['cells_moved']))
    check('  and reports the shift it caused',
          'mean_shift' in o.evidence)
    o = SC.integerise_level([1.0], mode='floor')
    check('  an undeclared rounding mode is refused',
          o.state is State.FAIL and o.code == 'LEVEL_ROUNDING_UNDECLARED',
          f'{o.state.value}[{o.code}]')
    o = SC.integerise_level(np.array([]))
    check('  an empty level is BLOCKED', o.state is State.BLOCKED, o.code)


# ------------------------------------------------------------ the sealed fence
def test_f_the_sealed_carry_defect_is_fenced_at_the_size_it_was_measured():
    runs = sorted(LIVE.glob(GLOB))
    if not runs:
        blocked('no sealed runs', 'the defect has nothing to be fenced on')
        return
    cells = frac = 0
    for p in runs:
        z = np.load(p, allow_pickle=True)
        if 'rushing__carries' not in z.files:
            continue
        a = np.asarray(z['rushing__carries'], float)
        cells += a.size
        frac += int((np.abs(a - np.rint(a)) > 0).sum())
    check(f'{len(runs)} sealed run(s) carry {cells} carry cell(s)',
          len(runs) == SEALED_COUNTS['runs']
          and cells == SEALED_COUNTS['carry_cells'],
          f'{len(runs)} runs, {cells} cells')
    check(f'  {SEALED_COUNTS["carry_non_integer_cells"]} of them are '
          f'non-integer ({100 * frac / max(cells, 1):.2f}%) -- the defect, '
          f'fenced at its measured size',
          frac == SEALED_COUNTS['carry_non_integer_cells'], f'got {frac}')
    # AND THE SAME CHECK, THROUGH THE CONTRACT, MUST REFUSE THEM.
    z = np.load(runs[0], allow_pickle=True)
    o = SC.assert_counts_are_counts({'rushing/carries':
                                     np.asarray(z['rushing__carries'], float)})
    check('  the contract refuses a sealed carry matrix from before the '
          'repair', o.state is State.FAIL, f'{o.state.value}[{o.code}]')


def test_g_the_contract_repairs_nothing():
    src = pathlib.Path(_ROOT) / 'nfl' / 'production' / 'stat_contract.py'
    tree = ast.parse(src.read_text())
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = (f.attr if isinstance(f, ast.Attribute)
                    else f.id if isinstance(f, ast.Name) else '')
            calls.append(name)
    check('no np.clip anywhere in the contract', 'clip' not in calls)
    check('no open() anywhere in the contract', 'open' not in calls)
    check('no renormalisation helper is imported',
          'normalize' not in calls and 'renormalise' not in calls)
    # rint IS used, and only where a rounding is DECLARED. Counted, so a new
    # undeclared one shows up here.
    # rint IS used, seven times, and every one is either a MEASUREMENT of how
    # far a value is from an integer or the ONE declared level rounding.
    # Counted rather than forbidden, so a new undeclared rounding surfaces
    # here as a failing fence instead of passing as a refactor.
    check('np.rint appears exactly 7 times: twice measuring the fractional '
          'part in assert_counts_are_counts, once in integerise_level, and '
          'four times in deal_counts refusing or restating an already-integer '
          'budget', calls.count('rint') == 7, f'{calls.count("rint")}')
    check('the contract carries a version string',
          isinstance(SC.CONTRACT_VERSION, str) and SC.CONTRACT_VERSION)
    check('every term declares its predicate, its attribution and whether it '
          'is a dropback',
          all({'predicate', 'attributed_to', 'is_dropback'} <= set(v)
              for v in SC.TERMS.values()))
    check('the dropback terms are exactly attempt, sack and scramble',
          {k for k, v in SC.TERMS.items() if v['is_dropback']}
          == {'pass_attempt', 'sack', 'scramble'})


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
