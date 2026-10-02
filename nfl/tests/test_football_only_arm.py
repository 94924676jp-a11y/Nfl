#!/usr/bin/env python3.12
"""The football-only arm: no sportsbook price may enter proprietary prediction (owner rule).

Forced in both directions. Under the arm, perturbing every line in the captured environment
(totals, spreads, implied points) must leave every player, kicker, DST and club-volume number
byte-identical. Under the incumbent MARKET arm the same perturbation must move the DST and the
touchdown pool -- the control that proves the test can see a dependence. The scoring-centre module
is checked by AST for the forbidden field names, and the draws builder must draw around the
football centre with the residuals measured around it.
"""
from __future__ import annotations

import ast
import io
import contextlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import football_points as FP  # noqa: E402
from nfl.tools import proj_v1 as PV  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []
STATE = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_STATE.json'
ROLE = _REPO / 'nfl/derived/SHOWDOWN_TONIGHT_ROLE_STATE.json'
_CACHE = {}


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('football_points never names a sportsbook field: total_line, club_spread, implied_total, moneyline (AST)')
def _ast_guard():
    src = (_REPO / 'nfl/sim/football_points.py').read_text()
    tree = ast.parse(src)
    names = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    offending = sorted(f for f in FP.FIELDS_FORBIDDEN if f in attrs or any(
        isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == f for n in ast.walk(tree)))
    # the names appear ONLY inside the FIELDS_FORBIDDEN tuple and the docstring, never as a read
    assert not offending, offending
    art = FP.load(); assert art and art['NO_MARKET_INPUT'].startswith('reads points'), 'artifact absent or unlabelled'
    return f"no subscript or attribute read of {list(FP.FIELDS_FORBIDDEN)}; artifact built over {art['n_games']} games"


def _perturb_team_game_lines(delta):
    # THE SECOND ROUTE. The volume layer's market response does not read the state environment at
    # all: market_response.club_market() takes this week's line from the club-game table (the
    # schedules capture). A test that perturbs only the environment cannot see it. So both routes
    # are perturbed: the state's lines AND the in-memory club-game rows for the forecast season.
    if PV._MR is None:
        from nfl.tools import market_response
        PV._MR = market_response.load()
    rows = PV._MR['team_game']
    rows = rows.values() if isinstance(rows, dict) else rows
    n = 0
    for r in rows:
        if int(r.get('season') or 0) == PV.FORECAST_SEASON:
            for k in ('total_line', 'club_spread', 'implied_total', 'opponent_implied_total'):
                if isinstance(r.get(k), (int, float)):
                    r[k] = r[k] + delta; n += 1
    return n


def _perturbed_state(tmp, delta):
    _perturb_team_game_lines(delta)
    st = json.loads(STATE.read_text())
    for g, e in st['environment']['games'].items():
        e['total_line'] = (e.get('total_line') or 40) + delta
        e['home_spread'] = (e.get('home_spread') or 0) + delta
        e['home_implied'] = (e.get('home_implied') or 20) + delta / 2
        e['away_implied'] = (e.get('away_implied') or 20) + delta / 2
    p = tmp / f'state_{delta}.json'; p.write_text(json.dumps(st)); return p


def _build(arm, state_path, tmp, tag):
    key = (arm, tag)
    if key in _CACHE:
        return _CACHE[key]
    saved = (PV.MARKET_ARM, PV.SLATE_WEEK, PV.ROLE, PV.POST, PV.OUT)
    try:
        PV.MARKET_ARM, PV.SLATE_WEEK, PV.ROLE, PV.POST = arm, 4, ROLE, state_path
        PV.OUT = (tmp / f'proj_{arm}_{tag}.json').resolve()
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                PV.main()
            except ValueError:
                pass   # the trailing relative_to print; the artifact is written before it
        art = json.loads(PV.OUT.read_text()); art['_path'] = str(PV.OUT)
    finally:
        PV.MARKET_ARM, PV.SLATE_WEEK, PV.ROLE, PV.POST, PV.OUT = saved
    _CACHE[key] = art
    return art


def _numbers(art):
    out = {}
    for k, r in art['rows'].items():
        if k == '_path':
            continue
        out[k] = tuple(r.get(f) for f in ('dk_points', 'dk_points_if_plays', 'pass_attempts', 'carries', 'targets', 'pass_td', 'rec_td'))
    for c, t in art['team_volume'].items():
        out[f'tv/{c}'] = tuple(round(t.get(f) or 0, 6) for f in ('proj_plays', 'proj_pass_attempts', 'proj_rush_attempts', 'proj_targets'))
    for c, t in art['td_account'].items():
        out[f'td/{c}'] = (t.get('team_expected_td'), t.get('implied_total'))
    return out


@check('under FOOTBALL_ONLY, moving every line by +7 and -7 leaves every player, kicker, DST, volume and TD number identical')
def _invariant_under_arm():
    tmp = pathlib.Path(tempfile.mkdtemp())
    a = _numbers(_build('FOOTBALL_ONLY', _perturbed_state(tmp, +7.0), tmp, 'plus'))
    b = _numbers(_build('FOOTBALL_ONLY', _perturbed_state(tmp, -7.0), tmp, 'minus'))
    diff = [k for k in a if a[k] != b.get(k)]
    assert not diff, diff[:8]
    art = _CACHE[('FOOTBALL_ONLY', 'plus')]
    assert art['market_arm'] == 'FOOTBALL_ONLY' and all(t.get('market_response_state') == 'NOT_APPLIED_FOOTBALL_ONLY_ARM' for t in art['team_volume'].values())
    assert art['IMPLIED_MEANS'].startswith('FOOTBALL_EXPECTED_POINTS')
    ks = [k for k, r in art['rows'].items() if r.get('position') in ('K', 'DST') and r.get('dk_points') is not None]
    return f"{len(a)} quantities identical across a 14-point swing in every line; {len(ks)} kicker/DST rows among them; market env kept only as DOWNSTREAM_COMPARISON_ONLY"


@check('CONTROL: under the incumbent MARKET arm the same perturbation moves the DST and the touchdown pool')
def _control_market_arm_moves():
    tmp = pathlib.Path(tempfile.mkdtemp())
    a = _numbers(_build('MARKET', _perturbed_state(tmp, +7.0), tmp, 'plus'))
    b = _numbers(_build('MARKET', _perturbed_state(tmp, -7.0), tmp, 'minus'))
    moved = [k for k in a if a[k] != b.get(k)]
    td_moved = [k for k in moved if k.startswith('td/')]; tv_moved = [k for k in moved if k.startswith('tv/')]
    assert td_moved, 'touchdown pool did not move under MARKET'
    assert tv_moved, 'volume layer did not move under MARKET even with the club-game lines perturbed'
    art = _CACHE[('MARKET', 'plus')]
    dst = [k for k, r in art['rows'].items() if r.get('position') == 'DST']
    assert any(k in moved for k in dst), 'DST did not move under the market arm'
    return f"{len(moved)} of {len(a)} quantities moved under MARKET: touchdown pool {len(td_moved)}, volume {len(tv_moved)}, DST among the rows (the dependence the arm removes is real and visible)"


@check('kickers are identical across arms: the kicking layer never read the market')
def _kickers_same():
    tmp = pathlib.Path(tempfile.mkdtemp())
    f = _build('FOOTBALL_ONLY', _perturbed_state(tmp, +7.0), tmp, 'plus'); m = _build('MARKET', _perturbed_state(tmp, +7.0), tmp, 'plus')
    ks = {k: r['dk_points'] for k, r in f['rows'].items() if r.get('position') == 'K'}
    assert ks and all(abs(m['rows'][k]['dk_points'] - v) < 1e-9 for k, v in ks.items()), ks
    return f"{len(ks)} kicker(s) identical across arms"


@check('the football centre is forward-only and carries a measured home field; tonight\'s centre needs no line')
def _centre():
    c = FP.centre_for_game('CLE', 'PIT', 2026, 4)
    assert c and c['BASIS'] == 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND' and c['basis']['home']['state'] == 'BLENDED'
    art = FP.load()
    assert art['home_field']['mean_margin_residual'] > 0 and art['total_residual']['sd'] > 13.0
    # forward-only: week 4's centre uses weeks 1-3 only
    assert c['basis']['home']['n_cur'] == 3 and c['basis']['away']['n_cur'] == 3
    return f"CLE {c['home_expected']:.2f} PIT {c['away_expected']:.2f} total {c['total']:.2f}; HFA {art['home_field']['mean_margin_residual']:+.2f}; total sd {art['total_residual']['sd']}"


@check('the draws builder draws around the football centre with the football residuals when the projection declares the arm')
def _draws_follow_arm():
    from nfl.tools import showdown_draws as SD
    tmp = pathlib.Path(tempfile.mkdtemp())
    art = _build('FOOTBALL_ONLY', _perturbed_state(tmp, +7.0), tmp, 'plus')
    pp = pathlib.Path(art['_path'])
    SD.OUT = tmp / 'draws.json'
    o = SD.build(str(pp), str(_perturbed_state(tmp, +7.0)), n_sims=60)
    assert o.state.name == 'PASS', (o.code, o.detail)
    d = json.loads(SD.OUT.read_text())
    sc = d['scoring_centre']; c = art['football_centre']['PIT@CLE']
    assert sc['basis'] == 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND' and abs(sc['total_line'] - c['total']) < 1e-9 and abs(sc['home_spread'] - c['home_margin']) < 1e-9, sc
    assert d['market_arm'] == 'FOOTBALL_ONLY'
    return f"scoring basis {sc['basis']}, total {sc['total_line']:.2f} (perturbed line was {c['total'] + 0:.2f} + 7 in the state, not read)"


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
