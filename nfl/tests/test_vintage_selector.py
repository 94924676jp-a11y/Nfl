"""WS-C: the chronology gate and the feed must be ONE selector with ONE clock.

WHAT THIS FILE IS GUARDING, IN ONE SENTENCE. `readiness.team_readiness` cut its
observations at `min(written_at, kickoff)` while `readiness.latest_injuries_rows`
-- the rows `layers.py:145` actually hands the appearance mechanism -- applied
no bound at all, so the gate and the feed answered the same question from two
different information sets and the unbounded one reached the model.

Every check below fails if that can happen again. Several of them build their
own manifest and their own blobs in a temp directory rather than asserting
against the live capture tree, because a check that depends on today's captures
stops being a check the day the captures move.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import pathlib
import random
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                 # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                # noqa: E402
from nfl.production.nonqb import readiness as RD                    # noqa: E402
from nfl.production.nonqb import roster_status as RS                # noqa: E402
from nfl.production.nonqb import vintage_selector as VS             # noqa: E402
from nfl.product import board as PB                                 # noqa: E402

PASSED = FAILED = 0

# The NE@SEA game WS12 measured L1 on. Kept as the anchor because the
# pre-kickoff and post-kickoff captures around it are both real.
KICKOFF = '2026-09-10T00:20:00Z'
PRE_CUT = '2026-09-08T18:00:00Z'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# ------------------------------------------------------------------ fixture
def _write_blob(d: pathlib.Path, name: str, rows, header) -> pathlib.Path:
    p = d / name
    with gzip.open(p, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def _manifest_line(source, blob, retrieved_at, sha, capture_id='20260101T000000Z',
                   valid_from=None):
    return json.dumps({
        'capture_id': capture_id, 'source': source, 'state': 'PASS',
        'value': {'blob': str(blob), 'sha256': sha,
                  'provenance': {'retrieved_at': retrieved_at},
                  'effective_scope': {'valid_from': valid_from,
                                      'authority': 'DERIVED_DETERMINISTIC'},
                  'n_data_rows': 1}})


_INJ_HDR = ['season', 'week', 'team', 'gsis_id', 'report_status',
            'practice_status']


def _fixture(tmp: pathlib.Path):
    """Three injuries captures: two pregame, one AFTER kickoff."""
    early = _write_blob(tmp, 'injuries.aaaa.csv.gz', [
        {'season': '2026', 'week': '1', 'team': 'NE', 'gsis_id': 'P1',
         'report_status': '', 'practice_status': 'Limited'}], _INJ_HDR)
    late_pregame = _write_blob(tmp, 'injuries.bbbb.csv.gz', [
        {'season': '2026', 'week': '1', 'team': 'NE', 'gsis_id': 'P1',
         'report_status': 'Questionable', 'practice_status': 'Limited'}],
        _INJ_HDR)
    postgame = _write_blob(tmp, 'injuries.cccc.csv.gz', [
        {'season': '2026', 'week': '1', 'team': 'NE', 'gsis_id': 'P1',
         'report_status': 'Out', 'practice_status': 'DNP'}], _INJ_HDR)
    lines = [
        _manifest_line('injuries', early, '2026-09-07T12:00:00+00:00', 'a' * 64),
        _manifest_line('injuries', late_pregame,
                       '2026-09-09T12:00:00+00:00', 'b' * 64),
        _manifest_line('injuries', postgame,
                       '2026-09-10T06:00:00+00:00', 'c' * 64),
    ]
    return lines, {'early': early, 'late_pregame': late_pregame,
                   'postgame': postgame}


# ============================================================ the six required
def test_a_capture_retrieved_after_kickoff_is_not_selectable():
    """The whole defect in one line. A post-kickoff capture must be
    UNREACHABLE, not merely undesirable."""
    with tempfile.TemporaryDirectory() as td:
        lines, blobs = _fixture(pathlib.Path(td))
        cut = VS.as_of_cut(KICKOFF, None)
        lawful, rejected = VS.candidates('injuries', as_of=cut,
                                         manifest_lines=lines)
        check('the post-kickoff capture is not among the lawful ones',
              all(pathlib.Path(v.blob) != blobs['postgame'] for v in lawful),
              str([v.blob for v in lawful]))
        late = [r for r in rejected
                if pathlib.Path(r.blob) == blobs['postgame']]
        check('  and it is REJECTED BY NAME rather than just absent',
              len(late) == 1 and late[0].chronology == VS.REJECT_LATE,
              str([(r.blob, r.chronology) for r in rejected]))
        check('  with a reason that says which clock refused it',
              bool(late) and 'after the cut' in (late[0].fallback_reason or ''),
              str(late[0].fallback_reason if late else None))
        check('  every rejection verdict comes from the closed vocabulary',
              all(r.chronology in VS.CHRONOLOGY for r in rejected + lawful),
              str({r.chronology for r in rejected}))


def test_with_two_lawful_pregame_captures_the_latest_lawful_one_wins():
    with tempfile.TemporaryDirectory() as td:
        lines, blobs = _fixture(pathlib.Path(td))
        cut = VS.as_of_cut(KICKOFF, None)
        o = VS.select('injuries', as_of=cut, manifest_lines=lines)
        check('two pregame captures are lawful and one is chosen',
              o.state is State.PASS and o.evidence['n_lawful'] == 2, o.code)
        check('  and it is the LATER of the two',
              o.state is State.PASS
              and pathlib.Path(o.value.blob) == blobs['late_pregame'],
              str(o.value.blob if o.state is State.PASS else o.code))
        check('  the selection carries source identity',
              o.value.source == 'injuries' and bool(o.value.blob)
              and bool(o.value.capture_id))
        check('  retrieved_at', o.value.retrieved_at ==
              '2026-09-09T12:00:00+00:00', str(o.value.retrieved_at))
        check('  a content hash', o.value.content_sha256 == 'b' * 64)
        check('  a chronology verdict', o.value.chronology == VS.LAWFUL)
        check('  and an evidence ceiling it does not pretend to close',
              'not recorded' in (o.value.evidence_ceiling or ''),
              str(o.value.evidence_ceiling)[:80])


def test_no_lawful_capture_is_a_named_refusal_and_never_a_silent_empty():
    with tempfile.TemporaryDirectory() as td:
        lines, _ = _fixture(pathlib.Path(td))
        cut = VS.as_of_cut(None, '2026-09-01T00:00:00Z')
        o = VS.select('injuries', as_of=cut, manifest_lines=lines)
        check('a cut before every capture BLOCKS by name',
              o.state is State.BLOCKED
              and o.code == 'VINTAGE_NO_LAWFUL_CAPTURE', o.code)
        check('  and counts what it refused rather than reporting nothing',
              o.evidence.get('n_rejected') == 3,
              str(o.evidence.get('n_rejected')))
        check('  and carries the evidence ceiling with the refusal',
              bool(o.evidence.get('evidence_ceiling')))
    # And on the live tree, through the production feed.
    try:
        RD.latest_injuries_rows(2026, as_of='2020-01-01T00:00:00Z')
        check('the production feed refuses when nothing is lawful', False,
              'it returned rows')
    except VS.NoLawfulVintage as e:
        check('the production feed refuses when nothing is lawful',
              'VINTAGE_NO_LAWFUL_CAPTURE' in str(e), str(e)[:120])
    except VS.VintageClockUnresolved as e:                    # pragma: no cover
        check('the production feed refuses when nothing is lawful', False,
              f'wrong refusal: {e}')


def test_the_gate_and_the_feed_resolve_to_the_same_vintage():
    """L1 AND L2 IN ONE CHECK. The gate is `team_report_history`; the feed is
    what `layers.py:145` eats. Per team, they must name the same blob."""
    for ko, wa in ((KICKOFF, None),
                   ('2026-09-13T17:00:00Z', None),
                   ('2026-09-13T17:00:00Z', '2026-09-12T12:00:00Z'),
                   ('2026-09-11T00:35:00Z', None)):
        cut = VS.as_of_cut(ko, wa)
        RD.cache_clear()
        seen, _newest = RD.team_report_history(2026, 1, as_of=cut)
        feed = RD.lawful_injuries_rows(2026, as_of=cut)
        if feed.state is not State.PASS:
            check(f'gate/feed at {cut.isoformat()}: feed refused',
                  not seen, f'{feed.code} while the gate found {len(seen)}')
            continue
        prov = feed.evidence['block_provenance']
        bad = [(t, d['blob'], (prov.get(f'{t}:1') or {}).get('blob'))
               for t, d in seen.items()
               if (prov.get(f'{t}:1') or {}).get('blob') != d['blob']]
        check(f'gate and feed name the same blob for all {len(seen)} team(s) '
              f'at {cut.isoformat()}', not bad, str(bad[:3]))


def test_changing_filesystem_ordering_cannot_change_the_selection():
    """`board.depth_rank` resolved by glob order and `coverage.load_week_plan`
    by st_mtime. Neither is a clock, and both make the answer depend on the
    checkout."""
    with tempfile.TemporaryDirectory() as td:
        lines, blobs = _fixture(pathlib.Path(td))
        cut = VS.as_of_cut(KICKOFF, None)
        base = VS.select('injuries', as_of=cut, manifest_lines=lines)
        rnd = random.Random(20260914)
        same = True
        for _ in range(25):
            shuffled = list(lines)
            rnd.shuffle(shuffled)
            got = VS.select('injuries', as_of=cut, manifest_lines=shuffled)
            if got.value.blob != base.value.blob:
                same = False
        check('25 permutations of the manifest read order give one answer',
              same, 'the selection moved with the read order')
        # mtime is not consulted, and the proof is that moving it does nothing.
        far = dt.datetime(2030, 1, 1).timestamp()
        os.utime(blobs['early'], (far, far))
        after = VS.select('injuries', as_of=cut, manifest_lines=lines)
        check('  and touching a blob to the newest mtime on disk moves '
              'nothing', after.value.blob == base.value.blob,
              f'{after.value.blob} != {base.value.blob}')
        check('  the selector says out loud what it refuses to order by',
              set(base.evidence['forbidden_inputs']) >= {
                  'filesystem mtime', 'glob order', 'file size'},
              str(base.evidence['forbidden_inputs']))


def test_replay_at_a_historical_written_at_picks_the_historical_vintage():
    """A rerun of an old forecast must read the old bytes. This is the whole
    point of a written_at: without it a replay silently consumes whatever has
    landed since."""
    cut = VS.as_of_cut(KICKOFF, PRE_CUT)
    o = VS.select('injuries', as_of=cut)
    if o.state is not State.PASS:
        check('a lawful injuries vintage exists at the replay cut', False,
              o.code)
        return
    check('the replay vintage predates the replay cut',
          VS.parse_ts(o.value.retrieved_at) <= cut,
          f'{o.value.retrieved_at} vs {cut.isoformat()}')
    newest = VS.select('injuries', as_of=RD._UNBOUNDED)
    check('  and it is NOT the newest capture on disk, so the cut is doing '
          'the work', o.value.blob != newest.value.blob,
          f'{o.value.blob} == {newest.value.blob}')
    again = VS.select('injuries', as_of=cut)
    check('  the same cut gives the same answer twice',
          again.value.blob == o.value.blob
          and again.value.content_sha256 == o.value.content_sha256)
    RD.cache_clear()
    feed = RD.lawful_injuries_rows(2026, as_of=cut)
    check('  and the feed at that cut carries only pre-cut blocks',
          feed.state is State.PASS
          and all(VS.parse_ts(v['retrieved_at']) <= cut
                  for v in feed.evidence['block_provenance'].values()),
          feed.code)


# ================================================ no clock is not any clock
def test_every_selector_refuses_without_a_clock():
    RD.gate_cuts_clear()
    for label, fn in (
            ('vintage_selector.select', lambda: VS.select('injuries')),
            ('vintage_selector.candidates', lambda: VS.candidates('injuries')),
            ('readiness.latest_injuries_rows',
             lambda: RD.latest_injuries_rows(2026)),
            ('readiness.lawful_injuries_rows',
             lambda: RD.lawful_injuries_rows(2026)),
            ('board.depth_rank', lambda: PB.depth_rank(2026, 1, ('DAL',))),
            ('board.roster_identity',
             lambda: PB.roster_identity(2026, 1, ('DAL',)))):
        try:
            fn()
            check(f'{label} refuses with no clock', False, 'it answered')
        except VS.VintageClockUnresolved:
            check(f'{label} refuses with no clock', True)
        except Exception as e:                                # noqa: BLE001
            check(f'{label} refuses with no clock', False,
                  f'{type(e).__name__}: {e}')
    check('an explicit as_of=None is refused too, because None never means '
          '"no bound"',
          _refuses(lambda: VS.select('injuries', as_of=None)))
    o = RS.status_map(2026, 1, ('SF', 'LA'))
    check('roster_status refuses with no clock, in its own vocabulary',
          o.state is not State.PASS and o.code == 'ROSTER_STATUS_NO_CLOCK',
          o.code)


def _refuses(fn):
    try:
        fn()
        return False
    except VS.VintageClockUnresolved:
        return True


def test_the_declared_clock_reaches_a_selector_it_cannot_be_passed_to():
    """THE layers.py CONSTRAINT, MADE EXECUTABLE.

    `nfl/production/nonqb/layers.py` is hashed by Q9's frozen candidate
    identity `481f005f682cd721` and calls `latest_injuries_rows(season)` with
    one argument. The clock therefore cannot be threaded through it, and is
    declared upstream instead -- the C1 pattern. If this stops working the
    feed goes back to being unbounded, which is L1.
    """
    cut_a = VS.as_of_cut('2026-09-13T17:00:00Z', '2026-09-12T12:00:00Z')
    with VS.clock(written_at='2026-09-12T12:00:00Z',
                  kickoff_utc='2026-09-13T17:00:00Z', origin='test'):
        rows = RD.latest_injuries_rows(2026)          # the layers.py arity
        inner = RD.lawful_injuries_rows(2026)
    check('a one-argument call inside a declared clock returns bounded rows',
          bool(rows) and inner.state is State.PASS
          and inner.evidence['as_of'] == cut_a.isoformat(),
          str(inner.evidence.get('as_of')))
    check('  every contributing block is within the declared cut',
          all(VS.parse_ts(v['retrieved_at']) <= cut_a
              for v in inner.evidence['block_provenance'].values()))
    check('  and the clock is gone again outside the block',
          VS.current_clock() is None and _refuses(
              lambda: RD.latest_injuries_rows(2026)))
    # Nesting must not leak either way.
    with VS.clock(written_at='2026-09-08T12:00:00Z', origin='outer'):
        outer = VS.current_clock().as_of
        with VS.clock(written_at='2026-09-11T12:00:00Z', origin='inner'):
            check('  a nested clock replaces the outer one for its extent',
                  VS.current_clock().as_of != outer)
        check('  and the outer one is restored on exit',
              VS.current_clock().as_of == outer)


def test_the_l2_gate_takes_written_at_from_the_declared_clock():
    """L2: `layers.py:117` passes kickoff and never written_at, so the gate
    resolved to `kickoff - 1us`. Measured at HEAD 837d52f: 85 player-rows
    differ across the 20 teams of the 10 executable week-1 games at a
    written_at of kickoff minus 24 hours."""
    RD.cache_clear()
    bare = RD.team_readiness(2026, 1, 'ATL', kickoff_utc='2026-09-13T17:00:00Z')
    RD.cache_clear()
    with VS.clock(written_at='2026-09-12T12:00:00Z',
                  kickoff_utc='2026-09-13T17:00:00Z', origin='test'):
        bound = RD.team_readiness(2026, 1, 'ATL',
                                  kickoff_utc='2026-09-13T17:00:00Z')
    check('bare, the gate cuts at kickoff',
          bare['as_of'].startswith('2026-09-13T16:59:59'), str(bare['as_of']))
    check('  under a declared clock it cuts at written_at instead',
          bound['as_of'] == '2026-09-12T12:00:00+00:00', str(bound['as_of']))
    check('  and the honest cut is allowed to refuse a game the leaking one '
          'passed', bare['state'].startswith('READY')
          and not bound['state'].startswith('READY'),
          f"{bare['state']} -> {bound['state']}")
    RD.cache_clear()


# ================================================== equivalence and refusal
def test_equivalence_where_the_old_selector_happened_to_be_right():
    """The replacement rule: prove the new selector picks the SAME bytes in the
    cases where the old one was lawful, so the diff isolates the cases where it
    was not. The old `latest_injuries_rows` took the newest capture on disk
    with no bound; the only regime in which that was lawful is a cut at or
    after that capture."""
    ts_old, old_rows = RD._latest_injuries(2026, as_of=None)
    new = RD.lawful_injuries_rows(2026, as_of=RD._UNBOUNDED)
    check('the unbounded enumerator still finds the newest capture on disk',
          bool(ts_old) and bool(old_rows), str(ts_old))
    if new.state is not State.PASS:
        check('the composed feed resolves at an open cut', False, new.code)
        return

    def key(r):
        return (r.get('season'), r.get('week'), r.get('team'), r.get('gsis_id'))

    a = {key(r): r for r in old_rows}
    b = {key(r): r for r in new.value}
    check('  at an open cut the composed feed is byte-identical to it',
          a == b, f'{len(a)} vs {len(b)} rows')
    check('  and it draws from exactly one blob there, so the composition '
          'adds nothing when nothing needs adding',
          len(new.evidence['contributing_blobs']) == 1,
          str(new.evidence['contributing_blobs']))


def test_the_feed_is_not_monotone_so_a_filter_would_not_have_been_enough():
    """The measured fact the composition exists for. If the captures ever
    become cumulative this check tells you, rather than the composition
    quietly becoming redundant."""
    counts = []
    for ts, path in sorted(RD._all_injury_captures(2026)):
        rows = RD._read_rows(path)
        wk = [r for r in rows if r.get('season') == '2026'
              and r.get('week') == '1']
        counts.append((ts, len({r['team'] for r in wk if r.get('team')})))
    shrinks = [i for i in range(1, len(counts))
               if counts[i][1] < counts[i - 1][1]]
    check('the injuries feed shrinks at least once, so "newest FILE" and '
          '"newest BLOCK per team" are different answers',
          bool(shrinks), str([(t[:19], n) for t, n in counts]))


def test_depth_rank_is_point_in_time_and_no_longer_glob_ordered():
    """L3. The old form globbed, iterated in filename order and did not break,
    so the answer came from the last blob in content-hash order."""
    teams = ('DAL', 'NYG')
    early = PB.depth_rank_outcome(2026, 1, teams, as_of='2026-09-07T12:00:00Z')
    late = PB.depth_rank_outcome(2026, 1, teams, as_of='2026-09-14T00:19:59Z')
    for label, o in (('early', early), ('late', late)):
        if o.state is not State.PASS:
            check(f'{label} depth selection resolves', False, o.code)
            return
    check('every chosen chart predates its own cut',
          all(VS.parse_ts(v['dt']) < VS.parse_ts('2026-09-07T12:00:00Z')
              for v in early.evidence['chosen'].values()),
          str(early.evidence['chosen']))
    check('  a later cut selects a later chart',
          all(VS.parse_ts(late.evidence['chosen'][t]['dt'])
              > VS.parse_ts(early.evidence['chosen'][t]['dt']) for t in teams),
          f"{early.evidence['chosen']} -> {late.evidence['chosen']}")
    check('  and the two cuts are genuinely different charts, so the clock is '
          'load-bearing',
          early.evidence['composite_sha256']
          != late.evidence['composite_sha256'])
    check('  the selection rule names what it will not order by',
          'Never glob order' in late.evidence['selection_rule'],
          late.evidence['selection_rule'])
    o = PB.depth_rank_outcome(2026, 1, teams, as_of='2026-08-01T00:00:00Z')
    check('  a cut before every chart is a named refusal, not an empty dict',
          o.state is not State.PASS
          and o.code in ('DEPTH_RANK_CAPTURE_ABSENT',
                         'DEPTH_RANK_NOT_POINT_IN_TIME'), o.code)


def test_depth_selection_survives_a_reordered_blob_set():
    """The R6 defect was resolution by filename order. A synthetic manifest in
    two orders must give one chart."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        hdr = ['dt', 'team', 'gsis_id', 'pos_abb', 'pos_rank', 'pos_slot']
        mk = lambda name, d, rank: _write_blob(tmp, name, [                # noqa: E731
            {'dt': d, 'team': 'DAL', 'gsis_id': 'P1', 'pos_abb': 'WR',
             'pos_rank': rank, 'pos_slot': '1'}], hdr)
        # Filename order is deliberately the REVERSE of dt order.
        a = mk('depth_charts.zzzz.reduced.csv.gz', '2026-09-06T11:00:00Z', 3)
        b = mk('depth_charts.aaaa.reduced.csv.gz', '2026-09-09T11:00:00Z', 1)
        lines = [_manifest_line('depth_charts', a,
                                '2026-09-06T12:00:00+00:00', 'z' * 64),
                 _manifest_line('depth_charts', b,
                                '2026-09-09T12:00:00+00:00', 'a' * 64)]
        man = tmp / 'manifest.jsonl'
        real = VS.MANIFEST
        try:
            answers = set()
            for order in (lines, list(reversed(lines))):
                man.write_text('\n'.join(order) + '\n')
                VS.MANIFEST = man
                o = PB.depth_rank_outcome(2026, 1, ('DAL',),
                                          as_of='2026-09-10T00:00:00Z')
                answers.add((o.state.name, o.value.get('P1')
                             if o.state is State.PASS else None))
            check('two manifest orders give one depth answer',
                  len(answers) == 1, str(answers))
            check('  and it is the chart with the newest lawful vendor dt, '
                  'not the one whose filename sorts last',
                  answers == {('PASS', ('WR', 1))}, str(answers))
            man.write_text('\n'.join(lines) + '\n')
            VS.MANIFEST = man
            o = PB.depth_rank_outcome(2026, 1, ('DAL',),
                                      as_of='2026-09-07T00:00:00Z')
            check('  a cut between the two charts selects the earlier one',
                  o.state is State.PASS and o.value.get('P1') == ('WR', 3),
                  str(o.value if o.state is State.PASS else o.code))
        finally:
            VS.MANIFEST = real


def test_roster_status_keeps_the_reference_design_it_lent_everyone_else():
    """WS12 scored rosters PROVEN_CLEAN because they have a CONTENT check as
    well as a clock check. Routing selection through the shared selector must
    not have cost either of them."""
    o = RS.status_map(2026, 1, ('SF', 'LA'),
                      observed_before='2026-09-10T20:00:00Z',
                      kickoff_utc='2026-09-11T00:35:00Z')
    if o.state is State.PASS:
        check('the chosen roster vintage predates the cut',
              VS.parse_ts(o.evidence['observed_at'])
              <= VS.parse_ts('2026-09-10T20:00:00Z'),
              str(o.evidence['observed_at']))
        check('  and it reports which bytes it read',
              bool(o.evidence.get('content_sha256'))
              and bool(o.evidence.get('source')))
        check('  no POSTHOC status reached the pool',
              not (set(o.evidence['status_counts']) & set(RS.POSTHOC)),
              str(o.evidence['status_counts']))
    else:
        check('roster status refuses by name when it cannot answer',
              o.code.startswith('ROSTER_STATUS_'), o.code)
    early = RS.status_map(2026, 1, ('SF', 'LA'),
                          observed_before='2020-01-01T00:00:00Z')
    check('a cut before every capture refuses by name',
          early.state is not State.PASS
          and early.code in ('ROSTER_STATUS_NO_ELIGIBLE_VINTAGE',
                             'ROSTER_STATUS_UNAVAILABLE'), early.code)
    check('  and the refusal counts what it rejected rather than saying '
          'nothing was there',
          early.code != 'ROSTER_STATUS_NO_ELIGIBLE_VINTAGE'
          or early.evidence.get('n_rejected', 0) > 0,
          str(early.evidence.get('n_rejected')))


def test_a_clock_is_compared_as_an_instant_and_never_as_a_string():
    """E4. `2026-09-10T16:00:00+00:00` sorts '+' below 'Z', so a string
    comparison mis-orders same-second cutoffs supplied in offset form."""
    z = '2026-09-10T16:00:00Z'
    off = '2026-09-10T16:00:00+00:00'
    check('the two spellings parse to one instant',
          VS.parse_ts(z) == VS.parse_ts(off))
    check('  and they really do sort differently as strings, so this is not '
          'a hypothetical', (z > off) != (VS.parse_ts(z) > VS.parse_ts(off)))
    a = VS.select('injuries', as_of=z)
    b = VS.select('injuries', as_of=off)
    check('  both spellings select the same vintage',
          a.state is b.state and (a.state is not State.PASS
                                  or a.value.blob == b.value.blob),
          f'{a.code} / {b.code}')
    check('  and as_of_cut agrees on them',
          VS.as_of_cut(None, z) == VS.as_of_cut(None, off))


def test_every_selection_carries_the_seven_things_a_consumer_needs():
    o = VS.select('injuries', as_of=VS.as_of_cut(KICKOFF, None))
    if o.state is not State.PASS:
        check('a vintage record is available to inspect', False, o.code)
        return
    rec = o.value.record()
    for field in ('source', 'blob', 'retrieved_at', 'published_at',
                  'content_sha256', 'chronology', 'evidence_ceiling',
                  'fallback_reason', 'as_of', 'selection_rule'):
        check(f'the record carries {field}', field in rec)
    check('  publication time is recorded with its authority, never bare',
          bool(rec['published_at']) is False
          or bool(rec['published_authority']),
          str(rec['published_authority']))
    check('  and every declared family states its own ceiling',
          all(VS.describe(f)['ceiling'] for f in VS.FAMILIES),
          str(sorted(VS.FAMILIES)))
    check('  an undeclared family is a KeyError, not a default',
          _raises_keyerror(lambda: VS.candidates('weather', as_of=KICKOFF)))


def _raises_keyerror(fn):
    try:
        fn()
        return False
    except KeyError:
        return True


def test_the_schedule_family_is_declared_without_claiming_a_leak():
    """L4. WS12 scored schedules UNPROVABLE rather than leaking, and measuring
    is what would change that. The family is declared here so a clock-aware
    selector EXISTS for it; the verdict is not upgraded by declaring one."""
    o = VS.select('schedules', as_of=VS.as_of_cut('2026-09-13T17:00:00Z'))
    check('a clock-aware schedule selector exists and resolves',
          o.state is State.PASS, o.code)
    check('  and the declared ceiling still says UNPROVABLE, not clean',
          'UNPROVABLE' in VS.describe('schedules')['ceiling'],
          VS.describe('schedules')['ceiling'][:80])


# ============================================================ RL-10 / RL-11
def test_a_lawful_vintage_missing_a_declared_column_is_not_a_success():
    """WS-L, RL-10 and RL-11. Both are a read that returned nothing being used
    as a value, and neither is visible from the clock alone -- so the check
    belongs at selection, next to the chronology verdict."""
    cut = VS.as_of_cut('2026-09-14T00:19:59Z')
    d = VS.select('depth_charts', as_of=cut)
    if d.state is not State.PASS:
        check('a depth vintage resolves to check columns against', False,
              d.code)
        return
    ok = VS.column_check(d.value)
    check('the declared depth columns are all present in the bytes',
          ok.state is State.PASS, f'{ok.code} {ok.evidence.get("missing")}')
    bad = VS.column_check(d.value, ('dt', 'team', 'gsis_id', 'pos_abb',
                                    'pos_rank', 'pos_slot'))
    check('  and pos_slot is NOT, which is RL-10 reproduced here',
          bad.state is State.FAIL
          and bad.code == 'VINTAGE_DECLARED_COLUMN_ABSENT'
          and bad.evidence['missing'] == ['pos_slot'],
          f'{bad.code} {bad.evidence.get("missing")}')
    gated = VS.select('depth_charts', as_of=cut,
                      require_columns=('dt', 'pos_slot'))
    check('  select() refuses a lawful vintage that lacks a required column',
          gated.state is State.FAIL
          and gated.code == 'VINTAGE_DECLARED_COLUMN_ABSENT', gated.code)
    undeclared = VS.column_check(d.value, ())
    check('  and a family that declares nothing gets NOT_APPLICABLE, which is '
          'a gap in the declaration rather than a pass',
          undeclared.state is State.NOT_APPLICABLE, undeclared.code)


def test_rl10_pos_slot_refuses_where_it_would_decide_and_nowhere_else():
    """The column is absent from every persisted blob and the old code read it
    as `int(... or 0)`. Measured harm is zero -- and a silent 0 could not have
    told anyone that."""
    vendor_tie = ('dt,team,gsis_id,pos_abb,pos_rank\n'
                  '2026-09-01T00:00:00Z,DAL,P1,WR,1\n'
                  '2026-09-01T00:00:00Z,DAL,P2,WR,1\n')
    o = DV.daily(vendor_tie)
    check('two players at one vendor (pos_abb, pos_rank) with no pos_slot is '
          'a named FAIL',
          o.state is State.FAIL
          and o.code == 'DEPTH_DAILY_POS_SLOT_REQUIRED_AND_ABSENT', o.code)
    check('  and it names the remedy as a capture-layer change',
          'pos_slot' in (o.evidence.get('remedy') or ''),
          str(o.evidence.get('remedy')))
    with_slot = ('dt,team,gsis_id,pos_abb,pos_rank,pos_slot\n'
                 '2026-09-01T00:00:00Z,DAL,P1,WR,1,2\n'
                 '2026-09-01T00:00:00Z,DAL,P2,WR,1,1\n')
    g = DV.daily(with_slot)
    check('  the same tie WITH pos_slot resolves, so the refusal is about the '
          'missing column and not about ties',
          g.state is State.PASS and g.value['DAL'][0][1]['P2'][0] == 1,
          str(g.value if g.state is State.PASS else g.code))
    check('  a zero pos_slot is a real value and not read as absence',
          DV._slot_sort(0) == 0 and DV._slot_sort(DV.SLOT_ABSENT) == -1)


def test_rl10_changed_no_depth_rank_in_the_repository():
    """One repair, one effect. The refusal is new; the ordering is not.

    The equivalence is computed against the pre-repair algorithm reproduced
    inline, ON ONE CAPTURE AT A TIME. It is deliberately not a comparison
    across captures: WS-L measured upstream RESTATING `gsis_id` in historical
    snapshots -- 2,363 rows across 133 of 170 slices differ in that one column,
    in both directions -- so two captures of the same slice can disagree on the
    join key without either being wrong.
    """
    def pre_repair(text):
        def rows(t):
            for r in csv.DictReader(__import__('io').StringIO(t)):
                pos = (r.get('pos_abb') or '').upper()
                if pos not in DV.SKILL or not r.get('gsis_id'):
                    continue
                try:
                    rk = int(r['pos_rank'])
                except (TypeError, ValueError, KeyError):
                    continue
                yield (r['dt'], r['team'], r['gsis_id'],
                       DV._NORM.get(pos, pos), rk, int(r.get('pos_slot') or 0))
        snap = {}
        for d, team, pid, pos, rk, slot in rows(text):
            snap.setdefault((team, d), {})
            cur = snap[(team, d)].get(pid)
            if cur is None or (rk, slot) < (cur[0], cur[2]):
                snap[(team, d)][pid] = (rk, pos, slot)
        by = {}
        for (team, d), players in snap.items():
            ranked = DV._ordinal([((v[0], v[2], pid), pid)
                                  for pid, v in players.items()])
            by.setdefault(team, []).append(
                (d, {pid: (ranked[pid], players[pid][1]) for pid in players}))
        for t in by:
            by[t].sort(key=lambda x: x[0])
        return by

    blobs = sorted((pathlib.Path(_ROOT) / 'nfl' / 'vintage').glob(
        'depth_charts.*.reduced.csv.gz'))
    check('there are persisted depth blobs to compare on', bool(blobs))
    n_absent = 0
    for b in blobs:
        txt = gzip.open(b, 'rt').read()
        got = DV.daily(txt)
        check(f'{b.name} still parses after the repair',
              got.state is State.PASS, got.code)
        if got.state is not State.PASS:
            continue
        check('  and every rank is identical to the pre-repair algorithm',
              got.value == pre_repair(txt), b.name)
        n_absent += got.evidence['n_rows_without_pos_slot']
        check('  pos_slot absence is DECLARED rather than defaulted',
              got.evidence['pos_slot_available'] is False
              and got.evidence['n_rows_without_pos_slot']
              == got.evidence['n_rows'],
              str(got.evidence['n_rows_without_pos_slot']))
        check('  and no vendor-position tie ever needed it',
              got.evidence['n_vendor_rank_ties'] == 0)
    check(f'{n_absent} rows across {len(blobs)} blobs carried no pos_slot, '
          f'and every one of them used to read as slot 0', n_absent > 0)


def test_the_depth_selector_states_what_it_cannot_resolve():
    """171 of 177 `dt` slices are durable nowhere. A point-in-time selector
    over a series with holes must say so, not reach for the nearest chart."""
    o = DV.captured(('DAL', 'NYG'), '2026-08-01T00:00:00Z')
    check('a cut before every surviving slice DEFERS by name',
          o.state is State.DEFERRED
          and o.code == 'DEPTH_CAPTURE_NOT_POINT_IN_TIME', o.code)
    ceiling = (o.evidence.get('owed') or {}).get('evidence_ceiling') or ''
    check('  and carries the durability ceiling with the refusal',
          '171 of 177' in ceiling, ceiling[:80])
    good = DV.captured(('DAL', 'NYG'), '2026-09-14T00:19:59Z')
    check('  a resolvable cut carries the ceiling too, because a successful '
          'selection does not close it',
          good.state is State.PASS
          and '171 of 177' in (good.evidence.get('evidence_ceiling') or ''),
          good.code)
    check('  and the family declaration repeats it where a selector looks',
          '171 of 177' in VS.describe('depth_charts')['ceiling'])


# ==================================================== the gate->feed handoff
def test_the_gate_hands_its_own_cut_to_the_feed():
    """TRANSITIONAL, AND THE TESTS SAY SO. The permanent repair declares the
    cut upstream; until that call site is rewired the gate two lines above the
    feed already knows it, and handing it over is what keeps the production
    path running WITHOUT the feed going back to unbounded."""
    RD.gate_cuts_clear()
    RD.cache_clear()
    RD.team_readiness(2026, 1, 'SF', kickoff_utc='2026-09-11T00:35:00Z')
    o = RD.lawful_injuries_rows(2026)
    check('the feed inherits the cut the gate just used',
          o.state is State.PASS and o.evidence['clock_basis'] == 'GATE_HANDOFF'
          and o.evidence['as_of'] == '2026-09-11T00:34:59.999999+00:00',
          f"{o.code} {o.evidence.get('clock_basis')} {o.evidence.get('as_of')}")
    check('  and records that it did, so GATE_HANDOFF is visible in the '
          'artifact rather than looking like a wired call site',
          o.evidence['clock_handoff']['origins'] ==
          ['team_readiness:2026w1:SF'],
          str(o.evidence.get('clock_handoff')))
    check('  a SECOND read without a fresh gate refuses, so a cut cannot be '
          'reused across games',
          _refuses(lambda: RD.lawful_injuries_rows(2026)))
    # An explicit clock beats it, and clears it.
    RD.gate_cuts_clear()
    RD.team_readiness(2026, 1, 'SF', kickoff_utc='2026-09-11T00:35:00Z')
    with VS.clock(written_at='2026-09-08T18:00:00Z', origin='test'):
        o2 = RD.lawful_injuries_rows(2026)
    check('  a declared clock beats the handoff',
          o2.evidence['clock_basis'] == 'DECLARED_CONTEXT'
          and o2.evidence['as_of'] == '2026-09-08T18:00:00+00:00',
          f"{o2.evidence['clock_basis']} {o2.evidence['as_of']}")
    check('  and consumes the outstanding handoff rather than leaving it to '
          'be inherited later', _refuses(lambda: RD.lawful_injuries_rows(2026)))
    RD.gate_cuts_clear()


def test_a_slate_wide_gate_hands_over_the_earliest_kickoff_and_not_the_last():
    """Sixteen games publish sixteen cuts. The only one lawful for every game
    is the earliest kickoff's; taking the last evaluated would be
    post-kickoff for whichever game started first."""
    RD.gate_cuts_clear()
    RD.cache_clear()
    gr = RD.game_readiness(2026, 1)
    kicks = sorted(g['kickoff_utc'] for g in gr['games'])
    check('the slate answer names the cut it handed over',
          gr.get('slate_as_of') == VS.as_of_cut(kicks[0], None).isoformat(),
          f"{gr.get('slate_as_of')} vs earliest kickoff {kicks[0]}")
    o = RD.lawful_injuries_rows(2026)
    check('  and the feed takes exactly that, not the last game evaluated',
          o.state is State.PASS
          and o.evidence['as_of'] == gr['slate_as_of'],
          f"{o.evidence.get('as_of')} vs {gr.get('slate_as_of')}")
    check('  which is strictly earlier than the last kickoff on the slate',
          VS.parse_ts(o.evidence['as_of']) < VS.parse_ts(kicks[-1]),
          f"{o.evidence['as_of']} vs {kicks[-1]}")
    RD.gate_cuts_clear()
    RD.cache_clear()


def test_the_production_appearance_call_no_longer_eats_an_unbounded_feed():
    """The end-to-end statement of L1 and L2 through the real layer, at the
    arity `football_engine` uses today."""
    players = [{'gsis_id': '00-0036355', 'position': 'WR', 'team': 'SF'},
               {'gsis_id': '00-0037240', 'position': 'WR', 'team': 'LA'}]
    from nfl.production.nonqb import layers as LY
    RD.gate_cuts_clear()
    RD.cache_clear()
    ap = LY.appearance(2026, 1, players, teams=('SF', 'LA'),
                       kickoff_utc='2026-09-11T00:35:00Z',
                       observed_before='2026-09-10T20:00:00Z')
    check('the production appearance path still runs', ap.state is State.PASS,
          f'{ap.state.name}[{ap.code}]')
    RD.gate_cuts_clear()
    RD.cache_clear()
    RD.team_readiness(2026, 1, 'SF', kickoff_utc='2026-09-11T00:35:00Z')
    feed = RD.lawful_injuries_rows(2026)
    ko = VS.parse_ts('2026-09-11T00:35:00Z')
    check('  and every block it would eat predates that kickoff',
          all(VS.parse_ts(v['retrieved_at']) < ko
              for v in feed.evidence['block_provenance'].values()),
          str([v['retrieved_at']
               for v in feed.evidence['block_provenance'].values()
               if VS.parse_ts(v['retrieved_at']) >= ko][:3]))
    # THE PRE-REPAIR MEASUREMENT, KEPT LIVE. The unbounded enumerator still
    # exists for the operator dashboard, so the size of what the repair removed
    # can be re-derived rather than quoted.
    ts, _rows = RD._latest_injuries(2026, as_of=None)
    kicks = {}
    from nfl.capture import coverage as C
    plan = C.load_week_plan(2026, 1)
    if plan.state is State.PASS:
        for c in plan.value:
            for t in c.game_id.split('_')[2:4]:
                kicks[t] = c.kickoff_utc
        after = [t for t, k in kicks.items() if VS.parse_ts(ts) >= k]
        check(f'  the capture the OLD feed took is post-kickoff for '
              f'{len(after)} of {len(kicks)} teams, which is what was removed',
              len(after) > 0, f'{ts} against {len(kicks)} kickoffs')
    RD.gate_cuts_clear()
