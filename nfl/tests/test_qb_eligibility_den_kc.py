"""The quarterback pool obeys player eligibility -- and that is all it does.

TWO SEPARATE CLAIMS, AND THIS MODULE KEEPS THEM SEPARATE ON PURPOSE.

1. ELIGIBILITY. `run_forecast` filtered the non-QB allocation pool on roster
   status and exempted quarterbacks by comment. A reserve-list quarterback
   therefore entered a live room: on 2026-09-14, for 2026_01_DEN_KC, Kansas
   City's Chris Oladokun (status RES) was in the pool and drew 55.00% of the
   club's modelled dropbacks against Patrick Mahomes's 37.76%. He cannot take
   a dropback, so his share is zero by the definition of the event.

2. THE SEASON BOUNDARY, WHICH THIS DOES NOT REPAIR. `previous_primary_detail`
   resolves the incumbent by ordinal `bisect`, so a season opener inherits the
   PRIOR SEASON's final-game primary. Removing an ineligible incumbent from the
   room does not put the bit on the right man; it removes the bit entirely.
   `d652afb` recorded the same result for DAL/NYG and named it honestly:
   "Removing the wrong quarterback moved the defect, it did not fix it."

The tests below assert (1) holds and (2) still does not, because the dangerous
reading of a green eligibility test is that the room is now sound.

NOTHING HERE CONDITIONS ON TONIGHT'S RESULT. Every assertion is about the
pregame configuration -- who is eligible, which ordinal the incumbent came
from, what the artifact records -- and none is about what any quarterback does.
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import run_forecast as RF                        # noqa: E402
from nfl.production.nonqb import roster_status as RS                 # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                 # noqa: E402

PASSED = FAILED = BLOCKED = 0

GAME_ID = '2026_01_DEN_KC'
SEASON, WEEK = 2026, 1
TEAMS = ('DEN', 'KC')
KICKOFF = '2026-09-15T00:15:00Z'
WRITTEN_AT = '2026-09-14T16:30:00Z'

# The Q9 prospective freeze, declared in nfl/research/q9b/Q9_PROSPECTIVE_FREEZE
# .json. This module must not move it and the check says so rather than
# trusting that nobody did.
Q9_LAYERS_SHA16 = '481f005f682cd721'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    """Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def _qb_compute_source():
    src = open(os.path.join(_ROOT, 'nfl/production/run_forecast.py'),
               encoding='utf-8').read()
    i = src.index('def _candidate_qb_compute()')
    j = src.find('\n    def ', i + 10)
    return src[i:j if j > 0 else len(src)]


def test_the_qb_pool_is_filtered_under_the_same_flag_as_the_non_qb_pool():
    """One filter, one flag, one status map -- not a second policy."""
    body = _qb_compute_source()
    check('the QB stage reads the active-roster flag',
          "eligibility_on = bool(fl.get('active_roster_only'))" in body
          and 'if eligibility_on:' in body)
    check('  and filters the QB list through roster_status.active_pool',
          'RS.active_pool(qbp' in body)
    check('  using the same status map the non-QB half uses',
          'RS.status_map(args.season, args.week, teams' in body
          and "observed_before=args.written_at" in body
          and "kickoff_utc=fx.get('kickoff_utc')" in body)
    check('  it never falls back to the unfiltered list',
          'except' not in body and 'or qbp' not in body)
    check('  a status refusal is returned, not swallowed',
          'return st' in body and 'return qpool' in body)
    check('  a team emptied by eligibility refuses by name',
          'QB_POOL_EMPTIED_BY_ELIGIBILITY' in body)


def test_reserve_and_practice_squad_quarterbacks_are_not_eligible():
    """On a synthetic status map, so this holds with no capture on disk."""
    qbs = [{'gsis_id': 'A', 'position': 'QB', 'team': 'X'},
           {'gsis_id': 'B', 'position': 'QB', 'team': 'X'},
           {'gsis_id': 'C', 'position': 'QB', 'team': 'X'},
           {'gsis_id': 'D', 'position': 'QB', 'team': 'X'}]
    o = RS.active_pool(qbs, {'A': 'ACT', 'B': 'RES', 'C': 'DEV'})
    check('the filter passes', o.state is State.PASS, o.code)
    kept = {q['gsis_id'] for q in o.value}
    check('  an active quarterback is kept', 'A' in kept)
    check('  a reserve-list quarterback is dropped', 'B' not in kept)
    check('  a practice-squad quarterback is dropped', 'C' not in kept)
    check('  a quarterback the roster does not describe is KEPT and counted',
          'D' in kept and o.evidence['n_unknown_status_kept'] == 1,
          str(o.evidence.get('n_unknown_status_kept')))
    check('  and each drop is recorded under its status code',
          o.evidence['dropped_by_status'] == {'DEV': 1, 'RES': 1},
          str(o.evidence.get('dropped_by_status')))


def test_tonights_two_rooms_lose_exactly_the_ineligible_quarterbacks():
    st = RS.status_map(SEASON, WEEK, TEAMS, observed_before=WRITTEN_AT,
                       kickoff_utc=KICKOFF)
    if st.state is not State.PASS:
        blocked('tonight\'s roster status', f'{st.code}: {st.detail[:120]}')
        return
    import csv
    import gzip
    import pathlib
    from nfl.research.shadow import information_set as IS
    info = IS.build(KICKOFF, observed_before=WRITTEN_AT)
    blob = info['sources']['weekly_rosters']['blob']
    rows = [r for r in csv.DictReader(
        gzip.open(pathlib.Path(_ROOT) / blob, 'rt'))
        if r['season'] == str(SEASON) and r['week'] == str(WEEK)
        and r['team'] in TEAMS]
    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rows
           if r['position'] == 'QB' and r['gsis_id']]
    if not qbp:
        blocked('tonight\'s QB pool', f'no QB rows for {TEAMS} in {blob}')
        return
    o = RS.active_pool(qbp, st.value)
    check('the QB pool filters cleanly', o.state is State.PASS, o.code)
    kept = {q['gsis_id'] for q in o.value}
    dropped = [q for q in qbp if q['gsis_id'] not in kept]
    check('  every dropped quarterback is named with his status code',
          all(st.value.get(q['gsis_id']) in RS.EXCLUDED for q in dropped),
          str([(q['gsis_id'], st.value.get(q['gsis_id'])) for q in dropped]))
    for t in TEAMS:
        check(f'  {t} still has an eligible quarterback',
              any(q['team'] == t for q in o.value))
    print(f"     dropped: {[(q['team'], q['gsis_id'], st.value.get(q['gsis_id'])) for q in dropped]}")


def test_eligibility_does_not_repair_the_season_boundary_incumbent():
    """THE CLAIM THIS MODULE EXISTS TO STOP. A green eligibility test must not
    be read as a sound quarterback room."""
    try:
        detail = QA.previous_primary_detail(SEASON, WEEK)
    except Exception as e:                                    # noqa: BLE001
        blocked('the incumbent resolver', f'{type(e).__name__}: {e}')
        return
    kc = detail.get('KC') or {}
    check('KC\'s week-1 incumbent is resolved across the season boundary',
          kc.get('is_season_opener') is True, str(kc))
    check('  and comes from the PRIOR season\'s final game',
          isinstance(kc.get('ordinal'), int)
          and kc['ordinal'] // 100 == SEASON - 1
          and kc['ordinal'] % 100 >= 17, str(kc.get('ordinal')))
    st = RS.status_map(SEASON, WEEK, TEAMS, observed_before=WRITTEN_AT,
                       kickoff_utc=KICKOFF)
    if st.state is not State.PASS:
        blocked('the eligibility of KC\'s declared incumbent', st.code)
        return
    status = st.value.get(kc.get('pid'))
    check('  eligibility removes him rather than correcting him',
          status is None or status != RS.ACTIVE,
          f'incumbent {kc.get("pid")} status {status}')
    check('  so after the filter the incumbent bit lands on NOBODY, which is '
          'a different room and not a repaired one',
          status is None or status in RS.EXCLUDED,
          f'{kc.get("pid")}: {status}')


def test_the_run_records_what_it_has_not_repaired():
    s = RF.QB_PARTICIPATION_LIMITATION
    check('the limitation string exists and is not empty', bool(s and s.strip()))
    check('  it names the season-boundary defect',
          'QB3_WEEK1_SEASON_BOUNDARY' in s)
    check('  it names the rank-3 default for an unranked quarterback',
          'rank 3' in s and 'qb_allocation' in s)
    check('  it cites the audit the numbers come from',
          'QB3_WEEK1_INCUMBENT_AUDIT.json' in s)
    check('  it states the consequence for a price comparison',
          'CONTAMINATED' in s and 'inadmissible' in s)
    src = open(os.path.join(_ROOT, 'nfl/production/run_forecast.py'),
               encoding='utf-8').read()
    check('  and the sealed run status carries it',
          "summary['qb_participation_limitation']" in src
          and "summary['qb_pool_eligibility']" in src)
    check('  only on a run that actually filtered -- absence stays absence',
          "if fx.get('_r5_qb_applied') else None" in src)


def test_q9_frozen_layers_are_untouched():
    p = os.path.join(_ROOT, 'nfl/production/nonqb/layers.py')
    got = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
    check('nfl/production/nonqb/layers.py is still the Q9-frozen artifact',
          got == Q9_LAYERS_SHA16, f'{got} != {Q9_LAYERS_SHA16}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
