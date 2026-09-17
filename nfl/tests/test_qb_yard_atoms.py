"""The per-catch atoms RC1 draws, and the signed integer partition built on them.

TWO SEPARATE CLAIMS, TESTED SEPARATELY, because conflating them is how a
mechanism change gets smuggled in wearing a plumbing change's clothes.

CLAIM A -- ADDITIVE. `layers.receiving_conversion` now returns the per-catch
yardage vector it already drew. It must not move one bit of `receptions` or
`receiving_yards`, and it must not consume one extra number from the stream.
The test does not take my word for that: it loads the PRE-CHANGE source out of
git, runs both on identical inputs, and compares the bytes.

CLAIM B -- THE DEAL. `credit_passing_line` given those atoms partitions them
instead of splitting their total. The pre-registration
(nfl/research/qb_yards/predeclaration_signed_deal.md) fixed seven acceptance
gates before any of this existed; sections 1-7 below are those gates, in order,
including the one that says a NEGATIVE team total must be dealt without error
and without a clip.

WHY NOT A MULTIVARIATE HYPERGEOMETRIC. The atoms are signed: the frozen 2026
receiving pools carry 2,043 negative per-catch yardages out of 69,981 own-
history atoms, with a minimum of -13. An urn cannot hold -13 balls. The
partition is over a labelled multiset, which has no sign assumption anywhere.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Outcome, State            # noqa: E402
from nfl.production.nonqb import layers as L                            # noqa: E402
from nfl.production.nonqb import football_engine as FE                  # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


# ---------------------------------------------------------------- fixtures
PIDS = ['R001', 'R002', 'R003', 'R004']
POS = ['WR', 'WR', 'TE', 'RB']
M = 64
ORD = 202602
SEED = 20260908


def _priors(pool=None):
    """A frozen-shaped prior with INTEGER atoms, negatives included on purpose."""
    pool = pool if pool is not None else np.array(
        [-13., -7., -3., 0., 1., 3., 4., 6., 9., 12., 17., 24., 41., 80.])
    return {
        'k_shrink': 4.0,
        'pos_catch_rate': {'WR': 0.62, 'TE': 0.68, 'RB': 0.74},
        'pos_yardage_pool': {'WR': pool, 'TE': pool, 'RB': pool},
        'own': {
            'R001': {'h_n': 40.0, 'h_rec': 60, 'h_tgt': 95,
                     'h_V_flat': [-11., -2., 0., 5., 8., 14., 22., 55.]},
            'R002': {'h_n': 3.0, 'h_rec': 4, 'h_tgt': 9,
                     'h_V_flat': [2., 7., 19.]},
            'R003': {'h_n': 0.0},
            'R004': {'h_n': 12.0, 'h_rec': 18, 'h_tgt': 22,
                     'h_V_flat': [-6., -1., 1., 3., 11.]},
        },
    }


def _targets(rng=None):
    r = np.random.default_rng(4242)
    return np.stack([r.poisson(mu, M) for mu in (8.5, 5.0, 4.0, 3.5)]).astype(float)


def _tc():
    return Outcome.ok('OPPORTUNITY_OK', value={}, test_only=True)


def _run(mod=L, **kw):
    return mod.receiving_conversion(
        _tc(), _targets(), _priors(), PIDS, POS, ORD, m=M, seed=SEED, **kw)


#: THE COMMIT IMMEDIATELY BEFORE THE ATOMS EXISTED, pinned by id and not by
#: `HEAD`.
#:
#: This test read `HEAD:nfl/production/nonqb/layers.py` and passed -- until the
#: change was committed, at which point HEAD CONTAINED the atoms, the
#: "HEAD did not already expose atoms" check failed, and the additivity
#: comparison silently became a file compared against itself. The suite caught
#: it on the first run after the commit.
#:
#: A before-and-after test whose "before" is a moving reference can only work
#: until it is committed. `137a257` is the parent of the QY1 commit and its
#: `layers.py` is `419ea433cba65dab`, which has no atom vector in it. Pinned,
#: this proof stays reproducible forever.
PRE_ATOM_COMMIT = '137a257'
PRE_ATOM_LAYERS_SHA16 = '419ea433cba65dab'


def _head_module():
    """`layers.py` as it stood BEFORE the atoms, loaded as its own module."""
    src = subprocess.run(
        ['git', '-C', _ROOT, 'show',
         f'{PRE_ATOM_COMMIT}:nfl/production/nonqb/layers.py'],
        capture_output=True, text=True)
    if src.returncode != 0 or not src.stdout:
        return None
    # `layers.py` resolves the repo root as `parents[3]` of its own path, so
    # the copy has to sit at the same depth or it cannot bootstrap sys.path.
    d = os.path.join(tempfile.mkdtemp(), 'nfl', 'production', 'nonqb')
    os.makedirs(d)
    path = os.path.join(d, 'layers_at_head.py')
    with open(path, 'w') as fh:
        fh.write(src.stdout)
    spec = importlib.util.spec_from_file_location('_layers_at_head', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================ CLAIM A
def test_A_the_atoms_are_exposed_and_well_formed():
    print('\nA. RC1 returns its per-catch atoms')
    o = _run()
    check('RC1 passes on the fixture', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail[:160]}')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('A: RC1 refused, nothing downstream is checkable')
        return
    v = o.value
    check('the atom vector is returned', 'receiving_yard_atoms' in v,
          str(sorted(v)))
    at = v['receiving_yard_atoms']
    R = np.asarray(v['receptions'])
    Y = np.asarray(v['receiving_yards'], float)
    check('one atom vector per player row', len(at) == len(PIDS), str(len(at)))
    check('every atom vector is float64',
          all(np.asarray(a).dtype == np.float64 for a in at),
          str([np.asarray(a).dtype.str for a in at]))
    check('atom count equals TOTAL receptions, per row',
          all(len(at[i]) == int(R[i].sum()) for i in range(len(PIDS))),
          str([(len(at[i]), int(R[i].sum())) for i in range(len(PIDS))]))
    # Draw-major layout: reconstruct Y from the atoms and the segment lengths.
    bad = []
    for i in range(len(PIDS)):
        a = np.asarray(at[i], float)
        ends = np.cumsum(R[i])
        for d in range(M):
            seg = a[ends[d] - R[i, d]:ends[d]]
            if len(seg) != int(R[i, d]) or float(seg.sum()) != float(Y[i, d]):
                bad.append((i, d, len(seg), int(R[i, d]),
                            float(seg.sum()), float(Y[i, d])))
    check('the atoms are laid out DRAW-MAJOR and sum EXACTLY to the totals',
          not bad, f'{len(bad)} bad cell(s), first {bad[:3]}')
    check('a zero-reception cell has a zero-length segment and a 0.0 total',
          not ((R == 0) & (np.abs(Y) > 0)).any(),
          f'{int(((R == 0) & (np.abs(Y) > 0)).sum())} cell(s)')
    flat = np.concatenate([np.asarray(a, float) for a in at if len(a)])
    check('every atom is an INTEGER yardage',
          bool(np.all(flat == np.rint(flat))),
          f'{int((flat != np.rint(flat)).sum())} non-integer atom(s)')
    check('the fixture actually exercises NEGATIVE atoms',
          bool((flat < 0).any()), f'min atom {float(flat.min())}')


def test_B_the_change_is_additive_against_the_pinned_source():
    print('\nB. nothing that existed before this change moved')
    import hashlib
    raw = subprocess.run(
        ['git', '-C', _ROOT, 'show',
         f'{PRE_ATOM_COMMIT}:nfl/production/nonqb/layers.py'],
        capture_output=True)
    if raw.returncode != 0 or not raw.stdout:
        # A shallow clone may not carry the parent. NOT_EXECUTED, never a pass:
        # an additivity proof that cannot read its own "before" has proved
        # nothing.
        NOT_EXECUTED.append(
            f'B: {PRE_ATOM_COMMIT} is not in this clone, so the pre-atom '
            f'source could not be read')
        print(f'  NOT_EXECUTED: {PRE_ATOM_COMMIT} unavailable in this clone')
        return
    got = hashlib.sha256(raw.stdout).hexdigest()[:16]
    check('the pinned pre-atom source is the one this test was written against',
          got == PRE_ATOM_LAYERS_SHA16, f'{got} != {PRE_ATOM_LAYERS_SHA16}')
    head = _head_module()
    if head is None:
        NOT_EXECUTED.append('B: pre-atom source could not be imported')
        return
    old = _run(mod=head)
    new = _run()
    check('both versions pass', old.state is State.PASS and new.state is State.PASS,
          f'old {old.state}[{old.code}] new {new.state}[{new.code}]')
    if not (old.state is State.PASS and new.state is State.PASS):
        NOT_EXECUTED.append('B: one arm refused')
        return
    check('the pinned source did NOT expose atoms (so this is not vacuous)',
          'receiving_yard_atoms' not in old.value, str(sorted(old.value)))
    for k in ('receptions', 'receiving_yards'):
        a = np.ascontiguousarray(np.asarray(old.value[k]))
        b = np.ascontiguousarray(np.asarray(new.value[k]))
        check(f'{k} is BYTE-identical to the pre-atom source',
              a.dtype == b.dtype and a.shape == b.shape
              and a.tobytes() == b.tobytes(),
              f'{a.dtype}/{a.shape} vs {b.dtype}/{b.shape}, '
              f'{int((np.asarray(a, float) != np.asarray(b, float)).sum())} '
              f'differing cell(s)')
    check('every other returned key is unchanged',
          sorted(set(old.value)) == sorted(set(new.value) -
                                           {'receiving_yard_atoms'}),
          f'{sorted(old.value)} vs {sorted(new.value)}')
    check('the evidence block is unchanged',
          {k: v for k, v in old.evidence.items() if k != 'value'}
          == {k: v for k, v in new.evidence.items() if k != 'value'},
          'evidence differs')
    # Same seed twice: no hidden stream consumption, and reproducible.
    again = _run()
    check('two runs at one seed are byte-identical',
          np.asarray(again.value['receiving_yards']).tobytes()
          == np.asarray(new.value['receiving_yards']).tobytes()
          and all(np.asarray(x).tobytes() == np.asarray(y).tobytes()
                  for x, y in zip(again.value['receiving_yard_atoms'],
                                  new.value['receiving_yard_atoms'])),
          'a second run at the same seed differs')


# ============================================================ CLAIM B
def _deal_fixture(nq=2, m=32, seed=7, neg=False):
    """Attempts, interceptions and a team line built FROM atoms, not fitted."""
    rng = np.random.default_rng(seed)
    att = rng.integers(4, 22, (nq, m)).astype(float)
    ints = np.minimum(rng.binomial(2, 0.25, (nq, m)), att).astype(float)
    completable = att - ints
    K = np.array([rng.integers(0, int(completable[:, j].sum()) + 1)
                  for j in range(m)], float)
    pool = (np.array([-19., -13., -8., -4., -2., -1.]) if neg
            else np.array([-13., -3., 2., 5., 9., 14., 28., 63.]))
    atoms = [rng.choice(pool, int(K[j])).astype(float) for j in range(m)]
    Y = np.array([a.sum() for a in atoms], float)
    TD = np.array([rng.integers(0, int(K[j]) + 1) if K[j] else 0
                   for j in range(m)], float)
    return att, ints, K, Y, TD, atoms


def test_C_the_deal_closes_exactly_and_stays_integer():
    print('\nC. the signed integer partition (gates 1, 4, 7)')
    att, ints, K, Y, TD, atoms = _deal_fixture()
    o = FE.credit_passing_line(att, ints, K, Y, TD,
                               np.random.default_rng(11),
                               atoms=atoms,
                               atom_rng=np.random.default_rng(12))
    check('the credit passes with atoms supplied', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail[:200]}')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('C: the deal refused')
        return
    py = np.asarray(o.value['pyds'], float)
    cm = np.asarray(o.value['cmp'], float)
    check('GATE 1: the per-passer yards sum EXACTLY to the team total, '
          'as integers not within a tolerance',
          bool(np.array_equal(np.rint(py.sum(0)).astype(np.int64),
                              np.rint(Y).astype(np.int64)))
          and bool(np.all(py.sum(0) == Y)),
          f'{int((py.sum(0) != Y).sum())} draw(s) do not close')
    check('GATE 7: every credited yardage is an INTEGER',
          bool(np.all(py == np.rint(py))),
          f'{int((py != np.rint(py)).sum())} non-integer cell(s)')
    check('GATE 4: zero completions means exactly zero yards, at the MAXIMUM',
          float(np.abs(py[cm == 0]).max() if (cm == 0).any() else 0.0) == 0.0,
          f'max |pyds| on a zero-completion cell '
          f'{float(np.abs(py[cm == 0]).max() if (cm == 0).any() else 0.0)}')
    check('the scheme is recorded in the outcome',
          'partition' in (o.evidence.get('scheme') or '').lower(),
          str(o.evidence.get('scheme'))[:160])
    check('the fixture is not degenerate: some passer gets NEGATIVE yards',
          bool((py < 0).any()), 'no negative credited cell in the fixture')


def test_D_a_negative_team_total_is_dealt_without_a_clip():
    print('\nD. GATE 3: a lawful negative team total')
    att, ints, K, Y, TD, atoms = _deal_fixture(neg=True, seed=5)
    check('the fixture really carries negative team totals', bool((Y < 0).any()),
          f'min team Y {float(Y.min())}')
    o = FE.credit_passing_line(att, ints, K, Y, TD,
                               np.random.default_rng(3),
                               atoms=atoms, atom_rng=np.random.default_rng(4))
    check('a negative total is dealt, not refused', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail[:200]}')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('D: refused a lawful negative total')
        return
    py = np.asarray(o.value['pyds'], float)
    neg = Y < 0
    check('the negative draws close exactly', bool(np.all(py[:, neg].sum(0) == Y[neg])),
          f'{int((py[:, neg].sum(0) != Y[neg]).sum())} bad draw(s)')
    check('nothing was clipped at zero: negative credits survive',
          bool((py[:, neg] < 0).any()), 'every credited cell is >= 0, which '
          'would mean a clip')


def test_E_the_deal_is_deterministic_and_refuses_bad_atoms():
    print('\nE. GATE 5 and the named refusals')
    att, ints, K, Y, TD, atoms = _deal_fixture(seed=9)
    a = FE.credit_passing_line(att, ints, K, Y, TD, np.random.default_rng(2),
                               atoms=atoms, atom_rng=np.random.default_rng(3))
    b = FE.credit_passing_line(att, ints, K, Y, TD, np.random.default_rng(2),
                               atoms=atoms, atom_rng=np.random.default_rng(3))
    check('GATE 5: two runs at one seed are byte-identical',
          a.state is State.PASS and b.state is State.PASS
          and np.asarray(a.value['pyds']).tobytes()
          == np.asarray(b.value['pyds']).tobytes(),
          f'{a.state}[{a.code}] / {b.state}[{b.code}]')
    # Atom count that does not match the completion count.
    bad = [x.copy() for x in atoms]
    j = next((j for j in range(len(bad)) if len(bad[j])), 0)
    bad[j] = np.append(bad[j], 7.0)
    o = FE.credit_passing_line(att, ints, K, Y, TD, np.random.default_rng(2),
                               atoms=bad, atom_rng=np.random.default_rng(3))
    check('an atom count that disagrees with the completions is REFUSED BY NAME',
          o.state is State.FAIL and o.code == 'PASSER_CREDIT_ATOM_COUNT_MISMATCH',
          f'{o.state}[{o.code}]')
    # Atoms that do not sum to the declared team total.
    bad2 = [x.copy() for x in atoms]
    if len(bad2[j]):
        bad2[j][0] += 1.0
    o2 = FE.credit_passing_line(att, ints, K, Y, TD, np.random.default_rng(2),
                                atoms=bad2, atom_rng=np.random.default_rng(3))
    check('atoms that do not sum to the team total are REFUSED BY NAME',
          o2.state is State.FAIL
          and o2.code == 'PASSER_CREDIT_ATOM_TOTAL_MISMATCH',
          f'{o2.state}[{o2.code}]')
    # A non-integer atom.
    bad3 = [x.copy() for x in atoms]
    if len(bad3[j]):
        bad3[j][0] += 0.5
        Y3 = Y.copy()
        Y3[j] += 0.5
        o3 = FE.credit_passing_line(att, ints, K, Y3, TD,
                                    np.random.default_rng(2),
                                    atoms=bad3, atom_rng=np.random.default_rng(3))
        check('a non-integer atom is REFUSED BY NAME rather than rounded',
              o3.state is State.FAIL
              and o3.code == 'PASSER_CREDIT_ATOM_NON_INTEGER',
              f'{o3.state}[{o3.code}]')
    else:
        NOT_EXECUTED.append('E: no non-empty atom vector in the fixture')


def test_F_without_atoms_the_incumbent_is_bit_for_bit_unchanged():
    print('\nF. GATE 6: every frozen arm is untouched')
    att, ints, K, Y, TD, atoms = _deal_fixture(seed=13)
    old = FE.credit_passing_line(att, ints, K, Y, TD, np.random.default_rng(77))
    check('the incumbent path still passes', old.state is State.PASS,
          f'{old.state}[{old.code}]')
    if old.state is not State.PASS:
        NOT_EXECUTED.append('F: incumbent refused')
        return
    py = np.asarray(old.value['pyds'], float)
    check('the incumbent still divides the total, so it is still '
          'NON-INTEGER -- the defect this repair is for',
          bool((py != np.rint(py)).any()),
          'the incumbent emitted only integers, which means the fixture no '
          'longer exercises the defect')
    check('the incumbent consumed NO atom stream: rng state is what it was',
          FE.credit_passing_line(att, ints, K, Y, TD,
                                 np.random.default_rng(77)
                                 ).value['pyds'].tobytes() == py.tobytes(),
          'the incumbent is no longer reproducible at a fixed seed')
    # And the atom path must differ from it, or the repair does nothing.
    new = FE.credit_passing_line(att, ints, K, Y, TD, np.random.default_rng(77),
                                 atoms=atoms, atom_rng=np.random.default_rng(78))
    check('the atom deal DIFFERS from the incumbent (the arm is a real arm)',
          new.state is State.PASS
          and np.asarray(new.value['pyds']).tobytes() != py.tobytes(),
          'the two arms are identical, so the candidate is not a candidate')
    check('but the COMPLETIONS are untouched by the yardage change',
          new.state is State.PASS
          and np.asarray(new.value['cmp']).tobytes()
          == np.asarray(old.value['cmp']).tobytes(),
          'the atom deal moved the completion allocation, which it must not: '
          'the yardage rng is a separate stream on purpose')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_atoms_are_exposed_and_well_formed,
               test_B_the_change_is_additive_against_the_pinned_source,
               test_C_the_deal_closes_exactly_and_stays_integer,
               test_D_a_negative_team_total_is_dealt_without_a_clip,
               test_E_the_deal_is_deterministic_and_refuses_bad_atoms,
               test_F_without_atoms_the_incumbent_is_bit_for_bit_unchanged):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
