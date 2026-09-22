"""Materiality weighs a share by an explicit rule, not by Python truthiness.

The rule this replaces was `carry_share or target_share or 0.0`. It gave the
right answer on every row this repository holds, and it gave it for the wrong
reason: wherever the target share was larger, the carry share was EXACTLY
0.0, which is falsy, so the `or` fell through. Correctness that rests on a
zero being falsy is correctness nobody chose.

Two things are proved here. That the new rule is stated rather than implied,
on cases chosen so that truthiness cannot supply the answer. And that on the
312 saved review dossiers NOTHING MOVES -- not a value, not a materiality
decision, not a disposition, not a slate verdict.
"""
from __future__ import annotations

import ast
import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import audit as AUD                        # noqa: E402
from nfl.production.review import dossier as DOS                      # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.review import gate as GATE                        # noqa: E402

PASSED = FAILED = 0
REVIEW = _REPO / 'nfl/research/player_review'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def mk(carry, target):
    d = DOS.PlayerPregameDossier(
        gsis_id='X', display_name='X', team='T', opponent='O', game_id='G',
        season=2026, week=2, information_cut='C',
        support_state='MODEL_SUPPORTED')
    d.canonical = DOS.CanonicalFacts(carry_share=carry, target_share=target)
    return d


def old_rule(carry, target):
    """The exact expression this slice removes."""
    return float(carry or target or 0.0)


# -- 1. the rule, on cases truthiness cannot answer -------------------------
CASES = (
    # carry, target, expected value, expected metric, old value
    (0.04, 0.20, 0.20, GATE.TARGET_SHARE, 0.04),
    (0.20, 0.04, 0.20, GATE.CARRY_SHARE, 0.20),
    (0.0, 0.20, 0.20, GATE.TARGET_SHARE, 0.20),
    (None, 0.20, 0.20, GATE.TARGET_SHARE, 0.20),
    (0.20, None, 0.20, GATE.CARRY_SHARE, 0.20),
    (0.0, 0.0, 0.0, GATE.CARRY_SHARE, 0.0),
    (None, None, None, GATE.NO_SHARE, 0.0),
)


def test_the_rule_is_stated_not_implied():
    for carry, target, want, metric, _old in CASES:
        m = GATE.team_opportunity_materiality(mk(carry, target))
        ok(m.value == want and m.selected_metric == metric,
           f'carry={carry!r:>5} target={target!r:>5} -> value={m.value!r}, '
           f'selected {m.selected_metric}')
        ok(m.carry_share == carry and m.target_share == target,
           f'   and both inputs are carried, not just the winner')
    m = GATE.team_opportunity_materiality(mk(None, None))
    ok(m.value is None and not m.available,
       'neither share present is UNAVAILABLE, not zero -- a player nobody '
       'measured is not a player measured at nothing')
    ok(m.for_threshold == 0.0,
       'and 0.0 stands in only where a comparison needs a number, visibly')


def test_the_shares_are_never_summed():
    m = GATE.team_opportunity_materiality(mk(0.30, 0.30))
    ok(m.value == 0.30,
       f'two equal shares give 0.30, not 0.60: {m.value}. carry_share is a '
       f'share of team carries and target_share of team targets; their sum '
       f'is not a share of anything.')
    ok(m.selected_metric == GATE.CARRY_SHARE,
       'and a tie resolves deterministically rather than arbitrarily')


def test_the_old_expression_is_gone():
    src = (_REPO / 'nfl/production/review/gate.py').read_text()
    tree = ast.parse(src)
    chains = []
    for n in ast.walk(tree):
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or):
            names = [v.attr for v in n.values
                     if isinstance(v, ast.Attribute)]
            if 'carry_share' in names or 'target_share' in names:
                chains.append(names)
    ok(not chains,
       f'no `or` chain over the shares EXECUTES in the gate: {chains}')
    ok('team_opportunity_materiality' in src
       and 'TeamOpportunityMateriality' in src,
       'the rule is a named helper with a typed result')


# -- 2. the threshold behaviour that was wrong ------------------------------
def test_the_ordinary_football_case_crosses_the_threshold_correctly():
    """A pass-catching back: a couple of carries, a fifth of the targets."""
    carry, target = 0.04, 0.20
    th = GATE.MATERIALITY_RULE['tests']['team_opportunity_share']['threshold']
    ok(th == 0.05, f'the threshold is unchanged at {th}')
    ok(old_rule(carry, target) == 0.04,
       f'OLD: {old_rule(carry, target)} -- the 0.20 was never seen')
    m = GATE.team_opportunity_materiality(mk(carry, target))
    ok(m.value == 0.20, f'NEW: {m.value}')
    ok(old_rule(carry, target) < th <= m.value,
       f'and the threshold sits BETWEEN them: {old_rule(carry, target)} '
       f'< {th} <= {m.value}')

    d = mk(carry, target)
    d.projection['dk_points'] = EV.ProjectionComponent(
        'dk_points', 1.0, EV.MEASURED)
    conflict = {'code': AUD.C_COLD_START_MATERIAL, 'severity': 'REVIEW',
                'gsis_id': 'X', 'evidence': {}}
    res = GATE.materiality(d, conflict)
    ok(res['tests']['team_opportunity_share'] is True,
       'the share test FIRES on him under the corrected rule')
    ok(res['material'] is True and 'team_opportunity_share' in res['fired'],
       f'so the conflict is material: {res["fired"]}')
    ok(res['measured']['team_opportunity_share'] == 0.20,
       f'recorded at {res["measured"]["team_opportunity_share"]}')
    ok(res['team_opportunity_share_detail']['selected_metric']
       == GATE.TARGET_SHARE,
       'and the report says WHICH resource triggered it, rather than '
       'leaving a reader to infer it from two numbers')

    low = mk(0.04, 0.03)
    low.projection['dk_points'] = EV.ProjectionComponent(
        'dk_points', 1.0, EV.MEASURED)
    r2 = GATE.materiality(low, conflict)
    ok(r2['tests']['team_opportunity_share'] is False,
       'while a player who is small on BOTH resources still does not fire')


# -- 3. held data: nothing moves -------------------------------------------
def held_dossiers():
    """The saved review dossiers, with canonical facts RECONSTRUCTED.

    These artifacts predate `CanonicalFacts`, so the shares are read from the
    saved axes -- which is where the same numbers live. The reconstruction is
    stated rather than hidden: it is what makes a comparison possible at all,
    and it uses no value the artifact does not contain.
    """
    out = []
    if not REVIEW.exists():
        return out
    for slate in sorted(REVIEW.iterdir()):
        pdir = slate / 'player_dossiers'
        if not pdir.exists():
            continue
        for f in sorted(pdir.glob('*.json')):
            j = json.loads(f.read_text())
            ax = j.get('axes') or {}
            d = DOS.PlayerPregameDossier(
                gsis_id=j.get('gsis_id'), display_name=j.get('display_name'),
                team=j.get('team'), opponent=j.get('opponent'),
                game_id=j.get('game_id'), season=j.get('season'),
                week=j.get('week'),
                information_cut=j.get('information_cut'),
                support_state=j.get('support_state'),
                uncertainty_state=j.get('uncertainty_state',
                                        EV.EVIDENCE_SUFFICIENT))
            d.canonical = DOS.CanonicalFacts(
                carry_share=(ax.get('carry_share') or {}).get('value'),
                target_share=(ax.get('target_share') or {}).get('value'))
            for name, a in ax.items():
                d.axes[name] = EV.Axis(name=name, value=a.get('value'),
                                       grade=a.get('grade', EV.UNAVAILABLE))
            for comp, c in (j.get('projection') or {}).items():
                d.projection[comp] = EV.ProjectionComponent(
                    component=comp, value=c.get('value'),
                    grade=c.get('grade', EV.PRIOR))
            out.append((slate.name, d))
    return out


def test_held_data_values_are_unchanged():
    held = held_dossiers()
    ok(len(held) == 312, f'{len(held)} saved dossiers read')
    moved, both = [], 0
    for slate, d in held:
        cs, ts = d.canonical.carry_share, d.canonical.target_share
        if cs is not None and ts is not None:
            both += 1
        new = GATE.team_opportunity_materiality(d).for_threshold
        if abs(new - old_rule(cs, ts)) > 1e-12:
            moved.append((slate, d.gsis_id, cs, ts,
                          old_rule(cs, ts), new))
    ok(both == 60, f'{both} of them carry BOTH shares')
    ok(not moved, f'and NOT ONE share value changes: {moved[:5]}')


def test_held_data_materiality_and_dispositions_are_unchanged():
    held = held_dossiers()
    by_slate = collections.defaultdict(dict)
    for slate, d in held:
        by_slate[slate][d.gsis_id] = d
    flips = collections.Counter()
    verdicts = {}
    for slate, dby in sorted(by_slate.items()):
        rp = REVIEW / slate / 'slate_review_report.json'
        if not rp.exists():
            continue
        report = json.loads(rp.read_text())
        g = GATE.evaluate(report, dossiers=list(dby.values()))
        v = GATE.payload(g)
        verdicts[slate] = v['verdict']
        for row in v['conflicts']:
            d = dby.get(row.get('gsis_id'))
            if d is None:
                continue
            cs, ts = d.canonical.carry_share, d.canonical.target_share
            mat = row['materiality']
            if mat.get('exempt'):
                continue
            # `measured` is ROUNDED to 6dp by the gate, so the comparison
            # rounds too. Comparing a rounded number against an unrounded
            # one measures the rounding, not the rule -- this test asserted
            # 45 flips that way before the rounding was matched.
            old_share = round(old_rule(cs, ts), 6)
            new_share = mat['measured']['team_opportunity_share']
            if abs(old_share - new_share) > 1e-9:
                flips['share_value'] += 1
            th = (GATE.MATERIALITY_RULE['tests']['team_opportunity_share']
                  ['threshold']) * mat['evidence_grade_scale']
            if (old_share >= th) != (new_share >= th):
                flips['share_test'] += 1
                # would the row's overall materiality have changed?
                others = [k for k, x in mat['tests'].items()
                          if x and k != 'team_opportunity_share']
                if not others:
                    flips['materiality'] += 1
                    flips['disposition'] += 1
    ok(not flips,
       f'over every conflict on every saved slate: no share value, no '
       f'share test, no materiality and no disposition flip: '
       f'{dict(flips) or "none"}')
    ok(verdicts, f'slate verdicts re-derived: {verdicts}')
    ok(all(x in GATE.VERDICTS for x in verdicts.values()),
       'every one is a real verdict, so the comparison was on live output')


def test_the_research_artifact_agrees():
    p = _REPO / 'nfl/research/review/MATERIALITY_SHARE_PRECEDENCE.json'
    ok(p.exists(), 'the measurement artifact is present')
    doc = json.loads(p.read_text())
    ok(doc['corpus']['n_materiality_flips'] == 0,
       'it recorded zero flips on held data')
    ok(doc['constructed_reachable_case']['n_materiality_flips'] > 0,
       'and a non-zero count on the constructed case, which is why the '
       'correction was made at all')
    ok('max' in doc['recommendation'],
       f'and recommended the rule now implemented')


def main():
    for t in (test_the_rule_is_stated_not_implied,
              test_the_shares_are_never_summed,
              test_the_old_expression_is_gone,
              test_the_ordinary_football_case_crosses_the_threshold_correctly,
              test_held_data_values_are_unchanged,
              test_held_data_materiality_and_dispositions_are_unchanged,
              test_the_research_artifact_agrees):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
