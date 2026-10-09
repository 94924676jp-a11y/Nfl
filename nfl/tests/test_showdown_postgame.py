"""Slate-generic Showdown postgame (nfl/postgame/showdown_postgame.py): parity, refusals, exact hindsight, scoring.

The ATL@NO 2026W4 package is the fixture: its actuals were reconciled to DraftKings' own points for all 172 owner
entries, so the generic scorer must reproduce them exactly, and the generic portfolio grader must identify that upload
as the accepted one from DK's points alone.
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import showdown_postgame as SP  # noqa: E402

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)

ATL_SD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
ATL_PBP = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4/NFLVERSE_PBP_2026.40fb5ce16256530d.csv.gz'
ATL_HIST = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4/DK_CONTEST_ENTRY_HISTORY_OWNER.8919692f3c4ca85b.csv'
ATL_ACT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json'


def _atl_state():
    return json.loads(next(ATL_SD.glob('SHOWDOWN_*_STATE.json')).read_text())


def test_generic_actuals_reproduce_atl_no_exactly():
    a = SP.actuals(ATL_PBP, _atl_state(), '2026_04_ATL_NO')
    old = json.loads(ATL_ACT.read_text())
    check(a['final'] == old['final_score'], f"final score reproduced {a['final']}")
    check(set(a['players']) == set(old['player_actuals']), f"same {len(old['player_actuals'])} players")
    bad = [k for k, v in old['player_actuals'].items() if abs(a['players'][k]['dk_A'] - v['dk_A']) > 1e-9
           or abs(a['players'][k]['dk_B'] - v['dk_B']) > 1e-9]
    check(not bad, f'every player DK points (rules A and B) reproduced exactly; mismatches {bad}')


def test_atl_module_delegates_to_generic_scorer():
    from nfl.postgame import showdown_atl_no_postgame as ATL
    a = ATL.actuals(ATL_PBP, _atl_state())
    b = SP.actuals(ATL_PBP, _atl_state(), '2026_04_ATL_NO')
    check(json.dumps(a, sort_keys=True, default=float) == json.dumps(b, sort_keys=True, default=float),
          'ATL module actuals are byte-identical to the generic scorer (one scorer, not two)')


def test_refuses_a_game_the_pbp_does_not_carry():
    try:
        SP.load_game(ATL_PBP, '2026_05_TB_DAL')
        check(False, 'a game absent from the pbp file must be refused, never graded against absence')
    except SP.PostgameError as e:
        check(str(e).startswith('GAME_NOT_IN_PBP'), f'absent game refused by name: {e}')


def test_accepted_portfolio_identified_from_dk_points():
    st = _atl_state()
    a = SP.actuals(ATL_PBP, st, '2026_04_ATL_NO')
    pts = {k: float(v['dk_A']) for k, v in a['players'].items()}
    lu = SP.lineups_from_upload(ATL_SD / 'SHOWDOWN_ATL_NO_DK_UPLOAD.csv', st)
    _rep, sc = SP.portfolio_report('FINAL', lu, pts, st)
    per = {'FINAL': {e: float(s) for (_, e, _, _), s in zip(lu, sc)}}
    # a decoy: the same lineups shifted by one entry cannot match DK's points entry by entry
    ids = [e for _, e, _, _ in lu]
    per['DECOY'] = {ids[(i + 1) % len(ids)]: float(s) for i, s in enumerate(sc)}
    fin = SP.contest_financials(ATL_HIST, ('196285137', '196285160', '196285161'), per)
    m = fin['accepted_portfolio_identification']
    check(m['FINAL']['entries_matching_dk_points'] == 172 == m['FINAL']['of'], f"accepted upload identified {m['FINAL']}")
    check(m['DECOY']['entries_matching_dk_points'] < 172, f"shifted decoy not identified {m['DECOY']}")


def test_financials_unknown_without_entry_history():
    f = SP.contest_financials(None, (), None)
    check(f['STATUS'] == 'UNKNOWN' and 'winnings' in f['fields_unknown'], 'no entry history -> financials UNKNOWN, never estimated')


def _brute(pts, players):
    best = -1e9
    for c in players:
        rest = [p for p in players if p is not c]
        for f in itertools.combinations(rest, 5):
            if c['cpt_salary'] + sum(p['salary'] for p in f) > SP.SALARY_CAP:
                continue
            if len({c['team'], *(p['team'] for p in f)}) < 2:
                continue
            best = max(best, 1.5 * pts[c['k']] + sum(pts[p['k']] for p in f))
    return round(best, 2)


def test_hindsight_optimum_is_exact_against_brute_force():
    rng = np.random.default_rng(7)
    pl, pts = {}, {}
    for i in range(12):
        team = 'A' if i % 2 else 'B'
        sal = int(rng.integers(2, 13)) * 1000
        k = f'P{i}|{team}'
        pl[str(i)] = {'name': f'P{i}', 'team': team, 'salary': sal, 'cpt_salary': int(sal * 1.5), 'position': 'WR'}
        pts[k] = float(max(0.0, rng.normal(8, 7)))     # several zeros: exercises the exact pruning
        pl[str(i)]['k'] = k
    hs = SP.hindsight_optimum(pts, {'players': pl}, set(pts))
    bf = _brute(pts, list(pl.values()))
    check(hs['score'] == bf, f"hindsight optimum {hs['score']} == brute force {bf} (pruning is exact)")
    check(hs['salary'] <= SP.SALARY_CAP, 'hindsight lineup under the cap')


def test_captain_scores_one_and_a_half_times():
    st = {'players': {'1': {'name': 'A', 'team': 'X'}, '2': {'name': 'B', 'team': 'Y'}}}
    nk = SP._name_key(st)
    pts = {'A|X': 10.0, 'B|Y': 4.0}
    check(SP.score_lineup('A', ('B',), pts, nk) == 19.0, 'captain scores 1.5x')


def test_pit_mid_rank_handles_ties():
    check(SP.pit([0, 0, 0, 0], 0) == 0.5, 'PIT of a tie is mid-rank')
    check(SP.pit([1, 2, 3, 4], 5) == 1.0 and SP.pit([1, 2, 3, 4], 0) == 0.0, 'PIT bounds')
