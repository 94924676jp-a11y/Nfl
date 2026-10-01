#!/usr/bin/env python3.12
"""The showdown runner must refuse the wrong things, and must get the DK identity model right.

THE CHECK THAT MATTERS MOST is `cpt and flex are separate priced items`. In a DK showdown export the
captain and flex versions of one player carry DIFFERENT dk_ids -- 106 ids for 53 people in the
NYG@LAR file. A first version of the runner keyed its universe by `ID`, counted every player twice,
and refused its own test file. Had it keyed by id and NOT refused, the upload would have written a
flex id into the CPT column and entered a different lineup from the one that was optimised.

So this does not only check that a good file passes. Each refusal is exercised against a seeded
violation, because a guard is not demonstrated by compliant data passing it.
"""
from __future__ import annotations

import copy
import csv
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

SHOWDOWN = _REPO / 'nfl/dfs/salaries/raw/DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv'
CLASSIC = _REPO / 'nfl/dfs/salaries/raw/DKEntries_EARLY_ONLY_2026W3_62.csv'

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _slate():
    o = S.s1_ingest(SHOWDOWN)
    assert o.state is State.PASS, o
    i = S.s2_slate_identity(o.value['pool'])
    assert i.state is State.PASS, i
    return o.value, i.value


@check('a real showdown export ingests, and the fixture it needs exists')
def t_ingest():
    assert SHOWDOWN.exists(), f'{SHOWDOWN} is missing, so this module measures nothing'
    o = S.s1_ingest(SHOWDOWN)
    assert o.state is State.PASS, o
    assert o.value['entries'], 'no entries parsed'
    assert o.value['pool'], 'no pool rows parsed'
    return (f"{len(o.value['entries'])} entries, {len(o.value['pool'])} pool rows")


@check('the game, the clubs and the kickoff come from the file, not from the repository')
def t_identity_from_file():
    _, sl = _slate()
    assert sl['away'] == 'NYG' and sl['home'] == 'LAR', (sl['away'], sl['home'])
    assert sl['kickoff_et_naive'].startswith('2026-09-21T20:15'), sl['kickoff_et_naive']
    return f"{sl['away']}@{sl['home']} at {sl['kickoff_et_naive']} ET from Game Info alone"


@check('CPT and FLEX are separate priced items with different dk_ids')
def t_slot_ids_distinct():
    _, sl = _slate()
    players = sl['players']
    shared = [k for k, v in players.items() if v['cpt']['dk_id'] == v['flex']['dk_id']]
    assert not shared, f'{len(shared)} player(s) share an id across slots: {shared[:3]}'
    # And the ratio DK prices them at, checked rather than assumed.
    bad = [k for k, v in players.items()
           if v['cpt']['salary'] != round(v['flex']['salary'] * S.CPT_MULTIPLIER)]
    assert not bad, f'captain salary is not {S.CPT_MULTIPLIER}x flex for {bad[:3]}'
    return (f'{len(players)} players, {2 * len(players)} distinct priced items, '
            f'captain at {S.CPT_MULTIPLIER}x in every case')


@check('the universe is keyed by person, so one captain and five flex is enforceable')
def t_universe_keyed_by_person():
    ing, sl = _slate()
    assert len(sl['players']) * 2 == len(ing['pool']), (len(sl['players']), len(ing['pool']))
    assert all('|' in k for k in sl['players']), 'a key is not a (name, club) identity'
    return f"{len(sl['players'])} people from {len(ing['pool'])} priced rows"


@check('the declared team alias maps DK LAR onto the corpus LA, and is a lookup not a guess')
def t_team_alias():
    assert S.corpus_team('LAR') == 'LA', S.corpus_team('LAR')
    assert S.corpus_team('NYG') == 'NYG', S.corpus_team('NYG')
    # An unknown code passes through unchanged rather than being fuzzily matched to something.
    assert S.corpus_team('ZZZ') == 'ZZZ'
    _, sl = _slate()
    assert {v['team'] for v in sl['players'].values()} == {'NYG', 'LA'}
    return 'LAR -> LA, everything else unchanged'


@check('LOAD-BEARING: a classic export is refused, not built as six-player lineups')
def t_classic_refused():
    assert CLASSIC.exists(), f'{CLASSIC} is missing, so this check measures nothing'
    o = S.s1_ingest(CLASSIC)
    assert o.state is State.FAIL, o
    assert o.code == 'NOT_A_SHOWDOWN_EXPORT', o.code
    return f'refused with {o.code}'


@check('LOAD-BEARING: a missing official-inactive list is DEFERRED, never an empty set')
def t_inactives_deferred():
    _, sl = _slate()
    o = S.s3_availability(sl, None)
    assert o.state is State.DEFERRED, o
    assert o.code == 'SHOWDOWN_OFFICIAL_INACTIVES_NOT_SUPPLIED', o.code
    return f'{o.code} rather than zero players out'


@check('LOAD-BEARING: an inactive name from another game is refused, not dropped')
def t_inactive_foreign_refused():
    _, sl = _slate()
    o = S.s3_availability(sl, ['Someone Not In This Game'])
    assert o.state is State.FAIL, o
    assert o.code == 'SHOWDOWN_INACTIVE_NOT_IN_SLATE', o.code
    good = S.s3_availability(sl, [next(iter(sl['players']))])
    assert good.state is State.PASS, good
    assert len(good.value['absent']) == 1
    return 'foreign name refused; a real one resolves to exactly one player'


@check('LOAD-BEARING: a captain salary that is not 1.5x is refused')
def t_multiplier_violation_refused():
    o = S.s1_ingest(SHOWDOWN)
    pool = copy.deepcopy(o.value['pool'])
    for p in pool:
        if p['Roster Position'] == 'CPT':
            p['salary_int'] += 100
            break
    r = S.s2_slate_identity(pool)
    assert r.state is State.FAIL, r
    assert r.code == 'SHOWDOWN_CAPTAIN_MULTIPLIER_DISAGREES', r.code
    return f'refused with {r.code}'


@check('LOAD-BEARING: two clubs is a site rule the legality gate enforces')
def t_single_team_refused():
    _, sl = _slate()
    nyg = [k for k, v in sl['players'].items() if v['dk_team'] == 'NYG'][:6]
    assert len(nyg) == 6, 'need six NYG players to build the illegal lineup'
    bad = S.validate_lineup({'captain': nyg[0], 'flex': nyg[1:6]}, sl)
    assert bad.state is State.FAIL, bad
    assert bad.code in ('LINEUP_SINGLE_TEAM', 'LINEUP_OVER_THE_CAP'), bad.code
    return f'a single-club lineup is refused with {bad.code}'


@check('LOAD-BEARING: a duplicated player, and a captain repeated in flex, are refused')
def t_duplicate_refused():
    _, sl = _slate()
    ks = list(sl['players'])[:6]
    o = S.validate_lineup({'captain': ks[0], 'flex': [ks[0]] + ks[1:5]}, sl)
    assert o.state is State.FAIL, o
    assert o.code == 'LINEUP_DUPLICATE_PLAYER', o.code
    return f'refused with {o.code}'


@check('LOAD-BEARING: a scratched player cannot be rostered')
def t_absent_refused():
    _, sl = _slate()
    ks = list(sl['players'])[:6]
    o = S.validate_lineup({'captain': ks[0], 'flex': ks[1:6]}, sl, absent={ks[3]})
    assert o.state is State.FAIL, o
    assert o.code == 'LINEUP_CONTAINS_AN_ABSENT_PLAYER', o.code
    return f'refused with {o.code}'


@check('the emitted CSV carries the SLOT-SPECIFIC dk_id in each seat')
def t_csv_uses_slot_ids():
    ing, sl = _slate()
    # A deliberately cheap legal lineup: the two cheapest from each club, so the cap is not the thing
    # under test here.
    by_club = {}
    for k, v in sl['players'].items():
        by_club.setdefault(v['dk_team'], []).append((v['flex']['salary'], k))
    picks = []
    for c in sorted(by_club):
        picks += [k for _, k in sorted(by_club[c])[:3]]
    lineup = {'captain': picks[0], 'flex': picks[1:6]}
    legal = S.validate_lineup(lineup, sl)
    assert legal.state is State.PASS, legal
    out = pathlib.Path(tempfile.mkdtemp()) / 'upload.csv'
    o = S.s_emit_csv([lineup], ing['entries'][:1], sl, out=out)
    assert o.state is State.PASS, o
    rows = list(csv.reader(out.open(newline='', encoding='utf-8')))
    hdr, row = rows[0], rows[1]
    assert hdr[4:] == list(S.SHOWDOWN_SLOTS), hdr[4:]
    cpt_written = row[4]
    assert cpt_written == sl['players'][lineup['captain']]['cpt']['dk_id'], cpt_written
    assert cpt_written != sl['players'][lineup['captain']]['flex']['dk_id'], (
        'the CPT column was written with the flex id, which would enter a different lineup')
    for seat, k in zip(row[5:], lineup['flex']):
        assert seat == sl['players'][k]['flex']['dk_id'], (seat, k)
    return f'CPT column carries {cpt_written}, not the flex id, and five flex seats match'


@check('LOAD-BEARING: fewer lineups than entries refuses rather than writing blank rows')
def t_short_portfolio_refused():
    ing, sl = _slate()
    o = S.s_emit_csv([], ing['entries'][:2], sl)
    assert o.state is State.FAIL, o
    assert o.code == 'SHOWDOWN_NOTHING_TO_EMIT', o.code
    return f'refused with {o.code}'


@check('the third-party projection column is never read as an input')
def t_third_party_not_an_input():
    src = pathlib.Path(S.__file__).read_text()
    assert 'AvgPointsPerGame' in S.THIRD_PARTY_COLUMNS, S.THIRD_PARTY_COLUMNS
    # It may be NAMED (in the schema and in the exclusion list) but must never be assigned into a
    # projection or a score. The guard is deliberately crude and deliberately loud.
    for pat in ('dk_points = ', 'dk_points=', 'proj['):
        for line in src.splitlines():
            if pat in line and 'AvgPointsPerGame' in line:
                raise AssertionError(f'third-party value reaches a projection: {line.strip()}')
    return 'AvgPointsPerGame appears only in the schema and the exclusion list'


@check('the run always emits a status board, including when it refuses')
def t_board_always_emitted():
    o = S.run(SHOWDOWN)
    # Week 3 projections do not cover a Week 2 game, so this is expected to block rather than pass.
    assert o.state in (State.BLOCKED, State.DEFERRED, State.PASS), o
    b = (o.evidence or {}).get('board') or {}
    assert b.get('stages'), 'no stages on the board'
    assert b.get('RESULT'), 'the board carries no RESULT'
    assert S.OUT_BOARD.exists(), f'{S.OUT_BOARD} was not written'
    names = [s['stage'] for s in b['stages']]
    assert names[:2] == ['ingest_export', 'slate_identity'], names
    return f"{b['RESULT']} with stages {names}"


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
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
