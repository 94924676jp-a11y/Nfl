"""CS2 stage 2: two quantities, conserved shares, and no imposed ordering.

The layer whose ABSENCE is the DATA_STATE_DEFECT in P2_DIAGNOSTIC. CS1 is a
quarterback panel, so current-season receiving and rushing usage never reached
non-QB allocation. Stage 1 measured it; stage 2 turns it into state.

THREE THINGS THESE CHECKS EXIST TO STOP

  a single "role" number. P(appears) and share|appears are estimated apart,
  because Cook's unconditional 0.454 averaged a defensible conditional share
  against an indefensible absence mass and hid which was wrong.

  an imposed ordering. Nothing forces RB1 above RB2. test_E builds a room
  where the backup genuinely appears more often and asserts CS2 says so.

  a saturated probability shipping quietly. A Beta posterior mean is exactly
  1.0 for a man who has never missed. test_F asserts that is COUNTED and not
  clipped, because the floor is a modelling choice and belongs in a
  preregistration.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import cs2_state as CS                      # noqa: E402
from sportsplatform.governance.outcome import State                   # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

FIT = _REPO/'nfl/research/cs2/CS2_STAGE2_FIT.json'
REDIAG = _REPO/'nfl/research/buf_allocation/CS2_REDIAGNOSTIC.json'

#: gsis_ids. Identity is never inferred from a name or a row order.
COOK = '00-0037248'
DAVIS = '00-0039875'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _rows(spec):
    """{(week, club, pid): counts} from a compact spec."""
    blank = dict(carries=0.0, targets=0.0, receptions=0.0,
                 rush_yards=0.0, rec_yards=0.0)
    out = {}
    for (wk, club, pid), d in spec.items():
        out[(wk, club, pid)] = {**blank, **d}
    return out


def test_A_shares_conserve_and_appearance_does_not():
    cur = _rows({(1, 'X', 'a'): {'carries': 10.0},
                 (1, 'X', 'b'): {'carries': 5.0},
                 (2, 'X', 'a'): {'carries': 8.0},
                 (2, 'X', 'b'): {'carries': 7.0}})
    o = CS.state(cur, {}, CS.CARRIES, kappa_a=1.0, kappa_s=5.0, n_weeks=2)
    check('A the state builds', o.state is State.PASS, f'{o.state}[{o.code}]')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('A-B state assertions')
        return
    s = sum(r['share_given_appears'] for r in o.value.values())
    check('A room shares sum to 1.0 within 1e-9', abs(s - 1.0) < 1e-9,
          f'{s:.12f}')
    p = sum(r['p_appears'] for r in o.value.values())
    check('A appearance probabilities are NOT a simplex and need not sum to 1',
          p > 1.0 + 1e-9, f'{p:.4f}')
    check('A and the artifact says why that is correct, not a bug',
          'simplex' in o.evidence['appearance_is_not_a_simplex'])


def test_B_the_two_quantities_are_reported_apart():
    cur = _rows({(1, 'X', 'a'): {'carries': 13.0},
                 (1, 'X', 'b'): {'carries': 1.0}})
    o = CS.state(cur, {}, CS.CARRIES, kappa_a=1.0, kappa_s=5.0, n_weeks=1)
    if o.state is not State.PASS:
        NOT_EXECUTED.append('B two quantities')
        return
    a = o.value[('X', 'a')]
    check('B every row carries BOTH an appearance and a conditional share',
          'p_appears' in a and 'share_given_appears' in a, str(sorted(a)))
    check('B and the evidence behind them travels too',
          a['n_opportunity'] == 13.0 and a['n_weeks_with_opportunity'] == 1,
          str((a['n_opportunity'], a['n_weeks_with_opportunity'])))


def test_C_a_player_with_no_prior_season_falls_back_and_is_counted():
    cur = _rows({(1, 'X', 'rookie'): {'carries': 4.0},
                 (1, 'X', 'vet'): {'carries': 6.0}})
    prior = {('X', 'vet'): (0.8, 1.0)}
    o = CS.state(cur, prior, CS.CARRIES, kappa_a=2.0, kappa_s=10.0,
                 n_weeks=1)
    if o.state is not State.PASS:
        NOT_EXECUTED.append('C fallback')
        return
    check('C the fallback is counted, not silent',
          o.evidence['n_prior_fallbacks'] == 1,
          str(o.evidence['n_prior_fallbacks']))
    check('C and named on the row itself',
          o.value[('X', 'rookie')]['prior_fallback'] == CS.FALLBACK_ROOM_MEAN,
          str(o.value[('X', 'rookie')]['prior_fallback']))
    check('C while the man with history carries none',
          o.value[('X', 'vet')]['prior_fallback'] is None)


def test_D_the_prior_target_is_the_players_own_share():
    """Amendment B1's one real choice, asserted rather than described."""
    season = _rows({(1, 'X', 'a'): {'carries': 9.0},
                    (1, 'X', 'b'): {'carries': 1.0},
                    (2, 'X', 'a'): {'carries': 9.0},
                    (2, 'X', 'b'): {'carries': 1.0}})
    pr = CS.prior_from_season(season, CS.CARRIES)
    check('D the prior is a per-player share of his room, not a room mean',
          abs(pr[('X', 'a')][0] - 0.9) < 1e-12
          and abs(pr[('X', 'b')][0] - 0.1) < 1e-12,
          str({k[1]: round(v[0], 4) for k, v in pr.items()}))
    check('D and a per-player appearance rate over club weeks',
          pr[('X', 'a')][1] == 1.0 and pr[('X', 'b')][1] == 1.0,
          str({k[1]: v[1] for k, v in pr.items()}))
    # With a heavy prior the estimate must move toward HIS share, not 0.5.
    cur = _rows({(1, 'X', 'a'): {'carries': 1.0},
                 (1, 'X', 'b'): {'carries': 1.0}})
    o = CS.state(cur, pr, CS.CARRIES, kappa_a=1.0, kappa_s=100.0, n_weeks=1)
    check('D a heavy prior pulls toward his own share, not toward the mean',
          o.value[('X', 'a')]['share_given_appears'] > 0.8,
          str(round(o.value[('X', 'a')]['share_given_appears'], 4)))


def test_E_no_monotonicity_is_imposed():
    """A backup who genuinely plays more must be allowed to say so."""
    cur = _rows({(1, 'X', 'starter'): {'carries': 12.0},
                 (2, 'X', 'backup'): {'carries': 3.0},
                 (3, 'X', 'backup'): {'carries': 4.0}})
    o = CS.state(cur, {}, CS.CARRIES, kappa_a=0.0, kappa_s=0.0, n_weeks=3)
    if o.state is not State.PASS:
        NOT_EXECUTED.append('E monotonicity')
        return
    st, bk = o.value[('X', 'starter')], o.value[('X', 'backup')]
    check('E the man who appeared in more weeks has the higher P(appears)',
          bk['p_appears'] > st['p_appears'],
          f"starter {st['p_appears']:.3f} backup {bk['p_appears']:.3f}")
    check('E while the man with more opportunity has the higher share',
          st['share_given_appears'] > bk['share_given_appears'],
          f"{st['share_given_appears']:.3f} vs "
          f"{bk['share_given_appears']:.3f}")
    check('E which is exactly the specialist the design refuses to erase',
          'short-yardage' in o.evidence['no_monotonicity_imposed'])


def test_F_a_saturated_probability_is_counted_not_clipped():
    cur = _rows({(1, 'X', 'ironman'): {'carries': 10.0},
                 (1, 'X', 'ghost'): {'targets': 0.0}})
    prior = {('X', 'ironman'): (0.9, 1.0), ('X', 'ghost'): (0.1, 0.0)}
    o = CS.state(cur, prior, CS.CARRIES, kappa_a=1.0, kappa_s=5.0, n_weeks=1)
    if o.state is not State.PASS:
        NOT_EXECUTED.append('F saturation')
        return
    check('F a man who has never missed reaches exactly 1.0',
          o.value[('X', 'ironman')]['p_appears'] == 1.0,
          str(o.value[('X', 'ironman')]['p_appears']))
    check('F and it is COUNTED', o.evidence['n_p_appears_at_one'] >= 1,
          str(o.evidence['n_p_appears_at_one']))
    check('F not clipped behind the reader\'s back',
          'nothing is clipped' in o.evidence['p_appears_saturates'])
    check('F and the floor is named as a preregistration decision',
          'preregistration' in o.evidence['p_appears_saturates'])


def test_G_the_forward_chain_beat_its_declared_comparators():
    if not FIT.exists():
        NOT_EXECUTED.append('G forward chain (CS2_STAGE2_FIT.json absent)')
        return
    d = json.loads(FIT.read_text())
    ev = d['evidence']
    check('G the chain excluded 2026 entirely',
          2026 not in ev['seasons'] and '2026' in ev['seasons_excluded'],
          str(ev['seasons']))
    check('G the ordinal guard recorded zero violations',
          '0 violations' in ev['ordinal_guard'], ev['ordinal_guard'])
    check('G it scored opportunity, never yards',
          ev['scored_on_opportunity_not_yards'] is True)
    base, unif = d['PRIOR_ONLY'], d['UNIFORM']
    ba, bl = d['best_appearance'], d['best_allocation']
    check('G CS2 beats PRIOR_ONLY on appearance',
          ba['brier'] < base['brier'],
          f"{ba['brier']:.5f} vs {base['brier']:.5f}")
    check('G CS2 beats PRIOR_ONLY on allocation',
          bl['logloss'] < base['logloss'],
          f"{bl['logloss']:.5f} vs {base['logloss']:.5f}")
    check('G and PRIOR_ONLY itself beats the no-information floor',
          base['brier'] < unif['brier'] and base['logloss'] < unif['logloss'],
          f"{base['brier']:.5f} vs {unif['brier']:.5f}")
    check('G a measured negative was declared reportable in advance',
          'does not ship' in ev['measured_negative_is_a_result'])


def test_H_the_buffalo_inversion_was_re_measured_not_assumed():
    if not REDIAG.exists():
        NOT_EXECUTED.append('H re-diagnostic (CS2_REDIAGNOSTIC.json absent)')
        return
    d = json.loads(REDIAG.read_text())
    check('H the re-diagnostic reads no outcome data',
          d['uses_outcome_data'] is False)
    check('H the prior strengths were READ from the chain, not chosen',
          'read here, not chosen' in d['kappa_source'])
    check('H the verdict is one of the three declared outcomes',
          d['verdict'] in ('INVERSION_RESOLVED', 'INVERSION_PERSISTS',
                           'NO_INVERSION_IN_EITHER'), d['verdict'])
    cook = next(r for r in d['rows'] if r['gsis_id'] == COOK)
    davis = next(r for r in d['rows'] if r['gsis_id'] == DAVIS)
    check('H the sealed board really was inverted',
          cook['sealed_p_zero_opportunity']
          > davis['sealed_p_zero_opportunity'],
          f"{cook['sealed_p_zero_opportunity']} vs "
          f"{davis['sealed_p_zero_opportunity']}")
    check('H nothing was written back into a projection',
          'No projection' in d['nothing_written_back'])
    check('H the one-week caveat travels with the result',
          'week 1 alone' in d['one_week'])
    check('H and the saturation limitation is attached, with what it blocks',
          d['saturation_limitation']['code']
          == 'CS2_APPEARANCE_SATURATES_AT_ONE'
          and 'production' in d['saturation_limitation']['blocks'],
          str(d['saturation_limitation']['blocks']))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_shares_conserve_and_appearance_does_not,
               test_B_the_two_quantities_are_reported_apart,
               test_C_a_player_with_no_prior_season_falls_back_and_is_counted,
               test_D_the_prior_target_is_the_players_own_share,
               test_E_no_monotonicity_is_imposed,
               test_F_a_saturated_probability_is_counted_not_clipped,
               test_G_the_forward_chain_beat_its_declared_comparators,
               test_H_the_buffalo_inversion_was_re_measured_not_assumed):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
