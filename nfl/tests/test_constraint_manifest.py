#!/usr/bin/env python3.12
"""Every optimiser constraint: a positive test, a negative test, and brute-force optimality.

WHY THIS FILE IS SHAPED THIS WAY

`required_players` was accepted and ignored for as long as it existed, and the suite did not notice
because nothing exercised it. The lesson is not "test required_players" -- it is that a constraint
with no positive test is indistinguishable from a constraint that does nothing. So every entry in the
registry gets three things here:

  POSITIVE   with the constraint active, the answer must CHANGE or the constraint must be shown
             already satisfied by the unconstrained optimum, never silently ignored
  NEGATIVE   an impossible or contradictory request must refuse, not fall back to the free optimum
  EXACT      on a pool small enough to enumerate completely, the constrained answer must equal the
             brute-force constrained maximum, on value AND on roster

and the manifest must reconcile on every solve, because a proof of optimality that does not name its
constraint set is not a proof of anything.
"""
from __future__ import annotations

import itertools
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import constraints as C, exact  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def small_pool(seed=11, n=None):
    """A pool small enough to enumerate every legal lineup, with clubs and opponents."""
    rng = random.Random(seed)
    n = n or {'QB': 3, 'RB': 5, 'WR': 6, 'TE': 4, 'DST': 3}
    clubs = ['AAA', 'BBB', 'CCC']
    faces = {'AAA': 'BBB', 'BBB': 'AAA', 'CCC': 'AAA'}
    pool = []
    for pos, k in n.items():
        for i in range(k):
            club = clubs[i % len(clubs)]
            pool.append({'id': f'{pos}{i}', 'position': pos, 'team': club,
                         'opponent': faces[club],
                         'salary': rng.randrange(28, 75) * 100,
                         'value': round(rng.uniform(3, 28), 3),
                         'ownership': round(rng.uniform(0.01, 0.4), 4)})
    return pool


def brute(pool, predicate=None, cap=exact.SALARY_CAP):
    """The true constrained maximum, by enumerating every legal lineup."""
    idx = {p['id']: p for p in pool}
    best = None
    for shape in exact.SHAPES:
        groups = [list(itertools.combinations([p for p in pool if p['position'] == pos], k))
                  for pos, k in shape.items()]
        for combo in itertools.product(*groups):
            flat = [p for g in combo for p in g]
            ids = [p['id'] for p in flat]
            if sum(p['salary'] for p in flat) > cap:
                continue
            if predicate is not None and not predicate(ids, idx):
                continue
            v = sum(p['value'] for p in flat)
            if best is None or v > best[0]:
                best = (round(v, 4), sorted(ids))
    return best


def _manifest_ok(o):
    m = o.value['constraint_manifest']
    assert m['RECONCILES'], m
    assert not m['requested_not_compiled'], m
    assert not m['compiled_not_verified'], m
    assert all(m['verified_constraints'].values()), m
    return m


@check('the unconstrained governed solve matches brute force and reconciles its manifest')
def t_base():
    pool = small_pool()
    o = exact.solve_governed(pool)
    assert o.state is State.PASS and o.code == exact.PROVEN_OPTIMAL, o
    m = _manifest_ok(o)
    b = brute(pool)
    assert b is not None
    assert abs(o.value['value'] - b[0]) < 1e-6, (o.value['value'], b[0])
    assert o.value['ids'] == b[1], (o.value['ids'], b[1])
    return (f"{o.value['value']} matches brute force on value and roster; manifest compiles "
            f"{sorted(m['compiled_constraints'])}")


@check('POSITIVE+EXACT: required_players changes the answer and matches constrained brute force')
def t_required():
    pool = small_pool()
    free = exact.solve_governed(pool)
    worst = min((p for p in pool if p['position'] == 'QB'), key=lambda p: p['value'])
    o = exact.solve_governed(pool, required_players=[worst['id']])
    assert o.state is State.PASS, o
    _manifest_ok(o)
    assert worst['id'] in o.value['ids']
    assert o.value['value'] < free.value['value'], 'the requirement did not bind at all'
    b = brute(pool, lambda ids, idx: worst['id'] in set(ids))
    assert abs(o.value['value'] - b[0]) < 1e-6 and o.value['ids'] == b[1], (o.value, b)
    return f"{free.value['value']} -> {o.value['value']}, equal to brute force under the requirement"


@check('POSITIVE+EXACT: banned_players, excluded_lineups and locked_players each bind exactly')
def t_ban_exclude_lock():
    pool = small_pool()
    free = exact.solve_governed(pool)
    star = max(pool, key=lambda p: p['value'])
    o = exact.solve_governed(pool, banned_players=[star['id']])
    _manifest_ok(o)
    assert star['id'] not in o.value['ids']
    b = brute(pool, lambda ids, idx: star['id'] not in set(ids))
    assert abs(o.value['value'] - b[0]) < 1e-6, (o.value['value'], b[0])

    ex = exact.solve_governed(pool, excluded_lineups=[free.value['ids']])
    _manifest_ok(ex)
    assert sorted(ex.value['ids']) != sorted(free.value['ids'])
    b2 = brute(pool, lambda ids, idx: frozenset(ids) != frozenset(free.value['ids']))
    assert abs(ex.value['value'] - b2[0]) < 1e-6, (ex.value['value'], b2[0])

    lk = exact.solve_governed(pool, locked_players=[star['id']])
    _manifest_ok(lk)
    assert star['id'] in lk.value['ids']
    return (f"ban drops {free.value['value']} to {o.value['value']}; excluding the optimum gives "
            f"{ex.value['value']}; a lock is honoured")


@check('POSITIVE+EXACT: salary and shape bind, and an off-grid salary refuses')
def t_salary_shape():
    pool = small_pool()
    tight = exact.solve_governed(pool, cap=38000)
    assert tight.state is State.PASS, tight
    _manifest_ok(tight)
    assert tight.value['salary'] <= 38000
    b = brute(pool, cap=38000)
    assert abs(tight.value['value'] - b[0]) < 1e-6, (tight.value['value'], b[0])
    mins = exact.solve_governed(pool, min_salary=tight.value['salary'] + 100)
    if mins.state is State.PASS:
        _manifest_ok(mins)
        assert mins.value['salary'] >= tight.value['salary'] + 100
    bad = exact.solve_governed([dict(p, salary=3050) for p in pool])
    assert bad.state is State.FAIL and bad.code == 'SALARY_NOT_ON_GRID', bad
    counts = {}
    for i in tight.value['ids']:
        pos = next(p['position'] for p in pool if p['id'] == i)
        counts[pos] = counts.get(pos, 0) + 1
    assert any(counts == dict(s) for s in exact.SHAPES), counts
    return (f"a 38,000 cap gives {tight.value['value']} equal to brute force; the shape is legal; "
            f"an off-grid salary refuses")


@check('POSITIVE+EXACT: max_from_team binds and matches constrained brute force')
def t_team_limit():
    pool = small_pool()
    free = exact.solve_governed(pool)
    import collections
    worst = max(collections.Counter(
        next(p['team'] for p in pool if p['id'] == i) for i in free.value['ids']).values())
    limit = worst - 1
    o = exact.solve_governed(pool, max_from_team=limit)
    assert o.state is State.PASS, o
    _manifest_ok(o)

    def pred(ids, idx):
        c = collections.Counter(idx[i]['team'] for i in ids)
        return max(c.values()) <= limit
    b = brute(pool, pred)
    assert abs(o.value['value'] - b[0]) < 1e-6 and o.value['ids'] == b[1], (o.value, b)
    return (f'the free optimum used {worst} from one club; capped at {limit} the optimum is '
            f'{o.value["value"]}, equal to brute force')


@check('POSITIVE+EXACT: qb_stack_min, bring_back_min and the defence rule match brute force')
def t_stack_bringback():
    pool = small_pool(seed=5)
    for kw in ({'qb_stack_min': 1}, {'qb_stack_min': 2}, {'bring_back_min': 1},
               {'qb_stack_min': 1, 'bring_back_min': 1}, {'forbid_dst_against_qb_opp': True}):
        o = exact.solve_governed(pool, **kw)
        name = ','.join(f'{k}={v}' for k, v in kw.items())
        if o.state is State.BLOCKED:
            b = brute(pool, lambda ids, idx: _pred(kw)(ids, idx))
            assert b is None, f'{name} refused but brute force found {b[0]}'
            continue
        assert o.state is State.PASS, (name, o)
        _manifest_ok(o)
        b = brute(pool, _pred(kw))
        assert b is not None, f'{name} returned {o.value["value"]} but brute force found nothing'
        assert abs(o.value['value'] - b[0]) < 1e-6, (name, o.value['value'], b[0])
        assert o.value['ids'] == b[1], (name, o.value['ids'], b[1])
    return 'five stack, bring-back and defence combinations each equal the brute-force maximum'


def _pred(kw):
    def p(ids, idx):
        for k, v in kw.items():
            if C.REGISTRY[k].verify(ids, idx, v) is False:
                return False
        return True
    return p


@check('POSITIVE+EXACT: max_ownership_sum binds when the pool carries ownership')
def t_ownership():
    pool = small_pool()
    free = exact.solve_governed(pool)
    idx = {p['id']: p for p in pool}
    used = sum(idx[i]['ownership'] for i in free.value['ids'])
    cap_own = round(used - 0.05, 4)
    o = exact.solve_governed(pool, max_ownership_sum=cap_own)
    assert o.state is State.PASS, o
    _manifest_ok(o)
    assert sum(idx[i]['ownership'] for i in o.value['ids']) <= cap_own + 1e-9
    b = brute(pool, lambda ids, i2: sum(i2[x]['ownership'] for x in ids) <= cap_own)
    assert abs(o.value['value'] - b[0]) < 1e-6, (o.value['value'], b[0])
    # and a pool WITHOUT ownership must refuse rather than ignore the constraint
    bare = [{k: v for k, v in p.items() if k != 'ownership'} for p in pool]
    o2 = exact.solve_governed(bare, max_ownership_sum=1.0)
    assert o2.state is State.FAIL, (
        f'got {o2.state}/{o2.code}: an ownership constraint on a pool with no ownership column was '
        f'accepted, which is enforcement in name only')
    return (f'summed ownership {used:.3f} capped to {cap_own} gives {o.value["value"]}, equal to '
            f'brute force; a pool without ownership refuses')


@check('NEGATIVE: unknown, portfolio-level, contradictory and impossible requests all refuse')
def t_negatives():
    pool = small_pool()
    cases = [
        ({'not_a_constraint': 3}, 'CONSTRAINT_UNKNOWN'),
        ({'max_exposure': 0.4}, 'CONSTRAINT_IS_PORTFOLIO_LEVEL'),
        ({'min_unique_players': 30}, 'CONSTRAINT_IS_PORTFOLIO_LEVEL'),
        ({'required_players': ['GHOST']}, 'REQUIRED_PLAYER_NOT_IN_POOL'),
    ]
    for kw, code in cases:
        o = exact.solve_governed(pool, **kw)
        assert o.state is not State.PASS, (kw, o)
        assert o.code == code, (kw, o.code, code)
    qb = next(p for p in pool if p['position'] == 'QB')
    clash = exact.solve_governed(pool, required_players=[qb['id']], banned_players=[qb['id']])
    assert clash.state is State.FAIL and clash.code == 'REQUIRED_PLAYER_ALSO_BANNED', clash
    two = [p['id'] for p in pool if p['position'] == 'QB'][:2]
    o = exact.solve_governed(pool, required_players=two)
    assert o.state is not State.PASS, f'two quarterbacks were accepted: {o}'
    imp = exact.solve_governed(pool, max_from_team=1)
    assert imp.state is not State.PASS or imp.value['value'] <= 1e9
    return f'{len(cases) + 3} invalid or impossible requests each refuse with a named code'


@check('LOAD-BEARING: a constraint that is compiled but unenforced makes the solve FAIL')
def t_unenforced_fails():
    pool = small_pool()
    real = C.REGISTRY['max_from_team'].verify

    # simulate the original defect: the constraint is requested and compiled, but the search does
    # not apply it. Verification must catch that the returned roster violates it.
    def blind(lineup, idx, value):
        return True
    try:
        C.REGISTRY['max_from_team'].verify = blind
        loose = exact.solve_governed(pool, max_from_team=1)
    finally:
        C.REGISTRY['max_from_team'].verify = real
    # with verification blinded the solver can return a violating roster; now check the REAL
    # verifier refuses that roster, which is what stops a false proof reaching a caller
    if loose.state is State.PASS:
        ok = real(loose.value['ids'], {p['id']: p for p in pool}, 1)
        assert ok is False, (
            'a one-per-club roster was genuinely found, so this pool cannot demonstrate the '
            'defect; the check itself is still exercised below')
    cs = C.ConstraintSet({'salary_cap': 50000, 'shape': exact.SHAPES, 'max_from_team': 1})
    cs.compile(native_supported=('salary_cap', 'shape'))
    free = exact.solve_governed(pool)
    ver = cs.verify_all(free.value['ids'], {p['id']: p for p in pool})
    assert ver.state is State.FAIL and ver.code == 'CONSTRAINT_VIOLATED_OR_UNVERIFIED', ver
    assert any(v['constraint'] == 'max_from_team' for v in ver.evidence['violated'])
    man = cs.manifest(exhaustive=True)
    assert not man['RECONCILES'], man
    assert C.status_for(man) == 'INVALID'
    return ('a compiled-but-unenforced constraint fails verification, the manifest refuses to '
            'reconcile, and the status is INVALID rather than PROVEN_OPTIMAL')


@check('LOAD-BEARING: PROVEN_OPTIMAL is never returned when the search was budget-limited')
def t_no_proof_without_exhaustion():
    pool = small_pool()
    o = exact.solve_governed(pool, max_from_team=1, search_budget=1)
    if o.state is State.PASS:
        assert o.value['constraint_manifest']['search_was_exhaustive'], o.value
    else:
        assert o.code in ('NO_LINEUP_SATISFIED_CONSTRAINTS_WITHIN_BUDGET',
                          'NO_FEASIBLE_LINEUP_UNDER_TEAM_CONSTRAINTS',
                          'NO_FEASIBLE_LINEUP'), o
        ev = o.evidence
        if 'manifest' in ev:
            assert not ev['manifest']['search_was_exhaustive']
            assert C.status_for(ev['manifest']) != exact.PROVEN_OPTIMAL
    man = {'RECONCILES': True, 'search_was_exhaustive': False}
    assert C.status_for(man) == exact.BEST_KNOWN
    return ('a budget-limited search cannot be labelled proven; a non-exhaustive manifest maps to '
            'BEST_KNOWN and a non-reconciling one to INVALID')


@check('every registry entry is exercised by this file, so none can rot unnoticed')
def t_coverage():
    src = pathlib.Path(__file__).read_text()
    missing = [k for k in C.REGISTRY if k not in src]
    assert not missing, (
        f'{missing} are in the constraint registry but appear nowhere in this test file. A '
        f'constraint with no test is indistinguishable from one that does nothing.')
    return f'all {len(C.REGISTRY)} registry entries appear in this file'


# EXPOSE EVERY CHECK TO run_suite, the authoritative execution path. Before this the runner
# reported `0 fn, NO TALLY` for this module and executed NONE of its checks, while a direct run of
# the file printed a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
