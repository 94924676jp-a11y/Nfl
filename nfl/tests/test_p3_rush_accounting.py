"""P3: QB rush accounting and composition, DECOMPOSED.

WHY THIS FILE IS DECOMPOSED AND THE PRODUCT GATE IS NOT

`quality_gates.gate_rush_accounting` compares ONE quantity against the team
carry level: `RB carries + QB scrambles + QB designed runs`. That is the right
quantity to gate on -- a quarterback run is one of the team's carries exactly
as a running back's is -- and the wrong one to repair from, because it sums two
layers and cannot say which of them broke. An earlier workstream read the fired
gate as a defect in A1's multinomial and wrote a repair for the running-back
deal. Decomposed against the sealed arrays of `96954efc523bd7d3`:

    board 2026_01_DEN_KC / 96954efc523bd7d3, V1_CANDIDATE_R9, 1,000 draws
      RB carries only     DEN 2 draws positive, max +0.2619, 0 over the gate
                          KC  2 draws positive, max +0.0854, 0 over the gate
      RB + QB rush opp    DEN 206 positive, 149 over the gate, max +6.1219
                          KC  237 positive, 148 over the gate, max +9.6915

The multinomial is sound. The impossibility enters with the quarterback.

WHAT EACH TEST IS FOR

A and B are the REPRODUCTION, one per decomposition half, measured on the
sealed cohort. They stay in the file after the repair: they record the defect
at its measured size on the board that carries it, and a board sealed before a
repair does not stop carrying what it carried.

C is the same reproduction at CONSTRUCTION level rather than corpus level: the
unwired composition -- `allocate()` with A1 drawing its own `designed_qb` while
the QB layer draws `rush_opp` -- breaches containment on synthetic inputs with
no board involved.

D through H are the REPAIR. They are written against
`rushing_a1.compose_rush_ownership`, and before that function existed every one
of them failed. They assert the constraint holds BY CONSTRUCTION -- for every
input the composition accepts, not for the inputs that happen to be in a
corpus.

I is the bypass: the containment assertion is shown to REJECT a seeded breach,
so the passes above come from the guard rather than from clean inputs.

NOTHING HERE TUNES TO DEN@KC. The realized 2026-09-15 outcome is not in this
repository -- the newest play-by-play capture predates kickoff and holds zero
DEN or KC rows -- so no realized carry count appears in this file as a target.
The sealed board is used as a FIXTURE OF THE DEFECT, never as a scoreboard.
"""
from __future__ import annotations

import inspect
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'own9')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State               # noqa: E402
from nfl.production.nonqb import rushing_a1 as R                  # noqa: E402

PASSED = FAILED = BLOCKED = 0

# The product gate's own tolerance, imported rather than retyped so the fence
# and the gate cannot drift apart.
from nfl.product.quality_gates import GROUNDING                   # noqa: E402
TOL = GROUNDING['RUSH_OVERALLOCATION_TOLERANCE']['value']
EPS = 1e-9

COHORT = pathlib.Path(_ROOT) / (
    'nfl/research/live/2026_01_DEN_KC/'
    'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R9/96954efc523bd7d3')


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


# ------------------------------------------------------------- the cohort
def _cohort():
    """The sealed arrays, decomposed per team. None when the board is absent.

    An absent board is BLOCKED, never a pass: "the fixture was missing" and
    "containment holds" are different answers.
    """
    if not (COHORT / 'player_draws.npz').exists():
        return None
    z = np.load(COHORT / 'player_draws.npz')
    man = json.loads((COHORT / 'player_draws_manifest.json').read_text())
    board = json.loads((COHORT / 'board.json').read_text())
    team_of = {p['gsis_id']: p.get('team') for p in (board.get('players') or [])}
    lay = man['layers']
    tv = {t: i for i, t in enumerate(lay['team_volume']['row_ids'])}
    qb_ids, rush_ids = lay['qb']['row_ids'], lay['rushing']['row_ids']
    rc = {t: i for i, t in enumerate(lay['rush_category']['row_ids'])}
    out = {}
    for t in lay['team_volume']['row_ids']:
        qi = [i for i, g in enumerate(qb_ids) if team_of.get(g) == t]
        ri = [i for i, g in enumerate(rush_ids) if team_of.get(g) == t]
        lev = z['team_volume__team_carries'][tv[t]].astype(np.float64)
        out[t] = {
            'lev': lev,
            'ro': z['qb__rush_opp'][qi].sum(0).astype(np.float64),
            'scr': z['qb__scr'][qi].sum(0).astype(np.float64),
            'rb': z['rushing__carries'][ri].sum(0).astype(np.float64),
            'cat': {c: z['rush_category__' + c][rc[t]].astype(np.float64)
                    for c in R.CATEGORIES}}
    return out


def test_a_rb_only_containment_holds_on_the_sealed_cohort():
    """HALF ONE OF THE DECOMPOSITION. The running-back deal is sound."""
    co = _cohort()
    if co is None:
        blocked('rb_only_containment', f'no sealed board at {COHORT}')
        return
    for t, d in sorted(co.items()):
        over = d['rb'] - d['lev']
        check(f'{t}: RB carries alone never exceed the gate tolerance',
              int((over > TOL).sum()) == 0,
              f'{int((over > TOL).sum())} draws, max {over.max():+.4f}')
        # The two positive draws are NAMED rather than rounded away: the level
        # A1 partitioned is `rint(level)` and the board publishes the
        # continuous one, so a back can hold up to half a carry more than the
        # published level without any carry having two owners.
        check(f'{t}: the positive RB-only draws are sub-carry',
              float(over.max()) < 0.5,
              f'max {over.max():+.4f}')


def test_b_rb_plus_qb_containment_breaches_on_the_sealed_cohort():
    """HALF TWO. The impossibility is in the quarterback's rush opportunity.

    This test asserts the BREACH. It is the reproduction, and it passes for as
    long as the board it reads carries the defect -- which is permanently,
    because a sealed board is not rebuilt.
    """
    co = _cohort()
    if co is None:
        blocked('rb_plus_qb_containment', f'no sealed board at {COHORT}')
        return
    for t, d in sorted(co.items()):
        over = d['rb'] + d['ro'] - d['lev']
        n_over, mx = int((over > TOL).sum()), float(over.max())
        check(f'{t}: RB + QB rush opportunity DOES breach on this board',
              n_over > 0 and mx > 1.0, f'{n_over} draws, max {mx:+.4f}')
        # And the breach is LARGER than the RB-only one by orders, which is
        # what aims the repair.
        rb_only = float((d['rb'] - d['lev']).max())
        check(f'{t}: the QB-inclusive breach dwarfs the RB-only residual',
              mx > 10 * max(rb_only, 1e-3), f'{mx:+.4f} vs {rb_only:+.4f}')
        # TWO ANSWERS FOR ONE QUANTITY, on the same board.
        dis = int((np.abs(d['cat']['designed_qb']
                          - (d['ro'] - d['scr'])) > EPS).sum())
        check(f'{t}: designed QB runs have TWO answers on this board',
              dis > 0, f'{dis} cells disagree')
        # The category partition DOES close in its declared form. The
        # 8.4278 / 10.2027 non-closure that was reported compares the six
        # categories against the CONTINUOUS level and omits the scrambles,
        # which A1 subtracts from the budget before partitioning.
        tot = sum(d['cat'].values())
        check(f'{t}: the A1 partition closes as declared '
              f'(categories + scrambles == integer level)',
              int((np.abs(tot + d['scr'] - np.rint(d['lev'])) > EPS).sum()) == 0,
              f'max |diff| {np.abs(tot + d["scr"] - np.rint(d["lev"])).max()}')


# ------------------------------------------------------- synthetic fixtures
LEAGUE = dict(zip(R.CATEGORIES, (0.028, 0.075, 0.800, 0.042, 0.004, 0.006)))
TEAMS = ('DEN', 'KC')


def _params(seed=11, resid_sd=0.02, n_hist=14):
    rng = np.random.default_rng(seed)
    return {
        'spec_version': R.SPEC_VERSION, 'season': 2026, 'week': 1,
        'history_cut_ord': 202601, 'categories': list(R.CATEGORIES),
        'k_shrink': R.K_SHRINK, 'ewma_halflife': R.EWMA_HALFLIFE,
        'league': dict(LEAGUE),
        'resid': {c: rng.normal(0.0, resid_sd, 400).astype(np.float32)
                  for c in R.CATEGORIES},
        'history': {t: {'n': n_hist,
                        **{c: list(np.clip(rng.normal(v, 0.01, n_hist), 0, 1))
                           for c, v in LEAGUE.items()}}
                    for t in TEAMS},
        'seasons_used': [2022, 2023, 2024, 2025], 'n_train': 3000}


def _qb_layer(m=400, seed=7, teams=TEAMS):
    """A QB layer drawn INDEPENDENTLY of the carry level, which is the real
    situation: `qb_v1` draws scrambles and rush opportunity from its own
    streams and nothing ever made them agree with D1's carry draw."""
    rng = np.random.default_rng(seed)
    lev = {t: rng.normal(26.0, 5.0, m) for t in teams}
    scr = {t: rng.integers(0, 6, m).astype(np.float64) for t in teams}
    des = {t: rng.integers(0, 9, m).astype(np.float64) for t in teams}
    ro = {t: scr[t] + des[t] for t in teams}
    return lev, scr, ro


def test_c_unwired_composition_breaches_by_construction():
    """THE OLD PATH, on synthetic inputs, with no board involved.

    `run_forecast` coupled the carry level against the SCRAMBLES only and then
    called `allocate` without `qb_designed_rush`, so A1 drew its own answer to
    "how many carries did the quarterbacks take" while the QB layer kept its
    own. Named owners are `rb category + QB rush opportunity`, and the gap
    between the two answers is exactly the amount by which they can exceed the
    level.
    """
    from nfl.production.nonqb import scramble_coherence as SC1
    par = _params()
    lev, scr, ro = _qb_layer()
    m = lev[TEAMS[0]].size
    car = {}
    for t in TEAMS:
        o = SC1.couple(scr[t], lev[t])          # the OLD, weaker bound
        if o.state is not State.PASS:
            blocked('unwired_composition', f'{t}: {o.code}')
            return
        car[t] = o.value
    a = R.allocate(2026, 1, TEAMS, car, scr, m=m, seed=20260908, params=par,
                   level_rounding='round_half_even')
    if a.state is not State.PASS:
        blocked('unwired_composition', f'{a.code}: {a.detail[:120]}')
        return
    breached = 0
    for t in TEAMS:
        lvl = np.asarray(a.value['team_carries'][t], np.float64)
        owners = np.asarray(a.value['carries'][(t, 'rb')], np.float64) + ro[t]
        over = owners - lvl
        breached += int((over > TOL).sum())
        check(f'{t}: the UNWIRED composition over-allocates', 
              int((over > TOL).sum()) > 0,
              f'{int((over > TOL).sum())} of {m} draws, max {over.max():+.4f}')
    check('the unwired breach is present on synthetic inputs too',
          breached > 0, f'{breached} draw cells')


# ------------------------------------------------------------- the repair
def _composed(m=400, seed=7, teams=TEAMS):
    par = _params()
    lev, scr, ro = _qb_layer(m=m, seed=seed, teams=teams)
    return R.compose_rush_ownership(
        2026, 1, teams, team_carry_level=lev, qb_scrambles=scr,
        qb_rush_opportunity=ro, m=m, seed=20260908, params=par,
        level_rounding='round_half_even'), lev, scr, ro


def test_d_composed_rush_ownership_contains_named_owners():
    """THE REPAIR. Named backs + QB rush opportunity <= the PUBLISHED level.

    Asserted on the level `compose_rush_ownership` publishes, because a bound
    against a level the board does not carry is not a bound a reader can check.
    """
    if not hasattr(R, 'compose_rush_ownership'):
        check('rushing_a1 exposes compose_rush_ownership', False,
              'the composition does not exist, so the constraint cannot hold '
              'by construction')
        return
    o, lev, scr, ro = _composed()
    if o.state is not State.PASS:
        check('compose_rush_ownership runs on ordinary inputs', False,
              f'{o.code}: {o.detail[:160]}')
        return
    check('compose_rush_ownership runs on ordinary inputs', True)
    v = o.value
    for t in TEAMS:
        lvl = np.asarray(v['team_carries_published'][t], np.float64)
        rb_cat = np.asarray(v['allocation']['carries'][(t, 'rb')], np.float64)
        q = np.asarray(v['qb_rush_opportunity'][t], np.float64)
        over = rb_cat + q - lvl
        check(f'{t}: rb category + QB rush opportunity <= published level, '
              f'every draw', int((over > EPS).sum()) == 0,
              f'{int((over > EPS).sum())} draws, max {over.max():+.4f}')
        # And the DECOMPOSED halves, separately, because a single summed
        # check is what aimed the last repair at the wrong layer.
        check(f'{t}: RB-only containment holds against the published level',
              int((rb_cat - lvl > EPS).sum()) == 0)
        check(f'{t}: QB-only containment holds against the published level',
              int((q - lvl > EPS).sum()) == 0,
              f'max {(q - lvl).max():+.4f}')


def test_e_composed_has_one_answer_for_designed_qb_runs():
    """ONE QUANTITY, ONE VALUE. `rush_category.designed_qb` IS `rush_opp - scr`."""
    if not hasattr(R, 'compose_rush_ownership'):
        check('rushing_a1 exposes compose_rush_ownership', False, 'absent')
        return
    o, lev, scr, ro = _composed()
    if o.state is not State.PASS:
        check('compose_rush_ownership runs', False, o.code)
        return
    v = o.value
    for t in TEAMS:
        a1 = np.asarray(v['allocation']['carries'][(t, 'designed_qb')],
                        np.float64)
        qbl = np.asarray(v['qb_rush_opportunity'][t], np.float64) \
            - np.asarray(v['allocation']['scrambles'][t], np.float64)
        check(f'{t}: designed_qb has ONE answer, cell for cell',
              int((np.abs(a1 - qbl) > EPS).sum()) == 0,
              f'{int((np.abs(a1 - qbl) > EPS).sum())} cells disagree')
    check('the composition declares the QB layer as the single owner',
          o.evidence.get('rush_opportunity_single_owner') is True,
          str(o.evidence.get('rush_opportunity_single_owner')))


def test_f_composed_partition_closes_in_its_declared_form():
    """Categories + scrambles == the published integer level, every draw."""
    if not hasattr(R, 'compose_rush_ownership'):
        check('rushing_a1 exposes compose_rush_ownership', False, 'absent')
        return
    o, lev, scr, ro = _composed()
    if o.state is not State.PASS:
        check('compose_rush_ownership runs', False, o.code)
        return
    v = o.value
    for t in TEAMS:
        tot = sum(np.asarray(v['allocation']['carries'][(t, c)], np.float64)
                  for c in R.CATEGORIES)
        s = np.asarray(v['allocation']['scrambles'][t], np.float64)
        lvl = np.asarray(v['team_carries_published'][t], np.float64)
        check(f'{t}: the six categories plus scrambles equal the level',
              int((np.abs(tot + s - lvl) > EPS).sum()) == 0,
              f'max |diff| {np.abs(tot + s - lvl).max()}')


def test_g_published_level_is_the_level_that_was_partitioned():
    """The stored-vector defect, closed.

    `run_forecast` sealed D1's raw continuous level while the engine
    partitioned the SC1-coupled, integerised one. A containment breach against
    a denominator the game never used cannot be attributed, which is why
    `draw_coherence.team_qb_rush_opportunity_within_team_carries` is a
    DIAGNOSTIC rather than a gate. The composition publishes ONE vector.
    """
    if not hasattr(R, 'compose_rush_ownership'):
        check('rushing_a1 exposes compose_rush_ownership', False, 'absent')
        return
    o, lev, scr, ro = _composed()
    if o.state is not State.PASS:
        check('compose_rush_ownership runs', False, o.code)
        return
    v = o.value
    for t in TEAMS:
        pub = np.asarray(v['team_carries_published'][t], np.float64)
        part = np.asarray(v['allocation']['team_carries'][t], np.float64)
        check(f'{t}: the published level IS the partitioned level',
              np.array_equal(pub, part))
        check(f'{t}: the published level is integral',
              not (np.abs(pub - np.rint(pub)) > EPS).any())
        # A PERMUTATION, so the marginal is untouched element for element.
        check(f'{t}: the published level is a permutation of D1 rounded',
              np.array_equal(np.sort(pub), np.sort(np.rint(lev[t]))),
              'SC1 may only choose which draw receives which value')


def test_h_the_composition_neither_clips_nor_renormalises():
    """No clip, no truncation, no post-hoc rescale, no deleted draw."""
    if not hasattr(R, 'compose_rush_ownership'):
        check('rushing_a1 exposes compose_rush_ownership', False, 'absent')
        return
    src = inspect.getsource(R.compose_rush_ownership)
    for bad in ('np.clip', 'np.minimum', 'np.maximum', 'np.delete'):
        check(f'compose_rush_ownership contains no {bad}', bad not in src)
    o, lev, scr, ro = _composed()
    if o.state is not State.PASS:
        check('compose_rush_ownership runs', False, o.code)
        return
    for k in ('clipping_applied', 'survivor_renormalisation_applied',
              'post_hoc_repairs', 'deleted_draws'):
        check(f'the composition reports {k} == 0',
              int(o.evidence.get(k, -1)) == 0, str(o.evidence.get(k)))
    # The QB layer's own draws leave untouched.
    for t in TEAMS:
        check(f'{t}: the QB rush opportunity draw is passed through unchanged',
              np.array_equal(
                  np.asarray(o.value['qb_rush_opportunity'][t], np.float64),
                  np.asarray(ro[t], np.float64)))
        check(f'{t}: the scramble draw is passed through unchanged',
              np.array_equal(
                  np.asarray(o.value['allocation']['scrambles'][t], np.float64),
                  np.asarray(scr[t], np.float64)))


def test_i_the_containment_assertion_rejects_a_seeded_breach():
    """The guard is shown to REJECT, so the passes above come from the guard."""
    if not hasattr(R, 'assert_named_owner_containment'):
        check('rushing_a1 exposes assert_named_owner_containment', False,
              'absent')
        return
    m = 50
    lvl = {'DEN': np.full(m, 24, np.int64)}
    backs = {'DEN': np.full((3, m), 7, np.int64)}        # 21 carries
    ok = {'DEN': np.full(m, 3, np.int64)}                # 21 + 3 = 24
    o = R.assert_named_owner_containment(['DEN'], lvl, backs, ok)
    check('a compliant set PASSES', o.state is State.PASS,
          f'{o.code}: {o.detail[:120]}')
    bad = {'DEN': np.full(m, 4, np.int64)}               # 21 + 4 = 25 > 24
    o2 = R.assert_named_owner_containment(['DEN'], lvl, backs, bad)
    check('a seeded one-carry breach FAILS', o2.state is State.FAIL,
          f'{o2.state.value}[{o2.code}]')
    check('the refusal names the decomposed halves',
          'rb_only_draws_over' in o2.evidence
          and 'rb_plus_qb_draws_over' in o2.evidence,
          sorted(o2.evidence))
    check('the refusal repairs nothing it was handed',
          np.array_equal(bad['DEN'], np.full(m, 4, np.int64)))


def test_j_the_engine_records_the_decomposed_verdict():
    """The engine ASKS the decomposed question, and on the real path.

    Asserted on the source rather than by running a full game: `run_game` is a
    multi-minute composition over real artifacts and a fence that expensive
    gets skipped. What is checked is that the call exists, that it is inside
    `run_game`, and that its verdict is recorded under a named key -- the
    three things that would be absent if the verdict were computed in a
    rehearsal script instead of in the engine.

    THE GAP THIS DOES NOT CLOSE, NAMED RATHER THAN LEFT FOR A READER TO FIND.
    `g['accounting']` is not serialised into any sealed artifact -- neither
    this verdict nor `rush_opportunity_single_owner`, which has been in the
    engine since R4, appears in board.json, run_status.json or
    forecast_artifact.json. The containment IS auditable from a sealed board
    through `draw_coherence.components.carries`, which carries
    `team_carry_allocation_containment` and
    `team_qb_rush_opportunity_within_team_carries` cell counts. Publishing the
    engine accounting block is a separate repair with a separate owner.
    """
    import ast as _ast
    from nfl.production.nonqb import football_engine as FE
    src = pathlib.Path(FE.__file__).read_text()
    tree = _ast.parse(src)
    fn = next((n for n in _ast.walk(tree)
               if isinstance(n, _ast.FunctionDef) and n.name == 'run_game'),
              None)
    if fn is None:
        check('football_engine.run_game could be parsed', False)
        return
    body = _ast.dump(fn)
    check('run_game calls assert_named_owner_containment',
          'assert_named_owner_containment' in body)
    check('run_game records rush_named_owner_containment',
          'rush_named_owner_containment' in body)
    check('the engine reaches it through rushing_a1, not a private copy',
          'RA1' in _ast.dump(fn))


def main():
    for fn in (test_a_rb_only_containment_holds_on_the_sealed_cohort,
               test_b_rb_plus_qb_containment_breaches_on_the_sealed_cohort,
               test_c_unwired_composition_breaches_by_construction,
               test_d_composed_rush_ownership_contains_named_owners,
               test_e_composed_has_one_answer_for_designed_qb_runs,
               test_f_composed_partition_closes_in_its_declared_form,
               test_g_published_level_is_the_level_that_was_partitioned,
               test_h_the_composition_neither_clips_nor_renormalises,
               test_i_the_containment_assertion_rejects_a_seeded_breach,
               test_j_the_engine_records_the_decomposed_verdict):
        print(fn.__name__)
        fn()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
