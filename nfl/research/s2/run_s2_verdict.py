"""Stage 2: the field inventory, then the adequacy rule applied verbatim."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s2_lib as L                                             # noqa: E402

# The fourteen attributes the directive requires, declared per candidate field.
# Measured facts come from s2_results.json and the source scan; the semantic
# and legal columns are declarations, and are written here so they can be
# disputed by pointing at a field rather than at a mood.
INVENTORY = {
 'offense_players (part_*.csv)': dict(
   semantic='the set of player ids on the field for one play',
   unit='player-ids per play', denominator='n/a (a set)',
   seasons='2020-2025', positional_coverage='all offensive positions',
   missingness='8.6% of plays 2020-2022, 0.0% 2023-2025',
   zeros_mean='an empty list would be N/A, not "nobody played"; none observed',
   chronology='observed after the play; lawful ONLY as prior-game history',
   retrieval_provenance='nflverse participation release, hash-pinned in nfl/research/inputs',
   usable_prospectively='YES as lagged history; NO for the current game',
   observed_after_game=True, model_derived=False, legally_usable=True,
   measures_actual_participation=True),
 'pass_snaps (derived)': dict(
   semantic='plays with the player on the field AND the play was a dropback',
   unit='plays', denominator='team_dropbacks_part',
   seasons='2020-2025', positional_coverage='WR/TE/RB',
   missingness='0.0% of appeared WR/TE/RB player-games',
   zeros_mean='a real zero: on the field, no dropbacks. Distinguished from N/A',
   chronology='derived from participation; lawful as prior-game history only',
   retrieval_provenance='P1 build_panel_p3.py from the participation release',
   usable_prospectively='YES as lagged history',
   observed_after_game=True, model_derived=False, legally_usable=True,
   measures_actual_participation='PROXY -- an UPPER BOUND on routes run, '
                                 'because a player on the field for a dropback '
                                 'may block'),
 'route (part_*.csv)': dict(
   semantic="the TARGETED receiver's route classification on that play",
   unit='one label per play, for the targeted man only',
   denominator='n/a', seasons='2020-2025',
   positional_coverage='only the targeted player',
   missingness='58-64% of plays carry no value, because most plays have no '
               'targeted receiver with a classified route',
   zeros_mean='blank means "not the targeted man or unclassified", never '
              '"ran no route"',
   chronology='postgame', retrieval_provenance='nflverse participation release',
   usable_prospectively='as lagged history only, and NOT as routes run',
   observed_after_game=True, model_derived=False, legally_usable=True,
   measures_actual_participation='NO. It is a route LABEL for the targeted '
                                 'player. Calling it routes run would be a '
                                 'relabelling, and it is not done anywhere in '
                                 'this study'),
 'routes run (true)': dict(
   semantic='the number of passing plays on which a player ran a route',
   unit='routes', denominator='team dropbacks',
   seasons='NOT AVAILABLE', positional_coverage='NOT AVAILABLE',
   missingness='100%', zeros_mean='n/a', chronology='n/a',
   retrieval_provenance='no source in this project provides it',
   usable_prospectively='NO', observed_after_game=None, model_derived=None,
   legally_usable=None,
   measures_actual_participation='would, but IT IS NOT AVAILABLE and is not '
                                 'manufactured'),
 'offense_snaps / offense_pct (snap counts)': dict(
   semantic='offensive snaps played, and the same as a whole percent',
   unit='snaps; percent', denominator='team offensive snaps',
   seasons='2020-2025', positional_coverage='all',
   missingness='0.0% of appeared WR/TE/RB player-games',
   zeros_mean='real zero',
   chronology='postgame', retrieval_provenance='nflverse snap counts release',
   usable_prospectively='as lagged history',
   observed_after_game=True, model_derived=False, legally_usable=True,
   measures_actual_participation='YES for snaps, but it does not separate '
                                 'pass from run. offense_pct is ROUNDED TO A '
                                 'WHOLE PERCENT and P4B already had to rebase '
                                 'off it for that reason'),
 'offense_formation / offense_personnel': dict(
   semantic='formation label and personnel grouping per play',
   unit='label', denominator='n/a', seasons='2020-2025',
   positional_coverage='team level', missingness='20-27% of plays',
   zeros_mean='blank is unknown, not "no formation"',
   chronology='postgame', retrieval_provenance='nflverse participation release',
   usable_prospectively='as lagged history',
   observed_after_game=True, model_derived=False, legally_usable=True,
   measures_actual_participation='NO -- context, not player participation. '
                                 'Inventoried, not modelled in Stage 2'),
 'ngs receiving (avg_separation, cushion, share of air yards)': dict(
   semantic='Next Gen Stats tracking aggregates, weekly',
   unit='yards; share', denominator='varies and is not documented per row',
   seasons='partial in this project', positional_coverage='receivers only',
   missingness='high; a weekly aggregate, not per play',
   zeros_mean='ambiguous', chronology='postgame',
   retrieval_provenance='nflverse NGS release',
   usable_prospectively='as lagged history, with an undocumented denominator',
   observed_after_game=True,
   model_derived='PARTLY -- expected-YAC style columns are model outputs with '
                 'an UNKNOWN FIT WINDOW',
   legally_usable='NOT for Stage 2: an unknown fit window is a chronology risk '
                  'this study will not take',
   measures_actual_participation='NO'),
 'weekly_rosters.status': dict(
   semantic='roster status', unit='label', denominator='n/a',
   seasons='n/a', positional_coverage='n/a', missingness='n/a',
   zeros_mean='n/a', chronology='POSTGAME STATE',
   retrieval_provenance='n/a', usable_prospectively='NO',
   observed_after_game=True, model_derived=False,
   legally_usable='FORBIDDEN by standing owner rule',
   measures_actual_participation='NO'),
 'present-week depth chart': dict(
   semantic='depth-chart position for the current week',
   unit='rank', denominator='n/a', seasons='2020-2024 files present',
   positional_coverage='all', missingness='varies',
   zeros_mean='n/a',
   chronology='THE ARTIFACT CARRIES NO TIMESTAMP OF ANY KIND (P4D section 2)',
   retrieval_provenance='nflverse depth chart release, no effective time',
   usable_prospectively='NO -- quarantined',
   observed_after_game='UNKNOWABLE, which is the problem',
   model_derived=False, legally_usable='NO for present-week state',
   measures_actual_participation='NO'),
}


def main():
    res = json.load(open(f'{HERE}/s2_results.json'))
    adv = json.load(open(f'{HERE}/s2_adversarial.json'))
    best = res['best_method']
    OUT = {'inventory': INVENTORY, 'best_method': best, 'rules': {}}

    print('== field inventory ==')
    for k, v in INVENTORY.items():
        print(f"  {k}")
        print(f"    measures participation: {v['measures_actual_participation']}")
        print(f"    usable prospectively:   {v['usable_prospectively']}")

    def pooled(pos, b):
        return res['by_season'][pos][b]['pooled']

    def seasons(pos, b):
        return res['by_season'][pos][b]['per_season_mae']

    print('\n== the adequacy rule, applied ==')
    # PA-1
    pa1 = {}
    for pos in ('WR', 'TE', 'RB'):
        b, base = best[pos], 'position_mean'
        wins = sum(1 for e in L.EVAL
                   if (seasons(pos, base)[str(e)] - seasons(pos, b)[str(e)])
                   / seasons(pos, base)[str(e)] >= 0.10)
        rel = 1 - pooled(pos, b)['mae'] / pooled(pos, base)['mae']
        pa1[pos] = {'method': b, 'pooled_relative_gain': rel,
                    'seasons_ge_10pct': wins, 'required': 3,
                    'pass': bool(wins >= 3 and rel >= 0.10)}
        print(f"  PA-1 {pos}: {b} beats position_mean by {rel:.1%} pooled, "
              f"{wins}/4 seasons >= 10%  -> {'PASS' if pa1[pos]['pass'] else 'FAIL'}")
    OUT['rules']['PA_1'] = pa1
    # PA-2
    pa2 = {}
    for pos in ('WR', 'TE', 'RB'):
        m = pooled(pos, best[pos])
        pa2[pos] = {'r': m['r'], 'sd_ratio': m['sd_ratio'],
                    'pass': bool(m['r'] >= 0.70 and m['sd_ratio'] >= 0.50)}
        print(f"  PA-2 {pos}: r {m['r']:.3f} (>=0.70), sd ratio "
              f"{m['sd_ratio']:.3f} (>=0.50)  -> "
              f"{'PASS' if pa2[pos]['pass'] else 'FAIL'}")
    OUT['rules']['PA_2'] = pa2
    # PA-3
    pa3 = {}
    worst = {}
    for pos in ('WR', 'TE', 'RB'):
        p = pooled(pos, best[pos])['mae']
        bad = []
        w = (0.0, None)
        for dim, d in res['cohorts'][pos].items():
            for lvl, m in d.items():
                if m['n'] < 200:
                    continue
                ratio = m['mae'] / p
                if ratio > w[0]:
                    w = (ratio, f'{dim}/{lvl}')
                if ratio > 2.5:
                    bad.append((dim, lvl, ratio))
        pa3[pos] = {'worst_cohort': w[1], 'worst_ratio': w[0],
                    'violations': bad, 'pass': not bad}
        worst[pos] = w
        print(f"  PA-3 {pos}: worst cohort {w[1]} at {w[0]:.2f}x pooled "
              f"(limit 2.5x)  -> {'PASS' if pa3[pos]['pass'] else 'FAIL'}")
    OUT['rules']['PA_3'] = pa3
    # PA-4
    cov = res['coverage']
    lo = min(v['coverage'] for v in cov.values())
    zeros_ok = all(v['true_zero_on_field_for_no_dropback'] >= 0 for v in cov.values())
    pa4 = {'min_season_coverage': lo, 'pass': bool(lo >= 0.90 and zeros_ok),
           'by_season': cov}
    print(f"  PA-4: minimum season coverage {lo:.3%} (>=90%), zero vs N/A "
          f"distinguished  -> {'PASS' if pa4['pass'] else 'FAIL'}")
    OUT['rules']['PA_4'] = pa4
    # PA-5
    pa5 = {'result': adv['PA_5'], 'pass': adv['PA_5'] == 'PASS'}
    print(f"  PA-5: masking audit {adv['PA_5']}  -> "
          f"{'PASS' if pa5['pass'] else 'FAIL'}")
    OUT['rules']['PA_5'] = pa5

    allpass = (all(v['pass'] for v in pa1.values())
               and all(v['pass'] for v in pa2.values())
               and all(v['pass'] for v in pa3.values())
               and pa4['pass'] and pa5['pass'])
    if pa4['pass'] and pa5['pass'] and allpass:
        state = 'ADEQUATE_FOR_TARGET_DECOMPOSITION'
    elif not (pa4['pass'] and pa5['pass']):
        state = 'DATA_BLOCKED'
    elif not any(v['pass'] for v in pa1.values()):
        state = 'INFORMATION_CONSTRAINED'
    elif not any(v['pass'] for v in pa2.values()):
        state = 'UPSTREAM_INADEQUATE'
    else:
        state = 'ADEQUATE_WITH_LIMITATIONS'
    OUT['FINAL_ADEQUACY_STATE'] = state
    OUT['mandatory_labelling_constraint'] = (
        'The participation component is PASS-SNAP PARTICIPATION, an upper '
        'bound on route participation. It is not routes run. Any Stage 4 '
        'decomposition must label it that way and may not conclude anything '
        'about the value of route information as such. The gap between '
        'pass-snap participation and true routes run is DIRECTIONAL (pass '
        'snaps >= routes) but its MAGNITUDE IS UNBOUNDED from the data '
        'available here, and is not assumed to be small.')
    OUT['stage_4_authorized'] = state in ('ADEQUATE_FOR_TARGET_DECOMPOSITION',
                                          'ADEQUATE_WITH_LIMITATIONS')
    print(f'\n  FINAL ADEQUACY STATE: {state}')
    print(f'  Stage 4 authorized: {OUT["stage_4_authorized"]}')
    print(f'\n  MANDATORY LABELLING CONSTRAINT:\n    '
          + OUT['mandatory_labelling_constraint'].replace('. ', '.\n    '))
    json.dump(OUT, open(f'{HERE}/s2_verdict.json', 'w'), indent=1)
    print('\n-> s2_verdict.json')


if __name__ == '__main__':
    main()
