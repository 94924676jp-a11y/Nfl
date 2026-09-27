"""Three fixes made while resolving the Week-3 Early Only slate, pinned.

WHAT THIS GUARDS

DEF-081. `early_only.slate()` raised DK_POOL_SPANS_MORE_THAN_ONE_WINDOW for two
different faults: a pool that genuinely mixes kickoff windows, and a pool with
exactly one window that is not the one the caller declared. In the second case
the message is simply false -- the pool spans exactly one window. A caller
branching on that code to reject a mixed export would also have rejected a good
single-window export whose declared time disagreed. The codes are now separate,
and this pins that the mixed code is raised ONLY when len(kicks) > 1.

DEF-082a. `identity.reconcile()` needs `opponent` and `is_home`; `pool()` emits
`away`, `home`, `team`. Composing them raised KeyError: 'opponent'.
`as_identity_rows()` bridges it -- and the point of the test is not that it
returns rows, but that it NAMES what it derived and what it cannot supply.
`inj_flag` and `dk_depth` are None because the entries export does not carry
them, and None here means NOT SUPPLIED. A missing injury flag is not a clean
bill of health, so the absence has to be listed, not defaulted.

DEF-082b. `reconcile()` dropped `dk_id`. The DraftKings player id is the only
identifier that is authoritative for the contest, and losing it at the identity
step left every downstream consumer joining on name and team -- the join that
produced four false "FC-only" rows in DK_WEEK3_EARLY_BASELINE.md section 6. An
UNMATCHED row must still carry its dk_id: unresolved is not anonymous.

The behavioural rules are driven by synthetic input so they hold when a
different export arrives. Where the delivered Week-3 blob is used, it is used
only for facts about those pinned bytes.
"""
from __future__ import annotations

import csv
import gzip
import io
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs.salaries import early_only as EO                  # noqa: E402
from nfl.dfs.salaries import identity as ID                    # noqa: E402
from sportsplatform.governance.outcome import State            # noqa: E402

PASSED = FAILED = 0
BLOB = pathlib.Path(_ROOT) / 'nfl/vintage/dk_entries.2c82fe5560677f56.csv.gz'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _pool_row(**kw):
    d = {'dk_id': '44240001', 'dk_name': 'A Player', 'dk_pos': 'WR',
         'salary': 5000, 'team': 'PHI', 'dk_team': 'PHI', 'away': 'PHI',
         'home': 'DAL', 'kickoff': '09/27/2026 01:00PM ET',
         'game_info': 'PHI@DAL 09/27/2026 01:00PM ET',
         'name_and_id': 'A Player (44240001)', 'roster_position': 'WR/FLEX',
         'flex_eligible': True}
    d.update(kw)
    return d


# ============================================== DEF-081 the two window faults

def test_mixed_window_pool_uses_the_spanning_code():
    rows = [_pool_row(), _pool_row(kickoff='09/27/2026 04:25PM ET')]
    o = EO.slate(rows)
    check('a genuinely mixed pool refuses', o.state is not State.PASS, str(o.state))
    check('and it uses the SPANNING code',
          o.code == 'DK_POOL_SPANS_MORE_THAN_ONE_WINDOW', str(o.code))


def test_single_window_that_is_not_declared_uses_the_other_code():
    rows = [_pool_row(kickoff='09/27/2026 04:25PM ET')]
    o = EO.slate(rows, expected_kickoff='09/27/2026 01:00PM ET')
    check('a single-window pool against a wrong declaration refuses',
          o.state is not State.PASS, str(o.state))
    check('and it does NOT claim the pool spans two windows',
          o.code != 'DK_POOL_SPANS_MORE_THAN_ONE_WINDOW', str(o.code))
    check('it uses the declared-window code',
          o.code == 'DK_POOL_WINDOW_IS_NOT_THE_DECLARED', str(o.code))


def test_the_spanning_code_is_never_raised_for_one_window():
    """The regression DEF-081 actually was: one code, two meanings."""
    for kick in ('09/27/2026 01:00PM ET', '09/27/2026 04:25PM ET',
                 '09/28/2026 08:15PM ET'):
        o = EO.slate([_pool_row(kickoff=kick)],
                     expected_kickoff='09/27/2026 01:00PM ET')
        check(f'single window {kick!r} never reports spanning',
              o.code != 'DK_POOL_SPANS_MORE_THAN_ONE_WINDOW', str(o.code))


def test_a_matching_single_window_pool_resolves():
    o = EO.slate([_pool_row()], expected_kickoff='09/27/2026 01:00PM ET')
    check('the declared window matching resolves', o.state is State.PASS,
          f'{o.state} {o.code}')


# ==================================== DEF-082a schema bridge names its gaps

def test_as_identity_rows_supplies_what_reconcile_requires():
    out = EO.as_identity_rows([_pool_row()])
    rows = out['rows'] if isinstance(out, dict) else out
    r = rows[0]
    for f in ('opponent', 'is_home'):
        check(f'{f} is supplied', f in r, str(sorted(r)))
    check('opponent of a PHI row in PHI@DAL is DAL', r.get('opponent') == 'DAL',
          str(r.get('opponent')))
    check('and that row is not home', r.get('is_home') is False,
          str(r.get('is_home')))


def test_the_home_side_is_derived_the_other_way():
    out = EO.as_identity_rows([_pool_row(team='DAL')])
    rows = out['rows'] if isinstance(out, dict) else out
    r = rows[0]
    check('opponent of the DAL row is PHI', r.get('opponent') == 'PHI',
          str(r.get('opponent')))
    check('and that row IS home', r.get('is_home') is True,
          str(r.get('is_home')))


def test_derivation_is_declared_not_silent():
    """The declaration is PER ROW, not on a wrapper, and that is better.

    A wrapper's note is lost the moment a caller iterates the rows. Carried on
    the row, `derived_fields` and `absent_fields` travel with the evidence into
    whatever consumes it, so a row cannot be read without its provenance being
    in reach.
    """
    r = EO.as_identity_rows([_pool_row()])[0]
    d = r.get('derived_fields') or ()
    a = r.get('absent_fields') or ()
    check('the row declares what was derived', 'opponent' in d and 'is_home' in d,
          str(d))
    check('the row declares what is absent', 'inj_flag' in a and 'dk_depth' in a,
          str(a))
    check('derived and absent are disjoint', not (set(d) & set(a)),
          str(sorted(set(d) & set(a))))
    check('nothing is declared derived that is not present',
          all(k in r for k in d), str([k for k in d if k not in r]))


def test_a_club_absent_from_its_own_game_string_refuses_to_guess():
    """opponent=None is the honest answer, not "pick a side"."""
    r = EO.as_identity_rows([_pool_row(team='KC')])[0]
    check('opponent is None when the club is in neither slot',
          r.get('opponent') is None, repr(r.get('opponent')))
    check('is_home is None too, not False',
          r.get('is_home') is None, repr(r.get('is_home')))
    check('and the row still carries its dk_id', bool(r.get('dk_id')),
          repr(r.get('dk_id')))


def test_fields_the_export_cannot_supply_are_named_not_defaulted():
    out = EO.as_identity_rows([_pool_row()])
    rows = out['rows'] if isinstance(out, dict) else out
    r = rows[0]
    check('inj_flag is None, not an empty string', r.get('inj_flag') is None,
          repr(r.get('inj_flag')))
    check('dk_depth is None, not an empty string', r.get('dk_depth') is None,
          repr(r.get('dk_depth')))
    if isinstance(out, dict):
        a = out.get('absent_fields') or ()
        check('inj_flag is declared absent', 'inj_flag' in a, str(a))
        check('dk_depth is declared absent', 'dk_depth' in a, str(a))
    check('a missing injury flag is NOT rendered as healthy',
          r.get('inj_flag') not in ('', 'ACTIVE', 'HEALTHY', 0, False),
          repr(r.get('inj_flag')))


def test_the_bridge_drops_nothing():
    rows = [_pool_row(dk_id=str(44240000 + i)) for i in range(7)]
    out = EO.as_identity_rows(rows)
    got = out['rows'] if isinstance(out, dict) else out
    check('n_out equals n_in', len(got) == 7, f'{len(got)} of 7')


# ========================================= DEF-082b dk_id survives identity

def _roster():
    o = ID.canonical_roster(season=2026, week=3)
    return o.value if o.state is State.PASS else None


def test_reconcile_carries_dk_id():
    roster = _roster()
    if roster is None:
        print('  skip  canonical roster unavailable -- not a pass')
        return
    out = EO.as_identity_rows([_pool_row(dk_id='44246968')])
    rows = out['rows'] if isinstance(out, dict) else out
    rec = ID.reconcile(rows, roster)
    got = rec['rows'] if isinstance(rec, dict) else rec
    check('reconcile returned a row', len(got) == 1, str(len(got)))
    if got:
        check('dk_id survived the identity step', 'dk_id' in got[0],
              str(sorted(got[0])))
        check('and it is the id we put in', got[0].get('dk_id') == '44246968',
              repr(got[0].get('dk_id')))


def test_dk_id_survives_on_the_delivered_slate_including_unmatched():
    """On the pinned Week-3 blob: 457 rows, every one identifiable.

    The six UNMATCHED rows are the ones that matter here. An unresolved
    identity must still carry the contest's own id, or the row cannot even be
    reported -- unresolved is not anonymous.
    """
    if not BLOB.exists():
        print('  skip  delivered blob absent')
        return
    o = EO.pool(BLOB)
    if o.state is not State.PASS:
        check('pool() resolved the delivered blob', False, str(o.code))
        return
    roster = _roster()
    if roster is None:
        print('  skip  canonical roster unavailable -- not a pass')
        return
    out = EO.as_identity_rows(o.value)
    rows = out['rows'] if isinstance(out, dict) else out
    rec = ID.reconcile(rows, roster)
    got = rec['rows'] if isinstance(rec, dict) else rec
    check('nothing dropped through identity', len(got) == 457, str(len(got)))
    have = [r for r in got if r.get('dk_id')]
    check('every reconciled row carries a dk_id', len(have) == len(got),
          f'{len(got) - len(have)} rows without one')
    check('dk_ids are unique', len({r['dk_id'] for r in have}) == len(have),
          'duplicate dk_id')
    unmatched = [r for r in got
                 if not (r.get('gsis_id') or r.get('canonical_id'))]
    if unmatched:
        check('UNMATCHED rows still carry their dk_id',
              all(r.get('dk_id') for r in unmatched),
              str([r.get('dk_name') for r in unmatched
                   if not r.get('dk_id')]))


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
