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


# DRAW ARRAYS AN ACCEPTED, REGISTERED CHANGE IS ALLOWED TO MOVE.
#
# A board in the store was produced by the code of its day. When an allocator
# is deliberately changed, its arrays stop matching that record -- and that is
# the change working, not determinism failing. Anything NOT in here that moves
# is undeclared drift and fails.
#
# Keyed by draw array, valued by the registration that authorised it.
DECLARED_DRAW_CHANGES = {
    'rushing__carries':
        'C1 -- the carry allocator\'s `other` mass on A1\'s denominator. '
        'predeclaration_c1_denominator.md sha256 9d0443e1',
    'rushing__rushing_td':
        'C1 -- derived from carries, so it moves with them. Same '
        'registration.',
    'qb__cmp':
        'B1 -- the passer-credit scheme. `shared_pass.credit_to_passers` '
        'assigned completions, passing TDs and passing yards AFTER the '
        '`cmp <= att` guard had already run, so the guard attested to values '
        'that were then overwritten: 5,278 `cmp > att` cells, 731 `ptd > cmp` '
        'and 11,616 `pyds != 0` on zero completions across 101 sealed runs, '
        'every one of them reporting PASS. Replaced by '
        '`football_engine.credit_passing_line`, which CONSTRUCTS a coherent '
        'line rather than repairing an impossible one, and REFUSES where no '
        'allocation can satisfy the inputs instead of emitting a '
        'coherent-looking lie. Registered by '
        'nfl/research/remediation/ws_o/WS_O_INVARIANT_CLASSIFICATION.md; A/B '
        'in test_draw_coherence::test_the_incumbent_scheme_produces_the_'
        'impossible_states_and_the_new_one_does_not -- same inputs, same '
        'seeds, 33 shared-pass runs: zero I1/N1/I2/I3 cells over 260,000 '
        'checked, per-quarterback mean completions moving by at most 0.0900 '
        'across 218 rows, and the ROOM total unchanged because the '
        'allocation still closes exactly on the team total.',
    'qb__ptd':
        'B1 -- assigned by the same replaced function. Same registration.',
    'qb__pyds':
        'B1 -- assigned by the same replaced function. Same registration.',
}


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
    # THE RUN ID IS NOT THE DETERMINISM CLAIM, AND THE GATE ON IT WAS WRONG
    # IN TWO WAYS THAT OUTLIVED THE THING IT WAS WRITTEN FOR.
    #
    # `run_id` hashes the execution identity, which includes `code_commit()`.
    # That used to return `<sha>+dirty[n]`, a COUNT of uncommitted paths, so
    # the run id moved whenever anything anywhere in the tree moved --
    # including this run's own outputs. The gate written for that form was
    # "compare run ids only when `git status --porcelain` is empty":
    #
    #   IT NEVER FIRED. The tree is essentially never clean in this
    #   repository, so the comparison was skipped on every execution this
    #   test has ever had -- and the skip branch recorded `check(..., True)`,
    #   a PASS for a comparison that did not happen. That is the
    #   absence-read-as-success defect inside the measurement system.
    #
    #   IT ASKED THE WRONG QUESTION. Under `nfl.identity.code_identity` the
    #   identity is a CONTENT digest over in-scope dirty SOURCE. An untracked
    #   note, a generated board and a research artifact do not move it, so a
    #   whole-tree cleanliness test is both too strict and beside the point.
    #
    # The right question is whether the code identity NOW is the code
    # identity that produced the STORED board. Boards sealed before WS-E
    # carry the withdrawn count-keyed form, which can never equal a
    # contract-form identity, and that is reported as NOT APPLICABLE with the
    # reason attached rather than as a pass.
    from nfl.identity import code_identity as CI
    from nfl.production import run_forecast as RUN
    now_cv = RUN.code_commit()
    stored_cv = str((json.loads((d / 'board.json').read_text())
                     if (d / 'board.json').exists() else {}
                     ).get('code_commit') or '')
    if stored_cv and now_cv == stored_cv:
        check('  it reproduces the same run id',
              bd['run_id'] == row['run_id'],
              f'{bd["run_id"]} != {row["run_id"]}')
    elif CI.refuses_count_keyed(stored_cv):
        print(f'  N/A   run id comparison: the stored board carries the '
              f'withdrawn count-keyed identity {stored_cv!r}, which no '
              f'contract-form run can reproduce. Not a determinism result '
              f'either way.')
    else:
        print(f'  N/A   run id comparison: the stored board was produced '
              f'under code identity {stored_cv!r} and this run is '
              f'{now_cv!r}. Different code, so a different run id is '
              f'expected.')
    # The draw comparison below is the determinism claim and is NEVER skipped.
    again = np.load(pathlib.Path(run_dir) / 'player_draws.npz')

    # DETERMINISM IS "SAME CODE, SAME INPUTS, SAME DRAWS", AND THAT IS WHAT IS
    # PROVEN HERE -- by building a SECOND time under the code running now.
    #
    # This used to be proven only by comparing against the STORED board, which
    # silently also pinned the code that produced it. The first accepted
    # change to an allocator therefore failed it as a determinism defect when
    # nothing about determinism had moved. A guard that cannot tell "the draws
    # are not reproducible" from "the model was deliberately changed" reports
    # the wrong defect, and the fix is to measure the two separately.
    tmp2 = tempfile.mkdtemp(prefix='determ2_')
    _s2, bd2, run_dir2 = build_one(
        2026, 1, GAME, row['written_at'], tmp2,
        fc.n_draws, 20260908, row['model_configuration'])
    twice = np.load(pathlib.Path(run_dir2) / 'player_draws.npz')
    repro = [k for k in again.files
             if k in twice.files and np.array_equal(again[k], twice[k])]
    check(f'  building twice under the current code reproduces all '
          f'{len(again.files)} arrays exactly',
          len(repro) == len(again.files) == len(twice.files),
          f'{len(repro)}/{len(again.files)} matched')
    check('  and the draw content digest is stable across those two builds',
          bd['draw_content_digest'] == bd2['draw_content_digest'],
          f"{bd['draw_content_digest'][:16]} vs "
          f"{bd2['draw_content_digest'][:16]}")

    # SEPARATELY: what has moved since the STORED board, and was it declared?
    # Undeclared drift in a draw array is still a defect and still fails.
    moved = sorted(k for k in fc.arrays if k in again.files
                   and not np.array_equal(fc.arrays[k], again[k]))
    undeclared = [k for k in moved if k not in DECLARED_DRAW_CHANGES]
    check('  every array that moved since the stored board was a DECLARED '
          'change',
          not undeclared,
          f'undeclared: {undeclared}' if undeclared
          else f'declared drift in {moved}' if moved
          else 'nothing moved')
    if moved:
        check('    and the declared change names its registration',
              all(DECLARED_DRAW_CHANGES.get(k) for k in moved),
              json.dumps({k: DECLARED_DRAW_CHANGES.get(k) for k in moved}))
    else:
        check('    and the digest therefore still matches the stored board',
              bd['draw_content_digest'] == row['draw_content_digest'],
              bd['draw_content_digest'])


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
