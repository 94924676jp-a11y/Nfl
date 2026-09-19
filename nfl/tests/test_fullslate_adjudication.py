"""The external full-slate DFS packet: preserved, reproduced, adjudicated.

WHAT THESE CHECKS ARE FOR

Not "the external numbers are right" -- that is the thing under adjudication.
They pin the three properties that make the adjudication trustworthy:

1. **The packet is unchanged.** An external artifact edited to agree with us is
   not evidence any more. Its sha256 is pinned.
2. **The reproduction actually ran and disagrees where it says it disagrees.**
   A reproduction that quietly matched everything would mean the comparison was
   not being made.
3. **No constant from the report leaked into production.** The report contains
   a correlation table, exposure percentages and salary thresholds, and the
   standing directive forbids every one of them as a literal.

The numeric values below are NOT re-derived here. Re-running the panel costs
minutes and pinning its outputs in a test would be a second copy of
FULLSLATE_REPRODUCTION.json that goes stale. What is pinned is the artifact's
internal consistency and the governance properties.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

PASSED = FAILED = 0

PACKET = pathlib.Path(_ROOT) / (
    'external-research/nfl-fullslate-dfs-construction-2026-09-18/'
    'nfl-fullslate-dfs-lineup-construction.pplx.md')
PACKET_SHA = '897caf231b4a594c64155f790d505909aeda0e808dd848fb57c53d2d0d6ce20a'
PROV = pathlib.Path(_ROOT) / 'external-research/EXTERNAL_PACKET_PROVENANCE.json'
REPRO = pathlib.Path(_ROOT) / 'nfl/research/dfs/fullslate/FULLSLATE_REPRODUCTION.json'
COUP = pathlib.Path(_ROOT) / 'nfl/research/dfs/fullslate/FULLSLATE_COUPLING_RECONCILIATION.json'
HYP = pathlib.Path(_ROOT) / 'nfl/research/dfs/fullslate/DFS_HYPOTHESES.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# ===================================================== the packet itself

def test_the_external_packet_is_preserved_byte_for_byte():
    if not check('the packet is present', PACKET.exists(), str(PACKET)):
        return
    got = hashlib.sha256(PACKET.read_bytes()).hexdigest()
    check('its sha256 is unchanged since import', got == PACKET_SHA,
          f'{got} against {PACKET_SHA}')
    check('provenance is recorded', PROV.exists(), str(PROV))
    if PROV.exists():
        d = json.loads(PROV.read_text())
        check('provenance pins the same hash',
              d['files_present'][0]['sha256'] == PACKET_SHA)
        check('it records an import time', bool(d.get('imported_at_utc')))
        check('it says the packet is not to be edited',
              'PRESERVED UNCHANGED' in d['immutability'])
        check('it records the packet as evidence, not architecture',
              'EVIDENCE_UNDER_ADJUDICATION' in d['status'], d['status'])


def test_the_four_missing_companion_files_are_recorded_as_missing():
    """The report says they are included. They are not. Silence would be a lie."""
    d = json.loads(PROV.read_text())
    missing = d['files_named_by_the_report_but_ABSENT']
    for f in ('measure_dfs_correlations.py', 'measure_tails.py',
              'dfs_correlation_results.json', 'dfs_tail_results.json'):
        check(f'{f} is recorded as absent', f in missing, str(missing))
    for f in missing:
        check(f'{f} is genuinely not on disk',
              not (PACKET.parent / f).exists())
    check('and the consequence is stated, not just the fact',
          're-implementation' in d['absence_is_load_bearing'],
          d['absence_is_load_bearing'][:80])


# ================================================== the reproduction ran

def test_the_reproduction_artifact_exists_and_reports_disagreement():
    if not check('the reproduction artifact exists', REPRO.exists(),
                 str(REPRO)):
        return
    d = json.loads(REPRO.read_text())
    s = d['summary']
    check('comparisons were actually made', s['n_compared'] > 40,
          str(s['n_compared']))
    check('and some of them disagree -- a reproduction that matched '
          'everything would mean no comparison was made',
          s['n_outside_tolerance'] > 0, str(s['n_outside_tolerance']))
    check('the tolerance was declared, not chosen after',
          'before running' in d['tolerance_declared'])
    check('every comparison resolved to a number',
          s['n_not_measured'] == 0, str(s['n_not_measured']))


def test_the_panel_sizes_match_the_reports_stated_design():
    """512 ex-ante against 544 realized is the Week-1 exclusion, verified."""
    d = json.loads(REPRO.read_text())
    for site in ('DK', 'FD'):
        for season in ('2024', '2025'):
            n_ex = d['panels'][f'ex_ante_{site}']['counts'][season]['n_team_games']
            n_re = d['panels'][f'realized_{site}']['counts'][season]['n_team_games']
            check(f'ex_ante_{site} {season} is 512 team-games', n_ex == 512,
                  str(n_ex))
            check(f'realized_{site} {season} is 544 team-games', n_re == 544,
                  str(n_re))
            check(f'{site} {season}: the difference is exactly the 32 '
                  f'week-1 team-games', n_re - n_ex == 32, str(n_re - n_ex))
    weeks = d['panels']['ex_ante_DK']['counts']['2024']['weeks']
    check('and week 1 is absent from the ex-ante panel', 1 not in weeks,
          str(weeks[:4]))


def test_role_collisions_are_measured_and_the_primary_variant_has_none():
    """26% of team-games have the QB as his own team's second carrier."""
    d = json.loads(REPRO.read_text())
    sens = d['role_variant_sensitivity']
    ind = sens['independent']['2024']['role_collisions']
    check('the independent reading collides on QB and RUSH2',
          ind.get('QB+RUSH2', {}).get('n', 0) > 100, str(ind.get('QB+RUSH2')))
    check('and it is reported as a share, not just a count',
          ind['QB+RUSH2']['pct'] > 20, str(ind['QB+RUSH2']['pct']))
    seq = sens['sequential_removal']['2024']['role_collisions']
    check('sequential removal has no collisions at all', seq == {}, str(seq))
    check('all three readings are reported, none declared "the" method',
          set(sens) == {'independent', 'sequential_removal',
                        'qb_excluded_only'}, str(sorted(sens)))


def test_the_leakage_direction_reproduces_independently():
    """DFS-H2. Every pair inflates under realized labels, in our own pipeline."""
    d = json.loads(REPRO.read_text())
    ex = d['panels']['ex_ante_DK']['same_team']
    re_ = d['panels']['realized_DK']['same_team']
    pairs = ['QB|PC1', 'QB|PC2', 'PC1|PC2', 'RUSH1|RUSH2']
    for p in pairs:
        for s in ('2024', '2025'):
            a, b = ex[s][p]['r'], re_[s][p]['r']
            check(f'{p} {s}: realized exceeds ex-ante', b > a,
                  f'ex_ante {a:+.3f} realized {b:+.3f}')


def test_dk_and_fd_dependence_are_close():
    """DFS-H5, the claim with the largest architectural consequence."""
    d = json.loads(REPRO.read_text())
    worst, where = 0.0, None
    for s in ('2024', '2025'):
        for pair, v in d['panels']['ex_ante_DK']['same_team'][s].items():
            a = v['r']
            b = d['panels']['ex_ante_FD']['same_team'][s][pair]['r']
            if a is None or b is None:
                continue
            if abs(a - b) > worst:
                worst, where = abs(a - b), f'{pair} {s}'
    check('max |DK - FD| across every same-team pair is under 0.02',
          worst < 0.02, f'{worst:.4f} at {where}')


def test_no_dst_claim_is_reported_as_reproduced():
    """An inability, recorded as one. There is no DST adapter to reproduce with."""
    d = json.loads(REPRO.read_text())
    check('the artifact names DST as not reproduced',
          any('DST' in k for k in d['not_reproduced']),
          str(list(d['not_reproduced'])))
    why = ' '.join(d['not_reproduced'].values())
    check('and gives the reason rather than leaving it blank',
          'no DST scoring adapter' in why, why[:100])
    check('naming the forbidden shortcut explicitly',
          'unverified site constants' in why.lower(), why[:160])


def test_the_adapter_schema_divergence_is_recorded():
    d = json.loads(REPRO.read_text())
    a = d['adapter_schema_divergence']
    check('the divergence is recorded as a finding',
          a['draftkings']['two_point_keys'] != a['fanduel']['two_point_keys'],
          str(a))
    check('with its consequence stated', 'KeyError' in a['consequence'])
    check('and it was handled in research code, not by editing an adapter',
          'leaving both certified adapters untouched' in a['handled_here_by'])


# ===================================================== the reconciliation

def test_the_coupling_reconciliation_separates_the_estimands():
    if not check('the coupling artifact exists', COUP.exists(), str(COUP)):
        return
    d = json.loads(COUP.read_text())
    for season in ('2024', '2025'):
        v = d['variants'][season]
        yards = next(x for k, x in v.items() if k.startswith('offense_yards_all'))
        fp = next(x for k, x in v.items()
                  if k.startswith('club_fantasy_points_all_players_all'))
        check(f'{season}: the yards estimand reproduces P5 (near zero or '
              f'negative)', yards['r'] < 0.05, f"{yards['r']:+.4f}")
        check(f'{season}: the fantasy-points estimand is positive',
              fp['r'] > 0.05, f"{fp['r']:+.4f}")
        check(f'{season}: the two differ in sign or materially in level',
              fp['r'] - yards['r'] > 0.1, f"{fp['r'] - yards['r']:+.4f}")
        check(f'{season}: both carry a game-clustered interval',
              yards['ci95_game_bootstrap'] and fp['ci95_game_bootstrap'])
    check('and the artifact refuses to authorize a simulator change',
          'says nothing about the world generator'
          in d['authorizes_no_simulator_change'])


# ========================================================= the governance

def test_the_hypotheses_are_registered_without_being_declared_true():
    d = json.loads(HYP.read_text())
    ids = {h['id'] for h in d['hypotheses']}
    for want in ('DFS-H1', 'DFS-H2', 'DFS-H3', 'DFS-H4', 'DFS-H5', 'DFS-H6'):
        check(f'{want} is registered', want in ids, str(sorted(ids)))
    for h in d['hypotheses']:
        check(f'{h["id"]} is REGISTERED, not SUPPORTED',
              h['status'] == 'REGISTERED', h['status'])
        check(f'{h["id"]} carries a falsifier',
              len(h.get('falsifier', '')) > 30, h.get('falsifier', '')[:40])
    check('none is policy until prospectively validated',
          'production policy until prospectively validated'
          in d['none_is_policy'], d['none_is_policy'][:90])
    check('and registration is explicitly not endorsement',
          'not endorsement' in d['none_is_policy'])
    check('they are kept OUT of the production assumption registry',
        'deliberately NOT' in d['register_scope'], d['register_scope'][:60])


def test_h3_carries_the_descriptive_versus_predictive_guard():
    """The tercile result conditions on a realized outcome. It may not ship."""
    d = json.loads(HYP.read_text())
    h3 = next(h for h in d['hypotheses'] if h['id'] == 'DFS-H3')
    check('H3 records that the tercile analysis is descriptive',
          'DESCRIPTIVE' in h3['evidence_now'], h3['evidence_now'][:80])
    check('H3 forbids it becoming a pre-lock feature',
          'cannot become a pre-lock feature' in h3['descriptive_not_predictive'])
    check('H3 requires a prediction-time experiment instead',
          'PREDICTION-TIME' in h3['prospective_experiment_required'])
    check('and forbids sportsbook totals as the conditioning variable',
          'FORBIDDEN predictive input'
          in h3['prospective_experiment_required'],
          h3['prospective_experiment_required'][:120])


#: Correlation coefficients from the report's table. A production module that
#: hardcoded one would be importing two seasons of sampling error and a
#: labelling choice our own reproduction disagrees with.
BANNED_COEFFICIENTS = (0.368, 0.274, 0.296, 0.318, 0.208, 0.259,
                       -0.375, -0.371, 0.1201, 0.2034)


def test_no_report_constant_is_hardcoded_in_production():
    """The report's correlation table is the strongest temptation in the packet.

    THIS CHECK WAS WRONG ONCE AND THE FIX IS THE POINT. A first version
    searched the raw text for "0.368" and flagged two files. Both hits were
    PROSE -- `run_forecast.py` describing a passer appearing in "59 of 160
    week-1 rooms (0.3688)" and `appearance_panel_2026.py` describing an
    appearance share -- and both were committed on 2026-09-14 and 2026-09-16,
    days before this packet arrived. 0.368 is also 1/e.

    A text search cannot tell a hardcoded coefficient from a sentence that
    happens to contain a number, and a guard that cries wolf on documentation
    gets switched off. So the literal is read from the AST, where a float in
    code is distinguishable from a float inside a string.
    """
    roots = ('nfl/production', 'nfl/product', 'nfl/dfs')
    offenders = []
    for root in roots:
        for path in (pathlib.Path(_ROOT) / root).glob('**/*.py'):
            try:
                tree = ast.parse(path.read_text(errors='replace'))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and \
                        isinstance(node.value, float):
                    if node.value in BANNED_COEFFICIENTS:
                        offenders.append(
                            f'{path.relative_to(_ROOT)}:{node.lineno}'
                            f'={node.value}')
                elif isinstance(node, ast.UnaryOp) and \
                        isinstance(node.op, ast.USub) and \
                        isinstance(node.operand, ast.Constant) and \
                        isinstance(node.operand.value, float):
                    if -node.operand.value in BANNED_COEFFICIENTS:
                        offenders.append(
                            f'{path.relative_to(_ROOT)}:{node.lineno}'
                            f'=-{node.operand.value}')
    check('no correlation coefficient from the report appears as a CODE '
          'literal in production, product or dfs', not offenders,
          str(offenders[:6]))
    check('  the detector fires on a real one',
          any(v in BANNED_COEFFICIENTS
              for v in [ast.literal_eval('0.368')]))


def test_the_reproduction_module_restates_no_scoring_coefficient():
    """It must read constants from the certified adapters, never retype them."""
    p = (pathlib.Path(_ROOT)
         / 'nfl/research/dfs/fullslate/reproduce_external_panel.py')
    tree = ast.parse(p.read_text())
    # The published-value tables are the thing under test and are exempt by
    # name; any OTHER float literal that looks like a scoring coefficient is
    # the defect this checks for.
    exempt = {'PUBLISHED_DK_EX_ANTE', 'PUBLISHED_DK_CROSS',
              'PUBLISHED_REALIZED_DK', 'PUBLISHED_FD_EX_ANTE',
              'PUBLISHED_REALIZED_CROSS', 'TOLERANCE'}
    bad = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & exempt:
                continue
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and \
                        isinstance(sub.value, float) and \
                        sub.value in (0.04, 0.1, 4.0, 6.0, 1.0, 0.5, -2.0):
                    bad.append(f'{names}={sub.value}')
    check('no scoring coefficient is restated at module level', not bad,
          str(bad))
    src = p.read_text()
    check('coefficients are resolved from the adapters',
          'resolve_coefficients' in src and 'RULES' in src)
    check('and a missing coefficient is refused rather than defaulted',
          'silent zero' in src)
