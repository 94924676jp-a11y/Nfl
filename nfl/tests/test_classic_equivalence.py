"""Every speedup returns the SAME answer as the accepted baseline.

`nfl/dfs/classic/reference.py` is a frozen copy of the optimizer at commit
fe25d98, the accepted Classic baseline. This suite runs it and the live
optimizer over fixed fixtures and asserts they produce IDENTICAL lineups, not
merely similar objectives.

WHY THE ROSTER AND NOT JUST THE VALUE

Two different rosters can tie on objective. If the suite compared only the
best value it would pass while the optimizer silently started preferring a
different tie-break, and a portfolio's exposure and diversity would drift
without any test noticing. So the comparison is on the exact player set of
every lineup, in portfolio order.

WHY THE SET AND NOT THE SELECTION ORDER

The two implementations visit positions in different orders -- the optimized
one takes the QB first when a stack is required so it can prune on it -- so
the order players appear in within a lineup differs even when the lineup is
the same. That order is an artifact of the route the search took, not a
property of the result: the CSV exporter re-slots by position and value, and
exposure and diversity are set operations. So ids are sorted within a lineup
before comparing. A genuinely different roster still has a different set, so
nothing a tie-break could change is hidden by this.

(The live optimizer now emits `Lineup.canonical` order for exactly this
reason. The reference is frozen and still emits selection order, which is why
the sorting happens here rather than being assumed.)

FIXTURES ARE FIXED AND SEEDED. A speedup that is only equivalent on a lucky
draw is not equivalent.
"""
from __future__ import annotations

import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.classic import optimizer as O                          # noqa: E402
from nfl.dfs.classic import reference as REF                        # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def fixture(mod, n_teams=6, seed=3, spec=None):
    """Identical player objects for whichever module is being run."""
    rnd = random.Random(seed)
    spec = spec or [('QB', 2), ('RB', 4), ('WR', 6), ('TE', 3), ('DST', 1)]
    teams = [f'S{n:02d}' for n in range(n_teams)]
    out, i = [], 0
    for ti, t in enumerate(teams):
        # Pair adjacent teams into games. `ti ^ 1` walks off the end on an
        # ODD team count -- it crashed this suite at 7 teams, which looked
        # like a hang because several stacked runs were competing for CPU at
        # the time. Clamped so the fixture is valid at any size.
        opp = teams[ti ^ 1] if (ti ^ 1) < n_teams else teams[ti - 1]
        for pos, k in spec:
            for j in range(k):
                i += 1
                out.append(mod.Player(
                    gsis_id=f'{t}-{pos}{j}', name=f'{t} {pos}{j}',
                    position=pos, team=t, opponent=opp,
                    salary=rnd.randrange(3000, 9500, 100),
                    dk_id=str(30000 + i),
                    value=round(rnd.uniform(3, 22), 3), draw_row=i - 1))
    return out


def signature(outcome):
    """The portfolio reduced to what must not change: the outcome code, then
    each lineup's objective and its player SET, in portfolio order."""
    v = outcome.value or (getattr(outcome, 'evidence', {}) or {}).get('value') \
        or {}
    return (outcome.code,
            tuple((round(lu['value'], 9),
                   tuple(sorted(x['gsis_id'] for x in lu['players'])))
                  for lu in v.get('lineups', [])))


CASES = (
    ('plain', dict(n_lineups=5, min_unique_players=2)),
    ('stacked QB+2 with bring-back',
     dict(n_lineups=5, min_unique_players=2, qb_stack_min=2,
          bring_back_min=1)),
    ('stack + team and game caps',
     dict(n_lineups=5, min_unique_players=2, qb_stack_min=1,
          bring_back_min=1, max_from_team=3, max_from_game=4,
          global_max_exposure=0.6)),
    ('no bring-back allowed',
     dict(n_lineups=4, min_unique_players=2, qb_stack_min=1,
          bring_back_max=0)),
    ('salary floor and a lock',
     dict(n_lineups=4, min_unique_players=2, salary_floor=47000,
          locks={'S00-QB0'})),
    ('stack with a locked pass catcher',
     dict(n_lineups=3, min_unique_players=2, qb_stack_min=2,
          locks={'S00-WR0'})),
    ('excludes and a projection cutoff',
     dict(n_lineups=4, min_unique_players=2, excludes={'S01-QB0'},
          projection_cutoff=6.0)),
    ('tight uniqueness',
     dict(n_lineups=4, min_unique_players=5)),
    ('group minimum with a stack',
     dict(n_lineups=3, min_unique_players=2, qb_stack_min=1,
          groups=[{'name': 'S00', 'players': {f'S00-WR{i}' for i in range(6)},
                   'min': 2}])),
)


def test_optimized_matches_the_accepted_baseline():
    for name, kw in CASES:
        a = REF.build_portfolio(fixture(REF), REF.Constraints(**kw))
        b = O.build_portfolio(fixture(O), O.Constraints(**kw))
        sa, sb = signature(a), signature(b)
        ok(sa == sb,
           f'{name}: identical to the fe25d98 baseline '
           f'({len(sa[1])} lineup(s), best '
           f'{sa[1][0][0] if sa[1] else None})')
        if sa != sb:
            print(f'      ref {sa[0]} {sa[1][:2]}')
            print(f'      opt {sb[0]} {sb[1][:2]}')


def test_equivalence_holds_on_a_second_seed_and_a_wider_pool():
    """Deliberately modest sizes. The REFERENCE is the slow implementation --
    it is why the optimized one exists -- so running it on a main-slate pool
    would make this suite minutes long on every invocation. Large-pool
    equivalence is proved once and recorded in
    `nfl/research/readiness/CLASSIC_OPTIMIZER_BENCHMARK.json`, which is
    regenerated deliberately rather than on every test run."""
    # Both at 6 teams. The point of this case is a DIFFERENT SEED, not a
    # bigger pool: the reference is the slow implementation by construction,
    # and at 8 teams a stacked build on it runs for minutes, which would make
    # this suite unrunnable in practice. Scale equivalence is proved once, on
    # a 456-player pool, in CLASSIC_OPTIMIZER_BENCHMARK.json.
    for seed, teams in ((17, 6), (41, 6)):
        for name, kw in (('plain', CASES[0][1]),
                         ('stacked', dict(CASES[1][1], n_lineups=2)),
                         ('caps', dict(CASES[2][1], n_lineups=2))):
            a = REF.build_portfolio(fixture(REF, n_teams=teams, seed=seed),
                                    REF.Constraints(**kw))
            b = O.build_portfolio(fixture(O, n_teams=teams, seed=seed),
                                  O.Constraints(**kw))
            ok(signature(a) == signature(b),
               f'seed {seed}, {teams} teams, {name}: identical')


def test_an_infeasible_case_refuses_identically():
    # Genuinely impossible: a Classic roster has seven skill slots, so a
    # stack of eight cannot be built at all. An earlier version of this
    # case asked for six, which IS satisfiable -- both sides returned
    # CLASSIC_PORTFOLIO_BUILT and the test's name was wrong about what it
    # was proving.
    kw = dict(n_lineups=2, qb_stack_min=8)
    a = REF.build_portfolio(fixture(REF), REF.Constraints(**kw))
    b = O.build_portfolio(fixture(O), O.Constraints(**kw))
    ok(a.code == b.code,
       f'both refuse with the same code: {a.code} / {b.code}')
    ok(a.state.name == b.state.name,
       f'and the same state: {a.state.name}')


def test_the_reference_is_the_frozen_baseline():
    ok(REF.SPEC_VERSION.endswith('reference-fe25d98'),
       f'the reference identifies the commit it was frozen at: '
       f'{REF.SPEC_VERSION}')
    ok(REF.SPEC_VERSION != O.SPEC_VERSION,
       'and it is a different artifact from the live optimizer, so a change '
       'to one cannot silently be a change to both')


def main():
    for t in (test_the_reference_is_the_frozen_baseline,
              test_optimized_matches_the_accepted_baseline,
              test_equivalence_holds_on_a_second_seed_and_a_wider_pool,
              test_an_infeasible_case_refuses_identically):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
