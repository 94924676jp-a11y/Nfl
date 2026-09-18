"""KNOWN_ROLE_DEFECT_CANNOT_DRIVE_PORTFOLIO_CONCENTRATION.

The regression case is a real portfolio that was really delivered. It is kept
in the tree, not paraphrased, because a fixture I wrote to fail would only
prove I can write a failing fixture. This one was built by an optimizer that
believed its inputs, on the night the defect was already in the repository.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.dfs import portfolio_guard as PG                # noqa: E402
from nfl.production.dfs import projection_confidence as PC          # noqa: E402
from sportsplatform.governance.outcome import Cause, State          # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

FIX = _REPO/'nfl/research/dfs/DET_BUF_2026W2'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _name(s):
    return re.sub(r'\s*\(\d+\)$', '', s).strip()


def load(path):
    out = []
    for r in csv.reader(open(path)):
        if r and r[0].isdigit():
            out.append({'captain': _name(r[4]),
                        'flex': [_name(x) for x in r[5:10]]})
    return out


#: The tags as they stood on 2026-09-17, from evidence already in the tree.
#: BUF non-QB skill players are ROLE_STATE_CONCERN because CS1 is
#: quarterback-only and the P2 diagnostic found an appearance inversion on this
#: roster. Nothing here is a claim about talent.
TAGS = {}
for p in ('Jahmyr Gibbs', 'Amon-Ra St. Brown', 'Jared Goff', 'Josh Allen',
          'Jameson Williams', 'Sam LaPorta', 'Isaac TeSlaa', 'Brock Wright',
          'Tyler Conklin', 'Sione Vaki', 'Tay Martin', 'Tom Kennedy',
          'Jackson Meeks', 'Joshua Dobbs', 'Jacob Saylors',
          'Tyler Bass', 'Jake Bates'):
    TAGS[p] = PC.MODEL_SUPPORTED
for p in ('James Cook III', 'Ray Davis', 'Frank Gore Jr.', 'DJ Moore',
          'Khalil Shakir', 'Keon Coleman', 'Dalton Kincaid', 'Dawson Knox',
          'Joshua Palmer', 'Greg Dortch', 'Jackson Hawes', 'Keleki Latu',
          'Kyle Allen'):
    TAGS[p] = PC.ROLE_STATE_CONCERN
TAGS['Skyler Bell'] = PC.KNOWN_INACTIVE_STALE
TAGS['Ty Johnson'] = PC.KNOWN_INACTIVE_STALE


def test_A_the_delivered_portfolio_is_refused():
    print('\nA. KNOWN_ROLE_DEFECT_CANNOT_DRIVE_PORTFOLIO_CONCENTRATION')
    lu = load(FIX/'PORTFOLIO_CLAUDE_40.csv')
    check('the fixture is the real 40-lineup portfolio', len(lu) == 40,
          str(len(lu)))
    o = PG.authorize(lu, TAGS, label='DET_BUF_2026W2 delivered')
    check('it is REFUSED', o.state is State.FAIL
          and o.code == PG.CODE_DEFECT_DRIVEN, f'{o.state}[{o.code}]')
    check('  with cause GOVERNANCE',
          o.evidence.get('cause') in (Cause.GOVERNANCE, Cause.GOVERNANCE.value))
    check('  and the refusal is HARD', o.code in PG.HARD_CODES)
    v = {x['player']: x for x in o.evidence['violations']}
    check('  Ray Davis is named', 'Ray Davis' in v, str(sorted(v)))
    if 'Ray Davis' in v:
        d = v['Ray Davis']
        check(f"    at {d['exposure']:.1%} against a "
              f"{d['cap']:.0%} cap", d['exposure'] > 0.70, str(d))
        check('    and over the captain cap too as well as the any-slot cap',
              d['over_captain'] and d['over_any'], str(d))
    check('  Frank Gore Jr. is named', 'Frank Gore Jr.' in v, str(sorted(v)))
    check('  the rule is carried in the evidence',
          o.evidence['rule'] ==
          'PORTFOLIO_MAY_NOT_BE_AUTHORIZED_IF_HIGH_EXPOSURE_IS_DRIVEN_BY_A_'
          'KNOWN_MODEL_DEFECT')


def test_B_the_alternate_portfolio_is_also_measured_not_assumed():
    print('\nB. the portfolio that was actually used is measured, not praised')
    lu = load(FIX/'PORTFOLIO_ALTERNATE_40.csv')
    check('it loads', len(lu) == 40, str(len(lu)))
    any_, cpt, n = PG.exposures(lu)
    rd = any_.get('Ray Davis', 0.0)
    check(f'  it also carries Ray Davis, at {rd:.1%}', rd > 0.30, str(rd))
    o = PG.authorize(lu, TAGS, label='DET_BUF_2026W2 alternate')
    check('  and it is ALSO refused by the same rule',
          o.state is State.FAIL and o.code == PG.CODE_DEFECT_DRIVEN,
          f'{o.state}[{o.code}]')
    check('  so the lesson is not "the other file was fine" -- it diluted the '
          'same defect rather than governing it',
          rd > PC.POLICY[PC.ROLE_STATE_CONCERN]['max_exposure'], str(rd))
    check('  James Cook is at 0% in BOTH portfolios, which is the same defect '
          'seen from the other end',
          any_.get('James Cook III', 0.0) == 0.0, str(any_.get('James Cook III')))


def test_C_the_control_a_governed_portfolio_passes():
    print('\nC. CONTROL: the guard is not refusing everything')
    # Same players, exposure inside the caps.
    core = ['Jahmyr Gibbs', 'Amon-Ra St. Brown', 'Jared Goff', 'Sam LaPorta',
            'Jameson Williams', 'Josh Allen']
    lu = []
    for i in range(40):
        cap = core[i % 4]
        flex = [p for p in core if p != cap][:4]
        flex += ['Ray Davis'] if i < 12 else ['Isaac TeSlaa']
        lu.append({'captain': cap, 'flex': flex})
    o = PG.authorize(lu, TAGS, label='control')
    check('a portfolio inside every cap is AUTHORIZED',
          o.state is State.PASS and o.code == 'PORTFOLIO_AUTHORIZED',
          f'{o.state}[{o.code}] {o.detail[:120]}')
    check('  Ray Davis is present but at 30%, under the 35% cap',
          abs(o.value['Ray Davis']['exposure'] - 0.30) < 1e-9,
          str(o.value.get('Ray Davis')))
    check('  and the pass says it is about exposure only, not quality',
          'says nothing about whether the portfolio is good' in o.detail)


def test_D_a_blocked_player_cannot_appear_at_all():
    print('\nD. an officially inactive player is not a capped player')
    lu = [{'captain': 'Jahmyr Gibbs',
           'flex': ['Josh Allen', 'Amon-Ra St. Brown', 'Jared Goff',
                    'Sam LaPorta', 'Skyler Bell']}] * 40
    o = PG.authorize(lu, TAGS, label='with an inactive')
    check('the portfolio is refused', o.state is State.FAIL
          and o.code == PG.CODE_BLOCKED_PLAYER, f'{o.state}[{o.code}]')
    check('  naming Skyler Bell',
          'Skyler Bell' in o.evidence['blocked_players_present'],
          str(o.evidence['blocked_players_present']))


def test_E_an_untagged_player_is_a_refusal_not_a_default():
    print('\nE. absence of a warning is not a statement of confidence')
    lu = [{'captain': 'Jahmyr Gibbs',
           'flex': ['Josh Allen', 'Amon-Ra St. Brown', 'Jared Goff',
                    'Sam LaPorta', 'Nobody At All']}] * 40
    o = PG.authorize(lu, TAGS, label='untagged')
    check('the portfolio is refused', o.state is State.FAIL
          and o.code == PG.CODE_UNTAGGED, f'{o.state}[{o.code}]')
    check('  naming the untagged player',
          'Nobody At All' in o.evidence['untagged'],
          str(o.evidence['untagged']))


def test_F_an_override_must_carry_evidence():
    print('\nF. a cap is beaten by evidence, never by preference')
    lu = load(FIX/'PORTFOLIO_CLAUDE_40.csv')
    o = PG.authorize(lu, TAGS, overrides={'Ray Davis': '   ',
                                          'Frank Gore Jr.': '  '},
                     label='empty override')
    check('an override with no evidence is refused by name',
          o.state is State.FAIL and o.code == PG.CODE_OVERRIDE_UNEVIDENCED,
          f'{o.state}[{o.code}]')
    # OVERRIDING ONLY THE TWO PLAYERS I EXPECTED STILL FAILS, and the third
    # name is the point: Khalil Shakir sits at 57.5% and is tagged
    # ROLE_STATE_CONCERN for the same reason the two backs are. The portfolio
    # was over the policy in three places, not two, and I had only noticed two.
    part = PG.authorize(
        lu, TAGS,
        overrides={'Ray Davis': 'hypothetical beat report',
                   'Frank Gore Jr.': 'hypothetical beat report'},
        label='partial override')
    check('  overriding two of the three violators still fails',
          part.state is State.FAIL and part.code == PG.CODE_DEFECT_DRIVEN,
          f'{part.state}[{part.code}]')
    left = {x['player'] for x in part.evidence['violations']}
    check('  and the remaining violator is named rather than absorbed',
          'Khalil Shakir' in left, str(sorted(left)))
    o2 = PG.authorize(
        lu, TAGS,
        overrides={'Ray Davis': 'beat writer confirms Cook inactive and Davis '
                                'takes the full early-down role -- hypothetical',
                   'Frank Gore Jr.': 'same report',
                   'Khalil Shakir': 'target share independent of the RB split '
                                    '-- hypothetical'},
        label='evidenced override')
    check('  an override naming evidence for every violator is accepted',
          o2.state is State.PASS, f'{o2.state}[{o2.code}]')
    check('  and the evidence string survives into the audit row',
          bool((o2.value or {}).get('Ray Davis', {}).get('override')),
          str((o2.value or {}).get('Ray Davis')))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_delivered_portfolio_is_refused,
               test_B_the_alternate_portfolio_is_also_measured_not_assumed,
               test_C_the_control_a_governed_portfolio_passes,
               test_D_a_blocked_player_cannot_appear_at_all,
               test_E_an_untagged_player_is_a_refusal_not_a_default,
               test_F_an_override_must_carry_evidence):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
