"""Every corpus fence must scan the whole corpus, and prove that it does.

THE DEFECT THIS MODULE EXISTS FOR.

On 2026-09-15 three corpus fences -- `test_conservation`, `test_draw_coherence`
and `test_stat_contract` -- were re-frozen at "104 sealed runs", with comments
saying "every sealed board". There were 121 board directories on disk. Each
fence carried its own private glob:

    GLOB = '2026_01_*/*/*/player_draws.npz'

TWO WRONG DIAGNOSES WERE PUBLISHED BEFORE THE RIGHT ONE, AND BOTH ARE RECORDED
HERE BECAUSE THE SECOND ONE SOUNDED CONVINCING.

  1. "104 = 116 .npz + 5 .npz.gz, and the five are invisible to a *.npz glob."
     The arithmetic is right and the cause is wrong.
  2. "Five 2026_01_SF_LA boards are excluded by file extension alone."
     Also wrong, and it would have produced a fix that did not work.

The actual cause is PATH DEPTH. All 17 missed directories sit two levels under
`live/`, and the glob hard-codes three (`game / label / run_id / file`).
Twelve of them (`REPLAY_C1/*`) are plain `.npz` and are missed anyway, which is
what rules the extension out. The five `2026_01_SF_LA/pre_inactives_*` boards
are gzipped AND shallow -- two independent reasons, so fixing only the
extension would still have missed them and the fence would still have reported
a smaller corpus as the corpus.

`nfl/research/sealed_index.py` already finds all 17. It was written for this
exact failure after a review reported NE@SEA as "NEVER FORECAST", and its
docstring states the rule: DISCOVERY IS BY CONTENT, NOT BY PATH CONVENTION.
The rule was in the tree, correct, and unused by the fences.

WHAT THIS MODULE ASSERTS. Not a count -- counts go stale the moment a board is
built, and a fence pinning one is a fence that gets re-frozen by whoever trips
it. It asserts AGREEMENT: each fence's corpus, however it chooses to find it,
must equal content discovery minus exclusions the fence DECLARES BY NAME. An
exclusion that is deliberate stays legal and stays visible; one that is an
accident of path shape or file encoding fails here, loudly, naming what it
dropped.
"""
from __future__ import annotations

import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research import sealed_index as SI          # noqa: E402

PASSED = FAILED = BLOCKED = 0
LIVE = (pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live').resolve()

# A fence may exclude a namespace on purpose. It must say so by name, here,
# with a reason. Anything not listed is expected to be scanned.
DECLARED_EXCLUSIONS = {
    'REPLAY_C1': 'replay artifacts of other runs, not independent forecasts',
}


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(cond)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def draw_dirs_on_disk():
    """Every directory under live/ holding a sealed draw file, either encoding."""
    return {p.parent.resolve()
            for p in list(LIVE.rglob('player_draws.npz'))
            + list(LIVE.rglob('player_draws.npz.gz'))}


def expected_corpus():
    """What a fence is expected to scan: on-disk, minus declared exclusions."""
    return {d for d in draw_dirs_on_disk()
            if d.relative_to(LIVE).parts[0] not in DECLARED_EXCLUSIONS}


def test_a_the_hazard_is_real_and_is_not_the_file_extension():
    print('\nA. the corpus is shallow in places and gzipped in places')
    disk = draw_dirs_on_disk()
    check('sealed boards exist', bool(disk), f'{len(disk)}')
    shallow = {d for d in disk if len(d.relative_to(LIVE).parts) == 2}
    gz = {p.parent.resolve() for p in LIVE.rglob('player_draws.npz.gz')}
    if not shallow:
        blocked('no board sits at depth 2, so the path-shape hazard cannot be '
                'demonstrated on live data', 'NO_SHALLOW_BOARD_ON_DISK')
        return
    check('  some boards sit two levels under live/, not three',
          bool(shallow), f'{len(shallow)}')
    check('  and the hazard is NOT merely the file extension: some shallow '
          'boards are plain .npz',
          bool(shallow - gz), f'{len(shallow - gz)} shallow and ungzipped')


def test_b_content_discovery_finds_every_board_on_disk():
    print('\nB. sealed_index finds boards by content')
    found = {pathlib.Path(r['dir']).resolve() for r in SI.discover_all()}
    missed = sorted(draw_dirs_on_disk() - found)
    check('every directory holding sealed draws is discovered by content',
          not missed,
          ', '.join(str(p.relative_to(LIVE)) for p in missed[:6]) or 'none')


def test_c_every_corpus_fence_agrees_with_content_discovery():
    print('\nC. no fence silently scans less than the corpus')
    import importlib
    want = expected_corpus()
    for mod_name in ('test_conservation', 'test_draw_coherence',
                     'test_stat_contract'):
        m = importlib.import_module(mod_name)
        corpus = getattr(m, 'sealed_corpus', None)
        if corpus is None:
            check(f'{mod_name} exposes a sealed_corpus() to audit', False,
                  'no sealed_corpus attribute -- the fence cannot be checked '
                  'against content discovery')
            continue
        seen = {pathlib.Path(p).resolve().parent for p in corpus()}
        dropped = sorted(want - seen)
        extra = sorted(seen - want)
        check(f'{mod_name} scans every non-excluded board',
              not dropped,
              f'{len(dropped)} dropped: ' + ', '.join(
                  str(p.relative_to(LIVE)) for p in dropped[:5]))
        check(f'  and scans nothing outside the corpus',
              not extra,
              f'{len(extra)} extra: ' + ', '.join(
                  str(p.relative_to(LIVE)) for p in extra[:5]))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
