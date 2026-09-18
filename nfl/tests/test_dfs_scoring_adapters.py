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
    # 0.04*300=12.0  +4*3=12.0  -1.0  +0.1*20=2.0  +3.0 (300-yard bonus)
    check('DK = 28.0', abs(DK.score(sl)[0] - 28.0) < 1e-9, str(DK.score(sl)[0]))
    # CORRECTED 2026-09-18. This read FD = 25.0, on a recalled table that had
    # FanDuel paying no yardage bonus. FanDuel pays the same +3.
    check('FD = 28.0', abs(FD.score(sl)[0] - 28.0) < 1e-9, str(FD.score(sl)[0]))
    check('  the two sites agree exactly on a passer who caught nothing, '
          'because receptions are now the only difference between them',
          abs(DK.score(sl)[0] - FD.score(sl)[0]) < 1e-9)
    no_bonus = one(pass_yards=299, pass_td=3, interceptions=1, rush_yards=20)
    # 299 * 0.04 = 11.96, not 12.00. The first version of this line expected
    # 25.0 by rounding the yardage in my head; the adapters were right and the
    # expectation was wrong. 11.96 + 12.0 - 1.0 + 2.0 = 24.96 on both sites.
    check('  and one yard short of 300 BOTH lose the bonus together',
          abs(DK.score(no_bonus)[0] - 24.96) < 1e-9
          and abs(FD.score(no_bonus)[0] - 24.96) < 1e-9,
          f'{DK.score(no_bonus)[0]} vs {FD.score(no_bonus)[0]}')


def test_B_running_back():
    print('\nB. RB: 100 rush yds, 1 rush TD, 5 catches, 40 rec yds')
    sl = one(rush_yards=100, rush_td=1, receptions=5, rec_yards=40)
    # DK 10.0 + 6.0 + 5*1.0 + 4.0 + 3.0 (100-rush bonus) = 28.0
    check('DK = 28.0', abs(DK.score(sl)[0] - 28.0) < 1e-9, str(DK.score(sl)[0]))
    # FD 10.0 + 6.0 + 5*0.5 + 4.0 + 3.0 = 25.5.  CORRECTED from 22.5.
    check('FD = 25.5', abs(FD.score(sl)[0] - 25.5) < 1e-9, str(FD.score(sl)[0]))
    check('  the gap is 2.5, which is exactly half a point per catch and '
          'nothing else', abs((DK.score(sl)[0] - FD.score(sl)[0]) - 2.5) < 1e-9)


def test_C_wide_receiver():
    print('\nC. WR: 8 catches, 100 rec yds, 1 rec TD')
    sl = one(receptions=8, rec_yards=100, rec_td=1)
    # DK 8*1.0 + 10.0 + 6.0 + 3.0 = 27.0
    check('DK = 27.0', abs(DK.score(sl)[0] - 27.0) < 1e-9, str(DK.score(sl)[0]))
    # FD 8*0.5 + 10.0 + 6.0 + 3.0 = 23.0.  CORRECTED from 20.0: the recalled
    # table charged this receiver three points for breaking 100 yards, which
    # is the outcome a tournament lineup exists to catch.
    check('FD = 23.0', abs(FD.score(sl)[0] - 23.0) < 1e-9, str(FD.score(sl)[0]))
    check('  a high-catch receiver still loses the most, at exactly 0.5 a '
          'catch', abs((DK.score(sl)[0] - FD.score(sl)[0]) - 4.0) < 1e-9)


def test_D_tight_end():
    print('\nD. TE: 4 catches, 50 rec yds, no TD')
    sl = one(receptions=4, rec_yards=50)
    check('DK = 9.0', abs(DK.score(sl)[0] - 9.0) < 1e-9, str(DK.score(sl)[0]))
    check('FD = 7.0', abs(FD.score(sl)[0] - 7.0) < 1e-9, str(FD.score(sl)[0]))
    check('  no bonus is reached by either site, so the whole gap is the '
          'four catches', abs((DK.score(sl)[0] - FD.score(sl)[0]) - 2.0) < 1e-9)


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
    check('  every FanDuel mean is at or below its DraftKings mean, the gap '
          'being half a point per catch',
          all(r['FANDUEL']['mean'] <= r['DRAFTKINGS']['mean'] + 1e-9
              for r in o.value))
    # THE IDENTITY. With the bonuses now agreeing, receptions are the only
    # scored quantity separating the sites, so this must hold to floating
    # point for every player in every world -- a far stronger check than any
    # pair of hand-built lines, because it fails if either adapter drifts on
    # any term.
    res = o.evidence['identity_fd_equals_dk_minus_half_ppr_max_residual']
    check(f'  FD = DK - 0.5 x receptions holds to {res:.1e} over all 29 '
          f'players and 8,000 worlds', res < 1e-9, str(res))
    zero_rec = [r for r in o.value if r['receptions_mean'] == 0.0]
    check('  and a player who never catches a pass scores identically on both',
          zero_rec and all(abs(r['fd_minus_dk_mean']) < 1e-9 for r in zero_rec),
          str([r['name'] for r in zero_rec][:4]))
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


def test_J_fanduel_rules_are_verified_and_the_correction_is_recorded():
    print('\nJ. FanDuel provenance, after OUT-022A and OUT-022B')
    r = FD.rules_state()
    check('the scoring table is now VERIFIED against a named source',
          r.state is State.PASS and r.code == 'FANDUEL_RULES_VERIFIED',
          f'{r.state}[{r.code}]')
    check('  every coefficient carries that provenance',
          set(FD.RULE_PROVENANCE.values()) == {FD.VERIFIED})
    # THE CORRECTION IS KEPT, NOT ERASED. All three coefficients that were
    # wrong are the three that had been flagged HIGHEST_RISK_IF_WRONG, which
    # is the argument for the gate rather than against it.
    c = FD.CORRECTIONS_2026_09_18
    for k in ('bonus_300_pass_yards', 'bonus_100_rush_yards',
              'bonus_100_rec_yards'):
        check(f'  {k}: was {c[k]["was"]}, now {c[k]["now"]}',
              c[k]['was'] == 0.0 and c[k]['now'] == 3.0, str(c[k]))
        check(f'    and the live table agrees', FD.BONUSES[k] == 3.0,
              str(FD.BONUSES[k]))
    check('  the bonuses now match DraftKings exactly',
          all(FD.BONUSES[k] == DK.RULES[k] for k in FD.BONUSES))
    check('  leaving receptions as the only difference',
          FD.RULES['reception'] == 0.5 and DK.RULES['reception'] == 1.0)
    sd = SR.assert_verified('DRAFTKINGS_SHOWDOWN')
    sf = SR.assert_verified('FANDUEL_SINGLE_GAME')
    check('  DraftKings legality verified against the real entries file',
          sd.state is State.PASS, f'{sd.state}[{sd.code}]')
    check('  FanDuel legality now verified against first-party documentation',
          sf.state is State.PASS, f'{sf.state}[{sf.code}]')
    fd_rules = SR.SITES['FANDUEL_SINGLE_GAME']
    corr = fd_rules['corrected_2026_09_18']
    check('  roster size corrected 5 -> 6', corr['roster_size'] ==
          {'was': 5, 'now': 6} and fd_rules['roster_size'] == 6)
    check('  MVP salary multiplier corrected False -> True, the field that '
          'changes the SHAPE of the optimisation',
          corr['salary_is_multiplied'] == {'was': False, 'now': True}
          and fd_rules['salary_is_multiplied'] is True)
    check('  so both formats now multiply the multiplier slot`s salary',
          SR.SITES['DRAFTKINGS_SHOWDOWN']['salary_is_multiplied']
          == fd_rules['salary_is_multiplied'] is True)
    check('  and they still differ on the cap',
          SR.SITES['DRAFTKINGS_SHOWDOWN']['salary_cap'] == 50000
          and fd_rules['salary_cap'] == 60000)


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
    fd6 = SR.assert_lineup_legal('FANDUEL_SINGLE_GAME',
                                 [12000, 11400, 10400, 6400, 2400, 400],
                                 ['DET', 'BUF', 'DET', 'BUF', 'BUF', 'BUF'])
    check('  the same six-player shape is now LEGAL on FanDuel too',
          fd6.state is State.PASS, f'{fd6.state}[{fd6.code}]')
    check('    with the MVP salary multiplied, same as DraftKings',
          abs(fd6.evidence['salary'] - dk6.evidence['salary']) < 1e-9,
          f"{fd6.evidence['salary']} vs {dk6.evidence['salary']}")
    check('    but $11,000 of headroom left, because the cap is 60000',
          abs(fd6.evidence['salary'] - 49000) < 1e-9)
    five_on_fd = SR.assert_lineup_legal('FANDUEL_SINGLE_GAME',
                                        [12000] * 5, ['DET'] * 3 + ['BUF'] * 2)
    check('  and a FIVE-player lineup -- the stale pre-2025 shape -- is '
          'refused', five_on_fd.state is State.FAIL
          and five_on_fd.code == 'LINEUP_WRONG_ROSTER_SIZE',
          f'{five_on_fd.state}[{five_on_fd.code}]')
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
               test_J_fanduel_rules_are_verified_and_the_correction_is_recorded,
               test_K_legality_is_enforced_per_site):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
