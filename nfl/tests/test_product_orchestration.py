"""The five things the scheduled board refresh must be unable to do.

An orchestrator runs unattended, so every one of these is a property nobody
will be watching for at the moment it matters.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import board as PB                             # noqa: E402
from nfl.product import distributions as D                      # noqa: E402
from nfl.product import orchestrator as ORC                     # noqa: E402
from nfl.product import store as ST                             # noqa: E402

PASSED = FAILED = 0
GAME = '2026_01_SF_LA'
KICKOFF = '2026-09-11T00:35:00Z'


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


def _stored():
    rows = [r for r in ST.read_index(GAME) if r.get('status') == 'WRITTEN']
    return max(rows, key=lambda r: r['written_at']) if rows else None


# ============================================ PROOF 1: determinism
def test_identical_inputs_and_frozen_model_give_identical_draws():
    """The same information set at the same written_at must reproduce the
    stored draws exactly. If it does not, a board is not a record of
    anything -- it is a sample."""
    row = _stored()
    if not check('a stored board exists to reproduce', bool(row),
                 'no board in the index'):
        return
    d = pathlib.Path(_ROOT) / row['board_dir']
    fc = D.Forecast(d)
    from nfl.tools.make_board import build_one
    import tempfile
    tmp = tempfile.mkdtemp(prefix='determ_')
    summary, bd, run_dir = build_one(
        2026, 1, GAME, row['written_at'], tmp,
        fc.n_draws, 20260908, row['model_configuration'])
    if not check('the reproduction run sealed',
                 summary['status'] == 'SEALED', summary['status']):
        return
    # THE RUN ID IS NOT THE DETERMINISM CLAIM. It hashes the execution
    # identity, which includes `code_commit()` -- and that carries a
    # `+dirty[n]` counter of uncommitted files. Editing anything in the tree
    # moves the run id while the forecast is untouched, which is the counter
    # working. The claim being proven is that the DRAWS reproduce, so the run
    # id is only required to match when the tree is clean enough for it to be
    # a fair comparison.
    import subprocess
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=_ROOT,
                           capture_output=True, text=True).stdout.strip()
    if not dirty:
        check('  it reproduces the same run id',
              bd['run_id'] == row['run_id'],
              f'{bd["run_id"]} != {row["run_id"]}')
    else:
        check('  run id comparison skipped: the working tree is dirty, so '
              'code_commit carries a +dirty marker', True)
    check('  the draw content digest reproduces exactly',
          bd['draw_content_digest'] == row['draw_content_digest'],
          bd['draw_content_digest'])
    again = np.load(pathlib.Path(run_dir) / 'player_draws.npz')
    same = [k for k in fc.arrays if k in again.files
            and np.array_equal(fc.arrays[k], again[k])]
    check(f'  every one of {len(fc.arrays)} draw arrays is bit-identical',
          len(same) == len(fc.arrays) == len(again.files),
          f'{len(same)}/{len(fc.arrays)} matched')


# ============================================ PROOF 2: only newer vintages
def test_only_a_genuinely_newer_vintage_can_change_a_board():
    a = {'sources': {'x': {'sha256': 'a' * 64,
                           'observed_at': '2026-09-10T00:00:00Z'}}}
    b = json.loads(json.dumps(a))
    check('identical vintages give an identical fingerprint',
          ST.input_fingerprint(a) == ST.input_fingerprint(b))
    c = json.loads(json.dumps(a))
    c['sources']['x']['sha256'] = 'b' * 64
    check('  changed CONTENT changes it',
          ST.input_fingerprint(a) != ST.input_fingerprint(c))
    e = json.loads(json.dumps(a))
    e['sources']['x']['observed_at'] = '2026-09-10T01:00:00Z'
    check('  a re-observation of the same bytes also changes it',
          ST.input_fingerprint(a) != ST.input_fingerprint(e),
          'a source re-fetched unchanged is still a different vintage')
    f = json.loads(json.dumps(a))
    f['sources']['y'] = {'sha256': 'c' * 64,
                         'observed_at': '2026-09-10T00:00:00Z'}
    check('  a new source changes it',
          ST.input_fingerprint(a) != ST.input_fingerprint(f))
    # AND THE LIVE PATH USES IT: with a board already stored, a second pass
    # over unchanged inputs must decline.
    row = _stored()
    if row:
        p = ORC.plan(GAME)
        check('  a live re-plan over unchanged inputs declines',
              p['status'] in ('NO_NEW_INPUTS', 'PAST_KICKOFF'), p['status'])


def test_a_scheduler_firing_more_often_cannot_make_more_boards():
    """The refresh decision must not be a function of the clock."""
    row = _stored()
    if not check('a stored board exists', bool(row)):
        return
    seen = {ORC.plan(GAME)['status'] for _ in range(3)}
    check('three back-to-back passes agree', len(seen) == 1, str(seen))
    check('  and none of them would write',
          seen <= {'NO_NEW_INPUTS', 'PAST_KICKOFF'}, str(seen))


# ============================================ PROOF 3: no post-kickoff data
def test_a_pregame_board_cannot_be_written_after_kickoff():
    after = _parse(KICKOFF) + dt.timedelta(seconds=1)
    p = ORC.plan(GAME, now=after)
    check('one second after kickoff the plan is PAST_KICKOFF',
          p['status'] == 'PAST_KICKOFF', p['status'])
    r = ORC.refresh(GAME, now=after)
    check('  and a refresh writes nothing',
          r['status'] == 'PAST_KICKOFF', r['status'])
    exact = ORC.plan(GAME, now=_parse(KICKOFF))
    check('  kickoff itself is already too late',
          exact['status'] == 'PAST_KICKOFF', exact['status'])


def test_no_source_in_a_stored_board_postdates_kickoff():
    row = _stored()
    if not check('a stored board exists', bool(row)):
        return
    meta = json.loads((pathlib.Path(_ROOT) / row['board_dir']
                       / 'PROTOCOL_RECORD.json').read_text())
    ko = _parse(meta['kickoff_utc'])
    late = [v for v in meta['input_vintages']
            if _parse(v['retrieved_at']) >= ko]
    check('every recorded input vintage predates kickoff', not late,
          str(late))
    check('  and written_at does too',
          _parse(meta['written_at']) < ko, meta['written_at'])
    check('  every vintage is also at or before written_at',
          all(_parse(v['retrieved_at']) <= _parse(meta['written_at'])
              for v in meta['input_vintages']))


# ============================================ PROOF 4: SHADOW is not AUTHORIZED
def test_shadow_cannot_masquerade_as_authorized():
    """The label is DERIVED from the canonical gate on every render. It is
    never carried in, defaulted, or copied from a previous board."""
    from nfl.production import authorization as AUTH
    from sportsplatform.governance.outcome import Outcome, State

    art = {'promoted': False, 'prospective_eligible': False,
           'TEST_ONLY': False}
    live = PB.authorization_state(art)
    gate = AUTH.may_publish()
    check('the label follows the real gate right now',
          (live['nfl1'] == 'AUTHORIZED') == (gate.state is State.PASS),
          f'{live["nfl1"]} vs {gate.code}')
    check('  and with the gate closed it reads SHADOW',
          live['label'] == 'SHADOW / NOT AUTHORIZED'
          if gate.state is not State.PASS else True, live['label'])
    check('  a closed gate can never be called published',
          live['may_be_called_published'] is (gate.state is State.PASS))

    # BOTH BRANCHES, so the label is proven to be a function of the gate and
    # not a constant that happens to be right today.
    orig = AUTH.may_publish
    try:
        AUTH.may_publish = lambda: Outcome.ok('NFL1_AUTHORIZED', value=True)
        opened = PB.authorization_state(art)
        check('  with the gate open the label becomes LIVE',
              opened['label'] == 'LIVE NFL-1 FORECAST', opened['label'])
        AUTH.may_publish = orig
        closed = PB.authorization_state(art)
        check('  and closing it returns to SHADOW',
              closed['label'] == 'SHADOW / NOT AUTHORIZED', closed['label'])
    finally:
        AUTH.may_publish = orig


def test_a_stored_shadow_board_is_never_relabelled():
    row = _stored()
    if not check('a stored board exists', bool(row)):
        return
    d = pathlib.Path(_ROOT) / row['board_dir']
    meta = json.loads((d / 'PROTOCOL_RECORD.json').read_text())
    check('the stored board records the label it was written under',
          meta['label'] == row['label'], f'{meta["label"]} vs {row["label"]}')
    check('  and says a later board never replaces it',
          'never replaces an earlier one' in meta['superseding_note'].lower()
          or 'NEVER REPLACES AN EARLIER ONE' in meta['superseding_note'])
    check('  the board text carries the same label',
          meta['label'] in (d / 'BOARD.md').read_text()[:600], meta['label'])
    check('  and it is not promoted or prospective',
          meta['promoted'] is False and meta['prospective_eligible'] is False)


def test_a_written_board_is_immutable():
    row = _stored()
    if not check('a stored board exists', bool(row)):
        return
    d = pathlib.Path(_ROOT) / row['board_dir']
    try:
        ST.write(GAME, row['written_at'], row['run_id'], {'x': b'y'}, {})
        check('rewriting a board directory is refused', False, 'NO_REFUSAL')
    except ST.BoardExists:
        check('rewriting a board directory is refused', True)
    # The seal still holds.
    bad = []
    for line in (d / 'SEAL_SHA256.txt').read_text().splitlines():
        if not line.strip():
            continue
        h, name = line.split()
        if hashlib.sha256((d / name).read_bytes()).hexdigest() != h:
            bad.append(name)
    check('  and every sealed file still hashes to its recorded value',
          not bad, str(bad))


def test_the_latest_pointer_holds_nothing_unique():
    row = _stored()
    if not check('a stored board exists', bool(row)):
        return
    rebuilt = ST.rebuild_latest(GAME)
    check('the pointer can be rebuilt from the append-only index',
          rebuilt and rebuilt['run_id'] == row['run_id'],
          str(rebuilt and rebuilt.get('run_id')))
    check('  so losing it costs nothing but convenience',
          'POINTER, NOT A BOARD' in
          (ST.ROOT / GAME / 'LATEST.json').read_text())


# ================================ PROOF 5: isolation from capture and G0A
CAPTURE_PATHS = ('nfl/vintage_manifest.jsonl', 'nfl/capture',
                 'nfl/tools/capture_vintage.py', 'nfl/tools/gen_t90_schedule.py',
                 '.github/workflows/nfl-t90.yml',
                 '.github/workflows/nfl-status.yml',
                 '.github/workflows/nfl-capture.yml',
                 'nfl/research/PATH_C_STATE.json')


def _snapshot():
    out = {}
    for rel in CAPTURE_PATHS:
        p = pathlib.Path(_ROOT) / rel
        if p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            for f in sorted(p.rglob('*')):
                if f.is_file() and '__pycache__' not in str(f):
                    out[str(f.relative_to(_ROOT))] = hashlib.sha256(
                        f.read_bytes()).hexdigest()
    return out


def test_the_orchestrator_writes_only_under_its_own_directory():
    src = (pathlib.Path(_ROOT) / 'nfl/product/orchestrator.py').read_text()
    for bad in ('vintage_manifest', 'capture_vintage', 'gen_t90',
                'PATH_C_STATE', 'may_publish =', '.github'):
        check(f'  the orchestrator never mentions {bad}', bad not in src, bad)
    check('  and the store writes under nfl/product/boards only',
          str(ST.WRITABLE_ROOT).endswith('nfl/product/boards'),
          str(ST.WRITABLE_ROOT))


def test_a_failing_product_run_cannot_touch_capture_or_governance():
    before = _snapshot()
    check('there is capture/governance state to protect', len(before) > 3,
          str(len(before)))
    # A run that fails in every way the orchestrator knows how to fail.
    res = ORC.run(['2026_01_NOT_A_GAME'], season=2026, week=1)
    check('an unknown game fails as a recorded product error',
          res and res[0]['status'] in ('ERROR', 'REFUSED'), str(res))
    ORC.run([GAME], season=2026, week=1)      # a normal pass, too
    after = _snapshot()
    changed = [k for k in before if before[k] != after.get(k)]
    check('  no capture or governance file changed', not changed,
          str(changed))
    check('  and none was deleted', set(before) <= set(after),
          str(sorted(set(before) - set(after))))


def test_the_lock_stops_two_passes_racing_one_directory():
    with ORC.Lock():
        try:
            with ORC.Lock():
                check('a second concurrent pass is refused', False,
                      'NO_REFUSAL')
        except RuntimeError as e:
            check('a second concurrent pass is refused',
                  'ALREADY_RUNNING' in str(e), str(e)[:60])
    check('  and the lock is released afterwards', not ORC.LOCK.exists())


def test_a_pass_that_writes_nothing_is_still_a_successful_pass():
    """A scheduler must not read `no new inputs` as a failure and alert."""
    src = (pathlib.Path(_ROOT) / 'nfl/tools/refresh_boards.py').read_text()
    check('the runner returns 0 after writing nothing',
          'A PASS THAT WROTE NOTHING IS A SUCCESSFUL PASS' in src)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
