"""Q7 panel: non-degeneracy, and a dropback check that is NOT a tautology.

WHAT THIS PROTECTS, AND WHY IT EXISTS.

`q7/panel.py` incremented every QB counter inside `if pid:` with
`pid = passer_player_id`. A `qb_scramble` play carries NO passer id -- nflverse
attributes it to `rusher_player_id` -- so the `scr` column was built as a
structurally-zero column: 1 scramble across 4,025 QB-games against 5,864
scrambles in the same six seasons of play-by-play.

THE EXISTING CHECK COULD NOT SEE IT. `db` is COMPOSED as `att + sacks + scr`
and then asserted to equal `att + sacks + scr`. That identity is true of any
three numbers whatsoever, including a zero. A tautology is not a test. It also
displaced the one check that WOULD have caught this: nflverse publishes its own
`qb_dropback` flag, and the panel never compared against it.

So this module asserts two things the old module could not:

  1. NON-DEGENERACY. Every built count column must vary. A column whose total
     is 0 or 1 across thousands of rows, or which is non-zero on at most one
     row, is a build failure and not a result. This is the generalised guard:
     this repository has now produced this failure mode twice (`qb2/build_qb.py`
     names the first), and the third instance should fail the build.

  2. EXTERNAL RECONCILIATION. The composed dropback total is compared against
     nflverse's own `qb_dropback`, re-derived HERE from the six raw files
     rather than read from any artifact the builder wrote, so the builder
     cannot certify itself. The residual is stated and bounded by a derived
     tolerance, not by a round number.

The composed identity is still checked. It is no longer the only check.
"""
from __future__ import annotations

import collections
import csv
import gzip
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.q7 import panel as PAN                          # noqa: E402

PASSED = FAILED = 0

# Count columns the builder composes. Every one of them must vary.
QB_COUNTS = ('db', 'att', 'cmp', 'sacks', 'scr', 'pyds', 'ptd', 'int')
RECV_COUNTS = ('targets', 'rec', 'rec_yds', 'rec_td')

# THE DERIVED TOLERANCE, not a round number.
#
# The panel's frozen definitions are `attempt = pass_attempt & !sack & !spike`
# and `dropback = attempts + sacks + scrambles`. nflverse's `qb_dropback` is
# set on attempts, sacks and scrambles too, but it is ZERO on a handful of rows
# that satisfy the panel's attempt definition anyway: measured over 2020-2025
# REG there are 9 such rows -- 7 two-point conversion passes, one replay-
# reversed sack inside a penalty `no_play`, and one blocked field goal carrying
# `pass_attempt = 1`. The panel must therefore sit ABOVE nflverse by exactly
# that count and by nothing else, so the tolerance is those rows re-derived
# below, not a percentage. Zero unexplained is the assertion.
MAX_UNEXPLAINED_DROPBACKS = 0

# Per player-game, the same reasoning bounds how many rows may disagree.
MAX_UNEXPLAINED_PLAYER_GAMES = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def degenerate(rows, columns):
    """Columns that do not vary. The rule, stated once and used everywhere.

    A count column is degenerate when its total over the frame is 0 or 1, or
    when at most one row carries a non-zero value. Both shapes are what a
    counter that is never reached looks like from the outside.
    """
    out = {}
    for c in columns:
        vals = [_i(r[c]) for r in rows]
        total = sum(vals)
        nonzero = sum(1 for v in vals if v)
        if total <= 1 or nonzero <= 1:
            out[c] = {'total': total, 'nonzero_rows': nonzero,
                      'n_rows': len(vals)}
    return out


# ------------------------------------------------- 1. non-degeneracy
def test_a_no_built_count_column_is_degenerate():
    for name, path, cols in (('qb', PAN.QB, QB_COUNTS),
                             ('receiver', PAN.RECV, RECV_COUNTS)):
        if not path.exists():
            check(f'the {name} panel exists', False, str(path))
            continue
        with gzip.open(path, 'rt', newline='') as fh:
            rows = list(csv.DictReader(fh))
        bad = degenerate(rows, cols)
        check(f'no {name}-panel count column is degenerate over '
              f'{len(rows)} rows', not bad, str(bad))


def test_b_the_builder_itself_refuses_a_degenerate_column():
    fn = getattr(PAN, 'assert_not_degenerate', None)
    if fn is None:
        check('panel.assert_not_degenerate exists, so the BUILD fails rather '
              'than the artifact shipping', False, 'missing')
        return
    ok_rows = [{'a': 1, 'b': 2}, {'a': 0, 'b': 3}, {'a': 4, 'b': 0}]
    try:
        fn(ok_rows, ('a', 'b'), 'FIXTURE')
        check('a varying column passes the guard', True)
    except SystemExit as e:                                       # noqa: BLE001
        check('a varying column passes the guard', False, str(e))
    # the exact shape of the defect: one non-zero row in thousands
    seeded = [{'a': 1, 'scr': 0} for _ in range(4000)]
    seeded[0]['scr'] = 1
    try:
        fn(seeded, ('a', 'scr'), 'FIXTURE')
        check('a structurally-zero column FAILS the guard', False,
              'the guard returned instead of raising')
    except SystemExit as e:                                       # noqa: BLE001
        check('a structurally-zero column FAILS the guard', True,
              str(e)[:80])
    all_zero = [{'a': 1, 'scr': 0} for _ in range(50)]
    try:
        fn(all_zero, ('a', 'scr'), 'FIXTURE')
        check('an all-zero column FAILS the guard too', False, 'returned')
    except SystemExit:                                            # noqa: BLE001
        check('an all-zero column FAILS the guard too', True)


# ------------------------------------- 2. external reconciliation
def _nflverse_reference():
    """Re-derived HERE from the raw files. Not read from any built artifact.

    Two references are returned, because they answer different questions.

      RAW       nflverse's own `qb_dropback`, counted per player-game with the
                same attribution the panel uses -- passer id, or rusher id on a
                play that carries none. This is the honest external number and
                the residual against it is REPORTED.

      EXPLAINED the raw reference plus the rows that satisfy the panel's frozen
                `attempt` definition (`pass_attempt & !sack & !spike`) while
                nflverse leaves `qb_dropback` at 0 -- replay reversals and
                penalty `no_play` rows carrying `pass_attempt = 1`, and one
                blocked field goal. The panel must equal this one EXACTLY, on
                every player-game. That is the derived tolerance: an enumerated
                set of rows, not a percentage.

    Scrambles are referenced as `qb_scramble & qb_dropback & !sack`, charged to
    `rusher_player_id`. The `!sack` clause is one 2020 row (2020_16_PHI_DAL)
    carrying both flags -- a scramble reversed to a sack on replay. A play
    cannot be both, and the panel counts it as the sack.
    """
    raw = collections.Counter()
    scr = collections.Counter()
    extra = []
    for s in PAN.SEASONS:
        p = PAN.RAW / f'play_by_play_{s}.csv.gz'
        if not p.exists():
            return None, None, None
        with gzip.open(p, 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                gid, off = r.get('game_id'), r.get('posteam')
                if not gid or not off:
                    continue
                d = _i(r.get('qb_dropback'))
                sk = _i(r.get('sack'))
                sc = _i(r.get('qb_scramble'))
                sp = _i(r.get('qb_spike'))
                pa = _i(r.get('pass_attempt'))
                pid = (r.get('passer_player_id') or '').strip()
                rid = (r.get('rusher_player_id') or '').strip()
                if pa and not sk and not sp and not d:
                    extra.append((gid, off, pid))
                if sc and d and not sk and rid:
                    scr[(gid, off, rid)] += 1
                if d:
                    who = pid or rid
                    if who:
                        raw[(gid, off, who)] += 1
    explained = collections.Counter(raw)
    for k in extra:
        explained[k] += 1
    return {'raw': raw, 'explained': explained, 'n_extra': len(extra)}, scr, extra


def test_c_composed_dropbacks_reconcile_against_nflverse_qb_dropback():
    if not PAN.QB.exists():
        check('the qb panel exists', False)
        return
    ref, ref_scr, extra = _nflverse_reference()
    if ref is None:
        check('the six raw play-by-play files are present', False)
        return
    rows = PAN.load_qb()
    panel = {(r['game_id'], r['team'], r['gsis_id']): r['db'] for r in rows}
    raw, explained = ref['raw'], ref['explained']
    panel_db, raw_db = sum(panel.values()), sum(raw.values())
    # reported, not asserted away
    print(f'    panel db {panel_db}  nflverse qb_dropback {raw_db}  '
          f'residual {panel_db - raw_db}  enumerated {ref["n_extra"]}')
    check('the residual against nflverse is exactly the enumerated set of '
          'attempt rows nflverse does not flag, and nothing else',
          panel_db - raw_db == ref['n_extra'] == MAX_UNEXPLAINED_DROPBACKS
          + ref['n_extra'],
          f'{panel_db} - {raw_db} = {panel_db - raw_db} vs '
          f'{ref["n_extra"]} enumerated')
    keys = set(panel) | set(explained)
    bad = sorted(k for k in keys
                 if panel.get(k, 0) != explained.get(k, 0))
    check('every QB-game carries the explained dropback count exactly',
          len(bad) <= MAX_UNEXPLAINED_PLAYER_GAMES,
          f'{len(bad)} of {len(keys)} disagree: {bad[:3]}')
    raw_keys = set(panel) | set(raw)
    agree = sum(1 for k in raw_keys if panel.get(k, 0) == raw.get(k, 0))
    check('the overwhelming majority of QB-games match raw nflverse too',
          agree >= len(raw_keys) - ref['n_extra'],
          f'{agree} of {len(raw_keys)}')
    panel_scr = sum(r['scr'] for r in rows)
    check('the panel scramble total matches the play-by-play',
          panel_scr == sum(ref_scr.values()),
          f'panel {panel_scr} vs pbp {sum(ref_scr.values())}')
    check('  and the column is not degenerate, which is the whole defect',
          panel_scr > 1000 and sum(1 for r in rows if r['scr']) > 1000,
          f'{sum(1 for r in rows if r["scr"])} rows carry a scramble')
    by = {(r['game_id'], r['team'], r['gsis_id']): r['scr'] for r in rows}
    scr_dis = sorted(k for k in set(by) | set(ref_scr)
                     if by.get(k, 0) != ref_scr.get(k, 0))
    check('  and matches per QB-game, not only in total',
          not scr_dis, f'{len(scr_dis)} disagree: {scr_dis[:3]}')


def test_d_the_composed_identity_still_holds_but_is_not_the_only_check():
    if not PAN.QB.exists():
        check('the qb panel exists', False)
        return
    rows = PAN.load_qb()
    bad = [r for r in rows if r['att'] + r['sacks'] + r['scr'] != r['db']]
    check('attempts + sacks + scrambles == dropbacks on every row',
          not bad, f'{len(bad)} of {len(rows)}')
    check('the identity is a tautology on composed counters and is recorded '
          'as one', 'tautology' in (PAN.reconcile.__doc__ or '').lower())
    check('completions never exceed attempts',
          not [r for r in rows if r['cmp'] > r['att']])
    check('passing touchdowns never exceed completions',
          not [r for r in rows if r['ptd'] > r['cmp']])
    check('the frame holds no 2026 row',
          max(r['season'] for r in rows) <= 2025,
          str(max(r['season'] for r in rows)))


def test_f_the_reconciliation_is_published_not_only_asserted():
    if not PAN.RECONCILIATION.exists():
        check('the reconciliation artifact exists', False,
              str(PAN.RECONCILIATION))
        return
    import json
    d = json.loads(PAN.RECONCILIATION.read_text())
    check('it names the external reference',
          'qb_dropback' in d.get('reference', ''), d.get('reference', ''))
    check('it reports the residual rather than hiding it',
          'residual_panel_minus_nflverse' in d,
          str(d.get('residual_panel_minus_nflverse')))
    check('it reports how many player-games disagree with raw nflverse',
          'player_games_disagreeing_with_raw_nflverse' in d,
          str(d.get('player_games_disagreeing_with_raw_nflverse')))
    check('nothing is left unexplained',
          d.get('unexplained_player_games') == 0,
          str(d.get('unexplained_player_games')))
    check('the tolerance is derived, not a round number',
          'not a percentage' in d.get('derivation', ''))


# --------------------------------------------- 3. supersession
def test_e_the_superseded_panel_is_preserved_not_overwritten():
    sup = getattr(PAN, 'SUPERSEDED_QB', None)
    if sup is None:
        check('panel.py names the artifact it supersedes', False, 'missing')
        return
    check('the superseded panel is still on disk, unedited', sup.exists(),
          str(sup))
    check('  and the corrected panel is a different file',
          PAN.QB.resolve() != sup.resolve(), f'{PAN.QB.name} vs {sup.name}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
