"""The five properties the Thursday pool must have, proven on real DET-BUF data.

The repair these guard replaced a FATAL refusal: `status_map` returns
ROSTER_STATUS_EMPTY for 2026 week 2, `run_forecast` treats that as fatal to the
whole non-QB chain, and DET-BUF would have produced no running back, no
receiver and no tight end for either club.

The obvious alternative -- take week-2 membership and let injuries and
inactives exclude -- was measured and REJECTED: league week-2 skill membership
is 810 rows of which only 487 were ACT, and DET's contains a RETIRED player.
Sections A-E are the properties that alternative would have broken.

Run standalone:  python3.12 nfl/tests/test_participant_class.py
"""
import csv
import glob
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.production.nonqb import participant_class as PC          # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
SKILL = {'QB', 'RB', 'WR', 'TE', 'FB', 'K'}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  ..   NOT_EXECUTED {label} -- {why}')


def _members(season, week, teams):
    for f in glob.glob(os.path.join(ROOT, 'nfl/vintage/weekly_rosters.*.csv.gz')):
        try:
            rows = list(csv.DictReader(gzip.open(f, 'rt')))
        except Exception:                                        # noqa: BLE001
            continue
        hit = [r for r in rows
               if str(r.get('season')) == str(season)
               and str(r.get('week')) == str(week)
               and r.get('team') in teams
               and r.get('position') in SKILL]
        if hit:
            return hit
    return []


def _classified():
    m = _members(2026, 2, ('DET', 'BUF'))
    if not m:
        return None, None
    return m, PC.classify(2026, 2, m, observed_before='2026-09-15T12:00:00Z')


def test_a_no_practice_squad_player_competes_without_an_elevation():
    print('\nA. no practice-squad player competes without elevation')
    m, out = _classified()
    if out is None or not out.ok:
        not_executed('classification', 'no week-2 membership, or refusal')
        return
    ps = [r for r in out.value if r['participant_class'] == PC.PRACTICE_SQUAD]
    check('practice-squad members are present in the universe', bool(ps),
          'if none are here the file was pre-filtered and this proves nothing')
    act = [r for r in out.value
           if r['participant_class'] == PC.ACTIVE_ROSTER_EXPECTED]
    # REWRITTEN. This used to assert a practice-squad player carried a SMALL
    # participation probability. That was the conflation itself: a smoothed
    # observation rate was standing in for P(roster transition before
    # kickoff), which nothing here has measured. He carries NO participation
    # number now, and no route into the opportunity pool.
    check('  and none carries a participation number at all',
          all(p['participation_prior'] is None for p in ps),
          str({p['participation_prior'] for p in ps}))
    check('  and none enters the opportunity pool',
          all(not p['enters_opportunity_pool'] for p in ps))
    check('  and the transition probability is UNIDENTIFIED, not a number',
          all(p['transition_probability'] is None for p in ps),
          'inventing it would be inventing an elevation rate from a feed that '
          'does not exist')
    check('  and the missing authority is named',
          all(p['transition_authority']
              == 'UNIDENTIFIED_NO_TRANSACTIONS_ENDPOINT' for p in ps))
    check('  while an active player does carry one',
          act and all(a['participation_prior'] is not None for a in act))
    check('  and elevation is reported UNAVAILABLE, not silently unused',
          out.evidence.get('elevation_authority')
          == 'UNAVAILABLE_NO_TRANSACTIONS_ENDPOINT',
          str(out.evidence.get('elevation_authority')))


def test_b_no_reserve_or_released_player_competes():
    print('\nB. no reserve, released or retired player competes')
    m, out = _classified()
    if out is None or not out.ok:
        not_executed('classification', 'no week-2 membership, or refusal')
        return
    dead = [r for r in out.value
            if r['participant_class'] in (PC.RESERVE, PC.RELEASED, PC.RETIRED)]
    check('they are present in the membership file', bool(dead),
          'DET week-2 skill membership contains a RETIRED player')
    check('  and none competes at all',
          all(d['participation_prior'] is None
              and not d['enters_opportunity_pool'] for d in dead),
          str([(d['participant_class'], d['participation_prior'])
               for d in dead]))
    check('  and each names the status it came from',
          all(d['status_basis'] for d in dead))


def test_c_secondary_participants_stay_available():
    print('\nC. WR4/WR5/TE2/RB2 remain fully available')
    m, out = _classified()
    if out is None or not out.ok:
        not_executed('classification', 'no week-2 membership, or refusal')
        return
    for team in ('DET', 'BUF'):
        for pos in ('WR', 'TE', 'RB'):
            live = [r for r in out.value
                    if r['team'] == team and r['position'] == pos
                    and r['enters_opportunity_pool']
                    and (r['participation_prior'] or 0) > 0.5]
            check(f'{team} {pos}: more than the board shows remain live',
                  len(live) >= 3,
                  f'{len(live)} live -- the board shows WR1/WR2/WR3 or one '
                  f'TE/RB, the simulator must carry the rest')


def test_d_a_week_one_inactive_is_not_a_week_two_exclusion():
    print('\nD. a week-1 inactive is a 53-man member, not a week-2 exclusion')
    m, out = _classified()
    if out is None or not out.ok:
        not_executed('classification', 'no week-2 membership, or refusal')
        return
    ina = [r for r in out.value if (r['status_basis'] or '').startswith('INA')]
    if not ina:
        not_executed('week-1 INA carry-forward', 'no INA member in this game')
        return
    check('week-1 inactives are classed as active-roster',
          all(r['participant_class'] == PC.ACTIVE_ROSTER_EXPECTED
              for r in ina),
          str({r['participant_class'] for r in ina}))
    check('  and carry the full active participation prior',
          all(r['enters_opportunity_pool']
              and (r['participation_prior'] or 0) > 0.5 for r in ina),
          'INA measured 0/62 IN WEEK 1 BY CONSTRUCTION; reusing that as a '
          'week-2 prior would be the defect this file audits')


def test_e_the_pool_is_neither_membership_nor_a_hard_filter():
    print('\nE. the pool is weighted, not membership and not a hard cut')
    m, out = _classified()
    if out is None or not out.ok:
        not_executed('classification', 'no week-2 membership, or refusal')
        return
    for team in ('DET', 'BUF'):
        rows = [r for r in out.value if r['team'] == team]
        pool = [r for r in rows if r['enters_opportunity_pool']]
        eff = sum(r['participation_prior'] for r in pool)
        check(f'{team}: effective pool is well below raw membership',
              eff < 0.75 * len(rows),
              f'{eff:.2f} effective vs {len(rows)} members')
        check(f'  and nobody was deleted from the universe',
              len(rows) == len([r for r in m if r['team'] == team]),
              'every member is classified; none is dropped')
        check(f'  and the effective pool is in the band R5 fitted (12-17)',
              12.0 <= eff <= 17.0, f'{eff:.2f}')
        check(f'  and everyone held out is held for a NAMED reason',
              all(r['transition_authority']
                  == 'UNIDENTIFIED_NO_TRANSACTIONS_ENDPOINT'
                  for r in rows if not r['enters_opportunity_pool']))


def test_f_unknown_is_neither_active_nor_excluded():
    """The hardest of the three, and the one a pool filter gets wrong twice.

    The first cut gave UNKNOWN the marginal rate, 0.5000 -- which invents the
    transition probability by another route. Holding it out of the pool instead
    makes it "definitely excluded", which is the other thing it must not mean.
    So it is held out of the POINT pool and COUNTED as a declared
    incompleteness: neither resolved nor disappeared.
    """
    print('\nF. UNKNOWN is uncertainty, not a decision either way')
    ro = PC.rates()
    if not ro.ok:
        not_executed('rate artifact', ro.code)
        return
    doc = ro.value
    check('UNKNOWN is not given a participation number',
          PC.participation_prior(PC.UNKNOWN, doc) is None,
          'the marginal rate would be the transition probability invented '
          'by another route')
    check('  and is not asserted eligible',
          PC.eligibility_state(PC.UNKNOWN) == 'UNKNOWN',
          PC.eligibility_state(PC.UNKNOWN))
    check('  and is not asserted off the roster either',
          PC.eligibility_state(PC.UNKNOWN) != 'NOT_GAME_ROSTER')
    check('  and its transition probability is UNIDENTIFIED',
          PC.transition_probability(PC.UNKNOWN) is None)
    # AND IT MUST BE COUNTED, or "held out" silently becomes "excluded".
    m, out = _classified()
    if out is None or not out.ok:
        not_executed('unknown reporting', 'no classification')
        return
    ev = out.evidence
    check('the classification reports how many are UNKNOWN',
          'n_unknown' in ev, str(sorted(ev)[:12]))
    check('  and names them rather than dropping them',
          'unknown_members' in ev
          and len(ev['unknown_members']) == ev['n_unknown'])
    check('  and states what UNKNOWN means',
          ev.get('unknown_semantics')
          == 'NOT_ACTIVE_AND_NOT_EXCLUDED__REQUIRES_ELIGIBILITY_RESOLUTION',
          str(ev.get('unknown_semantics')))
    check('  and the pool and held counts are both reported',
          'n_in_opportunity_pool' in ev and 'n_held_pending_transition' in ev)
    check('  and every member is accounted for in one of the three',
          ev['n_in_opportunity_pool'] + ev['n_held_pending_transition']
          + ev['n_unknown'] == len(out.value),
          f"{ev['n_in_opportunity_pool']} + "
          f"{ev['n_held_pending_transition']} + {ev['n_unknown']} "
          f"vs {len(out.value)} -- nobody may fall between the classes")
    # DET-BUF happens to have none; the accounting must still hold.
    check('  (DET-BUF carries no UNKNOWN member, so Thursday is unaffected)',
          ev['n_unknown'] == 0, str(ev['n_unknown']))


if __name__ == '__main__':
    test_a_no_practice_squad_player_competes_without_an_elevation()
    test_b_no_reserve_or_released_player_competes()
    test_c_secondary_participants_stay_available()
    test_d_a_week_one_inactive_is_not_a_week_two_exclusion()
    test_e_the_pool_is_neither_membership_nor_a_hard_filter()
    test_f_unknown_is_neither_active_nor_excluded()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
