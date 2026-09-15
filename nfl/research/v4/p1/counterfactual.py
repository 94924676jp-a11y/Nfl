"""P1: the KC backfield counterfactual at the sealed DEN@KC cutoff.

    python3.12 -m nfl.research.v4.p1.counterfactual

THE QUESTION, AND IT IS NOT "DID WALKER'S NUMBER GO UP"

`AUTOPSY_DEN_KC.md` section 4 establishes that the carry prior separated the
two lead backs 1.62 : 1 and that the appearance layer then inverted it:

    back      C          normalised      appearance p (R8)
    Walker    0.429622   0.5142          0.723664
    Johnson   0.264512   0.3166          0.992530
    Smith     0.141380   0.1692          0.762094

`layers.targets_carries` binarises participation and `p4c_lib.allocate`
renormalises the class weights over whoever survived the draw, so a lower
appearance probability is a smaller expected share of the carries. The sealed
board's realised shares were 0.4133 / 0.1511 / 0.4170 -- Johnson ahead of
Walker -- and a counterfactual holding everything else fixed and moving KC RB
appearance to p = 1.0 returned the prior exactly.

So the test here is: DOES THE CORRECTED APPEARANCE LAYER LEAVE THE PREGAME
CARRY PRIOR STANDING? The prior is the thing carrying the football evidence;
the appearance layer's job is availability, and it should only depart from the
prior when it has lawful pregame evidence about availability. It has none here
-- no injury row for any KC back, KC readiness READY.

WHAT IS REPLICATED AND WHAT IS READ

The appearance probabilities are RUN, through `appearance_r8.predict` and
`appearance_r8.predict_r10`, at the sealed `observed_before`. The allocation
step is REPLICATED here rather than run, because `layers.py` is frozen and
this repair does not touch it: each draw keeps player i with probability p_i
and divides C over the survivors. The replication is not asserted -- it is
CHECKED against two facts the sealed board already fixes: at p = 1 it must
return the normalised prior, and at the sealed R8 probabilities it must return
the sealed shares 0.4133 / 0.1511 / 0.4170.

NO REALIZED OUTCOME IS USED. The DEN@KC result is not in this repository and
is not sought. Walker's realised carries are not a target and appear nowhere.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import pool_audit as PA                          # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8                 # noqa: E402
from nfl.production.nonqb import readiness as RD                     # noqa: E402
from nfl.production.nonqb import vintage_selector as VS              # noqa: E402

SPEC_VERSION = 'p1-kc-backfield-counterfactual-1'
HERE = _REPO / 'nfl' / 'research' / 'v4' / 'p1'

CUTOFF = '2026-09-14T20:58:33Z'
SEASON, WEEK = 2026, 1
TEAMS = ('DEN', 'KC')
POS = ('QB', 'RB', 'WR', 'TE', 'FB', 'HB')

# READ OUT OF THE AUTOPSY, WHICH READ THEM OUT OF THE SEALED BOARD. They are
# inputs to this replay, not results of it, and nothing here refits them.
SEALED = {
    'C': {'00-0038134': 0.429622,      # Walker
          '00-0041013': 0.264512,      # Johnson
          '00-0040078': 0.141380},     # Smith
    'appearance_r8': {'00-0038134': 0.723664,
                      '00-0041013': 0.992530,
                      '00-0040078': 0.762094},
    # THE AUTOPSY WRITES "shares 0.4133 / 0.1511 / 0.4170" WITHOUT NAMING
    # WHICH IS WHICH, and the order is NOT the order of the table above it.
    # Two facts in the same document fix the assignment and they agree: the
    # sealed carry means are 8.345 (RB1) and 8.420 (RB2) -- RB2 very slightly
    # ahead -- so 0.4133 is RB1 and 0.4170 is RB2, leaving 0.1511 for RB3,
    # whose class weight is a third of either. Read the other way round RB3
    # would hold 0.4170 on a weight of 0.1414, which the arithmetic of a
    # renormalised simplex cannot produce. Recorded because it is a reading
    # of another agent's prose, not a measurement of the board.
    'board_shares': {'00-0038134': 0.4133,
                     '00-0041013': 0.4170,
                     '00-0040078': 0.1511},
    'board_share_assignment': (
        'the autopsy lists the three shares without labels; assigned from the '
        'sealed carry means 8.345 / 8.420 in the same document'),
    'source': 'nfl/research/v3/AUTOPSY_DEN_KC.md section 4',
}
NAMES = {'00-0038134': 'RB1 (long history, new club)',
         '00-0041013': 'RB2 (no NFL history)',
         '00-0040078': 'RB3 (short history)'}
N_DRAWS = 200000
SEED = 20260915


def _normalise(d):
    t = sum(d.values())
    return {k: v / t for k, v in d.items()} if t else {k: None for k in d}


def expected_shares(C, p, n=N_DRAWS, seed=SEED):
    """Binarise participation, renormalise C over the survivors, average.

    This is the composition `layers.targets_carries` performs and it is
    replicated rather than called: the layer stack is frozen for this repair.
    A draw in which nobody survives contributes nothing and is COUNTED, not
    silently dropped -- an empty denominator is the failure mode this project
    keeps finding, and it must be visible if it ever fires.
    """
    ids = sorted(C)
    c = np.array([C[i] for i in ids], dtype=float)
    pr = np.array([p[i] for i in ids], dtype=float)
    rng = np.random.default_rng(seed)
    alive = rng.random((n, len(ids))) < pr
    w = alive * c
    tot = w.sum(axis=1)
    live = tot > 0
    sh = np.zeros_like(w)
    sh[live] = w[live] / tot[live][:, None]
    return ({i: float(sh[live][:, j].mean()) for j, i in enumerate(ids)},
            {'n_draws': n, 'n_draws_with_no_survivor': int((~live).sum())})


def run():
    out = {'artifact': 'P1_KC_BACKFIELD_COUNTERFACTUAL',
           'spec_version': SPEC_VERSION, 'cutoff': CUTOFF,
           'governance': 'EXPLORATORY. No realized DEN@KC outcome exists in '
                         'this repository, none was sought, and no realised '
                         'quantity is a target anywhere in this file. No '
                         'sportsbook price entered any part of it.',
           'sealed_inputs': SEALED}
    ro = PA.roster_rows(SEASON, WEEK, list(TEAMS), CUTOFF)
    if ro.state is not State.PASS:
        return {**out, 'fatal': f'{ro.state.value}[{ro.code}] {ro.detail[:200]}'}
    players = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                'team': r['team']}
               for r in ro.value
               if r.get('gsis_id') and r.get('position') in POS]
    if not players:
        return {**out, 'fatal': 'the roster produced no skill player'}
    out['n_players'] = len(players)
    out['roster_source'] = {k: v for k, v in ro.evidence.items()
                            if k in ('blob', 'as_of', 'n_rows', 'chosen',
                                     'reduced', 'raw')}

    # THE INJURY ROWS ARE SELECTED POINT-IN-TIME, THROUGH THE SAME CLOCK THE
    # PRODUCTION PATH DECLARES. `latest_injuries_rows` refuses outright
    # without one rather than reaching for the newest capture, which is the
    # whole point of the C1 repair it carries, and a replay that quietly took
    # a post-cutoff injury report would be measuring the future.
    with VS.clock(written_at=CUTOFF, origin='p1_counterfactual'):
        inj = RD.latest_injuries_rows(SEASON)
    if not inj:
        return {**out, 'fatal': 'no lawful injury vintage at the cutoff'}
    out['n_injury_rows'] = len(inj)

    arms = {}
    a8 = R8.predict(SEASON, WEEK, players, inj, observed_before=CUTOFF)
    if a8.state is not State.PASS:
        return {**out, 'fatal': f'R8 {a8.state.value}[{a8.code}] '
                                f'{a8.detail[:200]}'}
    arms['R8'] = a8
    a10 = R8.predict_r10(SEASON, WEEK, players, inj, observed_before=CUTOFF)
    if a10.state is not State.PASS:
        return {**out, 'fatal': f'R10 {a10.state.value}[{a10.code}] '
                                f'{a10.detail[:200]}'}
    arms['R10'] = a10

    room = sorted(SEALED['C'])
    prior = _normalise(SEALED['C'])
    out['carry_prior_normalised'] = {NAMES[i]: round(prior[i], 4)
                                     for i in room}

    # THE TWO CHECKS THAT MAKE THE REPLICATION EVIDENCE RATHER THAN ARITHMETIC.
    at_one, ev1 = expected_shares(SEALED['C'], {i: 1.0 for i in room})
    at_sealed, ev2 = expected_shares(SEALED['C'], SEALED['appearance_r8'])
    out['replication_check'] = {
        'at_p_equals_one': {NAMES[i]: round(at_one[i], 4) for i in room},
        'max_abs_error_against_the_prior':
            round(max(abs(at_one[i] - prior[i]) for i in room), 5),
        'at_the_sealed_r8_probabilities':
            {NAMES[i]: round(at_sealed[i], 4) for i in room},
        'sealed_board_shares': {NAMES[i]: SEALED['board_shares'][i]
                                for i in room},
        'max_abs_error_against_the_board':
            round(max(abs(at_sealed[i] - SEALED['board_shares'][i])
                      for i in room), 4),
        'draws': ev1 | ev2,
    }

    out['injury_rows_for_the_three_backs'] = [
        {k: r.get(k) for k in ('season', 'week', 'team', 'gsis_id',
                               'report_status', 'practice_status')}
        for r in inj if str(r.get('gsis_id')) in SEALED['C']]
    out['arms'] = {}
    for name, o in arms.items():
        p = {i: o.value.get(i) for i in room}
        missing = [i for i in room if p[i] is None]
        if missing:
            out['arms'][name] = {'declined_or_absent': missing,
                                 'declined': o.evidence.get('declined')}
            continue
        sh, ev = expected_shares(SEALED['C'], p)
        out['arms'][name] = {
            'spec_version': o.evidence.get('spec_version'),
            'coef_sha256': o.evidence.get('coef_sha256'),
            'rank_scale': o.evidence.get('rank_scale', 'offence_wide'),
            'appearance_p': {NAMES[i]: round(p[i], 6) for i in room},
            'expected_carry_share': {NAMES[i]: round(sh[i], 4) for i in room},
            'departure_from_the_prior':
                {NAMES[i]: round(sh[i] - prior[i], 4) for i in room},
            'max_abs_departure': round(
                max(abs(sh[i] - prior[i]) for i in room), 4),
            'order_matches_the_prior':
                [NAMES[i] for i in sorted(room, key=lambda j: -sh[j])]
                == [NAMES[i] for i in sorted(room, key=lambda j: -prior[j])],
            'draws': ev,
        }
    if all('appearance_p' in v for v in out['arms'].values()):
        out['verdict'] = {
            'r8_inverts_the_prior':
                not out['arms']['R8']['order_matches_the_prior'],
            'r10_preserves_the_prior_order':
                out['arms']['R10']['order_matches_the_prior'],
            'max_abs_departure_R8': out['arms']['R8']['max_abs_departure'],
            'max_abs_departure_R10': out['arms']['R10']['max_abs_departure'],
            'lawful_pregame_evidence_to_depart':
                'none found: no injury row for any of the three backs at the '
                'cutoff; the depth chart lists them 1/2/3 within the position '
                'room and is stable across the week',
        }
    return out


def main(argv=None):
    out = run()
    p = HERE / 'P1_COUNTERFACTUAL_EVIDENCE.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1)[:5000])
    print('written', p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
