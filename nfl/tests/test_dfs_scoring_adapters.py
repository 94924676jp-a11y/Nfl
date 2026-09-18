"""Mechanical scoring: hand-built stat lines whose answers are known by hand.

The arithmetic is checked against numbers computed on paper, not against
another implementation of the same arithmetic. Where an implementation IS
available -- the engine's own DraftKings array -- it is reconciled exactly, and
that reconciliation is what licenses using the same assembly for FanDuel.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.scoring import statline as SL                          # noqa: E402
from nfl.dfs.scoring import draftkings as DK                        # noqa: E402
from nfl.dfs.scoring import fanduel as FD                           # noqa: E402
from nfl.dfs.scoring import site_rules as SR                        # noqa: E402
from nfl.dfs.scoring import dual_board as DB                        # noqa: E402
from sportsplatform.governance.outcome import Cause, State          # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def one(**kw):
    return SL.from_line(1, **kw)


def test_A_quarterback():
    print('\nA. QB: 300 pass yds, 3 pass TD, 1 INT, 20 rush yds')
    sl = one(pass_yards=300, pass_td=3, interceptions=1, rush_yards=20)
    # DK 0.04*300=12.0  +4*3=12.0  -1.0  +0.1*20=2.0  +3.0 (300-yard bonus)
    check('DK = 28.0', abs(DK.score(sl)[0] - 28.0) < 1e-9, str(DK.score(sl)[0]))
    # FD the same minus the bonus FanDuel is believed not to pay
    check('FD = 25.0', abs(FD.score(sl)[0] - 25.0) < 1e-9, str(FD.score(sl)[0]))
    check('  the whole difference is the 300-yard bonus',
          abs((DK.score(sl)[0] - FD.score(sl)[0]) - 3.0) < 1e-9)
    just_under = one(pass_yards=299, pass_td=3, interceptions=1, rush_yards=20)
    check('  and one yard short of 300 the two agree exactly',
          abs(DK.score(just_under)[0] - FD.score(just_under)[0]) < 1e-9,
          f'{DK.score(just_under)[0]} vs {FD.score(just_under)[0]}')


def test_B_running_back():
    print('\nB. RB: 100 rush yds, 1 rush TD, 5 catches, 40 rec yds')
    sl = one(rush_yards=100, rush_td=1, receptions=5, rec_yards=40)
    # DK 10.0 + 6.0 + 5*1.0 + 4.0 + 3.0 (100-yard bonus) = 28.0
    check('DK = 28.0', abs(DK.score(sl)[0] - 28.0) < 1e-9, str(DK.score(sl)[0]))
    # FD 10.0 + 6.0 + 5*0.5 + 4.0 = 22.5
    check('FD = 22.5', abs(FD.score(sl)[0] - 22.5) < 1e-9, str(FD.score(sl)[0]))
    check('  the gap is 3.0 bonus plus 2.5 of half-PPR',
          abs((DK.score(sl)[0] - FD.score(sl)[0]) - 5.5) < 1e-9)


def test_C_wide_receiver():
    print('\nC. WR: 8 catches, 100 rec yds, 1 rec TD')
    sl = one(receptions=8, rec_yards=100, rec_td=1)
    check('DK = 27.0', abs(DK.score(sl)[0] - 27.0) < 1e-9, str(DK.score(sl)[0]))
    check('FD = 20.0', abs(FD.score(sl)[0] - 20.0) < 1e-9, str(FD.score(sl)[0]))
    check('  a high-catch receiver loses the most on FanDuel, which is the '
          'half-PPR rule doing exactly what it should',
          (DK.score(sl)[0] - FD.score(sl)[0]) == 7.0)


def test_D_tight_end():
    print('\nD. TE: 4 catches, 50 rec yds, no TD')
    sl = one(receptions=4, rec_yards=50)
    check('DK = 9.0', abs(DK.score(sl)[0] - 9.0) < 1e-9, str(DK.score(sl)[0]))
    check('FD = 7.0', abs(FD.score(sl)[0] - 7.0) < 1e-9, str(FD.score(sl)[0]))


def test_E_kicker():
    print('\nE. K: two makes under 40, one 40s, one 50+, three extra points')
    sl = SL.from_line(1, xp_made=3)
    sl.fg_made_by_bucket = {'FG20s': np.array([1.0]), 'FG30s': np.array([1.0]),
                            'FG40s': np.array([1.0]), 'FG50+': np.array([1.0])}
    # 3+3 + 4 + 5 + 3 = 18.0 on both sites, distance-banded
    check('DK = 18.0', abs(DK.score_kicker(sl)[0] - 18.0) < 1e-9,
          str(DK.score_kicker(sl)[0]))
    check('FD = 18.0', abs(FD.score_kicker(sl)[0] - 18.0) < 1e-9,
          str(FD.score_kicker(sl)[0]))
    flat = SL.from_line(1, fg_made=4, xp_made=3)
    check('  with no distance buckets the fallback is flat 3.0 a make, and the '
          'two answers differ, so the fallback cannot be mistaken for the '
          'banded one',
          abs(DK.score_kicker(flat)[0] - 15.0) < 1e-9,
          str(DK.score_kicker(flat)[0]))


def test_F_unsupported_events_are_named_not_zeroed():
    print('\nF. what the simulation does not produce')
    for k in ('fumbles_lost', 'two_point_conversions', 'return_td', 'dst'):
        check(f'  {k} is declared NOT_SIMULATED with a reason',
              k in SL.NOT_SIMULATED and SL.NOT_SIMULATED[k],
              str(SL.NOT_SIMULATED.get(k)))
    fields = {f for f in SL.StatLine.__dataclass_fields__}
    check('  and no StatLine field pretends to carry them',
          not (fields & {'fumbles_lost', 'two_point', 'return_td'}),
          str(sorted(fields)))
    check('  both rule tables keep a coefficient for them, so a future '
          'simulation that emits them is scored rather than silently dropped',
          'fumble_lost' in DK.RULES and 'fumble_lost' in FD.RULES)
    check('  DST is not rosterable on either configured format',
          SR.SITES['FANDUEL_SINGLE_GAME']['dst_is_rosterable'] is False)


def test_G_draftkings_reconciles_to_the_engine():
    print('\nG. the anchor: DK adapter against the engine`s own array')
    o = DB.build()
    check('the dual board builds', o.state is State.PASS,
          f'{o.state}[{o.code}]')
    d = o.evidence['dk_reconciliation_max_abs_diff']
    check(f'  and reproduces dk_scoring/dk_points to {d:.1e} over 29 players '
          f'and 8,000 worlds', d < 1e-9, str(d))
    check('  which is what licenses the same assembly feeding FanDuel',
          o.evidence['same_draws_both_platforms'] is True)


def test_H_same_football_different_lawful_scores():
    print('\nH. cross-platform regression: one world, two lawful answers')
    o = DB.build()
    rows = {r['name']: r for r in o.value}
    star = rows['Amon-Ra St. Brown']
    check('a high-reception receiver scores materially less on FanDuel',
          star['fd_minus_dk_mean'] < -3.0, str(star['fd_minus_dk_mean']))
    qb = rows['Josh Allen']
    check('  a quarterback with no catches loses far less',
          abs(qb['fd_minus_dk_mean']) < abs(star['fd_minus_dk_mean']),
          f"{qb['fd_minus_dk_mean']} vs {star['fd_minus_dk_mean']}")
    check('  and every FanDuel mean is at or below its DraftKings mean, since '
          'FanDuel here has no bonus and a smaller reception credit',
          all(r['FANDUEL']['mean'] <= r['DRAFTKINGS']['mean'] + 1e-9
              for r in o.value))
    check('  P(zero) is essentially identical, because scoring rules cannot '
          'change whether a player produced anything',
          all(abs(r['FANDUEL']['p_zero'] - r['DRAFTKINGS']['p_zero']) < 0.01
              for r in o.value))


def test_I_no_platform_scoring_reaches_the_football_model():
    print('\nI. the boundary: nothing upstream imports a scoring adapter')
    offenders = []
    for tree in ('nfl/production', 'nfl/research/oas1', 'nfl/capture',
                 'nfl/ingest'):
        for mod in (_REPO / tree).rglob('*.py'):
            if '__pycache__' in mod.parts:
                continue
            src = mod.read_text()
            for node in ast.walk(ast.parse(src)):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module or '']
                for mname in mods:
                    if 'dfs.scoring' in mname or 'dfs.showdown' in mname:
                        offenders.append(f'{mod.relative_to(_REPO)} -> {mname}')
    check('no production, OAS1, capture or ingest module imports the DFS '
          'scoring or showdown layer', not offenders, str(offenders))
    check('  the arrow is one-directional by construction: the adapters import '
          'the engine`s artifacts, never the reverse',
          'nfl.dfs' not in (_REPO / 'nfl/production/team_volume_v1.py').read_text())


def test_J_fanduel_rules_are_not_treated_as_verified():
    print('\nJ. FanDuel provenance')
    r = FD.rules_state()
    check('the scoring table refuses to claim verification',
          r.state is State.BLOCKED and r.code == 'FANDUEL_RULES_UNVERIFIED',
          f'{r.state}[{r.code}]')
    check('  with cause NETWORK, naming what is missing',
          r.evidence.get('cause') in (Cause.NETWORK, Cause.NETWORK.value))
    check('  and the three highest-risk coefficients are named',
          set(FD.HIGHEST_RISK_IF_WRONG) == {'reception', 'bonus_100_rec_yards',
                                            'bonus_300_pass_yards'})
    check('  every FanDuel coefficient is marked UNVERIFIED',
          set(FD.RULE_PROVENANCE.values()) == {FD.UNVERIFIED})
    sd = SR.assert_verified('DRAFTKINGS_SHOWDOWN')
    sf = SR.assert_verified('FANDUEL_SINGLE_GAME')
    check('  DraftKings legality IS verified, against the real entries file',
          sd.state is State.PASS, f'{sd.state}[{sd.code}]')
    check('  FanDuel legality is NOT, and the refusal says what would clear it',
          sf.state is State.BLOCKED
          and 'salary export' in sf.detail, f'{sf.state}[{sf.code}]')
    check('  the two formats differ in roster size',
          SR.SITES['DRAFTKINGS_SHOWDOWN']['roster_size'] !=
          SR.SITES['FANDUEL_SINGLE_GAME']['roster_size'])
    check('  and, critically, in whether the multiplier slot costs extra salary',
          SR.SITES['DRAFTKINGS_SHOWDOWN']['salary_is_multiplied'] is True
          and SR.SITES['FANDUEL_SINGLE_GAME']['salary_is_multiplied'] is False)


def test_K_legality_is_enforced_per_site():
    print('\nK. lineup legality uses each site`s own config')
    dk6 = SR.assert_lineup_legal('DRAFTKINGS_SHOWDOWN',
                                 [12000, 11400, 10400, 6400, 2400, 400],
                                 ['DET', 'BUF', 'DET', 'BUF', 'BUF', 'BUF'])
    check('a legal DK Showdown lineup passes', dk6.state is State.PASS,
          f'{dk6.state}[{dk6.code}]')
    check('  and its captain salary was multiplied: 12000 * 1.5 shows up',
          abs(dk6.evidence['salary'] - (18000 + 11400 + 10400 + 6400 + 2400
                                        + 400)) < 1e-9,
          str(dk6.evidence['salary']))
    six_on_fd = SR.assert_lineup_legal('FANDUEL_SINGLE_GAME',
                                       [12000] * 6, ['DET'] * 3 + ['BUF'] * 3)
    check('  the same six-player shape is REFUSED on FanDuel',
          six_on_fd.state is State.FAIL
          and six_on_fd.code == 'LINEUP_WRONG_ROSTER_SIZE',
          f'{six_on_fd.state}[{six_on_fd.code}]')
    one_team = SR.assert_lineup_legal('DRAFTKINGS_SHOWDOWN',
                                      [1000] * 6, ['DET'] * 6)
    check('  a one-team lineup is refused', one_team.state is State.FAIL
          and one_team.code == 'LINEUP_TOO_FEW_TEAMS')
    over = SR.assert_lineup_legal('DRAFTKINGS_SHOWDOWN',
                                  [12000, 12000, 12000, 12000, 12000, 12000],
                                  ['DET', 'BUF', 'DET', 'BUF', 'DET', 'BUF'])
    check('  an over-cap lineup is refused', over.state is State.FAIL
          and over.code == 'LINEUP_OVER_CAP')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_quarterback, test_B_running_back, test_C_wide_receiver,
               test_D_tight_end, test_E_kicker,
               test_F_unsupported_events_are_named_not_zeroed,
               test_G_draftkings_reconciles_to_the_engine,
               test_H_same_football_different_lawful_scores,
               test_I_no_platform_scoring_reaches_the_football_model,
               test_J_fanduel_rules_are_not_treated_as_verified,
               test_K_legality_is_enforced_per_site):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
