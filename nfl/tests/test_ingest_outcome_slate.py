#!/usr/bin/env python3.12
"""ingest_outcome grades any slate, and reproduces an outcome OFFLINE from its stored raw blobs.

The module was hardcoded to DET_BUF week 2 (teams, week and output paths as constants). The slate
is now an argument; the default is unchanged; and a stored blob reproduces the artifact byte-for-
byte in substance while asserting the blob's own clock, never a live one.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import ingest_outcome as IO  # noqa: E402
from nfl.postgame import outcome as OC  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []
DB = _REPO / 'nfl/research/dfs/DET_BUF_2026W2'
GAMES_BLOB = DB / 'POSTGAME_OUTCOME/raw/nfldata_games.9c3b8476cb7d3fab.csv.gz'
STATS_BLOB = DB / 'POSTGAME_OUTCOME/raw/nflverse_stats_player_week.f35e9d110d363a69.csv.gz'
COMMITTED = json.loads((DB / 'POSTGAME_OUTCOME/OUTCOME.json').read_text())


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the default slate derives season 2026, week 2, DET @ BUF -- behaviour unchanged')
def _default():
    o = IO.slate_parts(OC.slate())
    assert o.state is State.PASS and o.value == ('2026', '2', 'DET', 'BUF'), o
    return o.detail


@check('another slate derives its own week and clubs; a malformed id is refused by name')
def _other():
    o = IO.slate_parts(OC.Slate('2026_04_PIT_CLE', '/tmp/x'))
    assert o.value == ('2026', '4', 'PIT', 'CLE'), o.value
    bad = IO.slate_parts(OC.Slate('g4_pit_cle', '/tmp/x'))
    assert bad.state is State.FAIL and bad.code == 'GAME_ID_MALFORMED', bad
    return f'{o.detail}; malformed -> {bad.code}'


@check('OFFLINE REPRODUCTION: DET_BUF rebuilt from its stored blobs matches the committed artifact')
def _reproduce():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='ingest_repro_'))
    try:
        sl = OC.Slate('2026_02_DET_BUF', tmp)
        o = IO.build(sl, games_blob=GAMES_BLOB, stats_blob=STATS_BLOB)
        assert o.state is State.PASS, (o.code, o.detail)
        art = json.loads(sl.artifact.read_text())
        fs = art['final_score']
        assert (fs['away_team'], fs['away_score'], fs['home_team'], fs['home_score']) == ('DET', 31, 'BUF', 41), fs
        assert art['source_sha256']['games'] == COMMITTED['source_sha256']['games']
        assert art['source_sha256']['stats_player_week'] == COMMITTED['source_sha256']['stats_player_week']
        assert len(art['players']) == len(COMMITTED['players']), (len(art['players']), len(COMMITTED['players']))
        nm = next(n for n, v in COMMITTED['players'].items() if v.get('pass_yards', 0) > 100)
        assert art['players'][nm]['pass_yards'] == COMMITTED['players'][nm]['pass_yards'], nm
        assert art['retrieved_at_basis'] == IO.STORED_BLOB, art['retrieved_at_basis']
        assert (sl.outcome_dir / 'FINAL_SCORE.json').exists()
        return (f"{fs['away_team']} {fs['away_score']} @ {fs['home_team']} {fs['home_score']}; "
                f"{len(art['players'])} players; {nm} pass_yards {art['players'][nm]['pass_yards']}; "
                f"basis {art['retrieved_at_basis']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check('a reproduction never claims a live clock, and a missing blob is refused by name')
def _clock_and_missing():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='ingest_repro_'))
    try:
        got = IO.fetch(IO.GAMES_URL, stem='nfldata_games', raw_dir=tmp, blob=GAMES_BLOB)
        assert got.state is State.PASS and got.evidence['retrieved_at_basis'] == IO.STORED_BLOB
        assert got.evidence['sha256'] == COMMITTED['source_sha256']['games']
        m = IO.fetch(IO.GAMES_URL, stem='nfldata_games', raw_dir=tmp, blob=tmp / 'nope.csv.gz')
        assert m.state is State.FAIL and m.code == 'STORED_BLOB_MISSING', m
        return f"basis {got.evidence['retrieved_at_basis']}; missing -> {m.code}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check('the wrong slate against a stored games blob is refused, never scored')
def _wrong_slate():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='ingest_repro_'))
    try:
        sl = OC.Slate('2026_04_PIT_CLE', tmp)
        o = IO.final_score(sl, blob=GAMES_BLOB)
        assert o.state is not State.PASS, o
        assert not sl.artifact.exists()
        return f'{o.state.name}[{o.code}]'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check('CLI: --game-id without --root is refused; a directory is never guessed')
def _cli_root_required():
    rc = IO.main(['--game-id', '2026_04_PIT_CLE'])
    assert rc == 1
    return 'SLATE_ROOT_REQUIRED'


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
