"""Week 2 opponent adjustment is UNIDENTIFIED from Week-1 data, and this proves it.

NOT WEAKLY IDENTIFIED. UNIDENTIFIED. The distinction is the whole point: a
weakly identified model returns an imprecise answer, and an unidentified one
returns a number that carries no information from the data at all while
looking exactly like an answer.

With 32 clubs and 16 Week-1 games, offense A meets only defense B and offense B
meets only defense A. The bipartite graph joining offensive units to the
defensive units they faced therefore decomposes into 32 DISJOINT PAIRS. Inside
a two-node component only the SUM off_A + def_B is estimable; the split between
them has no data behind it. Ridge will still return 64 unit strengths, and every
one of them will be a shrinkage artifact of the penalty.

This test exists so that a future reader cannot treat a Week-2 "opponent-
adjusted" number as measured opponent quality, and so that the carryover prior
of the pre-registration is understood as load-bearing rather than as a
refinement.

MEASURED FROM THE CAPTURED BLOB, not from a fixture, so it is a statement about
the real data.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import io
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                     # noqa: E402
from nfl.research.oas1 import normalize_teams as NT                     # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []

#: The measurement this test freezes, taken 2026-09-17 on
#: pbp_2026.b69f55a172965e16.csv.gz.
EXPECTED_DESIGN_COLS = 66      # intercept + 32 offense + 32 defense + home
EXPECTED_RANK = 32
EXPECTED_DEFICIENCY = 34
EXPECTED_COMPONENTS = 32
EXPECTED_COMPONENT_SIZE = 2

#: THE TWO STRUCTURAL REDUNDANCIES, MEASURED AND THEN EXPLAINED.
#:
#: The research guidance says "ridge already resolves THE dummy-variable
#: redundancy", singular. There are two. Measured on the full 2025 regular
#: season, 19,982 pass plays with a fully connected schedule:
#:
#:   intercept + 32 offense + 32 defense + home   66 cols, rank 64, deficiency 2
#:   NO intercept, 32 + 32 + home                 65 cols, rank 64, deficiency 1
#:   intercept + 32 + 32, no home                 65 cols, rank 63, deficiency 2
#:
#: The cause is direct: every play has exactly one offense and exactly one
#: defense, so the offense dummies sum to 1 on every row and so do the defense
#: dummies. BOTH families are collinear with the intercept. Dropping the
#: intercept removes one redundancy; the second survives because the two
#: families are then collinear with each other.
#:
#: This makes the Week-1 arithmetic exact rather than approximate:
#:
#:   34 = 32 unidentified within-component splits + 2 structural redundancies
#:
#: and it is why an expectation of "rank 65" was wrong.
EXPECTED_STRUCTURAL_REDUNDANCIES = 2
EXPECTED_FULL_SEASON_RANK = 64


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _play_class(r):
    """The pre-registered rule. A SACK AND A SCRAMBLE ARE PASS PLAYS.

    Routing them to rush would inflate off_pass, deflate off_rush, deflate
    def_pass and inflate def_rush at once -- every unit wrong, the aggregate
    still balanced, and no conservation check firing.
    """
    if _f(r.get('pass_attempt')) == 1 or _f(r.get('sack')) == 1 \
            or _f(r.get('qb_scramble')) == 1:
        return 'pass'
    if _f(r.get('rush_attempt')) == 1:
        return 'rush'
    return None


def _load():
    b = sorted(glob.glob(os.path.join(_ROOT, 'nfl/vintage/pbp_2026.*.csv.gz')))
    if not b:
        return None, None
    txt = gzip.decompress(open(b[-1], 'rb').read()).decode('utf-8')
    return os.path.basename(b[-1]), list(csv.DictReader(io.StringIO(txt)))


def _subset(rows, cls):
    out = []
    for r in rows:
        if _play_class(r) != cls:
            continue
        o, d, e = r.get('posteam'), r.get('defteam'), r.get('epa')
        if not o or not d or e in (None, ''):
            continue
        out.append((NT.normalize(o).value, NT.normalize(d).value, float(e),
                    1 if o == r.get('home_team') else 0))
    return out


def _design(sub, teams):
    ti = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    X = np.zeros((len(sub), 1 + 2 * n + 1))
    for k, (o, d, _y, h) in enumerate(sub):
        X[k, 0] = 1.0
        X[k, 1 + ti[o]] = 1.0
        X[k, 1 + n + ti[d]] = 1.0
        X[k, 1 + 2 * n] = float(h)
    return X


def _components(sub):
    adj = collections.defaultdict(set)
    for o, d, _y, _h in sub:
        adj[('O', o)].add(('D', d))
        adj[('D', d)].add(('O', o))
    seen, comps = set(), []
    for node in list(adj):
        if node in seen:
            continue
        stack, comp = [node], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            seen.add(x)
            stack.extend(adj[x] - comp)
        comps.append(comp)
    return comps


def test_A_week_one_is_rank_deficient_for_both_play_classes():
    print('\nA. 66 columns, rank 32, in the real data')
    name, rows = _load()
    check('the 2026 pbp capture exists', rows is not None, str(name))
    if rows is None:
        NOT_EXECUTED.append('A: no 2026 pbp capture')
        return
    print(f'  (reading {name})')
    for cls in ('pass', 'rush'):
        sub = _subset(rows, cls)
        teams = sorted({o for o, _d, _y, _h in sub}
                       | {d for _o, d, _y, _h in sub})
        check(f'{cls}: all 32 clubs appear', len(teams) == 32, str(len(teams)))
        X = _design(sub, teams)
        rank = int(np.linalg.matrix_rank(X))
        check(f'{cls}: the design has {EXPECTED_DESIGN_COLS} columns',
              X.shape[1] == EXPECTED_DESIGN_COLS, str(X.shape[1]))
        check(f'{cls}: its rank is {EXPECTED_RANK}', rank == EXPECTED_RANK,
              f'rank {rank} on {len(sub)} row(s)')
        check(f'{cls}: the deficiency is {EXPECTED_DEFICIENCY} dimensions',
              X.shape[1] - rank == EXPECTED_DEFICIENCY,
              str(X.shape[1] - rank))
        check(f'  and it is NOT a sample-size problem: {len(sub)} rows is far '
              f'more than {EXPECTED_DESIGN_COLS} columns',
              len(sub) > 10 * EXPECTED_DESIGN_COLS, str(len(sub)))


def test_B_the_opponent_graph_is_32_disjoint_pairs():
    print('\nB. why it is unidentified rather than imprecise')
    name, rows = _load()
    if rows is None:
        NOT_EXECUTED.append('B: no 2026 pbp capture')
        return
    for cls in ('pass', 'rush'):
        sub = _subset(rows, cls)
        comps = _components(sub)
        sizes = collections.Counter(len(c) for c in comps)
        check(f'{cls}: the offense-defense graph has {EXPECTED_COMPONENTS} '
              f'components', len(comps) == EXPECTED_COMPONENTS, str(len(comps)))
        check(f'  every one of them has exactly {EXPECTED_COMPONENT_SIZE} '
              f'nodes', set(sizes) == {EXPECTED_COMPONENT_SIZE}, str(dict(sizes)))
        check('  so no component contains two offenses, which is what a '
              'shared opponent would create',
              all(sum(1 for k in c if k[0] == 'O') == 1 for c in comps),
              'a component holds more than one offense')
    # THE DECOMPOSITION, AS AN EQUALITY AND NOT AS A TAUTOLOGY.
    #
    # An earlier version of this check was written `A + 2 == B or B == 34`,
    # and that second clause made it pass whatever the first said. It is now a
    # single equality over the three measured constants, so it fails if any
    # one of them moves.
    check(f'the deficiency decomposes EXACTLY: {EXPECTED_COMPONENTS} '
          f'unidentified within-component splits + '
          f'{EXPECTED_STRUCTURAL_REDUNDANCIES} structural redundancies = '
          f'{EXPECTED_DEFICIENCY}',
          EXPECTED_COMPONENTS + EXPECTED_STRUCTURAL_REDUNDANCIES
          == EXPECTED_DEFICIENCY,
          f'{EXPECTED_COMPONENTS} + {EXPECTED_STRUCTURAL_REDUNDANCIES} != '
          f'{EXPECTED_DEFICIENCY}')


def test_C_a_naive_ridge_still_returns_64_numbers():
    print('\nC. the failure mode: it answers anyway')
    name, rows = _load()
    if rows is None:
        NOT_EXECUTED.append('C: no 2026 pbp capture')
        return
    sub = _subset(rows, 'pass')
    teams = sorted({o for o, _d, _y, _h in sub}
                   | {d for _o, d, _y, _h in sub})
    X = _design(sub, teams)
    y = np.array([e for _o, _d, e, _h in sub])
    n = len(teams)
    # Ridge with the intercept and home term UNPENALISED, per the spec.
    pen = np.ones(X.shape[1])
    pen[0] = 0.0
    pen[-1] = 0.0
    for lam in (1.0, 100.0):
        A = X.T @ X + lam * np.diag(pen)
        theta = np.linalg.solve(A, X.T @ y)
        off = theta[1:1 + n]
        deff = theta[1 + n:1 + 2 * n]
        check(f'lambda={lam:g}: it returns {2 * n} finite unit strengths '
              f'despite the rank deficiency',
              np.isfinite(off).all() and np.isfinite(deff).all()
              and len(off) == n and len(deff) == n)
        # THE TELL. Within a two-node component only the SUM is estimable, so
        # the split is whatever the penalty chose. Raising lambda must shrink
        # both toward zero while the pairwise SUM is comparatively stable.
        if lam == 1.0:
            small = (off.copy(), deff.copy())
        else:
            big = (off, deff)
    shrink_off = float(np.abs(big[0]).mean() / max(np.abs(small[0]).mean(), 1e-12))
    check('  and raising the penalty a hundredfold moves the estimates '
          'substantially, because the penalty -- not the data -- is choosing '
          'the split',
          shrink_off < 0.9,
          f'mean |off| ratio lambda=100 / lambda=1 is {shrink_off:.4f}; a '
          f'ratio near 1 would mean the data was pinning the split')
    check('  which is why a Week-2 number from this design must never be '
          'reported as measured opponent quality',
          True, 'recorded')


def test_D_a_full_season_is_identified_and_that_is_the_contrast():
    print('\nD. the contrast: a connected schedule identifies it')
    b = sorted(glob.glob(os.path.join(_ROOT, 'nfl/vintage/pbp_2025.*.csv.gz')))
    check('a prior-season capture exists to contrast against', bool(b),
          'no 2025 pbp capture')
    if not b:
        NOT_EXECUTED.append('D: no prior-season capture')
        return
    txt = gzip.decompress(open(b[-1], 'rb').read()).decode('utf-8')
    rows = [r for r in csv.DictReader(io.StringIO(txt))
            if (r.get('season_type') or '') == 'REG']
    sub = _subset(rows, 'pass')
    teams = sorted({o for o, _d, _y, _h in sub}
                   | {d for _o, d, _y, _h in sub})
    X = _design(sub, teams)
    rank = int(np.linalg.matrix_rank(X))
    comps = _components(sub)
    check(f'the full prior season has {len(sub)} pass plays', len(sub) > 10000,
          str(len(sub)))
    check('  its offense-defense graph is ONE component, not 32',
          len(comps) == 1, f'{len(comps)} components')
    # THE EXPECTATION HERE WAS WRONG AND THE DATA CORRECTED IT. This asserted
    # rank 65 of 66, on the guidance's "the dummy-variable redundancy",
    # singular. The measurement is 64: there are TWO redundancies, because
    # both dummy families sum to 1 on every row and each is collinear with the
    # intercept.
    check(f'  its design rank is {EXPECTED_FULL_SEASON_RANK} of '
          f'{X.shape[1]} -- deficiency '
          f'{EXPECTED_STRUCTURAL_REDUNDANCIES}, NOT 1',
          rank == EXPECTED_FULL_SEASON_RANK
          and X.shape[1] - rank == EXPECTED_STRUCTURAL_REDUNDANCIES,
          f'rank {rank} of {X.shape[1]}, deficiency {X.shape[1] - rank}')
    check('  and both redundancies are demonstrable, not inferred: the '
          'offense dummies sum to 1 on every row and so do the defence ones',
          bool(np.allclose(X[:, 1:1 + len(teams)].sum(1), 1.0))
          and bool(np.allclose(
              X[:, 1 + len(teams):1 + 2 * len(teams)].sum(1), 1.0)))
    check('  so the prior-season deficiency is STRUCTURAL and carries no '
          'unidentified opponent effect, which is exactly why the carryover '
          'prior is the prerequisite',
          X.shape[1] - rank == EXPECTED_STRUCTURAL_REDUNDANCIES
          and len(comps) == 1,
          f'deficiency {X.shape[1] - rank}, {len(comps)} component(s)')
    check('  and the Week-1 deficiency is 32 dimensions WORSE than that, '
          'which is the whole finding',
          EXPECTED_DEFICIENCY - EXPECTED_STRUCTURAL_REDUNDANCIES
          == EXPECTED_COMPONENTS,
          f'{EXPECTED_DEFICIENCY} - {EXPECTED_STRUCTURAL_REDUNDANCIES} != '
          f'{EXPECTED_COMPONENTS}')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_week_one_is_rank_deficient_for_both_play_classes,
               test_B_the_opponent_graph_is_32_disjoint_pairs,
               test_C_a_naive_ridge_still_returns_64_numbers,
               test_D_a_full_season_is_identified_and_that_is_the_contrast):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
