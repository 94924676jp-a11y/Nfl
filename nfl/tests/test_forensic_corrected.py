"""The forensic corrected-candidate comparison, and what it may not become.

THIS IS A RESEARCH CANDIDATE AND THE TESTS EXIST TO KEEP IT ONE.

The comparison is only meaningful because the two runs share an execution
identity except in the one component declared as the treatment. Three things
can silently destroy that and each has its own check here:

*   the runs stop matching outside the treatment (then a difference is
    unattributable);
*   the treatment stops being applied (then the two runs are the same run and
    the comparison says nothing);
*   the artifact acquires a promotion flag, a prospective claim, or a market
    field (then a research candidate has quietly become production).

The fourth check is the one this session paid for: a verdict must never be
softer than its own evidence. `INPUT_DEFECT_FIXED` alone on the quarterback
repair would have hidden that the mixing MOVED to Sam Howell instead of
resolving, which is the single most important thing the comparison found.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research import forensic_corrected as FC                   # noqa: E402
from sportsplatform.governance.outcome import State                 # noqa: E402

PASSED = FAILED = 0
ART = pathlib.Path(_ROOT, 'nfl', 'research', 'live', FC.GAME,
                   'DAL_NYG_FORENSIC_CORRECTED_RESEARCH.json')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _art():
    if not ART.exists():
        return None
    return json.loads(ART.read_text())


def test_a_artifact_exists_and_is_not_empty():
    """An absent artifact is a failure, not a skip."""
    a = _art()
    check('the artifact exists', a is not None, str(ART))
    if a is None:
        return
    check('  it carries four verdicts, one per declared repair',
          len(a.get('verdicts') or []) == 4,
          str(len(a.get('verdicts') or [])))
    check('  and every section it claims is non-empty',
          all(a.get(k) for k in
              ('declared_treatment', 'team_budget_comparison',
               'qb_comparison', 'carry_budget_decomposition',
               'player_metric_comparison')))


def test_b_execution_identity_is_asserted_not_assumed():
    """Outside the declared treatment the two runs must be equal."""
    po, co = FC._load(FC.PRE_RUN), FC._load(FC.CORRECTED_RUN)
    if po.state is not State.PASS or co.state is not State.PASS:
        check('both sealed runs load', False,
              f'{po.code} / {co.code}')
        return
    o = FC.identity_check(po.value, co.value)
    check('execution identity matches outside the treatment',
          o.state is State.PASS, f'{o.code} {o.evidence.get("differing")}')
    check('  and the spec hash DIFFERS, which is what proves the treatment '
          'reached the engine',
          o.state is State.PASS
          and o.evidence['spec_hash']['pre']
          != o.evidence['spec_hash']['corrected'])
    check('  and the dirty-working-tree difference is NAMED, not dismissed',
          o.state is State.PASS
          and o.evidence['caveat_working_tree']['unresolved'] is True
          and o.evidence['caveat_working_tree']['committed_base_equal'] is True)


def test_c_the_treatment_is_actually_applied():
    """Zero after is only evidence if there was something there before."""
    po, co = FC._load(FC.PRE_RUN), FC._load(FC.CORRECTED_RUN)
    if po.state is not State.PASS or co.state is not State.PASS:
        check('both sealed runs load', False)
        return
    o = FC.treatment_applied(po.value, co.value)
    check('all six excluded identities carry zero after', o.state is State.PASS,
          o.detail)
    if o.state is not State.PASS:
        return
    check('  and every one of them carried opportunity BEFORE',
          all(v['pre_opportunity_mean'] > 0 for v in o.value.values()))
    check('  and the practice-squad quarterback is separated from the '
          'officially inactive players by BASIS, not pooled with them',
          o.value['00-0039398']['basis'] == 'NOT_ON_ACTIVE_53_PRACTICE_SQUAD'
          and sum(1 for v in o.value.values()
                  if v['basis'] == 'OFFICIAL_INACTIVE') == 5)


def test_d_the_carry_identity_closes_per_draw():
    """team_carries - scrambles == rb + non-RB, in every draw, or it is a leak.

    Closure ON AVERAGE would hide a per-draw crossing. The residual is checked
    at its worst absolute value, not its mean.
    """
    a = _art()
    if a is None:
        check('artifact present for the carry check', False)
        return
    for tm, d in a['carry_budget_decomposition'].items():
        check(f'{tm}: the carry identity closes in every draw',
              d['identity']['closes'],
              f"worst residual {d['identity']['worst_absolute_per_draw_residual']}")
        check(f'{tm}:   and the DELTA closes too, so nothing leaked',
              abs(d['delta_closes']['rush_play_budget_delta']
                  - d['delta_closes']['rb_plus_non_rb_delta']) < 1e-3,
              str(d['delta_closes']))


def test_e_nyg_conserves_because_its_qb_room_did_not_change():
    """The control arm. NYG lost three players and conserved its budgets.

    This is what says the redistribution came from the governed allocator and
    not from a hand transfer: a club whose quarterback room was untouched
    conserves its player-side sums to the last decimal.
    """
    a = _art()
    if a is None:
        check('artifact present for the conservation check', False)
        return
    s = a['player_metric_comparison']['per_team_sum']
    for metric in ('rushing/carries', 'receiving/targets'):
        d = s[f'{metric}|NYG']
        check(f'NYG conserves {metric} exactly', abs(d['delta']) < 0.01,
              f"delta {d['delta']:+.4f}")
    for metric in ('team_volume/team_carries', 'team_volume/team_targets',
                   'team_volume/team_dropbacks_part'):
        for tm in ('DAL', 'NYG'):
            d = a['team_budget_comparison'][f'{metric}|{tm}']
            check(f'{tm}: {metric} is upstream of eligibility and unmoved',
                  d['delta'] == 0.0, f"delta {d['delta']:+.4f}")


def test_f_the_qb_verdict_is_not_softer_than_its_evidence():
    """The mixing MOVED. A bare INPUT_DEFECT_FIXED would hide that."""
    a = _art()
    if a is None:
        check('artifact present for the verdict check', False)
        return
    v = {x['repair'][0]: x for x in a['verdicts']}
    check('B is not recorded as a clean fix',
          v['B']['verdict'] == 'INPUT_DEFECT_FIXED_BUT_'
                               'SPECIFICATION_DEFECT_REMAINS',
          v['B']['verdict'])
    dal = a['qb_comparison']['dropback_share']['DAL']
    howell, dak = dal['00-0037077'], dal['00-0033077']
    check('  and the evidence for it is the measurement, not an opinion: '
          'Howell rose while Prescott stayed short of a starter share',
          howell['delta'] > 0.3 and dak['corrected'] < 0.7,
          f"Howell {howell['pre']:.4f}->{howell['corrected']:.4f}, "
          f"Prescott {dak['corrected']:.4f}")
    check('  and DAL team dropbacks were CONSERVED, so the mass moved rather '
          'than disappearing',
          a['qb_comparison']['per_team_qb_sum']['qb/db|DAL']['delta'] == 0.0)
    check('C is UNRESOLVED rather than reported as run',
          v['C']['verdict'] == 'UNRESOLVED', v['C']['verdict'])
    check('D names the missing football assumption instead of inventing one',
          v['D']['verdict'] == 'SPECIFICATION_DEFECT_REMAINS'
          and any('REPORTED, not invented' in e for e in v['D']['evidence']))


def test_g_the_candidate_never_becomes_production():
    """Promotion, prospective evidence and market contamination, all refused."""
    a = _art()
    if a is None:
        check('artifact present for the governance check', False)
        return
    check('promoted is False', a['promoted'] is False)
    check('prospective_eligible is False', a['prospective_eligible'] is False)
    check('it creates no prospective evidence',
          a['creates_prospective_evidence'] is False)
    check('the sealed PRE artifact is recorded as unmodified',
          a['sealed_pre_artifact_preserved']['modified'] is False)
    blob = json.dumps(a).lower()
    for word in ('hardrock', 'hard rock', 'over_odds', 'under_odds',
                 'implied_prob', 'edge_pct', 'vig', 'closing_line'):
        check(f'  no market field or name reaches the artifact: {word!r}',
              word not in blob)
    src = pathlib.Path(_ROOT, 'nfl', 'research',
                       'forensic_corrected.py').read_text().lower()
    check('  and the builder itself opens no market source',
          'hardrock' not in src and 'oddsclient' not in src
          and 'market_comparison' not in src)


def test_h_what_it_does_not_establish_is_stated():
    """A comparison that does not say what it cannot show invites overreach."""
    a = _art()
    if a is None:
        check('artifact present for the limits check', False)
        return
    lim = ' '.join(a.get('what_this_does_not_establish') or []).lower()
    check('it disclaims accuracy from one game', 'one game' in lim)
    check('it says the season-boundary specification defect is not cleared',
          'qb3_week1_season_boundary' in lim)
    check('it says inactive ownership is still not enforced',
          'enforced=false' in lim)
    check('it says no quarterback market becomes admissible',
          'admissible' in lim)


def test_i_the_qb3_mechanism_is_attributed_not_asserted():
    """The split is reproduced from the allocator, or it is BLOCKED by name."""
    a = _art()
    if a is None:
        check('artifact present for the mechanism check', False)
        return
    m = a['qb3_mechanism']
    check('the mechanism section carries a five-state outcome',
          m['state'] in ('PASS', 'BLOCKED', 'FAIL', 'DEFERRED',
                         'NOT_APPLICABLE'), m['state'])
    if m['state'] == 'BLOCKED':
        check('  a blocked mechanism declares its cause',
              m.get('cause') in ('NETWORK', 'ENVIRONMENT', 'DEPENDENCY',
                                 'DATA', 'GOVERNANCE'), str(m.get('cause')))
        return
    if m['state'] != 'PASS':
        check('the mechanism section is PASS or BLOCKED', False, m['state'])
        return
    v = m['value']
    rep = v['reproduced_shares']['corrected_2qb']
    check('  the allocator reproduces the corrected board within 1 point',
          abs(rep['00-0037077']
              - a['qb_comparison']['dropback_share']['DAL']
              ['00-0037077']['corrected']) < 0.01,
          f"reproduced {rep['00-0037077']:.4f}")
    check('  shares close to 1 in every draw',
          rep['closure_max_abs_dev'] < 1e-9)
    check("  and Prescott's cell is the one the previous-primary signal put "
          'him in, not a rank-1 incumbent cell',
          v['prescott_cell'].startswith('(1, 0)'))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
