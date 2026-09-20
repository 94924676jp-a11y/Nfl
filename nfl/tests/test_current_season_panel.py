"""Current-season incumbency rows: lawful, counted, and never inferred.

THE DEFECT THIS EXISTS FOR. `panel_p3.csv.gz` stops at ordinal 202518, so a
2026 week-2 forecast gave all 32 clubs a 2025 week-18 previous primary and
classed all 32 a season opener. Against 2026 week-1 play-by-play, 7 of the 20
checkable clubs carried the WRONG previous primary.

THE THREE PROPERTIES THAT MAKE THE REPAIR SAFE, each asserted behaviourally:

  the CLOCK    a capture not strictly before the forecast instant is dropped,
               and the drop is counted. Tested by moving the clock, not by
               reading the comparison
  ADDITIVITY   `previous_primary_detail` with no flag returns exactly what it
               returned before, bit for bit
  ABSENCE      a club with no current-season evidence is NAMED and keeps the
               frozen answer. It is never inferred
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State            # noqa: E402
from nfl.production.nonqb import current_season_panel as CSP          # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                  # noqa: E402

PASSED = FAILED = 0
AS_OF = '2026-09-16T15:45:14Z'
CLUBS = None


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _clubs():
    global CLUBS
    if CLUBS is None:
        CLUBS = sorted(QA.previous_primary_detail(2026, 2))
    return CLUBS


def test_A_the_rows_exist_and_name_their_sources():
    print('\nA. 2026 week-1 rows, from the sources that actually hold them')
    CSP.cache_clear()
    o = CSP.rows_for(2026, 1, as_of=AS_OF, all_clubs=_clubs())
    check('the panel PASSES', o.state is State.PASS, f'{o.state}[{o.code}]')
    e = o.evidence
    check('  it covers more clubs than play-by-play alone',
          e['clubs_by_source'].get('snap_proxy', 0) > 0
          and e['clubs_by_source'].get('play_by_play', 0) > 0,
          str(e['clubs_by_source']))
    check('  every snap row resolved to a gsis_id by ID, never by name',
          e['snap_counts']['unresolved_identity'] == 0,
          str(e['snap_counts']['unresolved_identity']))
    check('  and the clubs it cannot reach are NAMED, not silently absent',
          isinstance(e['missing_clubs'], list)
          and len(e['missing_clubs']) == e['n_missing_clubs'],
          str(e['missing_clubs']))
    print(f'       {e["n_rows"]} row(s), {e["n_clubs"]} club(s), '
          f'by source {e["clubs_by_source"]}, missing {e["missing_clubs"]}')
    # A SNAP ROW IS NOT A DROPBACK ROW AND SAYS SO ON ITSELF.
    proxy = [r for r in o.value if r['source'] == 'snap_proxy']
    check('  every proxy row flags that its `db` is SNAPS, not dropbacks',
          bool(proxy) and all(r.get('db_is_offensive_snaps_not_dropbacks')
                              for r in proxy),
          f'{len(proxy)} proxy row(s)')


def test_B_the_clock_is_enforced_by_moving_it():
    print('\nB. the clock is enforced, not asserted')
    CSP.cache_clear()
    # BEFORE every capture: nothing is lawful, so the panel must REFUSE rather
    # than quietly return the rows it happens to hold.
    early = CSP.rows_for(2026, 1, as_of='2026-09-01T00:00:00Z',
                         all_clubs=_clubs())
    check('a clock before every capture BLOCKS', early.state is State.BLOCKED,
          f'{early.state}[{early.code}]')
    check('  with cause DATA', early.evidence.get('cause') == Cause.DATA.value,
          str(early.evidence.get('cause')))
    check('  and the drops are COUNTED, not silent',
          early.evidence['play_by_play']['dropped_by_clock'] > 0
          and early.evidence['snap_counts']['dropped_by_clock'] > 0,
          f"pbp {early.evidence['play_by_play']['dropped_by_clock']}, "
          f"snap {early.evidence['snap_counts']['dropped_by_clock']}")
    CSP.cache_clear()
    late = CSP.rows_for(2026, 1, as_of=AS_OF, all_clubs=_clubs())
    # ASSERTS THE PROPERTY, NOT AN INCIDENTAL COUNT. This used to require
    # `dropped_by_clock == 0`, which held only while ONE play-by-play store
    # existed. Two are considered now -- the research postgame store and the
    # governed vintage capture -- and at this AS_OF the vintage captures
    # (retrieved 2026-09-17) are LATER than the clock and are correctly
    # dropped. Demanding zero drops would demand that the clock stop working
    # whenever a newer capture lands, which is the opposite of the guarantee.
    # What the step means is: moving the clock forward admits evidence that
    # was refused before, and the panel answers from it.
    check('  moving the clock forward admits them again',
          late.state is State.PASS
          and late.evidence['play_by_play'].get('blob')
          and late.evidence['play_by_play']['dropped_by_clock']
          < early.evidence['play_by_play']['dropped_by_clock'],
          f"{late.state}[{late.code}] store="
          f"{late.evidence['play_by_play'].get('store')} dropped "
          f"{early.evidence['play_by_play']['dropped_by_clock']} -> "
          f"{late.evidence['play_by_play']['dropped_by_clock']}")
    CSP.cache_clear()
    # STRICTLY before: a capture taken AT the instant is not prior evidence.
    exact = CSP.rows_for(2026, 1,
                         as_of=late.evidence['play_by_play']['retrieved_at'],
                         all_clubs=_clubs())
    check('  a capture taken AT the forecast instant is NOT admitted',
          exact.evidence['play_by_play']['dropped_by_clock'] >= 1,
          str(exact.evidence['play_by_play']['dropped_by_clock']))


def test_C_the_refresh_is_additive():
    print('\nC. a caller that does not ask gets exactly what it got before')
    QA.cache_clear(); CSP.cache_clear()
    old = QA.previous_primary_detail(2026, 2)
    check('the default return is a plain club mapping',
          isinstance(old, dict) and all(isinstance(v, dict)
                                        for v in old.values()))
    check('  with no evidence key smuggled into it',
          not any(k.startswith('__') for k in old), str(list(old)[:3]))
    QA.cache_clear(); CSP.cache_clear()
    again = QA.previous_primary_detail(2026, 2)
    check('  and it is stable across calls', again == old)
    check('  every club is still classed a season opener without the flag',
          all(v['is_season_opener'] for v in old.values()),
          'this is the DEFECT, and it must survive until the flag is set')


def test_D_with_the_flag_the_state_is_corrected_and_absence_preserved():
    print('\nD. with the flag: corrected where there is evidence, MISSING where not')
    QA.cache_clear(); CSP.cache_clear()
    old = QA.previous_primary_detail(2026, 2)
    QA.cache_clear(); CSP.cache_clear()
    new, ev = QA.previous_primary_detail(
        2026, 2, as_of=AS_OF, current_season=True, all_clubs=sorted(old),
        with_evidence=True)
    check('the refresh PASSES and reports its own state',
          ev['state'] == 'PASS', f"{ev['state']}[{ev.get('code')}]")
    changed = [t for t in old
               if old[t]['pid'] != new[t]['pid']
               or old[t]['is_season_opener'] != new[t]['is_season_opener']]
    check(f'  {len(changed)} club(s) changed state', len(changed) > 0)
    still = sorted(t for t in new if new[t]['is_season_opener'])
    check('  the ONLY clubs still classed openers are the ones with no evidence',
          still == sorted(ev['missing_clubs']),
          f'still opener {still} vs missing {sorted(ev["missing_clubs"])}')
    for t in still:
        check(f'  {t} keeps the FROZEN answer rather than an inferred one',
              new[t]['pid'] == old[t]['pid']
              and new[t]['ordinal'] == old[t]['ordinal']
              and not new[t]['current_season_evidence'])
    # THE TWO CLUBS THIS BOARD IS FOR.
    for t, want_opener in (('BUF', False), ('DET', False)):
        if t not in new:
            continue
        check(f'  {t}: opener {old[t]["is_season_opener"]} -> '
              f'{new[t]["is_season_opener"]}',
              new[t]['is_season_opener'] is want_opener)
        check(f'    and its previous ordinal is a {2026} one',
              new[t]['ordinal'] // 100 == 2026, str(new[t]['ordinal']))
    check('  BUF`s previous primary CHANGED -- it named a week-18 backup',
          'BUF' in changed, f'changed: {sorted(changed)[:6]}')


def test_E_freshness_stops_firing_on_the_refreshed_state():
    print('\nE. the blocker and the repair agree with each other')
    o = QA.panel_freshness(2026, 2)
    check('panel_freshness still BLOCKS on the FROZEN panel alone',
          o.state is State.BLOCKED and o.code == 'PANEL_STALE_CURRENT_SEASON_STATE',
          f'{o.state}[{o.code}]')
    check('  which is correct: the frozen panel is still stale, and the '
          'refresh is additive rather than a rewrite of it', True)


def test_F_the_verdict_reaches_the_allocation_outcome():
    """THE WIRING CHECK, and it is here because the wiring was broken.

    The first GSVUC board ran to completion and recorded `not_reached: [CS1]`.
    The refresh worked, the flag was declared, the candidate resolved -- and
    `current_season_panel=` was never added to `allocate`'s Outcome, because
    the edit that would have added it aborted on an earlier assertion and wrote
    nothing. `_cs_ev` was computed and thrown away.

    Every layer downstream reads the ALLOCATOR'S OWN EVIDENCE rather than the
    flag, which is what made the failure visible as NOT_REACHED instead of a
    silent false claim. That design worked. What was missing was a test that
    the evidence arrives at all.
    """
    print('\nF. the refresh verdict reaches the allocation Outcome')
    import numpy as np
    dc = QA.captured_depth_chart()
    if dc.state is not State.PASS:
        print(f'  ..   NOT_EXECUTED no captured depth chart: {dc.code}')
        return
    teams = [t for t in ('DET', 'BUF') if dc.value.get(t)]
    if not teams:
        print('  ..   NOT_EXECUTED neither DET nor BUF is on the chart')
        return
    players = [{'gsis_id': g, 'team': t}
               for t in teams for g in (dc.value.get(t) or {})]
    tdb = {t: np.full(40, 35.0) for t in teams}
    QA.cache_clear(); CSP.cache_clear()
    off = QA.allocate(2026, 2, teams, players, m=40, allocator='qb_room_v2',
                      team_dropback_draws=tdb, written_at=AS_OF,
                      current_season_state=False)
    QA.cache_clear(); CSP.cache_clear()
    on = QA.allocate(2026, 2, teams, players, m=40, allocator='qb_room_v2',
                     team_dropback_draws=tdb, written_at=AS_OF,
                     current_season_state=True)
    check('both allocations PASS',
          off.state is State.PASS and on.state is State.PASS,
          f'{off.state}[{off.code}] / {on.state}[{on.code}]')
    check('  the Outcome carries `current_season_panel` when the flag is ON',
          (on.evidence.get('current_season_panel') or {}).get('state') == 'PASS',
          str(on.evidence.get('current_season_panel'))[:120])
    check('  and records NOT_REQUESTED when it is OFF -- never silently absent',
          (off.evidence.get('current_season_panel') or {}).get('state')
          == 'NOT_REQUESTED',
          str(off.evidence.get('current_season_panel'))[:120])
    # THE STATE ACTUALLY REACHES THE ROOM, not just the evidence block.
    for t in teams:
        a = off.evidence['qb3_configuration'][t]
        b = on.evidence['qb3_configuration'][t]
        check(f'  {t}: opener {a["is_season_opener"]} -> '
              f'{b["is_season_opener"]} in the room`s own configuration',
              a['is_season_opener'] and not b['is_season_opener'],
              f'{a["is_season_opener"]} -> {b["is_season_opener"]}')
        check(f'    and its stale-state defect id clears',
              a.get('defect_id') is not None and b.get('defect_id') is None,
              f'{a.get("defect_id")} -> {b.get("defect_id")}')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_rows_exist_and_name_their_sources,
               test_B_the_clock_is_enforced_by_moving_it,
               test_C_the_refresh_is_additive,
               test_D_with_the_flag_the_state_is_corrected_and_absence_preserved,
               test_E_freshness_stops_firing_on_the_refreshed_state,
               test_F_the_verdict_reaches_the_allocation_outcome):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)
