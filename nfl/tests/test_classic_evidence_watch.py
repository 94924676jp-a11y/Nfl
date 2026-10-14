#!/usr/bin/env python3.12
"""New evidence triggers the governed rebuild or an escalation, and the current file stops reading CURRENT (task #45 P0-6).

Built on the 2026-10-11 fixture. The scenario is the McLaurin one: the 16:17Z file was built on the 16:10Z packet; a newer
packet (here a synthetic 16:30Z packet saying "limited snaps") arrives. The contract requires a full rebuild; if one
cannot finish before lock the system must say so and the 16:17Z file must read STALE_FORECAST, not keep its label.

Also the pipeline's run lock: one build per slate, and a lock left by a dead process is recovered with the dead run's
ledger marked CRASHED_OR_KILLED.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import test_classic_release as TR  # noqa: E402  (fixture unpacker)
from nfl.tools import classic_evidence_watch as W  # noqa: E402
from nfl.tools import classic_slate_pipeline as PL  # noqa: E402

UTC = dt.timezone.utc
PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _setup(td: pathlib.Path, with_newer: bool):
    out = TR._unpack(['prod_1617Z'], td / 'out')
    pk = td / 'packets'
    pk.mkdir()
    shutil.copy(TR.PKT_1610, pk / TR.PKT_1610.name)
    if with_newer:
        d = json.loads(TR.PKT_1610.read_text())
        d['packet_id'] = '2026W5-synthetic-1630Z'
        d['received_at'] = '2026-10-11T16:30:00Z'
        d['source_detail'] = 'SYNTHETIC TEST PACKET: McLaurin limited snaps'
        (pk / 'ZZ_SYNTHETIC_1630Z.json').write_text(json.dumps(d))
    return out, pk


class _PreGate:
    """THE FIXTURE PREDATES THE ELIGIBILITY CONTRACT (OD-002, 2026-10-14). The 16:17Z W5 state carries no
    roster_eligibility record, so classic_release now BLOCKS it (ELIGIBILITY_NOT_APPLIED) -- asserted in test_00. This
    module tests the evidence WATCH (label transitions on newer packets), so its other checks treat the fixture as a
    pre-gate slate, exactly as 2026W2-W4 are, and say so here rather than silently."""

    def __enter__(self):
        from nfl.tools import classic_upload_verify as UV
        self.UV, self.real = UV, UV.LEGACY_PRE_ROSTER_GATE
        UV.LEGACY_PRE_ROSTER_GATE = frozenset(self.real | {'2026W5'})

    def __exit__(self, *a):
        self.UV.LEGACY_PRE_ROSTER_GATE = self.real


def test_00_the_fixture_is_blocked_by_the_eligibility_gate_and_nothing_else():
    print('\n00. OD-002: the pre-contract 16:17Z file is BLOCKED by ELIGIBILITY_NOT_APPLIED, and by nothing else')
    from nfl.tools import classic_release as R
    with tempfile.TemporaryDirectory() as d:
        out, _pk = _setup(pathlib.Path(d), with_newer=False)
        rel = R.evaluate('2026W5', latest_packet=TR.PKT_1610, out_dir=out,
                         now=dt.datetime(2026, 10, 11, 16, 20, tzinfo=UTC))
    b = rel['reasons']['blocking']
    check('release BLOCKED, the only blocker ELIGIBILITY_NOT_APPLIED',
          rel['release_state'] == 'BLOCKED' and len(b) == 1 and b[0].startswith('ELIGIBILITY_NOT_APPLIED'), b)


def test_01_no_new_evidence_keeps_the_label():
    with _PreGate():
        print('\n01. the packet the state consumed is the newest: no rebuild, the label stands')
        with tempfile.TemporaryDirectory() as d:
            out, pk = _setup(pathlib.Path(d), with_newer=False)
            o = W.run('2026W5', out_dir=out, pk_dir=pk, now=dt.datetime(2026, 10, 11, 16, 20, tzinfo=UTC))
            rec = json.loads((out / 'DK_2026W5_EARLY_EVIDENCE_WATCH.json').read_text())
        check('decision NO_NEW_EVIDENCE', rec['decision'] == 'NO_NEW_EVIDENCE', rec['decision'])
        check('the 16:17Z file stays CURRENT_BUT_UNCERTIFIED', rec['current_release']['release_state'] == 'CURRENT_BUT_UNCERTIFIED',
              rec['current_release'])
        check('no escalation', o.state.value == 'PASS' and 'escalation' not in rec, o.code)


def test_02_new_evidence_without_launch_escalates_and_marks_the_file_stale():
    with _PreGate():
        print('\n02. a newer packet and no launch: escalation, and the 16:17Z file reads STALE_FORECAST')
        with tempfile.TemporaryDirectory() as d:
            out, pk = _setup(pathlib.Path(d), with_newer=True)
            o = W.run('2026W5', out_dir=out, pk_dir=pk, now=dt.datetime(2026, 10, 11, 16, 31, tzinfo=UTC))
            rec = json.loads((out / 'DK_2026W5_EARLY_EVIDENCE_WATCH.json').read_text())
            rel = json.loads((out / 'DK_2026W5_EARLY_RELEASE.json').read_text())
        check('decision NEW_EVIDENCE, naming the newest packet', rec['decision'] == 'NEW_EVIDENCE'
              and rec['newest']['packet_id'] == '2026W5-synthetic-1630Z', rec.get('newest'))
        check('escalated NEW_EVIDENCE_REBUILD_NOT_LAUNCHED', o.state.value == 'BLOCKED'
              and rec['escalation']['code'] == 'NEW_EVIDENCE_REBUILD_NOT_LAUNCHED', rec.get('escalation'))
        check('the 16:17Z file is now STALE_FORECAST, and the release record beside it says so',
              rec['current_release']['release_state'] == 'STALE_FORECAST' and rel['release_state'] == 'STALE_FORECAST',
              (rec['current_release'], rel['release_state']))


def test_03_new_evidence_too_close_to_lock_is_refused_and_escalated():
    with _PreGate():
        print('\n03. a newer packet at 16:50Z with --launch: the pipeline refuses (cannot finish), the watch escalates')
        real = PL.OUT_DIR
        with tempfile.TemporaryDirectory() as d:
            out, pk = _setup(pathlib.Path(d), with_newer=True)
            try:
                PL.OUT_DIR = out
                o = W.run('2026W5', launch=True, out_dir=out, pk_dir=pk, now=dt.datetime(2026, 10, 11, 16, 50, tzinfo=UTC))
            finally:
                PL.OUT_DIR = real
            rec = json.loads((out / 'DK_2026W5_EARLY_EVIDENCE_WATCH.json').read_text())
            led = json.loads((out / 'DK_2026W5_EARLY_RUN_LEDGER.json').read_text())
        check('the pipeline was asked, and refused WOULD_NOT_FINISH_BEFORE_LOCK without running a stage',
              led['STATE'] == 'REFUSED_WOULD_NOT_FINISH_BEFORE_LOCK' and led['stages'] == [], led['STATE'])
        check('the watch escalates NEW_EVIDENCE_NOT_REBUILT', o.state.value == 'BLOCKED'
              and rec['escalation']['code'] == 'NEW_EVIDENCE_NOT_REBUILT', rec.get('escalation'))
        check('and the file the owner holds reads STALE_FORECAST', rec['current_release']['release_state'] == 'STALE_FORECAST')


def test_04_new_evidence_with_time_launches_the_full_pipeline_with_that_packet():
    print('\n04. a newer packet at 16:31Z with --launch: the governed pipeline is started with the newest packet')
    calls = []
    real_run = PL.run
    with tempfile.TemporaryDirectory() as d:
        out, pk = _setup(pathlib.Path(d), with_newer=True)
        try:
            PL.run = lambda *a, **k: calls.append((a, k)) or {'run_id': 'R', 'STATE': 'COMPLETE', 'FINAL': 'X'}
            o = W.run('2026W5', launch=True, out_dir=out, pk_dir=pk, now=dt.datetime(2026, 10, 11, 16, 31, tzinfo=UTC))
        finally:
            PL.run = real_run
    check('the pipeline is called exactly once', len(calls) == 1, len(calls))
    check('  with the newest packet, not the one the state consumed',
          calls and calls[0][1].get('packet', '').endswith('ZZ_SYNTHETIC_1630Z.json'), calls[:1])
    check('  for the whole slate (no exclusion, no tag): a rebuild, never a selection-only patch',
          calls and calls[0][0][0] == '2026W5' and 'exclude' not in calls[0][1] and 'tag' not in calls[0][1], calls[:1])
    check('a completed rebuild is not an escalation', o.state.value == 'PASS', o.code)


def test_05_one_build_per_slate_and_crash_recovery():
    print('\n05. the run lock: a live holder refuses a second build; a dead holder is recovered and marked crashed')
    real = PL.OUT_DIR
    with tempfile.TemporaryDirectory() as d:
        try:
            PL.OUT_DIR = pathlib.Path(d)
            ok1, _ = PL.acquire_run_lock('S', 'RUN-A')
            ok2, det2 = PL.acquire_run_lock('S', 'RUN-B')
            check('a second build while the first holder is alive is refused RUN_IN_PROGRESS',
                  ok1 and not ok2 and det2['code'] == 'RUN_IN_PROGRESS', det2)
            PL.release_run_lock('S', 'RUN-A')
            check('the holder releases its own lock', not (PL.OUT_DIR / 'DK_S_EARLY_RUN.lock').exists())
            dead = 2 ** 22 + 12345
            while PL._pid_alive(dead):
                dead += 1
            (PL.OUT_DIR / 'DK_S_EARLY_RUN.lock').write_text(json.dumps({'pid': dead, 'run_id': 'RUN-DEAD'}))
            (PL.OUT_DIR / 'DK_S_EARLY_RUN_LEDGER.json').write_text(json.dumps({'run_id': 'RUN-DEAD', 'STATE': 'RUNNING'}))
            ok3, det3 = PL.acquire_run_lock('S', 'RUN-C')
            led = json.loads((PL.OUT_DIR / 'DK_S_EARLY_RUN_LEDGER.json').read_text())
            check('a lock held by a dead process is recovered', ok3 and det3['recovered_stale_lock']['run_id'] == 'RUN-DEAD',
                  det3)
            check('and the dead run\'s ledger reads CRASHED_OR_KILLED, not RUNNING',
                  led['STATE'] == 'CRASHED_OR_KILLED' and led['recovered_by'] == 'RUN-C', led)
            check('the new lock names this process', json.loads((PL.OUT_DIR / 'DK_S_EARLY_RUN.lock').read_text())['pid']
                  == os.getpid())
        finally:
            PL.OUT_DIR = real


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    assert FAILED == 0, f'{FAILED} check(s) failed'


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
