"""Every emitted array has a DECLARED mathematical support.

WHY THIS REGISTRY EXISTS SEPARATELY FROM `metrics.SUPPORTED`. That one is the
PUBLICATION contract -- 17 entries with a label and a status, describing what
appears on a board. The engine emits 54 matrices. Putting the other 37 into it
would change what boards publish, which is a production change, not a
classification one.

WHY DECLARED RATHER THAN SNIFFED. `draw_coherence.py` already records why dtype
is useless: `rushing/carries` is int-typed nowhere and `qb/pyds` is float and
declared yards. Cardinality is worse -- a quantity would change contract when
the draw count changed.

THE CHECK THAT MATTERS is not that the table is full. It is that the table
agrees with the arrays a real board actually contains.
"""
from __future__ import annotations

import glob
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import metrics as M                                  # noqa: E402
from nfl.product import support_kinds as SK                           # noqa: E402
from nfl.research import sealed_index as SI                           # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  ..   NOT_EXECUTED {label} -- {why}')


def _boards():
    out = []
    for f in SI.live_draw_files():
        d = pathlib.Path(f).parent
        try:
            out.append((d, SI.load_draws(d)))
        except Exception:                                   # noqa: BLE001
            continue
    return out


def _generation(d):
    """Which engine generation sealed this board, from its OWN manifest.

    `EMITTED_KINDS.emitted` describes what the engine emits NOW. It is not a
    claim about every artifact ever sealed, and the corpus contains boards from
    before the counts repair. Read the board's declared components rather than
    guessing from its path.
    """
    import json
    try:
        b = json.loads((d / 'board.json').read_text())
    except (OSError, ValueError):
        return 'UNKNOWN'
    applied = (b.get('component_manifest') or {}).get('applied') or []
    return 'CURRENT' if 'R9' in applied else 'LEGACY'


def test_A_the_table_is_well_formed():
    print('\nA. every entry declares a kind this module names')
    check('the registry is non-empty', bool(SK.EMITTED_KINDS))
    bad = [k for k, v in SK.EMITTED_KINDS.items() if v.get('kind') not in SK.KINDS]
    check('  every kind is one of the declared kinds', not bad, str(bad[:3]))
    bad2 = [k for k, v in SK.EMITTED_KINDS.items()
            if v.get('emitted') not in (SK.INTEGER, SK.CONTINUOUS)]
    check('  every entry declares what the engine currently emits',
          not bad2, str(bad2[:3]))
    check('  `kind_of` never guesses: an unknown key returns None',
          SK.kind_of('not/a/real/array') is None)
    print(f'       by kind: {[(k, len(SK.by_kind(k))) for k in SK.KINDS]}')


def test_B_it_covers_every_array_a_real_board_emits():
    print('\nB. coverage is measured against real boards, not against itself')
    boards = _boards()
    if not boards:
        not_executed('coverage against sealed boards', 'no sealed board loaded')
        return
    seen, per = set(), []
    for d, z in boards:
        keys = {k.replace('__', '/', 1) for k in z.files}
        seen |= keys
        per.append((d, SK.unclassified(keys)))
    missing = SK.unclassified(seen)
    check(f'{len(boards)} board(s) emit {len(seen)} distinct array(s)',
          len(seen) > 0)
    check('  every one of them has a declared kind', not missing,
          f'UNCLASSIFIED: {missing[:6]}')
    worst = [(str(d), u) for d, u in per if u]
    check('  and no individual board carries an undeclared array', not worst,
          str(worst[:2]))


def test_C_the_declaration_matches_what_the_boards_HOLD():
    print('\nC. the declared emitted form is checked against the numbers')
    boards = _boards()
    if not boards:
        not_executed('empirical integrality', 'no sealed board loaded')
        return
    cur, legacy, n_cur, n_leg = [], set(), 0, 0
    for d, z in boards:
        gen = _generation(d)
        for f in z.files:
            key = f.replace('__', '/', 1)
            e = SK.EMITTED_KINDS.get(key)
            if not e or e['emitted'] != SK.INTEGER:
                # A CONTINUOUS declaration is not a promise: a continuous array
                # may happen to be integral on a small board, which is not a
                # contradiction.
                continue
            a = np.asarray(z[f], float)
            if a.size == 0:
                continue
            is_int = bool(np.all(np.abs(a - np.rint(a)) < 1e-9))
            if gen == 'CURRENT':
                n_cur += 1
                if not is_int:
                    cur.append((str(d).split('/')[-2], key))
            else:
                n_leg += 1
                if not is_int:
                    legacy.add(key)
    check(f'{n_cur} array instance(s) on CURRENT-generation boards checked',
          n_cur > 0)
    check('  every array declared INTEGER holds only integers on them',
          not cur, str(cur[:4]))
    # THE LEGACY BOARDS ARE A DIFFERENT STATEMENT AND MUST NOT BE SILENT.
    # `emitted` describes what the engine produces NOW. The corpus contains
    # boards sealed before the counts repair, and their fractional carries are
    # the defect `test_stat_contract` fences at its measured size -- 271,691
    # non-integer cells over 39 of 44 boards carrying a carries array.
    print(f'       legacy instances checked: {n_leg}; arrays non-integer on at '
          f'least one legacy board: {sorted(legacy)}')
    check('  and the legacy violations are confined to the fenced count family',
          legacy <= {'rushing/carries', 'team_volume/team_off_snaps',
                     'rush_category/rb', 'rush_category/te',
                     'rush_category/wr', 'rush_category/kneel',
                     'rush_category/fringe', 'rush_category/designed_qb',
                     'rush_player_pool/unmodelled_back_pool',
                     'receiving/targets', 'receiving/receptions'},
          f'a legacy board carries a non-integer array outside the known '
          f'fenced family: {sorted(legacy)}')


def test_D_the_discrepancies_are_the_known_defect_and_are_named():
    print('\nD. where support and emission disagree, that IS the defect')
    d = SK.discrepancies()
    check('the discrepancy list is non-empty -- the defect is real',
          bool(d), 'if this is empty the QB-yard defect has been repaired, '
                   'and this test must be updated deliberately')
    check('  it is exactly the QB-yard family and what inherits from it',
          set(d) == {'qb/pyds', 'qb/ryds', 'rushing_total/rushing_yards',
                     'dk_scoring/dk_points'}, str(d))
    for k in d:
        check(f'  {k} names the defect rather than only differing',
              SK.EMITTED_KINDS[k].get('defect') == 'QB_YARDS_CONTINUOUS_SHARE')


def test_E_it_does_not_contradict_the_publication_registry():
    print('\nE. two registries, one purpose each, and they must agree')
    shared, clash = 0, []
    for (layer, metric), spec in M.SUPPORTED.items():
        key = f'{layer}/{metric}'
        mine = SK.EMITTED_KINDS.get(key)
        if not mine:
            continue
        shared += 1
        # `metrics.SUPPORTED` uses the same two words for the same two things.
        if spec.get('kind') in ('count', 'yards') \
                and spec['kind'] != mine['kind']:
            clash.append((key, spec['kind'], mine['kind']))
    check(f'{shared} array(s) appear in both registries', shared > 0)
    check('  and none of them is given two different kinds', not clash,
          str(clash))
    check('  the publication registry is NOT extended by this one',
          len(M.SUPPORTED) < len(SK.EMITTED_KINDS),
          'adding internal arrays to SUPPORTED would change what boards '
          'publish')


def test_F_the_continuous_team_levels_are_not_counts():
    print('\nF. two arrays that look like counts and are not')
    for k in ('team_volume/team_dropbacks_part', 'team_volume/team_rz_carries'):
        check(f'{k} is a CONTINUOUS_LEVEL, not a count',
              SK.kind_of(k) == SK.CONTINUOUS_LEVEL, str(SK.kind_of(k)))
    # MEASURED, NOT ASSUMED. Across 112 sealed boards team_carries and
    # team_targets are all-integer on 3 -- the DET-BUF C3 boards, where C3
    # re-emitted a rinted level. I declared them counts on that one board's
    # evidence and the corpus check in test C refuted it.
    for k in ('team_carries', 'team_targets'):
        check(f'  team_volume/{k} is a CONTINUOUS_LEVEL too, on 112-board '
              f'evidence', SK.kind_of(f'team_volume/{k}') == SK.CONTINUOUS_LEVEL,
              str(SK.kind_of(f'team_volume/{k}')))
    check('  and team_off_snaps is the ONLY team_volume count',
          SK.kind_of('team_volume/team_off_snaps') == SK.COUNT
          and SK.by_kind(SK.CONTINUOUS_LEVEL) == sorted(
              f'team_volume/{k}' for k in ('team_carries',
                                           'team_dropbacks_part',
                                           'team_rz_carries', 'team_targets')),
          str(SK.by_kind(SK.CONTINUOUS_LEVEL)))
    check('  no emitted ARRAY is a probability, and none is declared one',
          SK.by_kind(SK.PROBABILITY) == [],
          'probabilities reach the board as derived thresholds, not draws')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_table_is_well_formed,
               test_B_it_covers_every_array_a_real_board_emits,
               test_C_the_declaration_matches_what_the_boards_HOLD,
               test_D_the_discrepancies_are_the_known_defect_and_are_named,
               test_E_it_does_not_contradict_the_publication_registry,
               test_F_the_continuous_team_levels_are_not_counts):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
