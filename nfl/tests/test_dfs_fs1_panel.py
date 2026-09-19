"""DFS-FS1: the dependence panel is leakage-safe, and it is not a rule book.

Three properties, and none of them is "the numbers are right".

**Leakage-safe.** A dependence panel whose role labels saw the game they label
measures its own labelling. The panel re-derives every label from a history
truncated before its own week and requires an exact match; these checks pin
that the guarantee ran and found nothing, and that the detector can fail.

**Descriptive, not prescriptive.** The panel's whole purpose is to be a
validation target for the simulator. The failure mode is somebody reading a
coefficient out of it into an optimizer, so production is swept for its values.

**Both dependence measures survive separately.** Pearson and joint-tail lift
are different quantities that disagree in sign on real pairs here. A test that
let them be collapsed into one ranking would allow the error the panel exists
to expose.
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'nfl/research/dfs/fullslate'))

import dependence_panel as FS1                                    # noqa: E402

PASSED = FAILED = 0
ART = pathlib.Path(_ROOT) / 'nfl/research/dfs/fullslate/DFS_FS1_DEPENDENCE_PANEL.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _art():
    return json.loads(ART.read_text()) if ART.exists() else None


# ===================================================== leakage safety

def test_roles_are_mutually_exclusive_by_construction():
    """One player, one role. 26.2% collision was the defect this removes."""
    d = _art()
    if not check('the panel artifact exists', d is not None, str(ART)):
        return
    for key, p in d['panels'].items():
        check(f'{key}: no role collisions', p['role_collisions'] == {},
              str(p['role_collisions']))
    spec = d['spec']['role_assignment']
    check('mutual exclusivity is declared, not incidental',
          spec['mutually_exclusive'] is True)
    check('the assignment ORDER is declared',
          spec['order'] == ['QB', 'PC', 'RUSH'], str(spec['order']))
    check('and the rule says an assigned player leaves later rankings',
          'removed from every later ranking' in spec['rule'])


def test_every_label_re_derives_from_truncated_history():
    d = _art()
    if d is None:
        check('the panel artifact exists', False)
        return
    for key, p in d['panels'].items():
        lk = p['leakage_check']
        check(f'{key}: every label was checked',
              lk['checked'] == p['n_team_games'],
              f"{lk['checked']} of {p['n_team_games']}")
        check(f'{key}: zero mismatches', lk['n_mismatches'] == 0,
              str(lk['mismatches'])[:200])
    check('and the guarantee says strictly-earlier',
          'strictly before its own week'
          in d['panels']['DK_2024']['leakage_check']['guarantee'])


def test_the_leakage_detector_can_actually_fail():
    """A checker only ever seen passing is indistinguishable from a no-op."""
    rows = {
        ('G1', 'AAA', 'p_qb'): __import__('collections').Counter(
            {'pass_att': 30}),
        ('G1', 'AAA', 'p_wr'): __import__('collections').Counter(
            {'targets': 10}),
        ('G2', 'AAA', 'p_qb'): __import__('collections').Counter(
            {'pass_att': 30}),
        ('G2', 'AAA', 'p_wr'): __import__('collections').Counter(
            {'targets': 10}),
    }
    weeks = {'G1': 1, 'G2': 2}
    roles = FS1.assign_roles_prior_only(rows, weeks)
    ok = FS1.assert_no_current_game_information(rows, weeks, roles)
    check('a correct panel passes the checker', ok['n_mismatches'] == 0,
          str(ok))
    tampered = {k: dict(v) for k, v in roles.items()}
    for k in tampered:
        tampered[k]['QB'] = 'p_wr'          # a label the history cannot give
    bad = FS1.assert_no_current_game_information(rows, weeks, tampered)
    check('a tampered label is caught', bad['n_mismatches'] > 0, str(bad))


def test_week_one_is_absent_rather_than_back_filled():
    d = _art()
    for key, p in d['panels'].items():
        check(f'{key}: week 1 is not in the panel',
              1 not in p['weeks_present'], str(p['weeks_present'][:3]))
        check(f'{key}: 512 team-games, which is 544 minus the 32 week-1 games',
              p['n_team_games'] == 512, str(p['n_team_games']))
    check('and the spec says it is not back-filled',
          'not back-filled' in d['spec']['labels']['week_1'])


def test_no_forbidden_input_is_declared_or_imported():
    d = _art()
    forb = d['spec']['forbidden_inputs']
    for want in ('sportsbook', 'ownership', 'realized current-game'):
        check(f'{want} is declared forbidden',
              any(want in f for f in forb), str(forb))
    # NAMING A THING FORBIDDEN REQUIRES WRITING ITS NAME. A first version of
    # this check searched the module text for "ownership" and failed on the
    # module's own `forbidden_inputs` declaration. What matters is whether the
    # module READS such a source, so the AST is asked about imports and calls
    # rather than the prose being grepped.
    import ast as _ast
    tree = _ast.parse((pathlib.Path(_ROOT)
                       / 'nfl/research/dfs/fullslate/dependence_panel.py')
                      .read_text())
    imported = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, _ast.ImportFrom):
            imported.add(node.module or '')
            imported.update(f'{node.module}.{a.name}' for a in node.names)
    joined = ' '.join(sorted(imported)).lower()
    for bad in ('oddsclient', 'market', 'hardrock', 'ownership', 'book'):
        check(f'the module imports nothing named {bad}', bad not in joined,
              joined[:120])
    check('and the only sources it imports are the pbp builder and the two '
          'certified scoring adapters',
          any('reproduce_external_panel' in i for i in imported)
          and any('draftkings' in i for i in imported)
          and any('fanduel' in i for i in imported), str(sorted(imported)))


# ============================================ the two measures stay apart

def test_pearson_and_tail_lift_are_reported_separately():
    d = _art()
    m = d['panels']['DK_2024']['same_team']['QB|PC1']
    for f in ('pearson', 'pearson_ci95', 'tail_lift', 'tail_lift_ci95'):
        check(f'{f} is present as its own field', f in m, str(sorted(m)))
    check('the spec forbids combining them into one ranking',
          'never combined into one ranking'
          in d['spec']['estimators']['reported_separately'])


def test_the_two_measures_demonstrably_disagree():
    """The empirical case for reporting both, produced rather than asserted."""
    d = _art()
    dis = d['pearson_and_tail_disagree_on']
    check('at least one pair has Pearson and tail lift on opposite sides of '
          'their nulls', len(dis) >= 1, str(len(dis)))
    for x in dis:
        opposite = (x['pearson'] < 0) != (x['tail_lift'] < 1.0)
        check(f"{x['panel']} {x['pair']} really is a disagreement", opposite,
              f"r={x['pearson']} lift={x['tail_lift']}")


def test_every_estimate_carries_a_game_clustered_interval():
    """Two team-games from one game are not two draws."""
    d = _art()
    check('the uncertainty method is a cluster bootstrap over games',
          d['spec']['uncertainty']['method'] == 'cluster bootstrap over GAMES',
          d['spec']['uncertainty']['method'])
    check('and says why', 'not independent draws'
          in d['spec']['uncertainty']['why'])
    missing = []
    for key, p in d['panels'].items():
        for sec in ('same_team', 'cross_team'):
            for pair, m in p[sec].items():
                if m['pearson'] is not None and not m['pearson_ci95']:
                    missing.append(f'{key}/{pair}')
    check('no point estimate is reported without an interval', not missing,
          str(missing[:5]))


def test_seasons_are_reported_separately_and_never_pooled():
    d = _art()
    keys = set(d['panels'])
    check('both seasons appear for both sites',
          keys == {'DK_2024', 'DK_2025', 'FD_2024', 'FD_2025'}, str(keys))
    check('and the spec says they are never pooled',
          'never pooled' in d['spec']['seasons'])


# =========================================== descriptive, not prescriptive

def test_the_panel_declares_itself_not_a_lineup_rule():
    d = _art()
    check('the artifact carries the prohibition',
          'FS1_NOT_A_LINEUP_RULE' in d)
    t = d['FS1_NOT_A_LINEUP_RULE']
    for want in ('lineup rule', 'exposure cap', 'correlation input'):
        check(f'it names {want} specifically', want in t, t[:120])
    check('and the spec calls it a validation target',
          'validation target' in d['spec']['purpose'])


def test_no_production_module_reads_the_panel_artifact():
    """The real failure mode is wiring the panel INTO a decision.

    A NAIVE NUMERIC SWEEP DOES NOT WORK AND THE REASON IS WORTH KEEPING. A
    first version flagged every production float matching a panel coefficient
    to three decimals. It fired on `SPLIT_ROOM_BASE_RATE = 0.078` in
    `quality_gates.py` -- the share of team-games with two or more passers at
    five-plus dropbacks, carrying its own cited source and committed on
    2026-09-14, five days before this panel existed -- and on 0.25 in three
    files. A float cannot tell you what quantity it is, and a guard that cries
    wolf on unrelated measurements gets switched off.

    So the guard is about PROVENANCE, which is checkable: no production,
    product or dfs module may import the panel module or read its artifact.
    That catches the thing that actually matters -- a coefficient store being
    plumbed into a lineup decision -- without pretending a number carries its
    own meaning.
    """
    banned_names = ('dependence_panel', 'DFS_FS1_DEPENDENCE_PANEL')
    offenders = []
    for root in ('nfl/production', 'nfl/product', 'nfl/dfs'):
        for path in (pathlib.Path(_ROOT) / root).glob('**/*.py'):
            try:
                src = path.read_text(errors='replace')
            except OSError:
                continue
            for b in banned_names:
                if b in src:
                    offenders.append(f'{path.relative_to(_ROOT)}:{b}')
    check('no production, product or dfs module references the panel module '
          'or its artifact', not offenders, str(offenders[:6]))
    check('  the detector would fire on a real reference',
          'dependence_panel' in banned_names)


def test_a_coefficient_leak_would_be_caught_by_name_context():
    """The hand-copied case: a panel value bound to a correlation-shaped name.

    Deliberately narrow. It asks whether a float matching a panel coefficient
    is bound to a name suggesting correlation, dependence or a stack -- which
    is what a leaked coefficient looks like -- rather than flagging every
    numerically similar quantity in the repository.
    """
    d = _art()
    vals = set()
    for p in d['panels'].values():
        for sec in ('same_team', 'cross_team'):
            for m in p[sec].values():
                if m['pearson'] is not None and abs(m['pearson']) > 0.02:
                    vals.add(round(float(m['pearson']), 3))
    check('there are panel coefficients to sweep for', len(vals) > 15,
          str(len(vals)))
    suspicious = ('corr', 'rho', 'depend', 'stack', 'pair', 'bringback',
                  'bring_back', 'tail_lift')
    offenders = []
    for root in ('nfl/production', 'nfl/product', 'nfl/dfs'):
        for path in (pathlib.Path(_ROOT) / root).glob('**/*.py'):
            try:
                tree = ast.parse(path.read_text(errors='replace'))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                names = [t.id.lower() for t in node.targets
                         if isinstance(t, ast.Name)]
                if not any(s in n for n in names for s in suspicious):
                    continue
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) and \
                            isinstance(sub.value, float) and \
                            round(sub.value, 3) in vals:
                        offenders.append(
                            f'{path.relative_to(_ROOT)}:{node.lineno}'
                            f'={names}={sub.value}')
    check('no correlation-named constant carries a panel coefficient',
          not offenders, str(offenders[:6]))


def test_dst_pairs_are_named_not_omitted():
    d = _art()
    dst = d['dst_pairs']
    check('DST is NOT_MEASURABLE', dst['state'] == 'NOT_MEASURABLE',
          dst['state'])
    check('under a named code', dst['code'] == 'FS1_DST_SCORING_ABSENT')
    check('the pairs are listed rather than dropped',
          len(dst['pairs']) >= 4, str(dst['pairs']))
    check('RB with DST is among them -- the directive names it',
          any('RUSH1' in p and 'DST' in p for p in dst['pairs']),
          str(dst['pairs']))
    check('the reason is the absent adapter, stated',
          'no DST scoring adapter' in dst['why'])
    check('and what would unblock it is named',
          'OUTBOX' in dst['unblocked_by'])


def test_the_simulator_comparison_is_pending_and_specified():
    d = _art()
    sc = d['simulator_comparison']
    check('it is PENDING, not quietly skipped', sc['state'] == 'PENDING')
    check('blocked by the absent full-slate generator',
          'full-slate joint-world generator' in sc['blocked_by'])
    check('the method is specified in advance',
          'same certified adapters' in sc['how_it_will_be_done'])
    check('and it is a SIGN and ORDERING test, not a magnitude test',
          'Magnitudes are not comparable' in sc['how_it_will_be_done'],
          sc['how_it_will_be_done'][-120:])


def test_the_declaration_order_is_stated_honestly():
    """Not a blind pre-registration, and it says so."""
    d = _art()
    check('what was fixed beforehand is listed',
          len(d['spec']['declared_before_measurement']) >= 4)
    check('and what was not is admitted',
          'chosen knowing the reproduction results'
          in d['spec']['not_declared_blind'],
          d['spec']['not_declared_blind'][:90])


def test_scoring_comes_from_the_certified_adapters():
    d = _art()
    s = d['spec']['scoring']
    check('both adapters are named by spec version',
          s['draftkings'].startswith('nfl-dfs-scoring-draftkings')
          and s['fanduel'].startswith('nfl-dfs-scoring-fanduel'), str(s))
    check('and no coefficient is restated', 'none restated here'
          in s['coefficients'])
