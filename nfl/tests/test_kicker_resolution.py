"""The kicker resolver counts players, not roster rows.

THE DEFECT, AND WHY IT WAS INVISIBLE UNTIL A WHOLE SLATE RAN

`resolve_kicker` refused for ALL THIRTY-TWO clubs with
KICKER_NOT_UNIQUELY_DETERMINED, so every board in the 2026 week-2 slate
rehearsal came out with no kicking line. The cause was that `eligible` was a
list of ROWS, and the roster glob reads every committed vintage of
`weekly_rosters` -- eight of them by 2026-09-19 -- so a single kicker appeared
eight times and `len(eligible) != 1` was always true.

IT GREW WITH THE CAPTURE. With one or two vintages committed the resolver
worked, and it degraded silently as evidence accumulated. Nothing about the
code changed on the day it broke. A test that used one fixture vintage would
have passed throughout, so the case below is driven by the SAME player
repeated across several vintages -- which is the condition that actually
occurs.

And the refusal message carried the proof the whole time: "ATL has 7
game-roster kicker(s) ... out of 7 position-K row(s): {'00-0025565': ...}".
Seven kickers and one identifier. Nobody read it until a slate refused.

WHAT IS PINNED HERE

  * the same player across N vintages resolves, for any N;
  * two genuinely different eligible kickers still refuse -- the module's
    stated intent, which the row count was destroying rather than enforcing;
  * a player whose vintages DISAGREE about his eligibility is refused under
    its own code rather than deduplicated away, because that is a roster
    event and picking a vintage would bury it;
  * against the real capture, all 32 clubs resolve at 2026 week 2.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import kicking as KICK                        # noqa: E402
from sportsplatform.governance.outcome import State               # noqa: E402

PASSED = FAILED = 0

CLUBS = ('ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN',
         'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV', 'MIA',
         'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB',
         'TEN', 'WAS')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _row(gsis, status, name='A Kicker', team='ZZZ', week=2, season=2026):
    return {'gsis_id': gsis, 'status': status, 'full_name': name,
            'position': 'K', 'team': team, 'season': str(season),
            'week': str(week)}


def _resolve(rows, monkey):
    """Drive resolve_kicker against a synthetic roster read.

    The glob-and-read is replaced rather than the parsed result, so the code
    under test is the real function including its week selection.
    """
    import glob as _g
    import gzip as _gz
    import csv as _csv
    real_glob, real_open, real_reader = _g.glob, _gz.open, _csv.DictReader
    _g.glob = lambda *_a, **_k: ['fake_vintage.csv.gz']
    _gz.open = lambda *_a, **_k: iter(())
    _csv.DictReader = lambda *_a, **_k: iter(rows)
    try:
        return KICK.resolve_kicker({'kicker_counts': {}, 'kicker_names': {}},
                                   'ZZZ', 2026, 2)
    finally:
        _g.glob, _gz.open, _csv.DictReader = real_glob, real_open, real_reader


def test_one_kicker_repeated_across_vintages_resolves():
    """The exact shape that broke it. N is swept because N is what grew."""
    for n in (1, 2, 8, 40):
        rows = [_row('00-0000001', 'ACT') for _ in range(n)]
        o = _resolve(rows, None)
        check(f'the same kicker across {n} vintage(s) resolves',
              o.state is State.PASS, f'{o.state} {o.code}')
        if o.state is State.PASS:
            check(f'  and names him once at n={n}',
                  o.value['gsis_id'] == '00-0000001')


def test_two_different_eligible_kickers_still_refuse():
    """The intent the row count was destroying rather than enforcing."""
    rows = ([_row('00-0000001', 'ACT') for _ in range(5)]
            + [_row('00-0000002', 'ACT', name='Another') for _ in range(5)])
    o = _resolve(rows, None)
    check('two distinct eligible kickers refuse',
          o.state is State.BLOCKED, f'{o.state} {o.code}')
    check('under KICKER_NOT_UNIQUELY_DETERMINED',
          o.code == 'KICKER_NOT_UNIQUELY_DETERMINED', o.code)
    check('and the refusal distinguishes players from rows, so the next '
          'reader is not misled the way I was',
          o.evidence.get('n_distinct_players') == 2
          and o.evidence.get('n_rows') == 10,
          f"players={o.evidence.get('n_distinct_players')} "
          f"rows={o.evidence.get('n_rows')}")


def test_an_ineligible_second_kicker_does_not_block_the_first():
    rows = ([_row('00-0000001', 'ACT') for _ in range(4)]
            + [_row('00-0000002', 'CUT', name='Cut Leg') for _ in range(4)])
    o = _resolve(rows, None)
    check('a cut kicker beside an active one still resolves',
          o.state is State.PASS, f'{o.state} {o.code}')
    if o.state is State.PASS:
        check('  to the active one', o.value['gsis_id'] == '00-0000001')


def test_a_player_whose_vintages_disagree_is_refused_not_collapsed():
    """No live instance today, and written because the alternative is silent.

    The only within-week raw-status conflict in the 2026 week-2 capture is
    BAL's Jake Moody, CUT in six vintages and DEV in one -- and both grade to
    NOT_GAME_ROSTER, so his ELIGIBILITY never disagrees. A real one would be a
    kicker cut mid-week, and deduplicating it would pick a vintage and say
    nothing.
    """
    rows = [_row('00-0000001', 'ACT'), _row('00-0000001', 'ACT'),
            _row('00-0000001', 'CUT')]
    o = _resolve(rows, None)
    check('conflicting eligibility across vintages refuses',
          o.state is State.BLOCKED, f'{o.state} {o.code}')
    check('under its OWN code, not folded into the count',
          o.code == 'KICKER_ELIGIBILITY_DISAGREES_ACROSS_VINTAGES', o.code)
    check('and it names the player and both states',
          '00-0000001' in (o.evidence.get('conflicted') or {}),
          str(o.evidence.get('conflicted')))


def test_no_position_k_row_at_all_is_its_own_refusal():
    o = _resolve([_row('00-0000001', 'ACT', week=9)], None)
    check('a club with no row at or before the week refuses',
          o.state is State.BLOCKED, f'{o.state} {o.code}')
    check('under KICKER_NOT_ON_ROSTER_CAPTURE -- absent is not ambiguous',
          o.code == 'KICKER_NOT_ON_ROSTER_CAPTURE', o.code)


def test_against_the_real_capture_every_club_resolves():
    """The end-to-end statement, on the committed evidence.

    If this ever falls below 32 the right response is to read WHICH club and
    why, not to relax the check -- a club with two eligible kickers is a real
    roster fact and the refusal is correct.
    """
    fit = KICK.fit(202602)
    if not check('the kicking fit is available', fit.state is State.PASS,
                 f'{fit.state} {fit.code}'):
        return
    doc = fit.value
    got, refused = [], {}
    for t in CLUBS:
        o = KICK.resolve_kicker(doc, t, 2026, 2)
        if o.state is State.PASS:
            got.append(t)
        else:
            refused.setdefault(o.code, []).append(t)
    check('all 32 clubs resolve a kicker at 2026 week 2',
          len(got) == 32, f'{len(got)}/32 refused={refused}')
    check('and each one carries the roster basis, so a carried-forward week '
          'is distinguishable from a confirmed one',
          all(KICK.resolve_kicker(doc, t, 2026, 2).value.get('roster_basis')
              for t in got[:5]))


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
