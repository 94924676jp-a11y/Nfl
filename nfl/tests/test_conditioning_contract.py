"""A conditional number must name and define the event it conditions on.

WHAT THIS MODULE ASSERTS
========================
1. A CONDITIONAL MEAN WITHOUT A NAMED EVENT IS REFUSED. This is the contract
   in one assertion. Anyone can divide a conditional by an unconditional and
   recover a probability, but a ratio does not say WHICH event it is the
   probability of -- and "he plays", "he is active", "he has a role" and "he
   records an opportunity" are four different events.
2. AND A NAMED EVENT MUST BE DEFINED. A reader cannot check a number against
   an event they have to guess at.
3. UNMEASURED STAGES ARE NOT_IDENTIFIED, NEVER 1.0. The QB chain declares
   ROSTER_ACTIVE and OWNS_MEANINGFUL_DROPBACKS, neither of which this artifact
   can evaluate, and they come back unmeasured rather than quietly assumed.
   Declaring a stage we cannot evaluate is the difference between "we did not
   measure this" and "this does not exist".
4. EVERY POSITION HAS A DELIBERATELY DECLARED CHAIN and an unknown position
   raises rather than defaulting to the receiver chain, which would assert a
   role structure nobody chose.
5. DST IS A GAME-LEVEL EVENT and carries no individual participation stage.
6. THE UNCONDITIONAL MEAN IS THE RIGHT NUMBER FOR A DFS SLOT and the record
   says so, because a player who does not appear scores zero.
7. THE REAL RUN DECOMPOSES AS MEASURED.
"""
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import conditioning_contract as CC  # noqa: E402

PASSED = FAILED = BLOCKED = 0
RUN = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'unsealed' / \
    '2026_03_ATL_GB' / '2fc4e9599f0889f1'


def chk(label, ok, detail=''):
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


def test_a_conditional_mean_must_name_and_define_its_event():
    vals = np.concatenate([np.full(400, 10.0), np.zeros(600)])
    mask = np.concatenate([np.ones(400, bool), np.zeros(600, bool)])
    rec = CC.build('WR', vals, opportunity_mask=mask, player='X')
    chk('the conditioning event is named',
        rec['conditioned_on'] == 'ANY_MODELLED_OPPORTUNITY')
    chk('and defined in the record itself',
        'records at least one non-zero modelled opportunity'
        in rec['conditioned_on_definition'])
    chk('the conditional mean is right', abs(rec['mean_conditional'] - 10) < 1e-9)
    chk('and the assertion passes', CC.assert_event_named(rec) is None)

    stripped = dict(rec, conditioned_on=None)
    try:
        CC.assert_event_named(stripped)
        chk('an unnamed event is refused', False, 'it passed')
    except CC.ContractError as e:
        chk('an unnamed event is refused', 'cannot be checked by a reader' in str(e))

    undefined = dict(rec)
    undefined.pop('conditioned_on_definition')
    try:
        CC.assert_event_named(undefined)
        chk('a named but undefined event is refused', False, 'it passed')
    except CC.ContractError as e:
        chk('a named but undefined event is refused', 'not defined' in str(e))


def test_unmeasured_stages_are_not_identified_never_one():
    vals = np.full(1000, 5.0)
    mask = np.ones(1000, bool)
    rec = CC.build('QB', vals, opportunity_mask=mask, player='X')
    chk('the QB chain declares three stages',
        len(rec['declared_chain']) == 3, str(rec['declared_chain']))
    states = {s['event']: s['state'] for s in rec['stages']}
    chk('ROSTER_ACTIVE is NOT_IDENTIFIED',
        states['ROSTER_ACTIVE'] == CC.NOT_IDENTIFIED)
    chk('OWNS_MEANINGFUL_DROPBACKS is NOT_IDENTIFIED',
        states['OWNS_MEANINGFUL_DROPBACKS'] == CC.NOT_IDENTIFIED)
    chk('only the opportunity stage is MEASURED',
        states['ANY_MODELLED_OPPORTUNITY'] == CC.MEASURED)
    unmeasured = [s for s in rec['stages'] if s['state'] == CC.NOT_IDENTIFIED]
    chk('and unmeasured stages carry no probability',
        all(s['p'] is None for s in unmeasured))
    chk('each saying not-measured is not the same as one',
        all('different from it being one' in s['why'] for s in unmeasured))
    chk('the record lists which stages went unmeasured',
        sorted(rec['unmeasured_stages'])
        == ['OWNS_MEANINGFUL_DROPBACKS', 'ROSTER_ACTIVE'])


def test_every_position_has_a_declared_chain():
    for pos in ('QB', 'RB', 'WR', 'TE', 'K', 'DST'):
        chk(f'{pos} has a declared chain', bool(CC.chain_for(pos)))
    chk('the chains are not all the same',
        len({CC.CHAINS['QB'], CC.CHAINS['WR'], CC.CHAINS['K'],
             CC.CHAINS['DST']}) == 4)
    try:
        CC.chain_for('LS')
        chk('an undeclared position raises', False, 'it defaulted')
    except CC.ContractError as e:
        chk('an undeclared position raises',
            'rather than defaulting to the receiver chain' in str(e))
    chk('every event in every chain is defined',
        all(e in CC.EVENTS for c in CC.CHAINS.values() for e in c))


def test_dst_is_a_game_level_event():
    rec = CC.build('DST', np.full(100, 7.0), opportunity_mask=None,
                   player='Packers')
    chk('its only stage is the game-level one',
        [s['event'] for s in rec['stages']] == ['GAME_LEVEL_EVENT'])
    chk('which is NOT_APPLICABLE rather than unmeasured',
        rec['stages'][0]['state'] == CC.NOT_APPLICABLE)
    chk('no conditional mean is offered', rec['mean_conditional'] is None)
    chk('and the unconditional mean still is',
        abs(rec['mean_unconditional'] - 7.0) < 1e-9)


def test_the_unconditional_is_the_right_number_for_a_dfs_slot():
    rec = CC.build('WR', np.concatenate([np.full(300, 12.0), np.zeros(700)]),
                   opportunity_mask=np.concatenate([np.ones(300, bool),
                                                    np.zeros(700, bool)]))
    chk('the record says what the unconditional integrates over',
        'including the worlds in which he does not appear'
        in rec['unconditional_means_what'])
    chk('and why that is correct for a DFS slot',
        'scores zero' in rec['unconditional_means_what'])


def test_thin_conditioning_is_withheld_and_empty_input_raises():
    n = CC.MIN_CONDITIONAL_DRAWS - 1
    vals = np.concatenate([np.full(n, 9.0), np.zeros(1000)])
    mask = np.concatenate([np.ones(n, bool), np.zeros(1000, bool)])
    rec = CC.build('RB', vals, opportunity_mask=mask)
    chk('below the floor the conditional mean is withheld',
        rec['mean_conditional'] is None
        and rec['conditional_basis'] == 'TOO_FEW_QUALIFYING_DRAWS')
    chk('but the event is still named',
        rec['conditioned_on'] == 'ANY_MODELLED_OPPORTUNITY')
    try:
        CC.build('WR', np.array([]))
        chk('empty draws raise', False, 'it returned')
    except CC.ContractError as e:
        chk('empty draws raise', 'not a projection' in str(e))


def test_the_real_run_decomposes_as_measured():
    manifest = RUN / 'player_draws_manifest.json'
    if not manifest.exists():
        return blocked('real run', f'{RUN} absent')
    from nfl.research.unsealed.conditionality import opportunity_mask
    m = json.loads(manifest.read_text())
    z = np.load(RUN / 'player_draws.npz', allow_pickle=True)
    arrays = {k: z[k] for k in z.keys()}
    rid = list(m['layers']['dk_scoring']['row_ids'])
    D = arrays['dk_scoring__dk_points']

    rush = rid.index('00-0033662')
    love = rid.index('00-0036264')
    r = CC.build('QB', D[rush],
                 opportunity_mask=opportunity_mask(arrays, m['layers'],
                                                   '00-0033662'),
                 player='Cooper Rush')
    lv = CC.build('QB', D[love],
                  opportunity_mask=opportunity_mask(arrays, m['layers'],
                                                    '00-0036264'),
                  player='Jordan Love')
    CC.assert_event_named(r)
    CC.assert_event_named(lv)
    chk('Rush conditions on the opportunity event at about 0.657',
        abs(r['p_conditioning_event'] - 0.657) < 0.002,
        str(r['p_conditioning_event']))
    chk('his conditional mean is a starter line',
        abs(r['mean_conditional'] - 14.04) < 0.05,
        str(r['mean_conditional']))
    chk('Love conditions at about 0.957',
        abs(lv['p_conditioning_event'] - 0.957) < 0.002)
    chk('so the two unconditional means are not the same quantity',
        r['p_conditioning_event'] < 0.7 < lv['p_conditioning_event'])
    chk('and both records name two unmeasured stages',
        len(r['unmeasured_stages']) == 2 == len(lv['unmeasured_stages']))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
