"""Q6: the pregame firewall, the two layers kept apart, and the decision rule.

WHAT THESE TESTS PROTECT.

  * NO POST-KICKOFF OR POST-HOC ROSTER STATUS. `weekly_rosters.status` is
    refused by name, and so is any 2026 row. The check is on the feature list
    this code builds and on the artifacts it emits, never on what some
    upstream file happens to contain.

  * THIS GAME'S SNAP SHARE IS NOT A FEATURE. A player has a snap share if and
    only if he appeared, so the column and its own missingness flag both carry
    the label. R8 records scoring an in-sample Brier of 0.04101 the one time
    it was featurised; the test here is that perturbing it changes no feature.

  * THE TWO LAYERS STAY APART. P(appears) and role-given-appears are scored
    separately and the composition is a Bernoulli draw times a renormalised
    share, not one unconditional number.

  * THE COMPOSITION PRESERVES THE TEAM TOTAL EXACTLY. A multinomial over the
    simplex reconciles on every draw; the reported maximum error must be 0.

  * THE DECISION RULE IS THE ONE THAT WAS WRITTEN DOWN, and both candidate
    arms are scored against it so that adopting whichever did better
    afterwards is visibly not what happened.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production.nonqb import appearance_r7 as R7              # noqa: E402
from nfl.research.q6 import analyse as AN                         # noqa: E402
from nfl.research.q6 import forward_chain as FC                   # noqa: E402
from nfl.research.q6 import frame as FR                           # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _results():
    return json.loads(AN.RESULTS.read_text()) if AN.RESULTS.exists() else None


def _rows(path):
    if not path.exists():
        return None
    with gzip.open(path, 'rt', newline='') as fh:
        return list(csv.DictReader(fh))


# ==================================================== the pregame firewall
def test_a_roster_status_and_postgame_inputs_are_refused_by_name():
    check('the declared Q6 additions pass the pregame check',
          FR.assert_pregame_only(FR.FEATURE_NAMES_Q6_ADDED) is True)
    for bad in ('weekly_rosters.status', 'roster_status', 'inactive_list',
                'realized_targets', 'postgame_snaps', 'vegas_wp'):
        try:
            FR.assert_pregame_only(list(FR.FEATURE_NAMES_Q6_ADDED) + [bad])
            check(f'{bad} is refused', False)
        except ValueError as e:
            check(f'{bad} is refused by name', bad in str(e))
    check('game-day roster status heads the refused list',
          'weekly_rosters.status' in FR.FORBIDDEN_INPUTS)


def test_b_the_artifacts_say_what_they_did_not_use():
    r = _results()
    if r is None:
        check('the forward-chain results artifact exists', False)
        return
    check('no market input is recorded as used',
          r['market_inputs_used'] == [], str(r['market_inputs_used']))
    check('no roster-status input is recorded as used',
          r['roster_status_inputs_used'] == [])
    check('no 2026 row was used', r['live_2026_rows_used'] == 0)
    check('nothing is promoted', r['promoted'] is False)
    check('it is labelled research only', r['is_research_only'] is True)
    check('the evaluation seasons are all historical',
          max(r['eval_seasons']) <= 2025, str(r['eval_seasons']))
    rows = _rows(AN.APPEARANCE_ROWS)
    if rows:
        check('the emitted appearance rows carry no 2026 season',
              max(int(x['season']) for x in rows) <= 2025)
        check('  and no column whose name is a refused input',
              not FR.market_columns(list(rows[0]))
              if hasattr(FR, 'market_columns') else
              not [c for c in rows[0]
                   if any(s in c.lower() for s in FR.FORBIDDEN_INPUTS)])


# ================================================= no label in the features
def test_c_this_games_snap_share_is_not_a_feature():
    r = {'w': 3, 'pos': 'WR', 'rank': 2, 'n_cur': 4, 'snap': 0.8,
         'inj_status': 'Questionable', 'inj_practice': None,
         'inj_available': 1}
    a = FR.featurise_q6(dict(r), 1.2)
    b = dict(r)
    b['snap'] = 0.0
    c = FR.featurise_q6(b, 1.2)
    check('perturbing this game\'s snap share changes no feature',
          a == c, f'{sum(1 for x, y in zip(a, c) if x != y)} differ')
    d = dict(r)
    d['snap'] = None
    check('  and removing it entirely changes no feature',
          FR.featurise_q6(d, 1.2) == a)


def test_d_the_q6_additions_are_exactly_what_was_declared():
    r = {'w': 3, 'pos': 'WR', 'rank': 1, 'n_cur': 4,
         'inj_status': 'Out', 'inj_practice': None, 'inj_available': 1}
    base = FR.featurise_r8(dict(r), 1.2)
    got = FR.featurise_q6(dict(r), 1.2)
    check('Q6 adds exactly the declared number of columns',
          len(got) - len(base) == len(FR.FEATURE_NAMES_Q6_ADDED),
          f'{len(got) - len(base)} vs {len(FR.FEATURE_NAMES_Q6_ADDED)}')
    check('  and leaves R8\'s own columns untouched',
          got[:len(base)] == base)
    added = got[len(base):]
    names = list(FR.FEATURE_NAMES_Q6_ADDED)
    i = names.index('inj_Out_x_rank_r1')
    check('an Out starter fires the Out-by-rank-1 interaction',
          added[i] == 1.0, str(added[i]))
    check('  and fires no other interaction',
          sum(added[:len(R7.STATUS) * len(FR.RANK_GROUPS)]) == 1.0)
    q = dict(r)
    q['rank'] = 5
    a2 = FR.featurise_q6(q, 1.2)[len(base):]
    check('the same designation at rank 5 fires a DIFFERENT cell',
          a2[i] == 0.0 and a2[names.index('inj_Out_x_rank_r4plus_or_unlisted')] == 1.0)
    check('that distinction is the whole hypothesis, and R8 cannot make it',
          len(base) < len(got))


def test_e_the_practice_ladder_is_an_ordinal_with_a_missing_flag():
    check('full participation is the bottom of the ladder',
          FR.practice_ordinal('Full Participation in Practice') == 0.0)
    check('limited is in the middle',
          FR.practice_ordinal('Limited Participation in Practice') == 0.5)
    check('did-not-participate is the top',
          FR.practice_ordinal('Did Not Participate In Practice') == 1.0)
    check('an unrecognised value is missing, not zero',
          FR.practice_ordinal('') is None
          and FR.practice_ordinal(None) is None
          and FR.practice_ordinal('\n    ') is None)
    r = {'w': 3, 'pos': 'TE', 'rank': 2, 'n_cur': 2, 'inj_practice': None}
    names = list(FR.FEATURE_NAMES_Q6_ADDED)
    base = len(FR.featurise_r8(dict(r), 1.2))
    got = FR.featurise_q6(dict(r), 1.2)[base:]
    check('a missing practice status sets the flag, and the value stays 0',
          got[names.index('practice_ordinal')] == 0.0
          and got[names.index('practice_ordinal_missing')] == 1.0)


def test_f_blanking_the_injury_block_removes_exactly_the_injury_block():
    r = {'w': 5, 'pos': 'RB', 'rank': 1, 'n_cur': 3, 'appeared': 1,
         'inj_status': 'Questionable',
         'inj_practice': 'Limited Participation in Practice',
         'inj_available': 1,
         'v1': {'f_rate3': 0.5, 'f_practice_improving': 1.0,
                'f_practice_worsening': 0.0, 'f_practice_seq': 'a>b'}}
    q = FR.blank_injury_block(r)
    check('the designation is gone', q['inj_status'] is None)
    check('the practice status is gone', q['inj_practice'] is None)
    check('availability reads as unfiled', q['inj_available'] == 0)
    check('the practice-derived features are gone too',
          q['v1']['f_practice_improving'] is None
          and q['v1']['f_practice_worsening'] is None)
    check('nothing else moves',
          q['v1']['f_rate3'] == 0.5 and q['appeared'] == 1
          and q['rank'] == 1)
    check('the original row is not mutated',
          r['inj_status'] == 'Questionable' and r['inj_available'] == 1)


# ============================================ the two layers, kept apart
def test_g_appearance_and_role_are_reported_separately():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    check('the appearance arms are reported on their own',
          set(r['appearance_arms']) == set(FC.APPEARANCE_ARMS))
    check('the role arms are reported on their own',
          set(r['role_arms']) == set(FC.ROLE_ARMS))
    check('the composition is reported as its own layer',
          bool(r['composition']) and bool(r['role']) and bool(r['appearance']))
    check('the role layer is scored against the realised appearance set, '
          'and says so',
          any('realised appearance set' in h for h in r['held_fixed']))
    check('the team total is declared held fixed across arms',
          any('team total' in h for h in r['held_fixed']))


def test_h_the_composition_preserves_the_team_total_exactly():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    for metric, ent in r['composition'].items():
        check(f'{metric}: reconciliation error is exactly zero on every draw',
              ent['team_reconciliation_error_max'] == 0.0,
              str(ent['team_reconciliation_error_max']))
        z = ent['by_arm']['BASELINE']['zero_inflation']
        check(f'{metric}: the zero rate is measured against the realisation',
              z['predicted_zero_rate'] is not None
              and z['observed_zero_rate'] is not None,
              f"{z['predicted_zero_rate']} vs {z['observed_zero_rate']}")
        check(f'{metric}: an appearing player CAN still be given zero',
              z['predicted_zero_rate'] > 0.1,
              str(z['predicted_zero_rate']))


def test_i_starter_dilution_and_replacement_are_reported_per_class():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    for metric, ent in r['composition'].items():
        d = ent['by_arm']['BASELINE']['starter_dilution']
        for rc in FR.ROLE_CLASSES:
            check(f'{metric}: {rc} dilution is reported', rc in d, str(list(d)))
        check(f'{metric}: the ratio says which way is dilution',
              'dilution' in d['reads'])
        rp = ent['by_arm']['BASELINE']['replacement_misallocation']
        check(f'{metric}: replacement is measured only where a starter was out',
              'starter was absent' in rp['reads'])


# ================================================ the missing-data policy
def test_j_every_fallback_declares_reduced_confidence():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    pol = r['missing_data_policy']['policies']
    for name in ('HARD_DEFER', 'HISTORICAL_ROLE_FALLBACK',
                 'PROBABILISTIC_FALLBACK', 'INFORMED'):
        check(f'{name} is compared', name in pol, str(sorted(pol)))
    check('the role-class fallback declares LOW confidence',
          pol['HISTORICAL_ROLE_FALLBACK']['declares_confidence']
          == 'LOW_CONFIDENCE_ROLE_CLASS_ONLY')
    check('the probabilistic fallback declares REDUCED confidence',
          pol['PROBABILISTIC_FALLBACK']['declares_confidence']
          == 'REDUCED_CONFIDENCE_NO_INJURY_REPORT')
    check('neither fallback masquerades as fully informed',
          pol['HISTORICAL_ROLE_FALLBACK']['declares_confidence']
          != pol['INFORMED']['declares_confidence']
          and pol['PROBABILISTIC_FALLBACK']['declares_confidence']
          != pol['INFORMED']['declares_confidence'])
    hd = pol['HARD_DEFER']
    check('hard defer forecasts nobody, and the cost is counted',
          hd['coverage'] == 0.0 and hd['n_players_forecast'] == 0
          and hd['n_players_refused'] > 0, str(hd['n_players_refused']))
    check('  including how many team-weeks it removes',
          hd['n_team_weeks_refused'] > 0, str(hd['n_team_weeks_refused']))
    check('the two answering policies are scored against the informed one',
          'brier_cost_vs_informed' in pol['PROBABILISTIC_FALLBACK'])


# ======================================================= the decision rule
def test_k_the_decision_rule_is_the_one_written_down():
    def mk(brier_ok, ll_ok, cells, sig_better=(), sig_worse=(),
           comp_worse=False):
        cd = {}
        for i, imp in enumerate(cells):
            g = f'POS{i}|class'
            cd[g] = {'improves': imp, 'delta': -1.0 if imp else 1.0,
                     'block_bootstrap_by_team_game': {
                         'excludes_zero': g in sig_better or g in sig_worse}}
        return {
            'appearance': {'overall': {
                'R8': {'brier': 1.0, 'log_loss': 1.0},
                'Q6_CALIBRATED': {'brier': 0.9 if brier_ok else 1.1,
                                  'log_loss': 0.9 if ll_ok else 1.1}}},
            'appearance_cells': {'Q6_CALIBRATED': cd},
            'composition': {'targets': {'by_arm': {'Q6_BOTH': {
                'delta_pct_vs_baseline': 1.0 if comp_worse else -1.0,
                'block_bootstrap_by_team_game': {
                    'excludes_zero': comp_worse}}}}},
        }
    s = mk(True, True, [True] * 3, sig_better=('POS0|class',))
    check('both metrics improve, majority of cells, one significant -> SUPPORT',
          AN.decide(s)['decision'] == 'SUPPORT', AN.decide(s)['decision'])
    s = mk(True, False, [True] * 3, sig_better=('POS0|class',))
    check('log loss failing drops it to WEAK_SUPPORT',
          AN.decide(s)['decision'] == 'WEAK_SUPPORT', AN.decide(s)['decision'])
    s = mk(True, True, [True, False, False], sig_worse=('POS1|class',))
    check('a significantly worse cell -> REJECT',
          AN.decide(s)['decision'] == 'REJECT', AN.decide(s)['decision'])
    s = mk(False, False, [False] * 3)
    check('nothing improves -> REJECT', AN.decide(s)['decision'] == 'REJECT')
    s = mk(True, True, [True] * 3, sig_better=('POS0|class',),
           comp_worse=True)
    check('a significantly worse composition metric -> REJECT',
          AN.decide(s)['decision'] == 'REJECT', AN.decide(s)['decision'])
    check('the rule travels in the artifact, not only in code',
          'SUPPORT' in AN.decide(s)['rule']
          and 'REJECT' in AN.decide(s)['rule'])


def test_l_both_candidate_arms_are_scored_against_the_rule():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    d = r.get('decision_by_arm') or {}
    check('both candidate arms carry a verdict',
          set(d) == {'Q6_FEATURES', 'Q6_CALIBRATED'}, str(sorted(d)))
    check('the headline arm was fixed in code, not chosen after the fact',
          AN.HEADLINE_ARM == 'Q6_CALIBRATED')
    check('  and the headline verdict is that arm\'s verdict',
          r['decision']['decision'] == d[AN.HEADLINE_ARM]['decision'])
    check('  and says so', 'selection on the' in
          r['decision'].get('headline_arm_note', ''))
    check('every verdict is one of the three states',
          all(v['decision'] in ('SUPPORT', 'WEAK_SUPPORT', 'REJECT')
              for v in d.values()))
    check('a degraded conditional-role metric is reported either way',
          'conditional_role_metrics_significantly_worse' in r['decision'])


def test_m_intervals_are_clustered_on_team_games():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    check('the clustering is declared', 'team-game' in r['clustering'])
    b = r['appearance']['paired_vs_R8']['Q6_FEATURES'][
        'block_bootstrap_by_team_game']
    check('there are fewer clusters than rows',
          b['n_clusters'] < b['n_rows'], f"{b['n_clusters']}/{b['n_rows']}")
    check('  by a large factor, so the clustering is doing work',
          b['n_rows'] / b['n_clusters'] > 5,
          f"{b['n_rows'] / b['n_clusters']:.1f} rows per team-game")
    d = np.array([1.0, -1.0, 1.0, -1.0])
    same = AN.boot_paired(d, ['g1', 'g1', 'g1', 'g1'], n=50)
    check('a single cluster cannot be resampled into significance',
          same['ci_lo'] == same['ci_hi'] == 0.0, str(same))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
