"""A4/A5: official inactives are captured atomically and reach the projections.

The point of this module is the second half. A system that captures the
inactive list correctly and fails to propagate it into the numbers is worse
than one that never captured it, because it looks governed and is not.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production.nonqb import inactives as INA                    # noqa: E402
from nfl.production.nonqb import roster_status as RS                 # noqa: E402
from nfl.production.nonqb import layers as LY                        # noqa: E402

PASSED = FAILED = 0
KO = '2026-09-11T00:35:00Z'
T90 = '2026-09-10T23:05:00Z'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _roster():
    """A two-club roster with one WR, one RB and one TE per side."""
    r = {}
    for t, base in (('SF', 1), ('LA', 2)):
        for i, (pos, nm) in enumerate((('WR', 'Alpha Receiver'),
                                       ('RB', 'Bravo Runner'),
                                       ('TE', 'Charlie End'),
                                       ('WR', 'Delta Slot'),
                                       ('RB', 'Echo Back'))):
            r[f'00-00{base}000{i}'] = {'name': f'{nm} {t}', 'team': t,
                                       'position': pos}
    return r


# ============================================= A4 — atomic, provable capture
def test_bytes_are_stored_before_they_are_parsed():
    # INTO A TEMPORARY ROOT, NEVER THE LIVE VINTAGE. The first version of this
    # test wrote a synthetic inactives blob and four manifest rows into
    # nfl/vintage at 23:05Z, and the information-set selector then chose that
    # file as tonight's official list. That is the defect this whole module is
    # about, produced by the module's own test.
    root = pathlib.Path(tempfile.mkdtemp(prefix='inactives-test-'))
    raw = b'<html><body>SF INACTIVES Alpha Receiver SF</body></html>'
    o = INA.store(raw, retrieved_at=T90, source_url='https://example/inactives',
                  game_id='2026_01_SF_LA', http_status=200, root=root)
    if not check('a capture stores', o.state is State.PASS, o.code):
        return
    blob = root / o.value
    check('  the blob exists on disk', blob.exists(), str(blob))
    import gzip
    check('  and round-trips to the exact bytes',
          gzip.open(blob, 'rb').read() == raw)
    check('  the recorded hash is of those bytes',
          o.evidence['sha256'] == hashlib.sha256(raw).hexdigest())
    check('  the retrieval clock is recorded',
          o.evidence['retrieved_at'] == T90, o.evidence['retrieved_at'])
    check('  and publication and retrieval are separate fields',
          'published_at' in o.evidence)
    again = INA.store(raw, retrieved_at='2026-09-10T23:20:00Z',
                      source_url='https://example/inactives',
                      game_id='2026_01_SF_LA', root=root)
    check('  a re-capture of identical bytes is a MEASUREMENT, not a new blob',
          again.state is State.PASS and
          again.evidence['content_unchanged'] is True)
    rows = [json.loads(x) for x in
            open(root / 'nfl' / 'vintage_manifest.jsonl') if x.strip()]
    ours = [r for r in rows if r['source'] == INA.SOURCE
            and (r.get('value') or {}).get('sha256') == o.evidence['sha256']]
    check('  and both captures are appended to the manifest',
          len(ours) >= 2, str(len(ours)))


def test_empty_bytes_are_an_error_not_an_empty_inactive_list():
    o = INA.store(b'', retrieved_at=T90, source_url='u', game_id='g',
                  root=tempfile.mkdtemp(prefix='inactives-test-'))
    check('an empty capture fails by name',
          o.state is State.FAIL and o.code == 'INACTIVES_EMPTY_BYTES', o.code)


def test_a_capture_with_no_clock_is_refused():
    o = INA.store(b'x', retrieved_at=None, source_url='u', game_id='g',
                  root=tempfile.mkdtemp(prefix='inactives-test-'))
    check('no retrieval clock is a named FAIL',
          o.state is State.FAIL and o.code == 'INACTIVES_NO_RETRIEVAL_CLOCK',
          o.code)


def test_one_sided_completeness_is_refused():
    """THE GUARD. Half a governed forecast may not be labelled complete."""
    o = INA.sets({'SF': ['00-0010000'], 'LA': []}, _roster(), ['SF', 'LA'],
                 retrieved_at=T90, kickoff_utc=KO, game_id='2026_01_SF_LA')
    check('one club missing refuses the complete label',
          o.state is State.DEFERRED and o.code == INA.INCOMPLETE,
          f'{o.state}[{o.code}]')
    check('  and names which club', o.evidence['teams_without_a_list'] == ['LA'],
          str(o.evidence['teams_without_a_list']))
    both = INA.sets({'SF': ['00-0010000'], 'LA': ['00-0020000']}, _roster(),
                    ['SF', 'LA'], retrieved_at=T90, kickoff_utc=KO,
                    game_id='2026_01_SF_LA')
    check('  while both clubs present is COMPLETE',
          both.state is State.PASS and both.code == INA.COMPLETE, both.code)


def test_a_post_kickoff_list_is_refused():
    o = INA.sets({'SF': ['00-0010000'], 'LA': ['00-0020000']}, _roster(),
                 ['SF', 'LA'], retrieved_at='2026-09-11T00:40:00Z',
                 kickoff_utc=KO, game_id='2026_01_SF_LA')
    check('a list retrieved after kickoff is a named FAIL',
          o.state is State.FAIL and o.code == 'INACTIVES_POST_KICKOFF', o.code)


def test_an_ambiguous_name_is_refused_not_guessed():
    roster = {'00-0000001': {'name': 'Chris Smith', 'team': 'SF'},
              '00-0000002': {'name': 'Chris Smith', 'team': 'SF'}}
    o = INA.resolve({'SF': ['Chris Smith']}, roster)
    check('two players with one name is a named FAIL',
          o.state is State.FAIL and
          o.code == 'INACTIVES_IDENTITY_AMBIGUOUS', o.code)


def test_a_name_with_no_match_is_reported_not_dropped_silently():
    o = INA.resolve({'SF': ['Alpha Receiver SF', 'Nobody Here']}, _roster())
    check('the resolvable name resolves',
          o.state is State.PASS and len(o.value['SF']) == 1, str(o.value))
    check('  and the unmatched one is named',
          o.evidence['n_unmapped'] == 1 and
          'SF:Nobody Here' in o.evidence['unmapped'], str(o.evidence))


def test_a_missing_team_block_defers():
    o = INA.parse('<html>SF only</html>', ['SF', 'LA'])
    check('a document naming one club defers',
          o.state is State.DEFERRED and
          o.code == 'INACTIVES_TEAM_NOT_REPRESENTED', o.code)


# ======================================= A5 — the list reaches the numbers
def _draws(roster, m=200, p=1.0):
    return {pid: np.ones(m, dtype=np.int64) for pid in roster}


def test_an_inactive_players_appearance_becomes_zero():
    roster = _roster()
    d = _draws(roster)
    wr = '00-0010000'          # SF WR1
    o = INA.apply_to_appearance(d, [wr])
    if not check('the application runs', o.state is State.PASS, o.code):
        return
    check('  the inactive WR appears in NO draw',
          int(np.asarray(o.value[wr]).sum()) == 0,
          str(np.asarray(o.value[wr]).sum()))
    check('  and he is named as zeroed', o.evidence['zeroed'] == [wr])
    others = [p for p in roster if p != wr]
    check('  every other player is bit-identical',
          all(np.array_equal(np.asarray(o.value[p]), np.asarray(d[p]))
              for p in others))
    check('  and the other club is untouched',
          all(int(np.asarray(o.value[p]).sum()) == 200
              for p in others if p.startswith('00-002')))


def test_an_inactive_rb_and_te_behave_the_same_way():
    roster = _roster()
    for pid, what in (('00-0010001', 'RB'), ('00-0010002', 'TE')):
        o = INA.apply_to_appearance(_draws(roster), [pid])
        check(f'  an inactive {what} appears in no draw',
              int(np.asarray(o.value[pid]).sum()) == 0)


def test_an_empty_list_is_not_a_successful_application():
    o = INA.apply_to_appearance(_draws(_roster()), [])
    check('no inactive supplied is NOT_APPLICABLE, not PASS',
          o.state is State.NOT_APPLICABLE and
          o.code == 'INACTIVES_NONE_SUPPLIED', f'{o.state}[{o.code}]')


def test_an_inactive_who_is_not_in_the_draw_set_is_counted():
    o = INA.apply_to_appearance(_draws(_roster()), ['00-0099999'])
    check('a player absent from the draw set is named, not ignored',
          o.evidence['n_inactive_not_in_the_draw_set'] == 1,
          str(o.evidence['n_inactive_not_in_the_draw_set']))


def test_zero_appearance_forces_zero_share_in_the_accounting():
    """The tie that makes propagation real, checked against the enforcer."""
    from nfl.production.nonqb import accounting as ACC
    m, n = 8, 3
    A = np.ones((n, m))
    A[1] = 0.0                                    # player 1 is inactive
    share = np.full((n, m), 1.0 / n)
    share[1] = 0.0
    share[0] = share[2] = 0.5
    other = np.zeros((1, m))
    tv = np.full((1, m), 30.0)
    opp = share * tv[0][None, :]
    starts, counts = np.array([0]), np.array([n])
    o = ACC.reconcile_nonqb(share, other, tv, opp, A, starts, counts)
    check('a coherent zero-share/zero-appearance set reconciles',
          o.state is State.PASS, f'{o.state}[{o.code}] {o.detail[:120]}')
    # THE GUARD: give the inactive player share anyway and it must FAIL.
    bad = share.copy()
    bad[1] = 0.2
    bad[0] = bad[2] = 0.4
    o2 = ACC.reconcile_nonqb(bad, other, tv, bad * tv[0][None, :], A,
                             starts, counts)
    check('  and an inactive player holding share is REFUSED',
          o2.state is not State.PASS, f'{o2.state}[{o2.code}]')


def test_the_layer_seam_carries_inactive_ids():
    import inspect
    for fn, name in ((LY.appearance, 'layers.appearance'),
                     (LY._run_real, 'layers._run_real')):
        check(f'{name} accepts inactive_ids',
              'inactive_ids' in inspect.signature(fn).parameters)
    from nfl.production.nonqb import football_engine as FE
    check('football_engine.run_game accepts inactive_ids',
          'inactive_ids' in inspect.signature(FE.run_game).parameters)
    import nfl.production.run_forecast as RF
    check('  and run_forecast supplies them from the fixture',
          "inactive_ids=fx.get('official_inactive_ids')" in
          inspect.getsource(RF.build))


# ===================================== A2 — the quarantined status is guarded
def test_a_posthoc_roster_status_is_refused():
    check('INA is declared post-hoc', 'INA' in RS.POSTHOC)
    check('  and is NOT in the excluded-codes table', 'INA' not in RS.EXCLUDED)
    o = RS.active_pool([{'gsis_id': 'a'}, {'gsis_id': 'b'}],
                       {'a': 'ACT', 'b': 'INA'})
    check('  an unrecognised code is KEPT and named, never dropped silently',
          o.state is State.PASS and o.evidence['n_kept'] == 2 and
          o.evidence['kept_unrecognised_status'] == {'INA': 1},
          str(o.evidence))
    check('  and only declared codes are ever dropped',
          o.evidence['only_declared_codes_are_dropped'] ==
          sorted(RS.EXCLUDED), str(o.evidence))


def test_tonights_roster_capture_is_free_of_posthoc_contamination():
    o = RS.status_map(2026, 1, ['SF', 'LA'],
                      observed_before='2026-09-11T00:35:00Z')
    if o.state is not State.PASS:
        print(f'  ..   roster status unavailable ({o.code}); skipped')
        return
    counts = o.evidence['status_counts']
    check('SF and LA carry no post-hoc status before kickoff',
          not (set(counts) & set(RS.POSTHOC)), str(counts))
    check('  ACT is the active ROSTER, not the game-day list',
          counts.get('ACT', 0) > 60,
          f"{counts.get('ACT')} ACT players across two clubs, of whom about "
          f"46 will dress")


def test_that_leak_guard_actually_catches_a_leak():
    """A guard is not demonstrated by compliant data passing it.

    The narrowed guard must still reject the thing it exists to reject, so a
    rehearsal row is seeded into an in-memory copy of the live manifest and
    the detector is required to name it. Without this, narrowing the guard
    could have quietly turned it off.
    """
    man = pathlib.Path(_ROOT) / 'nfl' / 'vintage_manifest.jsonl'
    lines = man.read_text().splitlines()

    def detect(rows):
        bad = []
        for line in rows:
            if not line.strip():
                continue
            r = json.loads(line)
            v = r.get('value') or {}
            if (r.get('source') == INA.SOURCE
                    and v.get('spec_version') == INA.SPEC_VERSION
                    and v.get('isolated_root')):
                bad.append(r['capture_id'])
        return bad

    check('the real manifest is clean under the detector', not detect(lines))
    seeded = json.dumps({
        'capture_id': 'SEEDED_LEAK', 'source': INA.SOURCE, 'state': 'PASS',
        'value': {'spec_version': INA.SPEC_VERSION,
                  'isolated_root': '/tmp/rehearsal'}})
    check('and a seeded rehearsal row IS caught',
          detect(lines + [seeded]) == ['SEEDED_LEAK'])
    real = json.dumps({
        'capture_id': 'REAL_LIVE', 'source': INA.SOURCE, 'state': 'PASS',
        'value': {'spec_version': INA.SPEC_VERSION, 'isolated_root': None,
                  'game_id': '2026_01_SF_LA'}})
    check('while a genuine live capture is NOT',
          detect(lines + [real]) == [])


def test_the_live_vintage_was_not_touched_by_this_module():
    """THE GUARD ON THE GUARD. If a test ever writes a synthetic inactives
    capture into the live vintage again, this fails."""
    man = pathlib.Path(_ROOT) / 'nfl' / 'vintage_manifest.jsonl'
    bad = []
    for line in man.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        v = r.get('value') or {}
        # WHAT THIS GUARD IS FOR, AND WHAT IT IS NOT FOR.
        #
        # It was written when the official source was unreachable, so the ONLY
        # way an inactives capture could appear in the live manifest was a
        # test writing a synthetic one -- and one did. Flagging every
        # inactives row was therefore a sound proxy for "a rehearsal leaked".
        #
        # It stopped being sound the moment a REAL list was ingested. On
        # 2026-09-11 the genuine delivery wrote two live rows and this guard
        # called them contamination, while they were in fact the only
        # game-attributed captures in the whole manifest. A guard that fires
        # on success is not protecting anything.
        #
        # The leak itself is what to test for: a capture written under a
        # caller-supplied root is a rehearsal and must never appear here.
        if (r.get('source') == INA.SOURCE
                and v.get('spec_version') == INA.SPEC_VERSION
                and v.get('isolated_root')):
            bad.append(r['capture_id'])
    check('no synthetic inactives capture is in the live manifest',
          not bad, str(bad[:5]))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
