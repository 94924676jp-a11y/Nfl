"""A research portfolio that refuses the claims it cannot support.

WHAT THIS MODULE ASSERTS
========================
1. THE MEAN IS EXACT AND THE CEILING IS A LOWER BOUND, and both say so in
   their own fields. Dependence cannot move the mean of a sum; it moves p95 by
   about +51% on these marginals, so an independent-sum quantile is a floor
   under the true ceiling and is never labelled otherwise.
2. LEGAL SHOWDOWN CONSTRUCTION IS ENFORCED: six distinct players, both clubs
   represented, captain priced from the captain column, cap respected.
3. RANKING ON PROJECTION ALONE PRODUCES TEN SPELLINGS OF ONE BET. This is the
   regression test for a failure this module actually had: the first selector
   put one player in all ten lineups and covered zero of one declared thesis.
   Exposure and thesis caps are asserted to prevent it.
4. CONSTRAINTS ARE NEVER RELAXED TO REACH A ROUND NUMBER. A portfolio that
   cannot satisfy them comes back short, and an unmet thesis is reported
   rather than dropped.
5. AN UNBUILDABLE PORTFOLIO RAISES rather than returning a short list that
   looks complete.
6. THE SUMMARY CARRIES THE FORBIDDEN CLAIMS BY NAME, so the artifact itself
   states what it may not be read as.
"""
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs import research_portfolio as RP  # noqa: E402

PASSED = FAILED = BLOCKED = 0
RNG = np.random.default_rng(20260924)


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _pool(n=12):
    out = {}
    for i in range(n):
        out[f'P{i:02d}'] = {'team': 'ATL' if i % 2 else 'GB',
                            'pos': 'RB' if i % 3 == 0 else 'WR',
                            'CPT': 9000 - i * 300, 'FLEX': 6000 - i * 200}
    return out


def _marginals(pool):
    return {n: RNG.gamma(2.0, 4.0 + i, size=2000)
            for i, n in enumerate(pool)}


def _theses(pool):
    return [{'name': 'GB_LEAN',
             'holds': lambda lu, p: sum(1 for x in lu
                                        if p[x]['team'] == 'GB') >= 4},
            {'name': 'ATL_LEAN',
             'holds': lambda lu, p: sum(1 for x in lu
                                        if p[x]['team'] == 'ATL') >= 4}]


def test_mean_is_exact_and_ceiling_is_a_declared_lower_bound():
    pool = _pool()
    marg = _marginals(pool)
    lu = tuple(list(pool)[:6])
    s = RP.score(lu, marg)
    expect = (marg[lu[0]].mean() * RP.CAPTAIN_MULTIPLIER
              + sum(marg[n].mean() for n in lu[1:]))
    chk('the mean equals the sum of marginal means',
        abs(s['mean'] - expect) < 1e-9, f"{s['mean']} vs {expect}")
    chk('and says it is exact', 'EXACT' in s['mean_basis'])
    chk('the ceiling field is labelled a lower bound',
        'LOWER BOUND ONLY' in s['ceiling_basis'])
    chk('p95 is at or above p90', s['indep_sum_p95'] >= s['indep_sum_p90'])
    chk('the captain contribution carries the 1.5x',
        abs(s['per_player_mean'][lu[0]]
            - marg[lu[0]].mean() * 1.5) < 1e-9)


def test_legal_showdown_construction_is_enforced():
    pool = _pool()
    one_team = {n: v for n, v in pool.items() if v['team'] == 'GB'}
    lu = tuple(list(one_team)[:6])
    chk('a single-club lineup is illegal', not RP.legal(lu, pool))
    dup = (list(pool)[0],) + tuple([list(pool)[1]] * 5)
    chk('a lineup with repeats is illegal', not RP.legal(dup, pool))
    good = tuple(list(pool)[:6])
    chk('a two-club lineup of six distinct players is legal',
        RP.legal(good, pool))
    chk('captain salary comes from the captain column',
        RP.salary_of(good, pool)
        == pool[good[0]]['CPT'] + sum(pool[n]['FLEX'] for n in good[1:]))
    chk('an over-cap lineup is illegal', not RP.legal(good, pool, cap=100))


def test_projection_ranking_alone_collapses_the_portfolio():
    """The regression test for a failure this module had."""
    pool = _pool()
    marg = _marginals(pool)
    cands = RP.build_candidates(pool, marg, _theses(pool))
    loose = RP.select(cands, n=10, max_overlap=5, max_per_captain=10)
    exposure = {}
    for c in loose['lineups']:
        for p in c['lineup']:
            exposure[p] = exposure.get(p, 0) + 1
    chk('unconstrained selection concentrates on a few players',
        max(exposure.values()) >= 8, str(sorted(exposure.values())[-3:]))

    tight = RP.select(cands, n=10, max_overlap=4, max_per_captain=2,
                      max_player_exposure=6,
                      min_thesis_coverage={'GB_LEAN': 2, 'ATL_LEAN': 2})
    tight_exposure = {}
    for c in tight['lineups']:
        for p in c['lineup']:
            tight_exposure[p] = tight_exposure.get(p, 0) + 1
    chk('the exposure cap is respected',
        max(tight_exposure.values()) <= 6, str(max(tight_exposure.values())))
    caps = {}
    for c in tight['lineups']:
        caps[c['captain']] = caps.get(c['captain'], 0) + 1
    chk('the captain cap is respected', max(caps.values()) <= 2)
    covered = {t for c in tight['lineups'] for t in c['theses']}
    chk('both theses are covered', {'GB_LEAN', 'ATL_LEAN'} <= covered,
        str(covered))


def test_constraints_are_never_relaxed_to_reach_a_round_number():
    pool = _pool()
    marg = _marginals(pool)
    cands = RP.build_candidates(pool, marg, _theses(pool))
    impossible = RP.select(cands, n=10, max_overlap=0, max_per_captain=1,
                           max_player_exposure=1)
    chk('an impossible constraint set returns SHORT',
        impossible['short_by'] > 0, str(impossible['short_by']))
    chk('and says the constraints were not relaxed',
        'NOT relaxed' in impossible['note'], impossible['note'][:80])

    unmet = RP.select(cands, n=2, max_overlap=4, max_per_captain=2,
                      min_thesis_coverage={'NO_SUCH_THESIS': 3})
    chk('an unmet thesis is reported, not dropped',
        'unmet_thesis_coverage' in unmet
        and unmet['unmet_thesis_coverage'].get('NO_SUCH_THESIS'),
        str(unmet.get('unmet_thesis_coverage')))


def test_an_unbuildable_portfolio_raises():
    thin = {'A': {'team': 'GB', 'CPT': 1, 'FLEX': 1},
            'B': {'team': 'ATL', 'CPT': 1, 'FLEX': 1}}
    try:
        RP.build_candidates(thin, {'A': np.ones(5), 'B': np.ones(5)}, [])
        chk('too few players raises', False, 'it returned')
    except RP.PortfolioError as e:
        chk('too few players raises', 'Refusing to build' in str(e))
    pool = _pool()
    marg = _marginals(pool)
    try:
        RP.build_candidates(pool, marg, [], cap=1)
        chk('an impossible cap raises', False, 'it returned')
    except RP.PortfolioError as e:
        chk('an impossible cap raises', 'refusal, not an empty' in str(e))
    try:
        RP.select([], n=1)
        chk('selecting from nothing raises', False, 'it returned')
    except RP.PortfolioError:
        chk('selecting from nothing raises', True)


def test_the_summary_names_what_it_may_not_claim():
    pool = _pool()
    marg = _marginals(pool)
    cands = RP.build_candidates(pool, marg, _theses(pool))
    sel = RP.select(cands, n=6, max_overlap=4, max_per_captain=2,
                    max_player_exposure=5)
    s = RP.summarise(sel, pool)
    chk('the artifact carries the label',
        s['label'] == 'RESEARCH_DFS_PORTFOLIO_NOT_JOINT-WORLD_VALIDATED')
    for claim in ('lineup win probability', 'top-1 probability',
                  'measured cross-player correlation'):
        chk(f'forbidden claim named: {claim}', claim in s['forbidden_claims'])
    chk('the objective is stated in the artifact',
        'No term in this objective is a win probability' in s['objective'])
    chk('overlap is reported as a counted fact',
        s['pairwise_overlap']['max'] is not None)
    chk('and nothing in the reading promises a probability',
        'Nothing here is a probability of winning anything' in s['reading'])


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
