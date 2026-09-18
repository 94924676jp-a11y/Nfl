"""Showdown DFS research layer: the rules that would have stopped 2026-09-17.

Every fixture is a real artifact. The portfolios are the files that were
actually delivered, and the draws are the sealed pregame board.

USES_LIVE_GAME_OUTCOME_DATA = FALSE for every check in this module.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.showdown import universe as U                          # noqa: E402
from nfl.dfs.showdown import captain_metrics as CM                  # noqa: E402
from nfl.dfs.showdown import candidates as CD                       # noqa: E402
from nfl.dfs.showdown import portfolio_report as PR                 # noqa: E402
from nfl.production.dfs import projection_confidence as PC          # noqa: E402
from sportsplatform.governance.outcome import Cause, State          # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []
FIX = _REPO / 'nfl/research/dfs/DET_BUF_2026W2'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _nm(s):
    return re.sub(r'\s*\(\d+\)$', '', s).strip()


def load_portfolio(fn):
    return [{'captain': _nm(r[4]), 'flex': [_nm(x) for x in r[5:10]]}
            for r in csv.reader(open(FIX / fn)) if r and r[0].isdigit()]


_U = U.build()
PLAYERS = _U.value['playable'] if _U.state is State.PASS else []
OPT = json.loads((FIX / 'OPTIMAL_WORLDS.json').read_text())['rows']


def test_A_captain_metrics_are_features_not_exposure():
    print('\nA. captain metrics')
    o = CM.metrics(PLAYERS)
    check('metrics build', o.state is State.PASS, f'{o.state}[{o.code}]')
    check('  no exposure percentage is produced',
          o.evidence['exposure_percentages_produced'] is False)
    check('  ties for top scorer are excluded, not broken arbitrarily',
          0 <= o.evidence['share_of_worlds_with_tied_top'] < 0.05,
          str(o.evidence['share_of_worlds_with_tied_top']))
    by = {r['name']: r for r in o.value}
    # THE MEAN AND THE CEILING DISAGREE, which is the whole point.
    goff, shak = by['Jared Goff'], by['Khalil Shakir']
    check('  Goff outscores Shakir on the MEAN',
          goff['mean'] > shak['mean'],
          f"{goff['mean']:.2f} vs {shak['mean']:.2f}")
    check('  but Shakir is at least as likely to be the top raw scorer, so a '
          'mean-ranked captain list is ranking the wrong quantity',
          shak['p_top1_unique'] >= goff['p_top1_unique'],
          f"{shak['p_top1_unique']:.4f} vs {goff['p_top1_unique']:.4f}")
    check('  the captain transform is mechanical 1.5x',
          abs(by['Jahmyr Gibbs']['cpt_mean']
              - 1.5 * by['Jahmyr Gibbs']['mean']) < 1e-9)


def test_B_optimal_frequency_is_not_the_mean_ranking():
    print('\nB. simulated optimal-lineup frequency')
    o = {r['name']: r for r in OPT}
    check('the quantity is labelled, not left to the reader',
          all(r['quantity'] == 'SIMULATED_OPTIMAL_LINEUP_FREQUENCY'
              for r in OPT))
    # Goff is 4th by mean and 3rd by optimality; Gore is 13th by mean and
    # 12th by optimality at a twentieth of the salary. The orderings differ.
    by_mean = [r['name'] for r in sorted(OPT, key=lambda r: -r['mean_dk'])]
    by_opt = [r['name'] for r in sorted(OPT, key=lambda r: -r['p_optimal'])]
    check('  the mean ordering and the optimality ordering are NOT the same',
          by_mean != by_opt)
    check('  Jared Goff is more optimal than his mean rank suggests',
          by_opt.index('Jared Goff') < by_mean.index('Jared Goff'),
          f"opt {by_opt.index('Jared Goff')} mean {by_mean.index('Jared Goff')}")
    check('  every probability is a share of solved worlds',
          all(0.0 <= r['p_optimal'] <= 1.0 for r in OPT))
    check('  optimal-captain shares sum to about one',
          abs(sum(r['p_optimal_captain'] for r in OPT) - 1.0) < 0.02,
          str(round(sum(r['p_optimal_captain'] for r in OPT), 4)))


def test_C_captain_exposure_cannot_be_created_by_an_arbitrary_minimum():
    """CAPTAIN_EXPOSURE_CANNOT_BE_CREATED_SOLELY_BY_ARBITRARY_MINIMUM_COUNT"""
    print('\nC. CAPTAIN_EXPOSURE_CANNOT_BE_CREATED_SOLELY_BY_ARBITRARY_'
          'MINIMUM_COUNT')
    lus = load_portfolio('PORTFOLIO_CLAUDE_40.csv')
    cpt = {}
    for lu in lus:
        cpt[lu['captain']] = cpt.get(lu['captain'], 0) + 1
    at_cap = sorted(k for k, v in cpt.items() if v == 6)
    check('the delivered portfolio has captains pinned at exactly 6/40',
          len(at_cap) >= 5, f'{cpt}')
    check('  6/40 is 15.0%, which is the counter and not a football claim',
          abs(6 / 40 - 0.15) < 1e-12)
    o = {r['name']: r for r in OPT}
    bad = []
    for nm in at_cap:
        po = o.get(nm, {}).get('p_optimal_captain')
        if po is not None and abs(0.15 - po) > 0.05:
            bad.append((nm, round(po, 4)))
    check('  and for most of them 15% is nowhere near their simulated '
          'optimal-captain share', len(bad) >= 3, str(bad))
    rd = o.get('Ray Davis', {}).get('p_optimal_captain')
    check(f'  Ray Davis: 15.0% captain exposure against '
          f'{rd:.2%} optimal-captain', rd is not None and rd < 0.06, str(rd))
    # QUARANTINED MEANS "NOT EXECUTABLE", NOT "NEVER MENTIONED". The first
    # version of this check grepped for the string and went red on
    # captain_metrics.py -- whose DOCSTRING quotes the rule, which is exactly
    # where a withdrawn rule belongs. The AST distinguishes a name that runs
    # from a name that is being described.
    import ast
    live = []
    for mod in (_REPO / 'nfl/dfs/showdown').glob('*.py'):
        for node in ast.walk(ast.parse(mod.read_text())):
            if isinstance(node, ast.Name) and 'capct' in node.id:
                live.append(f'{mod.name}:{node.id}')
    check('  the mechanical minimum is quarantined: it survives in prose and '
          'nowhere in executable code', not live, str(live))
    doc = (_REPO / 'nfl/dfs/showdown/captain_metrics.py').read_text()
    check('  and the withdrawn rule IS recorded, so the next reader knows it '
          'existed', 'capct[ck] >= 6' in doc)


def test_D_confidence_tags_reach_the_lineup_and_the_report():
    print('\nD. confidence propagates into candidate, portfolio and report')
    d = CD.describe('Jahmyr Gibbs',
                    ['Josh Allen', 'Amon-Ra St. Brown', 'Khalil Shakir',
                     'Ray Davis', 'Frank Gore Jr.'], PLAYERS)
    check('a candidate carries a tag for every player',
          d.state is State.PASS and len(d.value['confidence_tags']) == 6,
          f'{d.state}[{d.code}]')
    check('  and counts its concern-tagged players',
          d.value['n_concern_tagged'] == 3,
          str(d.value['concern_players']))
    check('  no numeric haircut was applied to the projection',
          abs(d.value['projected_mean']
              - (1.5 * next(p['draws'].mean() for p in PLAYERS
                            if p['name'] == 'Jahmyr Gibbs')
                 + sum(next(p['draws'].mean() for p in PLAYERS
                            if p['name'] == n)
                       for n in ('Josh Allen', 'Amon-Ra St. Brown',
                                 'Khalil Shakir', 'Ray Davis',
                                 'Frank Gore Jr.')))) < 1e-6,
          'uncertainty is preserved, not converted into a penalty')
    alt = PR.report(load_portfolio('PORTFOLIO_ALTERNATE_40.csv'), PLAYERS,
                    optimal=OPT, label='alternate')
    check('  the portfolio report carries tag share by slot',
          alt.state is State.PASS
          and PC.ROLE_STATE_CONCERN in alt.evidence['confidence_tag_slot_share'],
          f'{alt.state}[{alt.code}]')


def test_E_an_unresolvable_player_stops_the_report():
    print('\nE. the delivered portfolio rosters players the model cannot name')
    o = PR.report(load_portfolio('PORTFOLIO_CLAUDE_40.csv'), PLAYERS,
                  optimal=OPT, label='delivered')
    check('the report REFUSES rather than scoring around them',
          o.state is State.FAIL
          and o.code == 'PORTFOLIO_CONTAINS_UNDESCRIBABLE_LINEUP',
          f'{o.state}[{o.code}]')
    names = {n for e in o.evidence['errors']
             for n in re.findall(r"'([^']+)'", e['detail'])}
    check('  naming the kickers, whose identity the board cannot resolve',
          {'Tyler Bass', 'Jake Bates'} & names == {'Tyler Bass', 'Jake Bates'},
          str(sorted(names)))
    check('  15 of 40 lineups are affected',
          len(o.evidence['errors']) == 15, str(len(o.evidence['errors'])))
    check('  and the reason is the refused (team, position) join',
          'team' in U.KICKER_JOIN_REFUSED)


def test_F_salary_relief_dependence_is_measured():
    print('\nF. the cheap-punt failure mode, measured')
    d = CD.describe('Jahmyr Gibbs',
                    ['Josh Allen', 'Amon-Ra St. Brown', 'Khalil Shakir',
                     'Ray Davis', 'Frank Gore Jr.'], PLAYERS)
    dep = d.value['salary_relief_dependence']
    check('the cheapest player is identified', dep['cheapest_player']
          == 'Frank Gore Jr.', str(dep))
    check(f"  at ${dep['cheapest_salary']} for "
          f"{dep['cheapest_mean_dk']:.2f} points, "
          f"{dep['cheapest_pts_per_1k']:.1f} per $1k",
          dep['cheapest_pts_per_1k'] > 10.0, str(dep))
    check('  and the best affordable replacement is named, so the dependence '
          'is a number rather than an impression',
          dep['best_affordable_replacement_mean'] >= 0.0
          and 'mean_lost_by_swapping' in dep, str(dep))
    check('  no threshold is fitted from the outcome',
          isinstance(CD.CHEAP_SALARY, int))


def test_G_the_audit_reports_and_does_not_repair():
    print('\nG. the audit highlights mismatches instead of fixing them')
    o = PR.report(load_portfolio('PORTFOLIO_ALTERNATE_40.csv'), PLAYERS,
                  optimal=OPT, label='alternate')
    check('it reports', o.state is State.PASS, f'{o.state}[{o.code}]')
    check('  and says so explicitly',
          o.evidence['this_module_does_not_repair'] is True)
    m = {e['player']: e for e in o.evidence['exposure_vs_optimality_mismatches']}
    check('  Khalil Shakir is flagged: exposure far above simulated optimality',
          'Khalil Shakir' in m, str(sorted(m)))
    check('  duplicated cores and uniqueness distance are reported',
          'duplicated_cores' in o.evidence
          and o.evidence['uniqueness_distance'] is not None)
    check('  cheap-punt reliance is reported per player',
          isinstance(o.evidence['cheap_punt_reliance'], dict))


def test_H_no_live_game_data_anywhere_in_this_layer():
    print('\nH. the live-game information barrier')
    for mod in sorted((_REPO / 'nfl/dfs/showdown').glob('*.py')):
        src = mod.read_text()
        check(f'  {mod.name} reads no live result',
              'box_score' not in src and 'final_score' not in src
              and 'live_result' not in src)
    check('the universe declares it', _U.evidence['uses_live_game_outcome_data']
          is False)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_captain_metrics_are_features_not_exposure,
               test_B_optimal_frequency_is_not_the_mean_ranking,
               test_C_captain_exposure_cannot_be_created_by_an_arbitrary_minimum,
               test_D_confidence_tags_reach_the_lineup_and_the_report,
               test_E_an_unresolvable_player_stops_the_report,
               test_F_salary_relief_dependence_is_measured,
               test_G_the_audit_reports_and_does_not_repair,
               test_H_no_live_game_data_anywhere_in_this_layer):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
