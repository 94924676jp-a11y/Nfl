"""A sealed forecast must stay discoverable when the namespace moves on.

THE INCIDENT.

A live-game review asserted NE@SEA "was NEVER FORECAST". It had been:
`nfl/research/shadow/g1_ne_sea/` held a V1_CANDIDATE forecast sealed before
the outcome was opened (bba6f0b) and scored against the realised game
(604eaac). Both commits are in history, both artifacts were in the working
tree, and the evaluator could not see either -- so one of two live games
silently vanished from the evidence base and its absence was reported as a
fact about the world.

The cause was DISCOVERY ONLY. Nothing was deleted, moved out of git, or left
on another branch. `research.daily_board.discover` hard-coded one root and one
label grammar, and the shadow artifact matched neither.

These tests exist so that never recurs: discovery is by CONTENT, every
historical namespace is searched, and a namespace being retired from fashion
is not allowed to retire its artifacts.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research import sealed_index as SI                          # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def test_a_the_ne_sea_shadow_forecast_is_discoverable():
    """THE REGRESSION. This is the artifact the review said did not exist."""
    hits = SI.for_game('2026_01_NE_SEA')
    check('NE@SEA has at least one discoverable sealed forecast',
          len(hits) >= 1, f'{len(hits)} found')
    if not hits:
        return
    shadow = [h for h in hits if h['namespace'] == 'shadow']
    check('  and it is found in the SHADOW namespace, not only live/',
          shadow, str([h['namespace'] for h in hits]))
    g1 = [h for h in shadow if h['label'] == 'g1_ne_sea']
    check('  the original g1_ne_sea seal is among them', g1, str(
        [h['label'] for h in shadow]))
    if g1:
        check('    it carries stored draws', g1[0]['has_draws'])
        check('    it carries its evaluation', g1[0]['has_evaluation'])
        check('    and it resolves to the canonical game id',
              g1[0]['game_id'] == '2026_01_NE_SEA', str(g1[0]['game_id']))


def test_b_discovery_is_by_content_not_by_path_convention():
    """A sealed forecast in a namespace nobody has invented yet."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='seal-ns-'))
    odd = tmp / 'some_future_namespace' / 'whatever_2026_01_AA_BB'
    odd.mkdir(parents=True)
    (odd / 'SEALED_FORECAST.json').write_text(json.dumps({
        'game_id': '2026_01_AA_BB', 'model_configuration': 'V1_CANDIDATE',
        'kickoff_utc': '2026-09-13T17:00:00Z'}))
    real = SI.NAMESPACES
    SI.NAMESPACES = real + (('future', tmp),)
    try:
        found = [r for r in SI.discover_all() if r['namespace'] == 'future']
        check('a directory in an unknown namespace is still recognised',
              len(found) == 1, str(len(found)))
        if found:
            check('  identified by its sealed marker',
                  'SEALED_FORECAST.json' in found[0]['markers'],
                  str(found[0]['markers']))
            check('  with its game id read from content',
                  found[0]['game_id'] == '2026_01_AA_BB',
                  str(found[0]['game_id']))
    finally:
        SI.NAMESPACES = real


def test_c_a_directory_with_no_seal_is_not_a_forecast():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='seal-neg-'))
    (tmp / 'not_a_board').mkdir()
    (tmp / 'not_a_board' / 'README.md').write_text('nothing here')
    real = SI.NAMESPACES
    SI.NAMESPACES = (('probe', tmp),)
    try:
        check('a directory carrying no sealed artifact is NOT indexed',
              not SI.discover_all(), str(SI.discover_all()))
    finally:
        SI.NAMESPACES = real


def test_d_a_label_that_hides_the_game_id_is_still_matched():
    """`g1_ne_sea` does not contain `2026_01_NE_SEA`, and must still match."""
    check('the label alias resolves teams out of a legacy directory name',
          SI._looks_like('2026_01_NE_SEA', 'g1_ne_sea'))
    check('  and does not match an unrelated game',
          not SI._looks_like('2026_01_SF_LA', 'g1_ne_sea'))
    check('  nor match on a single shared team',
          not SI._looks_like('2026_01_NE_KC', 'g1_kc_den'))


def test_e_retiring_a_namespace_is_what_breaks_history():
    """Guard the guard: the namespace list is append-only by intent."""
    names = [n for n, _ in SI.NAMESPACES]
    for required in ('live', 'shadow', 'product'):
        check(f'  {required!r} is still searched', required in names,
              str(names))
    check('shadow is searched, which is the namespace that was missed',
          'shadow' in names)


def test_f_every_indexed_artifact_reports_what_it_has():
    recs = SI.discover_all()
    check('the index finds the artifacts this repository holds',
          len(recs) > 5, f'{len(recs)} sealed artifact(s)')
    for r in recs:
        check_once = all(k in r for k in
                         ('namespace', 'dir', 'markers', 'game_id',
                          'has_draws', 'has_evaluation', 'promoted'))
        if not check_once:
            check('every record carries the fields a ledger needs', False,
                  str(sorted(r)))
            return
    check('every record carries the fields a ledger needs', True,
          f'{len(recs)} records')
    check('  and nothing discovered is marked promoted',
          not any(r['promoted'] for r in recs),
          str([r['label'] for r in recs if r['promoted']]))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
