"""The decomposition is a MEASUREMENT LAYER, so its tests measure it.

What these guard, in order of how much they would cost to get wrong:

1.  It reproduces the three numbers the sealed DEN@KC run already carries. A
    decomposition that disagreed with the artifact it decomposes would be
    reporting its own arithmetic.
2.  The ratio identity is pinned to the RIGHT probability. E[Y] = P(part) *
    E[Y | part] holds against P(zero OPPORTUNITY) and is off against P(zero
    OUTCOME) by exactly the draws where a participating player produced zero.
    Both are persisted and the test asserts which one closes.
3.  No rate is ever graded as measured. Every ratio link must carry
    DERIVED_BY_DIVISION, because a ratio computed backwards from two engine
    outputs reproduces itself whatever the engine did.
4.  A team with no modelled layer is a STATE. If DEN's absent receiving layer
    ever renders as 0.0 targets, that is a forecast of zero and this suite
    fails.
5.  The prohibited link stays uncomputed. `carries x yards-per-carry` is named
    in the board as the forbidden implementation; a diagnostic that helpfully
    fills it in would be a model change wearing a diagnostic's clothes.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import decomposition as DC                          # noqa: E402
from sportsplatform.governance.outcome import (Cause, Outcome,       # noqa: E402
                                               OutcomeError, State)

PASSED = FAILED = BLOCKED = 0

BOARD = pathlib.Path(
    _ROOT, 'nfl', 'research', 'live', '2026_01_DEN_KC',
    'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8', 'f91342d6787a66a1')

MAHOMES = '00-0033873'
NIX = '00-0039732'
KC_RB1 = '00-0038134'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


_CACHE = {}


def art():
    """The decomposed board, or None with a named reason. Never a silent {}."""
    if 'a' in _CACHE:
        return _CACHE['a']
    if not BOARD.is_dir():
        _CACHE['a'] = None
        return None
    res = DC.decompose(BOARD)
    _CACHE['a'] = res.value if res.state is State.PASS else None
    if _CACHE['a'] is None:
        print(f'  (decompose returned {res})')
    return _CACHE['a']


def _player(a, gid):
    for p in a['players']:
        if p['gsis_id'] == gid:
            return p
    return None


def _chain(a, gid, name):
    p = _player(a, gid)
    if p is None:
        return None
    for c in p['chains']:
        if c['chain'] == name:
            return c
    return None


def _links(a, gid, name):
    c = _chain(a, gid, name)
    return [] if c is None else c['links']


# ---------------------------------------------------------------------------
def test_decompose_returns_a_pass_with_content():
    if not BOARD.is_dir():
        blocked('sealed DEN@KC board', f'{BOARD} is not present in this tree')
        return
    res = DC.decompose(BOARD)
    check('decompose returns PASS', res.state is State.PASS, str(res))
    a = res.value
    check('artifact names its contract',
          a.get('contract_version') == DC.CONTRACT, str(a.get('contract_version')))
    check('both teams decomposed', a.get('teams') == ['DEN', 'KC'],
          str(a.get('teams')))
    check('players are non-empty', len(a['players']) == 19,
          f"{len(a['players'])} players")
    n_chains = sum(len(p['chains']) for p in a['players'])
    check('every player carries at least one chain',
          all(len(p['chains']) >= 1 for p in a['players']), f'{n_chains} chains')


def test_worked_example_reproduces():
    """The three numbers the sealed run already carries."""
    a = art()
    if a is None:
        blocked('worked example', 'no decomposed board')
        return
    want = {(MAHOMES, 'e_outcome'): 144.02,
            (MAHOMES, 'e_outcome_given_participates'): 244.92,
            (NIX, 'e_outcome'): 202.35,
            (NIX, 'e_outcome_given_participates'): 212.56}
    for (gid, field), expect in sorted(want.items()):
        v = _chain(a, gid, 'QB_PASSING')['views'][field]
        check(f'{gid} {field} == {expect}', abs(v - expect) <= 0.005,
              f'measured {v}')
    m = _chain(a, MAHOMES, 'QB_PASSING')['views']
    check('Mahomes P(zero outcome) == 0.413',
          abs(m['p_zero_outcome'] - 0.413) < 1e-9, str(m['p_zero_outcome']))
    check('Mahomes P(zero opportunity) == 0.412 and is NOT the same number',
          abs(m['p_zero_opportunity'] - 0.412) < 1e-9 and
          m['p_zero_opportunity'] != m['p_zero_outcome'],
          f"opp {m['p_zero_opportunity']} vs out {m['p_zero_outcome']}")
    rb = _chain(a, KC_RB1, 'RB_RUSHING')['views']
    check('KC RB1 E[carries] == 10.92', abs(rb['e_opportunity'] - 10.92) <= 0.005,
          str(rb['e_opportunity']))
    check('KC RB1 P(zero carries) == 0.150',
          abs(rb['p_zero_opportunity'] - 0.150) < 1e-9,
          str(rb['p_zero_opportunity']))
    check('KC RB1 E[carries | carries > 0] == 12.85',
          abs(rb['e_opportunity_given_nonzero_opportunity'] - 12.85) <= 0.005,
          str(rb['e_opportunity_given_nonzero_opportunity']))


def test_ratio_identity_closes_on_participation_not_on_outcome():
    a = art()
    if a is None:
        blocked('ratio identity', 'no decomposed board')
        return
    n = 0
    for p in a['players']:
        c = _chain(a, p['gsis_id'], 'QB_PASSING')
        if c is None:
            continue
        v = c['views']
        n += 1
        check(f"{p['gsis_id']} identity closes on P(participates)",
              v['ratio_identity_holds_against_p_participates'] is True,
              f"cond/uncond {v['cond_over_uncond_on_participation']} vs "
              f"1/p_part {v['one_over_p_participates']}")
    check('every QB was checked', n == 6, f'{n} QB chains')
    # AND IT DOES NOT CLOSE AGAINST P(zero attempts) FOR THE BACKUPS, which is
    # the finding: a QB can take a dropback, be sacked or scramble, and attempt
    # no pass. Mahomes and Nix have no such draw, which is why the worked
    # example appeared to close on the attempt-zero probability.
    for gid, expect in (('00-0033873', True), ('00-0039732', True),
                        ('00-0035264', False), ('00-0036879', False),
                        ('00-0036945', False), ('00-0040906', False)):
        v = _chain(a, gid, 'QB_PASSING')['views']
        check(f'{gid} zero-attempt set == non-participation set is {expect}',
              v['p_zero_opportunity_equals_non_participation'] is expect,
              f"{v['participating_draws_with_zero_opportunity']} dropback "
              f"draws with no attempt")
    v = _chain(a, MAHOMES, 'QB_PASSING')['views']
    check('the outcome-zero version does NOT close, and the gap is recorded',
          abs(v['cond_over_uncond_on_participation'] -
              v['one_over_one_minus_p_zero_outcome']) > 1e-6,
          f"{v['cond_over_uncond_on_participation']} vs "
          f"{v['one_over_one_minus_p_zero_outcome']}")


def test_measured_links_were_actually_checked_per_draw():
    a = art()
    if a is None:
        blocked('measured links', 'no decomposed board')
        return
    dbid = [l for l in _links(a, MAHOMES, 'QB_PASSING')
            if l['step'] == 'dropbacks -> attempts']
    check('the dropback identity link exists', len(dbid) == 1, str(len(dbid)))
    if dbid:
        check('db == att + sacks + scr holds on every draw',
              dbid[0]['holds_on_every_draw'] is True
              and dbid[0]['worst_absolute_deviation'] == 0.0,
              str(dbid[0]['worst_absolute_deviation']))
    kc = a['team_chains']['KC']
    by = {c['identity']: c for c in kc['conservation']}
    check('sum(receptions) == sum(QB completions) exactly',
          by['sum(receiving__receptions) == sum(qb__cmp)']
          ['holds_on_every_draw'] is True,
          str(by['sum(receiving__receptions) == sum(qb__cmp)']
              ['worst_absolute_deviation']))
    check('sum(receiving yards) == sum(QB passing yards) exactly',
          by['sum(receiving__receiving_yards) == sum(qb__pyds)']
          ['holds_on_every_draw'] is True,
          str(by['sum(receiving__receiving_yards) == sum(qb__pyds)']
              ['worst_absolute_deviation']))
    rbb = by['sum(modelled RB carries) <= designed_rush_budget']
    check('modelled RB carries stay inside the rush-play budget to 1e-5',
          rbb['holds_within_tolerance'] is True, str(rbb['worst_excess']))
    check('and the containment is reported as inexact, not rounded to exact',
          rbb['holds_exactly'] is False and rbb['worst_excess'] > 0,
          f"worst excess {rbb['worst_excess']} on "
          f"{rbb['draws_at_the_boundary']} boundary draws")


def test_no_rate_is_ever_graded_as_measured():
    a = art()
    if a is None:
        blocked('evidence grading', 'no decomposed board')
        return
    bad, rates = [], 0
    for p in a['players']:
        for c in p['chains']:
            for l in c['links']:
                looks_like_a_rate = ('/' in l['step'] or
                                     l['step'].startswith('share') or
                                     'share' in l['step'] or
                                     'rate' in l['step'] or
                                     'probability' in l['step'] or
                                     ' per ' in l['step'])
                if not looks_like_a_rate:
                    continue
                rates += 1
                if l['evidence'] != DC.DIVIDED:
                    bad.append((p['gsis_id'], l['step'], l['evidence']))
    check('at least one rate link exists to grade', rates > 0, f'{rates} rates')
    check('every rate link is graded DERIVED_BY_DIVISION', not bad, str(bad[:3]))


def test_absent_team_layer_is_a_state_and_never_a_zero():
    a = art()
    if a is None:
        blocked('absent layers', 'no decomposed board')
        return
    den = a['team_layer_states']['DEN']
    for layer in ('receiving', 'rushing'):
        check(f'DEN {layer} layer is ABSENT_TEAM_DEFERRED',
              den[layer]['state'] == DC.LAYER_ABSENT_DEFERRED,
              den[layer]['state'])
        check(f'DEN {layer} absence carries the governance code',
              den[layer]['code'] == 'APPEARANCE_TEAM_DEFERRED',
              str(den[layer]['code']))
        check(f'DEN {layer} reports zero rows, not zero opportunity',
              den[layer]['n_rows'] == 0, str(den[layer]['n_rows']))
    den_nonqb = [p for p in a['players']
                 if p['team'] == 'DEN'
                 and any(c['chain'] in ('RECEIVING', 'RB_RUSHING')
                         for c in p['chains'])]
    check('no DEN player carries a fabricated receiving or rushing chain',
          not den_nonqb, str([p['gsis_id'] for p in den_nonqb]))
    check('KC layers are modelled',
          all(a['team_layer_states']['KC'][l]['state'] == DC.LAYER_MODELLED
              for l in ('qb', 'receiving', 'rushing')),
          str(a['team_layer_states']['KC']))


def test_prohibited_rushing_conversion_stays_uncomputed():
    a = art()
    if a is None:
        blocked('rushing conversion', 'no decomposed board')
        return
    c = _chain(a, KC_RB1, 'RB_RUSHING')
    term = [l for l in c['links'] if l['step'] == 'carries -> rushing yards']
    check('the carries -> rushing yards link is present and ABSENT',
          len(term) == 1 and term[0]['evidence'] == DC.ABSENT,
          str([l['evidence'] for l in term]))
    if term:
        check('it carries the board\'s governance code',
              term[0]['code'] == 'RUSHING_CONVERSION_CONTROL_UNDEFINED',
              str(term[0]['code']))
        check('it offers NO substitute', term[0]['substitute'] is None,
              str(term[0]['substitute']))
        check('it emits no value', term[0]['value'] is None,
              str(term[0]['value']))
    check('the rushing view has a null outcome rather than a filled-in one',
          c['views']['e_outcome'] is None, str(c['views']['e_outcome']))
    ypc = [l for l in c['links'] if 'yards per carry' in l['step'].lower()]
    check('no yards-per-carry link was invented anywhere', not ypc, str(ypc))


def test_routes_are_named_as_absent_with_an_honest_substitute():
    a = art()
    if a is None:
        blocked('routes', 'no decomposed board')
        return
    c = _chain(a, '00-0039067', 'RECEIVING')
    rt = [l for l in c['links'] if l['step'] == 'team_dropbacks -> routes run']
    check('the routes link exists', len(rt) == 1, str(len(rt)))
    if rt:
        check('routes are ABSENT, not proxied silently',
              rt[0]['evidence'] == DC.ABSENT and rt[0]['value'] is None,
              str(rt[0]['evidence']))
        check('the substitute is NAMED as a proxy',
              'participation' in (rt[0]['substitute'] or ''),
              str(rt[0]['substitute']))
        check('the direction of the substitution error is stated',
              'UPPER' in (rt[0]['why_honest'] or ''),
              (rt[0]['why_honest'] or '')[:60])


def test_the_allocation_denominator_is_the_summed_pool_not_the_stored_total():
    a = art()
    if a is None:
        blocked('denominator', 'no decomposed board')
        return
    m = a['team_chains']['KC']['means']
    check('stored team_targets differs from the summed target pool',
          abs(m['stored_team_targets'] - m['sum_modelled_targets']) > 1.0,
          f"stored {m['stored_team_targets']} vs summed "
          f"{m['sum_modelled_targets']}")
    check('the summed pool sits below QB attempts, never above',
          m['sum_modelled_targets'] <= m['qb_attempts'],
          f"{m['sum_modelled_targets']} vs {m['qb_attempts']}")
    links = _links(a, '00-0039067', 'RECEIVING')
    stored = [l for l in links if l.get('code') ==
              'WS09_J12_STORED_TEAM_TARGETS_IS_NOT_THE_DENOMINATOR']
    check('the wrong denominator is persisted and flagged',
          len(stored) == 1 and stored[0]['is_the_allocation_denominator']
          is False, str(len(stored)))
    right = [l for l in links
             if l['step'] == 'target share of the modelled target pool']
    wrong = [l for l in links if 'WRONG' in l['step']]
    check('both shares are persisted so the error size is visible',
          len(right) == 1 and len(wrong) == 1,
          f'{len(right)} right, {len(wrong)} wrong')
    if right and wrong:
        check('the two shares genuinely differ',
              abs(right[0]['value'] - wrong[0]['value']) > 0.01,
              f"{right[0]['value']} vs {wrong[0]['value']}")


def test_participation_is_identified_for_qbs_and_bounded_for_everyone_else():
    a = art()
    if a is None:
        blocked('participation', 'no decomposed board')
        return
    qb = _chain(a, MAHOMES, 'QB_PASSING')['participation']
    check('QB participation is identified in the draws',
          qb['basis'] == DC.PART_IDENTIFIED, qb['basis'])
    check('and the implication was verified, not assumed',
          qb['verified_cells_violating'] == 0,
          str(qb['verified_cells_violating']))
    check('QB P(participates) is a number',
          isinstance(qb['p_participates'], float), str(qb['p_participates']))
    for gid in (KC_RB1, '00-0039067'):
        for name in ('RB_RUSHING', 'RECEIVING'):
            c = _chain(a, gid, name)
            if c is None:
                continue
            pt = c['participation']
            check(f'{gid} {name} participation is bound-only',
                  pt['basis'] == DC.PART_BOUND_ONLY, pt['basis'])
            check(f'{gid} {name} refuses to state P(participates)',
                  pt['p_participates'] is None, str(pt['p_participates']))
            check(f'{gid} {name} carries a lower bound instead',
                  isinstance(pt['p_participates_lower_bound'], float),
                  str(pt['p_participates_lower_bound']))
            check(f'{gid} {name} conditional is flagged unidentified',
                  c['views']['conditional_is_identified'] is False
                  and c['views']['conditional_caveat'] is not None,
                  str(c['views']['conditional_is_identified']))


def test_every_row_exposes_the_five_required_fields():
    a = art()
    if a is None:
        blocked('required fields', 'no decomposed board')
        return
    need = ('p_participates', 'p_zero_opportunity',
            'e_opportunity_given_participates',
            'e_outcome_given_participates', 'e_outcome')
    missing, n = [], 0
    for p in a['players']:
        for c in p['chains']:
            if c['views'] is None:
                continue
            n += 1
            for f in need:
                if f not in c['views']:
                    missing.append((p['gsis_id'], c['chain'], f))
    check('every chain was inspected', n == 28, f'{n} chains with views')
    check('all five required fields present on every row', not missing,
          str(missing[:3]))


def test_a_missing_input_is_a_named_refusal_not_an_empty_row():
    res = DC.decompose(pathlib.Path(_ROOT, 'nfl', 'no', 'such', 'board'))
    check('a missing board is BLOCKED', res.state is State.BLOCKED, str(res))
    check('with a named code',
          res.code == 'DECOMPOSITION_INPUT_UNREADABLE', res.code)
    check('and a declared cause',
          res.evidence.get('cause') == Cause.DATA.value,
          str(res.evidence.get('cause')))
    raised = False
    try:
        bool(res)
    except OutcomeError:
        raised = True
    check('the Outcome cannot be read as a boolean', raised)


def test_rows_join_by_declared_identity_not_by_position():
    if not BOARD.is_dir():
        blocked('row identity', f'{BOARD} is not present')
        return
    board, manifest, draws = DC.load(BOARD)
    for layer in ('qb', 'receiving', 'rushing', 'team_volume'):
        declared = manifest['layers'][layer]['row_ids']
        got = DC.rows_of(manifest, layer)
        check(f'{layer} rows come from row_ids',
              got == {rid: i for i, rid in enumerate(declared)},
              f'{len(got)} rows')
    check('a layer that does not exist yields no rows, not row 0',
          DC.rows_of(manifest, 'not_a_layer') == {})
    raised = False
    try:
        DC.matrix(draws, 'qb', 'not_a_metric')
    except DC.DecompositionInputError:
        raised = True
    check('a missing array is a named raise', raised)


if __name__ == '__main__':
    for fn in sorted(k for k in list(globals()) if k.startswith('test_')):
        print(fn)
        globals()[fn]()
    print(f'PASSED {PASSED} FAILED {FAILED} BLOCKED {BLOCKED}')
    sys.exit(1 if FAILED else 0)
