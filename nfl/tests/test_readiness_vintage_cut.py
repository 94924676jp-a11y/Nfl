"""The consumed-clock contract: `retrieved_at <= written_at < kickoff`.

WHY THIS FILE EXISTS. `readiness.team_report_history` took each team's injury
block from the newest capture ON DISK and let the caller notice afterwards
that it was too late. For 2026_01_NE_SEA that meant a capture from
2026-09-10T13:37Z -- thirteen hours AFTER kickoff -- became the team's block,
readiness refused with INJURY_REPORT_CHRONOLOGY_FAILURE, and the entire non-QB
chain reported NOT_APPLICABLE for a game whose pre-kickoff report existed all
along in `injuries.1bf460ad261559a8.csv.gz`, retrieved 32.2 hours before
kickoff with 11 rows covering exactly NE and SEA.

The guard was right. The selector never looked. These checks pin the selector.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production.nonqb import readiness as RD                  # noqa: E402

PASSED = FAILED = 0

# The NE@SEA facts every check below is anchored on, each read from the
# vintage manifest rather than remembered.
KICKOFF = '2026-09-10T00:20:00Z'
PRE_CUT = '2026-09-08T17:10:00Z'      # after the last pre-kickoff capture
POST_CAPTURE_DAY = '2026-09-10T13:00:00Z'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _parse(t):
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def test_the_fixture_this_file_depends_on_actually_exists():
    """A post-kickoff capture must exist, or every check here is vacuous."""
    RD.cache_clear()
    allcaps = RD._all_injury_captures(2026)
    ko = _parse(KICKOFF)
    after = [ts for ts, _p in allcaps if _parse(ts) >= ko]
    before = [ts for ts, _p in allcaps if _parse(ts) < ko]
    check('the manifest holds captures AFTER the NE@SEA kickoff',
          bool(after), 'no post-kickoff capture: these checks cannot fail')
    check('  and captures BEFORE it', bool(before),
          'no pre-kickoff capture: there is nothing correct to select')


def test_a_valid_pre_kickoff_report_is_selected_over_a_later_one():
    RD.cache_clear()
    cut = RD.as_of_cut(KICKOFF, PRE_CUT)
    seen, _newest = RD.team_report_history(2026, 1, as_of=cut)
    for t in ('NE', 'SEA'):
        d = seen.get(t)
        if not check(f'{t} has a block under the pre-kickoff cut', bool(d)):
            continue
        got = _parse(d['newest_capture'])
        check(f'  {t} selected a capture at or before the cut',
              got <= cut, f'{d["newest_capture"]} > {cut.isoformat()}')
        check(f'  {t} selected one strictly before kickoff',
              got < _parse(KICKOFF), d['newest_capture'])
        check(f'  {t} selected a block with rows in it', d['n_rows'] > 0,
              str(d['n_rows']))


def test_a_post_kickoff_report_can_never_make_a_replay_READY():
    """The headline regression. The post-kickoff capture carries the filled
    report_status that would satisfy the input contract; the cut must keep it
    out, whatever the caller's clock is set to."""
    RD.cache_clear()
    now = {t: RD.team_readiness(2026, 1, t) for t in ('NE', 'SEA')}
    for t, d in now.items():
        check(f'{t}: judged against its own kickoff, is not READY off a '
              f'post-kickoff report',
              not d['state'].startswith('READY'),
              f"{d['state']} from {d.get('newest_capture')}")
        if d.get('newest_capture'):
            check(f'  {t}: and the block it did use predates kickoff',
                  _parse(d['newest_capture']) < _parse(KICKOFF),
                  str(d.get('newest_capture')))
    RD.cache_clear()
    replay = {t: RD.team_readiness(2026, 1, t, kickoff_utc=KICKOFF,
                                   written_at=PRE_CUT)
              for t in ('NE', 'SEA')}
    for t, d in replay.items():
        check(f'{t}: under the replay clock it is not READY either',
              not d['state'].startswith('READY'), d['state'])
    # AND THE GUARD MUST BE LOAD-BEARING: with no cut at all, the very same
    # data DOES read READY. If this stops being true the checks above pass for
    # a reason that has nothing to do with the cut.
    RD.cache_clear()
    seen_all, _ = RD.team_report_history(2026, 1, as_of=None)
    late = [t for t in ('NE', 'SEA')
            if seen_all.get(t)
            and _parse(seen_all[t]['newest_capture']) >= _parse(KICKOFF)]
    check('  without a cut the selector really would take a post-kickoff '
          'block, so the cut is doing the work',
          sorted(late) == ['NE', 'SEA'], str(late))


def test_written_at_binds_as_well_as_kickoff():
    """`retrieved_at <= written_at` is half the contract and is checked on its
    own: a forecast written on the 8th may not read the 10th's capture even
    though the 10th is still before a Sunday kickoff."""
    RD.cache_clear()
    cut = RD.as_of_cut('2026-09-14T00:00:00Z', PRE_CUT)
    check('the tighter of the two clocks wins',
          cut == _parse(PRE_CUT), cut.isoformat())
    seen, _n = RD.team_report_history(2026, 1, as_of=cut)
    for t, d in seen.items():
        if _parse(d['newest_capture']) > _parse(PRE_CUT):
            check(f'{t} respected the written_at bound', False,
                  d['newest_capture'])
            return
    check('every team block respects the written_at bound', True)


def test_no_eligible_vintage_defers_honestly():
    RD.cache_clear()
    d = RD.team_readiness(2026, 1, 'NE', written_at='2026-01-01T00:00:00Z')
    check('a clock before every capture reports ABSENCE',
          d['state'] == 'INJURY_REPORT_NOT_YET_FILED', d['state'])
    check('  with no rows claimed', d['n_rows'] == 0, str(d['n_rows']))
    check('  and it says which cut produced the absence',
          str(d.get('as_of', '')).startswith('2026-01-01'),
          str(d.get('as_of')))
    check('  and it never reads absence as "nobody is injured"',
          'ABSENCE OF A REPORT' in d['reason'], d['reason'][:80])


def test_the_cache_cannot_serve_one_clock_to_another():
    """A cache that restamps a hit under a different clock is not a cache."""
    RD.cache_clear()
    early, _a = RD.team_report_history(2026, 1,
                                       as_of=RD.as_of_cut(KICKOFF, PRE_CUT))
    late, _b = RD.team_report_history(
        2026, 1, as_of=RD.as_of_cut(None, POST_CAPTURE_DAY))
    ne_e = early.get('NE', {}).get('newest_capture')
    ne_l = late.get('NE', {}).get('newest_capture')
    check('two different cuts give two different answers', ne_e != ne_l,
          f'{ne_e} == {ne_l}')
    again, _c = RD.team_report_history(2026, 1,
                                       as_of=RD.as_of_cut(KICKOFF, PRE_CUT))
    check('  and re-asking the first cut still gives the first answer',
          again.get('NE', {}).get('newest_capture') == ne_e,
          f'{again.get("NE", {}).get("newest_capture")} != {ne_e}')


def test_selection_is_by_timestamp_and_not_by_size_or_order():
    """The rehearsal roster selector picks the biggest file and lands on a
    post-kickoff vintage. This selector must not be able to."""
    RD.cache_clear()
    cut = RD.as_of_cut(KICKOFF, PRE_CUT)
    eligible = RD._all_injury_captures(2026, as_of=cut)
    check('every returned capture is within the cut',
          all(_parse(ts) <= cut for ts, _p in eligible),
          str([ts for ts, _p in eligible if _parse(ts) > cut][:3]))
    check('  and they come back newest-first',
          [ts for ts, _p in eligible] == sorted(
              [ts for ts, _p in eligible], reverse=True))
    biggest = max((os.path.getsize(p), ts)
                  for ts, p in RD._all_injury_captures(2026)) \
        if RD._all_injury_captures(2026) else None
    if biggest and _parse(biggest[1]) > cut:
        check('  the largest capture on disk is outside the cut and was '
              'NOT selected',
              all(ts != biggest[1] for ts, _p in eligible), biggest[1])


def test_game_readiness_carries_the_consumed_clock():
    RD.cache_clear()
    g = RD.game_readiness(2026, 1, written_at=PRE_CUT)
    check('game_readiness records the clock it ran under',
          g.get('written_at') == PRE_CUT, str(g.get('written_at')))
    ne = [x for x in g['games'] if x['game_id'] == '2026_01_NE_SEA']
    check('  and NE@SEA is not executable off a post-kickoff report',
          bool(ne) and not ne[0]['may_execute_d2'],
          str(ne[0]['state']) if ne else 'game absent')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
