"""DraftKings Classic: legality, constraints, governance, export.

The acceptance condition these cases serve: a gate-passed board can become
legal DraftKings Classic lineups WITHOUT bypassing review or freshness
governance. So the suite proves two different things -- that the lineups are
legal and the constraints bind, and that there is no way in through the side.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np                                                  # noqa: E402

from nfl.dfs.classic import export as EX                            # noqa: E402
from nfl.dfs.classic import optimizer as O                          # noqa: E402
from nfl.dfs.classic import pool as POOL                            # noqa: E402
from nfl.dfs.classic import rules as R                              # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def mkpool(n_teams=6, seed=3, salary=None):
    rnd = random.Random(seed)
    spec = [('QB', 2), ('RB', 4), ('WR', 6), ('TE', 3), ('DST', 1)]
    teams = [f'T{i:02d}' for i in range(n_teams)]
    out, i = [], 0
    for ti, t in enumerate(teams):
        opp = teams[ti ^ 1]
        for pos, k in spec:
            for j in range(k):
                i += 1
                out.append(O.Player(
                    gsis_id=f'{t}-{pos}{j}', name=f'{t} {pos}{j}',
                    position=pos, team=t, opponent=opp,
                    salary=(salary if salary else
                            rnd.randrange(3000, 9500, 100)),
                    dk_id=str(20000 + i),
                    value=round(rnd.uniform(3, 22), 3), draw_row=i - 1))
    return out


def one(players, **kw):
    return O.solve_one(players, O.Constraints(**kw))


# -- 1. roster legality -----------------------------------------------------
def test_every_lineup_is_a_legal_dk_roster():
    p = mkpool()
    o = O.build_portfolio(p, O.Constraints(n_lineups=6, min_unique_players=1))
    ok(o.state.name == 'PASS', f'the portfolio builds: {o.code}')
    for lu in o.value['lineups']:
        pos = [x['pos'] for x in lu['players']]
        sal = [x['salary'] for x in lu['players']]
        legal, why = R.assert_roster_legal(pos, sal)
        ok(legal, f'legal roster: {lu["shape"]} ${lu["salary"]} -- {why}')
        ok(len(lu['players']) == R.ROSTER_SIZE, '9 players')


def test_the_three_shapes_are_the_complete_set():
    ok(len(R.LEGAL_SHAPES) == 3,
       f'a Classic roster is one of exactly three shapes: {R.LEGAL_SHAPES}')
    for s in R.LEGAL_SHAPES:
        ok(sum(s.values()) == R.ROSTER_SIZE,
           f'{s} sums to {R.ROSTER_SIZE}')
    ok(R.shape_is_legal({'QB': 1, 'RB': 2, 'WR': 4, 'TE': 1, 'DST': 1}),
       'RB2/WR4/TE1 (WR flex) is legal')
    ok(not R.shape_is_legal({'QB': 2, 'RB': 2, 'WR': 3, 'TE': 1, 'DST': 1}),
       'two QBs is not')


def test_salary_cap_binds():
    lu = one(mkpool(), n_lineups=1)
    ok(lu is not None and lu.salary <= R.SALARY_CAP,
       f'under the cap: ${lu.salary} <= ${R.SALARY_CAP}')


def test_salary_floor_binds():
    lu = one(mkpool(), n_lineups=1, salary_floor=49500)
    ok(lu is not None and lu.salary >= 49500,
       f'a declared floor binds: ${lu.salary} >= $49,500')


def test_an_unaffordable_pool_yields_no_lineup():
    o = O.build_portfolio(mkpool(salary=9900), O.Constraints(n_lineups=1))
    ok(o.state.name == 'FAIL' and o.code == 'NO_LEGAL_LINEUP',
       'when nine players cannot fit the cap, the refusal names the '
       'constraints rather than returning an empty list')


# -- 2. locks, excludes, groups --------------------------------------------
def test_locks_are_always_present():
    p = mkpool()
    cheap = min((x for x in p if x.position == 'WR'), key=lambda x: x.value)
    lu = one(p, n_lineups=1, locks={cheap.gsis_id})
    ok(lu is not None and cheap.gsis_id in lu.ids,
       f'the lowest-value WR is rostered because he is locked: {cheap.name}')


def test_excludes_are_never_present():
    p = mkpool()
    best = max(p, key=lambda x: x.value)
    lu = one(p, n_lineups=1, excludes={best.gsis_id})
    ok(lu is not None and best.gsis_id not in lu.ids,
       f'the highest-value player is absent because he is excluded: '
       f'{best.name}')


def test_mutually_exclusive_admits_at_most_one():
    p = mkpool()
    wrs = sorted((x for x in p if x.position == 'WR'),
                 key=lambda x: -x.value)[:3]
    ex = {w.gsis_id for w in wrs}
    lu = one(p, n_lineups=1, mutually_exclusive=[ex])
    ok(lu is not None and len(lu.ids & ex) <= 1,
       f'at most one of a mutually exclusive set: {len(lu.ids & ex)}')


def test_group_min_and_max_bind():
    p = mkpool()
    grp = {x.gsis_id for x in p if x.team == 'T00'}
    lu = one(p, n_lineups=1,
             groups=[{'name': 'T00', 'players': grp, 'min': 3}])
    ok(lu is not None and len(lu.ids & grp) >= 3,
       f'a group minimum binds: {len(lu.ids & grp)} from T00')
    lu2 = one(p, n_lineups=1,
              groups=[{'name': 'T00', 'players': grp, 'max': 1}])
    ok(lu2 is not None and len(lu2.ids & grp) <= 1,
       f'a group maximum binds: {len(lu2.ids & grp)} from T00')


def test_projection_cutoff_excludes_the_cheap_and_bad():
    p = mkpool()
    lu = one(p, n_lineups=1, projection_cutoff=8.0)
    ok(lu is not None and all(x.value >= 8.0 for x in lu.players),
       'nobody below the cutoff is rostered')


# -- 3. stacking ------------------------------------------------------------
def test_qb_stack_minimum_binds():
    for n in (1, 2):
        lu = one(mkpool(), n_lineups=1, qb_stack_min=n)
        qb = next(x for x in lu.players if x.position == 'QB')
        got = sum(1 for x in lu.players if x.team == qb.team
                  and x.position in ('WR', 'TE', 'RB'))
        ok(got >= n, f'QB + {n} pass catcher(s): got {got} with {qb.name}')


def test_bring_back_minimum_and_maximum_bind():
    lu = one(mkpool(), n_lineups=1, qb_stack_min=1, bring_back_min=1)
    qb = next(x for x in lu.players if x.position == 'QB')
    got = sum(1 for x in lu.players if x.game == qb.game
              and x.team != qb.team and x.position != 'DST')
    ok(got >= 1, f'a bring-back is present: {got}')
    lu2 = one(mkpool(), n_lineups=1, bring_back_max=0)
    qb2 = next(x for x in lu2.players if x.position == 'QB')
    got2 = sum(1 for x in lu2.players if x.game == qb2.game
               and x.team != qb2.team and x.position != 'DST')
    ok(got2 == 0, f'and bring_back_max=0 means no bring-back: {got2}')


def test_max_from_team_and_game_bind():
    lu = one(mkpool(), n_lineups=1, max_from_team=2)
    counts = {}
    for x in lu.players:
        counts[x.team] = counts.get(x.team, 0) + 1
    ok(max(counts.values()) <= 2,
       f'no more than 2 from one team: {counts}')
    lu2 = one(mkpool(), n_lineups=1, max_from_game=3)
    g = {}
    for x in lu2.players:
        g[x.game] = g.get(x.game, 0) + 1
    ok(max(g.values()) <= 3, f'no more than 3 from one game: {g}')


def test_no_dfs_philosophy_is_hard_coded():
    c = O.Constraints()
    ok(c.qb_stack_min == 0 and c.bring_back_min == 0
       and c.max_from_team is None,
       'the default Constraints enforce no stack, no bring-back and no team '
       'cap: the philosophy is the callers, not the optimizer\'s')


# -- 4. exposure and diversity ---------------------------------------------
def test_max_exposure_binds_and_is_reported():
    o = O.build_portfolio(mkpool(), O.Constraints(
        n_lineups=10, min_unique_players=1, global_max_exposure=0.3))
    r = o.value['realized_exposure']
    ok(max(r.values()) <= 0.3 + 1e-9,
       f'no player exceeds 30% exposure: max {max(r.values())}')
    ok(o.value['exceeded_max_exposure'] == {},
       'and the report confirms none exceeded')


def test_unmet_minimum_exposure_is_reported_not_hidden():
    p = mkpool()
    worst = min(p, key=lambda x: x.value)
    o = O.build_portfolio(p, O.Constraints(
        n_lineups=4, min_unique_players=1,
        min_exposure={worst.gsis_id: 1.0}))
    ok(worst.gsis_id in o.value['unmet_min_exposure'],
       'a minimum exposure the build could not reach is REPORTED as unmet '
       'rather than silently ignored')


def test_uniqueness_prevents_near_clones():
    p = mkpool()
    loose = O.build_portfolio(p, O.Constraints(n_lineups=5,
                                               min_unique_players=1))
    tight = O.build_portfolio(p, O.Constraints(n_lineups=5,
                                               min_unique_players=4))
    ok(tight.value['diversity']['max_overlap'] <=
       R.ROSTER_SIZE - 4,
       f'with min_unique=4 no two lineups share more than 5: '
       f'{tight.value["diversity"]["max_overlap"]}')
    ok(tight.value['diversity']['n_distinct_players'] >=
       loose.value['diversity']['n_distinct_players'],
       f'and the portfolio uses at least as many distinct players: '
       f'{loose.value["diversity"]["n_distinct_players"]} -> '
       f'{tight.value["diversity"]["n_distinct_players"]}')


def test_concentration_is_always_reported():
    o = O.build_portfolio(mkpool(), O.Constraints(n_lineups=5))
    for k in ('team_concentration', 'game_concentration',
              'stack_concentration', 'diversity'):
        ok(k in o.value, f'{k} is reported on every portfolio')


# -- 5. objectives ----------------------------------------------------------
def test_shared_world_objectives_refuse_without_worlds():
    p = mkpool()
    for obj in (O.OBJ_PERCENTILE, O.OBJ_TOP_X, O.OBJ_EXPECTED_RANK):
        o = O.score_pool(p, objective=obj, draws=None)
        ok(o.state.name == 'BLOCKED' and
           o.code == 'OBJECTIVE_REQUIRES_SHARED_WORLDS',
           f'{obj} refuses without shared worlds rather than quietly '
           f'becoming the mean')


def test_shared_world_objectives_reorder_the_pool():
    p = mkpool()
    rng = np.random.default_rng(5)
    M = rng.normal(10, 6, (len(p), 400))
    base = [x.gsis_id for x in sorted(p, key=lambda x: -x.value)][:10]
    o = O.score_pool(p, objective=O.OBJ_TOP_X, draws=M, top_x=0.1)
    ok(o.state.name == 'PASS', f'top-X% scores: {o.code}')
    new = [x.gsis_id for x in
           sorted(o.value['players'], key=lambda x: -x.value)][:10]
    ok(new != base,
       'a simulation objective produces a different ordering than the mean, '
       'which is the point of having more than one')
    ok(o.value['uses_shared_worlds'] and o.value['n_worlds'] == 400,
       f'and it says it used {o.value["n_worlds"]} shared worlds')


def test_an_unknown_objective_is_refused():
    o = O.score_pool(mkpool(), objective='MAXIMISE_VIBES')
    ok(o.state.name == 'FAIL' and o.code == 'UNKNOWN_OBJECTIVE',
       'an unregistered objective is refused by name')


def test_no_roi_is_claimed():
    o = O.build_portfolio(mkpool(), O.Constraints(n_lineups=2))
    ok('no_roi_claim' in o.value and
       'ownership and field models are unavailable' in o.value['no_roi_claim'],
       'every portfolio carries the statement that no ROI, duplication or '
       'leverage estimate is made')


# -- 6. determinism ---------------------------------------------------------
def test_deterministic_replay():
    p = mkpool()
    c = O.Constraints(n_lineups=5, min_unique_players=2,
                      global_max_exposure=0.6)
    runs = {json.dumps(O.build_portfolio(p, c).value['lineups'],
                       sort_keys=True, default=str) for _ in range(4)}
    ok(len(runs) == 1, f'four builds give one portfolio, not {len(runs)}')


def test_input_order_does_not_change_the_result():
    p = mkpool()
    c = O.Constraints(n_lineups=3, min_unique_players=2)
    a = O.build_portfolio(p, c).value['lineups']
    shuffled = list(p)
    random.Random(99).shuffle(shuffled)
    b = O.build_portfolio(shuffled, c).value['lineups']
    ok([x['value'] for x in a] == [x['value'] for x in b],
       'shuffling the pool gives the same lineup values: the search is '
       'ordered by value and salary, never by arrival')


# -- 7. governance: there is no way in through the side --------------------
def test_pool_refuses_when_review_never_ran():
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        (d / 'board').mkdir()
        (d / 'board' / 'PLAYER_BOARD.json').write_text(json.dumps(
            {'rows': [], 'slate_key': 'S'}))
        o = POOL.build_pool(board_dir=d / 'board', draws_dir=d / 'nope',
                            review_dir=d / 'nope')
        ok(o.state.name in ('FAIL', 'BLOCKED'),
           f'no gate, no pool: {o.code}')


def test_pool_refuses_without_a_board():
    with tempfile.TemporaryDirectory() as td:
        o = POOL.build_pool(board_dir=td, draws_dir=td, review_dir=td)
        ok(o.state.name == 'BLOCKED' and o.code == 'BOARD_ABSENT',
           'a Classic pool is built from a written board, never from '
           'projections handed in directly')


def test_pool_has_no_argument_that_takes_raw_projections():
    import inspect
    sig = set(inspect.signature(POOL.build_pool).parameters)
    banned = {'players', 'projections', 'values', 'points', 'pool'}
    ok(not (sig & banned),
       f'build_pool takes {sorted(sig)} -- no parameter accepts a bare list '
       f'of projections, so the gate cannot be routed around')


# -- 8. CSV export ----------------------------------------------------------
def test_csv_exports_dk_ids_and_verifies_itself():
    o = O.build_portfolio(mkpool(), O.Constraints(n_lineups=4,
                                                  min_unique_players=1))
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / 'entries.csv'
        w = EX.write_csv(o.value, p)
        ok(w.state.name == 'PASS', f'the CSV writes: {w.code}')
        ok(w.value['n_lineups'] == 4, '4 lineups exported')
        import csv as _csv
        rows = list(_csv.reader(p.open()))
        ok(rows[0] == list(EX.HEADER),
           f'DK Classic header in DK order: {rows[0]}')
        ok(all(len(r) == R.ROSTER_SIZE for r in rows[1:]),
           'every row is 9 columns')
        ok(all(c.isdigit() for r in rows[1:] for c in r),
           'every cell is a DraftKings id, not a name')


def test_export_refuses_a_player_without_a_dk_id():
    p = [O.Player(**{**x.__dict__, 'dk_id': None}) if x.position == 'TE'
         else x for x in mkpool()]
    o = O.build_portfolio(p, O.Constraints(n_lineups=1))
    with tempfile.TemporaryDirectory() as td:
        w = EX.write_csv(o.value, pathlib.Path(td) / 'e.csv')
        ok(w.state.name == 'FAIL' and w.code == 'DK_ID_MISSING',
           'a missing DK id refuses the export rather than writing a blank '
           'that DraftKings would reject or mis-match')


def test_export_refuses_an_empty_portfolio():
    with tempfile.TemporaryDirectory() as td:
        w = EX.write_csv({'lineups': []}, pathlib.Path(td) / 'e.csv')
        ok(w.state.name == 'BLOCKED' and w.code == 'NO_LINEUPS_TO_EXPORT',
           'a header-only CSV is never written as a successful export')


# -- 9. workflow stage permissions -----------------------------------------
def test_a_research_stage_may_not_build_lineups():
    from nfl.production.workflow import stages as W
    for n in ('EARLY_BOARD', 'PRACTICE_REFRESH', 'DEEP_RESEARCH'):
        o = W.assert_may_optimize(n)
        ok(o.state.name == 'BLOCKED' and o.code == 'STAGE_MAY_NOT_OPTIMIZE',
           f'{n} is a research stage and refuses to optimize: {o.code}')
        ok(W.assert_may_project(n).state.name == 'PASS',
           f'{n} may still project')


def test_the_sunday_stages_may_optimize():
    from nfl.production.workflow import stages as W
    for n in ('SATURDAY_BOARD', 'OFFICIAL_INACTIVES', 'FINAL_PRELOCK'):
        ok(W.assert_may_optimize(n).state.name == 'PASS',
           f'{n} may build lineups')


def test_an_undeclared_stage_has_no_permissions():
    from nfl.production.workflow import stages as W
    o = W.assert_may_optimize('SOME_TUESDAY_THING')
    ok(o.state.name == 'FAIL' and o.code == 'UNKNOWN_WORKFLOW_STAGE',
       'an undeclared stage is refused rather than defaulted to allowed')


def test_every_stage_declares_its_sources_and_artifacts():
    from nfl.production.workflow import stages as W
    for n in W.ORDER:
        s = W.STAGES[n]
        ok(bool(s.required_sources) and bool(s.artifacts) and bool(s.freshness),
           f'{n} declares required sources, artifacts and a freshness rule')


# -- 10. DraftKings identity ------------------------------------------------
DK_FILE = (_REPO / 'nfl/dfs/salaries/raw/'
           'DKEntries_EARLY_ONLY_2026W2_51.csv')


def test_the_embedded_player_table_is_found_and_parsed():
    from nfl.dfs.classic import dk_identity as DK
    if not DK_FILE.exists():
        ok(True, 'no DK file in this checkout; case skipped')
        return
    o = DK.parse_salary_file(DK_FILE)
    ok(o.state.name == 'PASS', f'the file parses: {o.code}')
    v = o.value
    ok(v['header_at_column'] > 0,
       f'the player table is EMBEDDED at column {v["header_at_column"]}, not '
       f'at the start -- reading only the first header finds no ids at all')
    ok(v['n_rows'] > 300, f'{v["n_rows"]} player rows')
    ok(not v['positions_not_recognised'],
       f'every DK position is recognised: {v["by_position"]}')
    ok(not v['duplicate_dk_ids'], 'no duplicate DK ids')
    ok(all(r['dk_id'].isdigit() for r in v['rows']),
       'every row carries a numeric DK id')


def test_dst_is_named_as_having_no_gsis_id():
    from nfl.dfs.classic import dk_identity as DK
    if not DK_FILE.exists():
        ok(True, 'skipped')
        return
    c = DK.crosswalk(DK.parse_salary_file(DK_FILE))
    ok(c.value['n_dst'] > 0,
       f'{c.value["n_dst"]} defences are separated out')
    ok('carry no gsis_id' in c.value['dst_note'],
       'and the artifact states they have no gsis_id and no dossier, so '
       'their absence from the board is expected rather than a defect')


def test_unresolved_identities_are_counted_and_named():
    from nfl.dfs.classic import dk_identity as DK
    if not DK_FILE.exists():
        ok(True, 'skipped')
        return
    c = DK.crosswalk(DK.parse_salary_file(DK_FILE))
    ok(c.value['n_unresolved'] > 0 and c.value['unresolved'],
       f'with no crosswalk supplied, all {c.value["n_unresolved"]} non-DST '
       f'rows are reported unresolved BY NAME rather than silently dropped')
    ok(c.value['n_resolved'] == 0,
       'and none is resolved by guessing')


def test_a_missing_dk_file_refuses():
    from nfl.dfs.classic import dk_identity as DK
    o = DK.parse_salary_file('/nonexistent/DKSalaries.csv')
    ok(o.state.name == 'BLOCKED' and o.code == 'DK_SALARY_FILE_ABSENT',
       'no DK file means no authority on DK positions, by name')


def test_a_file_without_a_player_table_refuses():
    from nfl.dfs.classic import dk_identity as DK
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / 'x.csv'
        f.write_text('Entry ID,Contest Name\n1,foo\n')
        o = DK.parse_salary_file(f)
        ok(o.state.name == 'FAIL' and o.code == 'DK_PLAYER_TABLE_NOT_FOUND',
           'a file with entry rows but no player table refuses rather than '
           'returning an empty roster of ids')


def test_a_group_minimum_does_not_blow_up_the_search():
    """A group minimum must PRUNE, not merely be checked at the leaf.

    This is a regression guard with a wall clock in it, which is normally a
    bad idea. It is here because the defect it guards is a timing defect and
    nothing else detects it: the search returned the RIGHT lineup the whole
    time, so every correctness assertion passed while a 4-team fixture with
    one `min: 2` group took 36.62 seconds against the frozen baseline's 0.07
    -- a 500x regression introduced by the stacked decomposition, which
    multiplies the leaf-only group test across every (QB, mate-count,
    bring-back-count, distribution) cell.

    The ceiling is deliberately loose. It is not a performance target; it is
    two orders of magnitude below the broken behaviour and two above the
    fixed one, so it fires on a reintroduced regression and not on a slow
    machine.
    """
    import time
    rnd = random.Random(3)
    spec = [('QB', 2), ('RB', 4), ('WR', 6), ('TE', 3), ('DST', 1)]
    teams = [f'S{n:02d}' for n in range(4)]
    players, i = [], 0
    for ti, t in enumerate(teams):
        opp = teams[ti ^ 1]
        for pos, k in spec:
            for j in range(k):
                i += 1
                players.append(O.Player(
                    gsis_id=f'{t}-{pos}{j}', name=f'{t} {pos}{j}',
                    position=pos, team=t, opponent=opp,
                    salary=rnd.randrange(3000, 9500, 100),
                    dk_id=str(30000 + i),
                    value=round(rnd.uniform(3, 22), 3), draw_row=i - 1))
    c = O.Constraints(
        n_lineups=3, min_unique_players=2, qb_stack_min=1,
        groups=[{'name': 'S00', 'min': 2,
                 'players': {f'S00-WR{j}' for j in range(6)}}])
    t0 = time.time()
    out = O.build_portfolio(players, c)
    elapsed = time.time() - t0
    ok(out.state.name == 'PASS',
       f'the group-constrained build succeeds: {out.code}')
    lus = (out.value or {}).get('lineups', [])
    ok(len(lus) == 3, f'and returns every lineup asked for: {len(lus)}')
    ok(all(sum(1 for x in lu['players']
               if x['gsis_id'].startswith('S00-WR')) >= 2 for lu in lus),
       'every lineup honours the group minimum')
    ok(elapsed < 5.0,
       f'and the group minimum prunes rather than being tested at the leaf: '
       f'{elapsed:.2f}s (broken behaviour was 36.62s on this fixture)')


def main():
    for t in (test_every_lineup_is_a_legal_dk_roster,
              test_the_three_shapes_are_the_complete_set,
              test_salary_cap_binds, test_salary_floor_binds,
              test_an_unaffordable_pool_yields_no_lineup,
              test_locks_are_always_present,
              test_excludes_are_never_present,
              test_mutually_exclusive_admits_at_most_one,
              test_group_min_and_max_bind,
              test_projection_cutoff_excludes_the_cheap_and_bad,
              test_qb_stack_minimum_binds,
              test_bring_back_minimum_and_maximum_bind,
              test_max_from_team_and_game_bind,
              test_no_dfs_philosophy_is_hard_coded,
              test_max_exposure_binds_and_is_reported,
              test_unmet_minimum_exposure_is_reported_not_hidden,
              test_uniqueness_prevents_near_clones,
              test_concentration_is_always_reported,
              test_shared_world_objectives_refuse_without_worlds,
              test_shared_world_objectives_reorder_the_pool,
              test_an_unknown_objective_is_refused,
              test_no_roi_is_claimed,
              test_deterministic_replay,
              test_input_order_does_not_change_the_result,
              test_pool_refuses_when_review_never_ran,
              test_pool_refuses_without_a_board,
              test_pool_has_no_argument_that_takes_raw_projections,
              test_csv_exports_dk_ids_and_verifies_itself,
              test_export_refuses_a_player_without_a_dk_id,
              test_export_refuses_an_empty_portfolio,
              test_a_research_stage_may_not_build_lineups,
              test_the_sunday_stages_may_optimize,
              test_an_undeclared_stage_has_no_permissions,
              test_every_stage_declares_its_sources_and_artifacts,
              test_the_embedded_player_table_is_found_and_parsed,
              test_dst_is_named_as_having_no_gsis_id,
              test_unresolved_identities_are_counted_and_named,
              test_a_missing_dk_file_refuses,
              test_a_file_without_a_player_table_refuses,
              test_a_group_minimum_does_not_blow_up_the_search):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
