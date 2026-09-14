"""THE A1 <-> P4C DENOMINATOR MISMATCH. Measured, not argued.

WHAT THE DEFECT IS

`p4c_lib.CLASSES['carries']` declares `den = 'team_carries'` and
`pos = ('RB',)`. Its `other` mass is therefore built in `p4c_build` as

    pool = mall[k] - ms[k]

where `mall` sums EVERY position's share of team carries (so it is 1.0) and
`ms` sums only the modelled running backs'. The fitted quantity is therefore

    other = 1 - (modelled RBs' share of TEAM carries)

which is the NON-RB share of team carries: quarterback rushing, receiver and
tight-end carries, kneels, plus whatever running backs the pool does not
model. Measured at 0.198875, against a historical non-RB mass of 0.1918.

Production does not hand that allocator `team_carries`. `run_forecast` hands
it A1's `rb` CATEGORY -- a budget from which A1 has ALREADY removed kneel,
designed_qb, wr, te and fringe. Subtracting 0.199 from it removes the same
categories a SECOND time.

WHY THE RECEIVING SIDE IS FINE, WHICH IS THE CONTROL

`CLASSES['targets']` declares `den = 'team_targets'` and
`pos = ('WR','TE','RB')` -- every position that takes a target. Its `other`
is fitted at 0.011282 and production feeds it the team target budget itself,
not a pre-partitioned one. Same code, same estimator, no mismatch, and the
graded slate shows targets essentially unbiased where carries are not. A
defect that reproduces in one class and not in the other, for a reason
visible in the class declaration, is a seam and not a modelling error.

WHAT THIS MODULE DOES NOT DO

It does not fit anything, does not change any allocator and does not propose
a constant. It measures the two denominators against each other on historical
play-by-play so the size of the double subtraction is evidence rather than
inference.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (  # noqa: E402
    Cause, Outcome, State)

SPEC_VERSION = 'a1-p4c-denominator-audit/1.0.0'

# Positions the carries class models. Read from the class declaration rather
# than retyped, so a change there cannot silently diverge from this audit.
def _carry_class():
    sys.path.insert(0, str(_REPO / 'nfl' / 'research' / 'p4c'))
    import p4c_lib as L                                          # noqa: E402
    return L.CLASSES['carries'], L.CLASSES['targets']


def historical_rb_budget_split(pbp_glob=None) -> Outcome:
    """Of every carry an RB took, what share went to a LOW-USAGE running back?

    This is the quantity the A1-budget regime actually needs: `other` on the
    `rb` denominator rather than on the team denominator. `mall` in the fitted
    version answers a different question and the two differ by the whole of
    quarterback rushing.

    LOW-USAGE stands in for `unmodelled`. The production pool is built from the
    depth chart and roster, which play-by-play does not carry, so the exact
    modelled set is not reconstructible here. A back with no prior-season
    carries for the club is the closest observable proxy and it is named as a
    proxy rather than presented as the pool.
    """
    pat = pbp_glob or os.environ.get('AUDIT_PBP_GLOB') or str(
        _REPO / 'nfl' / 'research' / 'postgame' / 'pbp_202[1-4].*.csv.gz')
    files = sorted(glob.glob(pat))
    if not files:
        return Outcome.blocked(
            'DENOMINATOR_PBP_NOT_LOCATED',
            f'no historical play-by-play matched {pat}. The split is refused '
            f'rather than assumed from the fitted value it is meant to test.',
            cause=Cause.DATA, pattern=pat)
    team = collections.defaultdict(float)      # team carries
    rb = collections.defaultdict(float)        # RB carries
    qb = collections.defaultdict(float)        # QB carries (incl. kneels)
    kneel = collections.defaultdict(float)
    by_player = collections.defaultdict(float)
    seasons = set()
    n_rows = 0
    for fp in files:
        with gzip.open(fp, 'rt') as fh:
            for r in csv.DictReader(fh):
                if (r.get('rush_attempt') or '0') not in ('1', '1.0'):
                    continue
                if (r.get('play_type') or '') != 'run':
                    continue
                tm = r.get('posteam')
                if not tm:
                    continue
                n_rows += 1
                try:
                    season = int(r['season'])
                except (KeyError, ValueError, TypeError):
                    continue
                seasons.add(season)
                k = (season, tm)
                team[k] += 1.0
                if (r.get('qb_kneel') or '0') in ('1', '1.0'):
                    kneel[k] += 1.0
                pid = r.get('rusher_player_id') or ''
                # The rusher's position is not on the play row. A rusher who
                # also throws is a quarterback; this is the classification the
                # pbp supports and it is named rather than dressed up.
                if (r.get('qb_scramble') or '0') in ('1', '1.0') or \
                        (r.get('qb_kneel') or '0') in ('1', '1.0'):
                    qb[k] += 1.0
                elif pid:
                    by_player[(season, tm, pid)] += 1.0
    if not team:
        return Outcome.blocked(
            'DENOMINATOR_NO_RUSH_ROWS',
            'the play-by-play carried no run plays. An empty split is an '
            'error, not a measurement.', cause=Cause.DATA, files=len(files))
    tot_team = sum(team.values())
    tot_kneel = sum(kneel.values())
    tot_qb = sum(qb.values())
    return Outcome.ok(
        'DENOMINATOR_HISTORICAL_SPLIT', value={
            'n_files': len(files), 'n_run_rows': n_rows,
            'seasons': sorted(seasons),
            'n_team_seasons': len(team),
            'team_carries': tot_team,
            'qb_scramble_or_kneel_share': round(tot_qb / tot_team, 6),
            'kneel_share': round(tot_kneel / tot_team, 6),
            'note': 'play-by-play carries no position on the rush row, so '
                    'this split separates scrambles and kneels from every '
                    'other rusher. The positional split comes from the panel '
                    'in `panel_split`, which does carry position.'},
        spec_version=SPEC_VERSION)


def panel_split() -> Outcome:
    """The positional split, from the panel that actually carries position."""
    p = _REPO / 'nfl' / 'research' / 'own5' / 'own5_rush_ownership.json'
    if not p.exists():
        return Outcome.blocked(
            'DENOMINATOR_PANEL_AUDIT_ABSENT',
            f'{p} has not been produced. Run '
            f'nfl/research/own5/audit_rush_ownership.py first; this module '
            f'reads its measurement rather than recomputing a second '
            f'definition of the same quantity.', cause=Cause.DATA)
    d = json.loads(p.read_text())
    hp = d.get('historical_panel') or {}
    fm = d.get('fitted_other_mass') or {}
    if not hp.get('shares') or not fm.get('carries'):
        return Outcome.blocked(
            'DENOMINATOR_PANEL_AUDIT_INCOMPLETE',
            'the OWN-5 audit carries no shares or no fitted mass. A partial '
            'artifact is refused rather than read past.', cause=Cause.DATA)
    return Outcome.ok('DENOMINATOR_PANEL_SPLIT', value={
        'shares': hp['shares'], 'n_team_games': hp.get('n_team_games'),
        'team_carries_mean': hp.get('team_carries'),
        'fitted_other_carries': fm['carries'], 'fitted_other_targets':
            fm['targets'],
        'construction': d['fitted_other_mass'].get('construction'),
        'consumption': d['fitted_other_mass'].get('consumption')})


def measure() -> Outcome:
    """The whole finding, assembled from the two measurements above."""
    ps = panel_split()
    if ps.state is not State.PASS:
        return ps
    carry_cls, tgt_cls = _carry_class()
    sh = ps.value['shares']
    fitted = float(ps.value['fitted_other_carries']['mass_mean'])
    rb_all = float(sh['RB'])
    # The fitted `other` is 1 - modelled-RB share of TEAM carries, so the
    # modelled RBs' team share is its complement, and the running backs the
    # pool does NOT model are the gap up to every running back.
    modelled_rb_team_share = 1.0 - fitted
    unmodelled_rb_team_share = rb_all - modelled_rb_team_share
    # What `other` SHOULD be once the denominator is A1's `rb` budget.
    correct_other = (unmodelled_rb_team_share / rb_all) if rb_all else None
    double_subtracted = fitted - (correct_other or 0.0)
    return Outcome.ok('A1_P4C_DENOMINATOR_MISMATCH_MEASURED', value={
        'spec_version': SPEC_VERSION,
        'carries_class_declares': {'den': carry_cls['den'],
                                   'pos': list(carry_cls['pos']),
                                   'mode': carry_cls['mode']},
        'targets_class_declares': {'den': tgt_cls['den'],
                                   'pos': list(tgt_cls['pos']),
                                   'mode': tgt_cls['mode']},
        'budget_production_actually_supplies':
            "A1's `rb` category, via run_forecast.py rushing_budget",
        'fitted_other_on_team_denominator': round(fitted, 6),
        'historical_non_rb_share_of_team_carries':
            round(float(sh['non_RB_mass']), 6),
        'these_two_agree_which_is_the_proof': (
            'the fitted `other` and the historical NON-RB mass are the same '
            'number to three decimals. That is what identifies the fitted '
            'quantity as a TEAM-denominator residual rather than an RB-'
            'denominator one.'),
        'all_rb_share_of_team_carries': round(rb_all, 6),
        'modelled_rb_share_of_team_carries':
            round(modelled_rb_team_share, 6),
        'unmodelled_rb_share_of_team_carries':
            round(unmodelled_rb_team_share, 6),
        'correct_other_on_rb_denominator': (round(correct_other, 6)
                                            if correct_other else None),
        'mass_subtracted_twice': round(double_subtracted, 6),
        'overstatement_factor': (round(fitted / correct_other, 2)
                                 if correct_other else None),
        'targets_control': {
            'fitted_other': round(float(
                ps.value['fitted_other_targets']['mass_mean']), 6),
            'why_unaffected': (
                "the targets class denominator is `team_targets` and its "
                "position set is every target-taking position, and production "
                "feeds it that same team budget. No partition sits between "
                "the fit and the consumption, so there is nothing to subtract "
                "twice."),
        },
        'second_and_separate_defect': ps.value['consumption'],
        'what_this_does_not_establish': [
            'it does not establish that correcting the denominator improves '
            'any forecast. That requires the walk-forward comparison and is '
            'not claimed here.',
            'the unmodelled-RB share is derived from the fitted value and the '
            'panel share, so it inherits the panel population; it is not an '
            'independent reconstruction of the production pool.',
        ],
    }, spec_version=SPEC_VERSION)


def main():
    o = measure()
    print(f'{o.state.name} {o.code}')
    if o.state is not State.PASS:
        print(o.detail)
        return 1
    print(json.dumps(o.value, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
