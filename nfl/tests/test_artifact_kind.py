"""A sealed board is what the artifact DECLARES, not what the directory holds.

OWNER RULING 2026-09-23. Discovery treated "a directory containing
player_draws.npz" as a sealed board, and nine test modules then failed on the
ABSENCE of a board.json in two directories that are correctly not boards:

  post_inactives_V1_CANDIDATE/fced077d0db6ab41
      run_status.json: status REFUSED, first_failure artifact_sealing /
      CURRENT_SEASON_INPUT_STALE. It never reached board generation.

  post_inactives_V1_CANDIDATE_R9_W1P_GA_OFFICIAL
      ARTIFACT.json: "Reporting it as a full post-inactives board would be
      the false green this project exists to refuse."

Nothing was missing. Discovery was wrong about what it had found. This is a
truth-model correction, not a test-only exception, which is why the fixtures
below are about the RULE and the last test is about the real tree.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research import sealed_index as SI                           # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def run_dir(td, *, status=None, artifact=None, board=False, what_not=None,
            draws=True):
    d = pathlib.Path(td) / f'r{abs(hash((status, artifact, board, what_not)))}'
    d.mkdir(parents=True, exist_ok=True)
    if draws:
        np.savez(d / 'player_draws.npz', qb__att=np.zeros((2, 4)))
    if status is not None:
        (d / 'run_status.json').write_text(json.dumps(
            {'run_id': 'X', 'status': status}))
    if artifact is not None or what_not is not None:
        doc = {}
        if artifact is not None:
            doc['artifact'] = artifact
        if what_not is not None:
            doc['WHAT_THIS_IS_NOT'] = what_not
        (d / 'ARTIFACT.json').write_text(json.dumps(doc))
    if board:
        (d / 'board.json').write_text('{}')
    return d


# -- the four rules --------------------------------------------------------
def test_a_refused_run_is_not_a_board():
    with tempfile.TemporaryDirectory() as td:
        for st in SI.NON_SEALING_STATUS:
            k = SI.artifact_kind(run_dir(td, status=st))
            ok(k['kind'] == SI.KIND_REFUSED_RUN,
               f'draw file + status {st} is {k["kind"]}, not a board')
        k = SI.artifact_kind(run_dir(td, status='REFUSED'))
        ok('did not seal' in k['why'],
           'and the reason says a run that did not seal is not publishable')
        ok(k['evidence']['status'] == 'REFUSED',
           'carrying the declaration it read')


def test_a_declared_non_board_is_not_a_board():
    with tempfile.TemporaryDirectory() as td:
        for dec in SI.DECLARED_NON_BOARD:
            k = SI.artifact_kind(run_dir(td, artifact=dec))
            ok(k['kind'] == SI.KIND_DERIVED_NON_BOARD,
               f'draw file + ARTIFACT.json {dec} is {k["kind"]}')
        # AND THE DECLARATION WINS OVER A SEAL MARKER. An overlay that
        # happens to carry a board.json is still what it says it is.
        k = SI.artifact_kind(run_dir(td, artifact='POST_INACTIVES_BOARD_DRAWS',
                                     board=True, status='SEALED'))
        ok(k['kind'] == SI.KIND_DERIVED_NON_BOARD,
           f'a declared non-board carrying a board.json AND status SEALED is '
           f'still not promoted: {k["kind"]}')
        k2 = SI.artifact_kind(run_dir(td, what_not='this is not a board'))
        ok(k2['kind'] == SI.KIND_DERIVED_NON_BOARD,
           'and a bare WHAT_THIS_IS_NOT statement is enough on its own')


def test_a_declared_board_stays_discoverable():
    with tempfile.TemporaryDirectory() as td:
        k = SI.artifact_kind(run_dir(td, status='SEALED', board=True))
        ok(k['kind'] == SI.KIND_SEALED_BOARD,
           f'status SEALED + a seal marker is a board: {k["kind"]}')
        k2 = SI.artifact_kind(run_dir(td, board=True))
        ok(k2['kind'] == SI.KIND_SEALED_BOARD,
           'and an older board with no status file is one too -- its seal '
           'marker is the only declaration present and it is affirmative')


def test_missing_or_contradictory_declarations_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        k = SI.artifact_kind(run_dir(td))
        ok(k['kind'] == SI.KIND_INDETERMINATE,
           f'draws alone, with no declaration at all, is {k["kind"]} -- NOT '
           f'a board')
        k2 = SI.artifact_kind(run_dir(td, status='SEALED'))
        ok(k2['kind'] == SI.KIND_INDETERMINATE,
           'status SEALED with no seal marker is indeterminate: the two '
           'declarations do not agree and neither is guessed past')
        k3 = SI.artifact_kind(run_dir(td, status='WHO_KNOWS', board=True))
        ok(k3['kind'] == SI.KIND_INDETERMINATE,
           f'an unrecognised status is indeterminate even beside a seal '
           f'marker: {k3["kind"]}')
        ok('not guessed into one' in k3['why'],
           'and the rule is stated in the verdict')


# -- the real tree ---------------------------------------------------------
def test_the_two_det_buf_directories_are_correctly_excluded():
    c = SI.classify_live()
    ok(sum(len(v) for v in c.values()) == len(SI.live_draw_files()),
       f'every discovered draw directory is classified: '
       f'{ {k: len(v) for k, v in c.items()} }')
    ok(len(c[SI.KIND_SEALED_BOARD]) < len(SI.live_draw_files()),
       'and the board set is strictly smaller than the draw-file set, which '
       'is the whole point')
    refused = [d for d in c[SI.KIND_REFUSED_RUN] if 'fced077d0db6ab41' in d]
    ok(bool(refused),
       f'the REFUSED DET-BUF run is classified as a refused run: {refused}')
    derived = [d for d in c[SI.KIND_DERIVED_NON_BOARD]
               if 'GA_OFFICIAL' in d]
    ok(bool(derived),
       f'and the declared non-board as a derived artifact: {derived}')
    ok(not c[SI.KIND_INDETERMINATE],
       f'nothing in the live tree is indeterminate: '
       f'{c[SI.KIND_INDETERMINATE]}')
    ok(len(SI.sealed_boards()) == len(c[SI.KIND_SEALED_BOARD]),
       'and sealed_boards() returns exactly the declared boards')


def test_refused_runs_stay_discoverable_for_audit():
    """Excluded from BOARDS, not from existence. An audit of refusals needs
    them, and `live_draw_files` is what it says it is."""
    files = [str(p.parent) for p in SI.live_draw_files()]
    ok(any('fced077d0db6ab41' in f for f in files),
       'the refused run is still returned by live_draw_files()')
    ok(not any('fced077d0db6ab41' in str(p.parent)
               for p in SI.sealed_boards()),
       'and is absent from sealed_boards()')


def main():
    for t in (test_a_refused_run_is_not_a_board,
              test_a_declared_non_board_is_not_a_board,
              test_a_declared_board_stays_discoverable,
              test_missing_or_contradictory_declarations_fail_closed,
              test_the_two_det_buf_directories_are_correctly_excluded,
              test_refused_runs_stay_discoverable_for_audit):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
