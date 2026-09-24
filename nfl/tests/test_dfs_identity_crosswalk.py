"""The DK identity crosswalk, and the gate that stops a partial one.

WHAT THIS MODULE ASSERTS
========================
1. THE NORMALISATION IS NARROW IN BOTH DIRECTIONS. It joins spellings of one
   human (`A.J. Brown`/`AJ Brown`, a dropped `Jr.`) and it does NOT join two
   different humans. The second half matters more than the first: a
   normalisation that over-collapses silently assigns one player's salary to
   another player's projection, and nothing downstream would see it.
2. TEAM SCOPING IS LOAD-BEARING. The same name on the other team does not
   match. This is asserted rather than assumed because the index is keyed by
   team and a refactor that flattened it would still resolve the ATL/GB pool
   perfectly -- the real input cannot catch that regression, so a synthetic
   one does.
3. AMBIGUITY AND ABSENCE ARE REPORTED, NEVER GUESSED. Two same-named
   teammates yield AMBIGUOUS with both candidates listed and no `gsis_id`; an
   absent name yields UNRESOLVED. Neither silently picks one. Owner
   constraint: do not silently fuzzy-match uncertain identities.
4. A PARTIAL CROSSWALK CANNOT BE CONSUMED AS A COMPLETE ONE.
   `assert_complete` raises on both failure classes and names the count. This
   is the whole point of the module: this project's recurring defect is a
   step that returned something partial being read as success.
5. TEAM DST SITS ON ITS OWN IDENTITY AXIS. A team defence is classified, not
   matched against the player roster, and carries no `gsis_id`.
6. THE CAPTAIN SLOT IS PRICING, NOT IDENTITY. DK's CPTN row is the same human
   at 1.5x and collapses to one entry carrying both salaries.
7. EMPTY INPUTS RAISE RATHER THAN RETURNING A CLEAN ZERO.
8. THE REAL ATL/GB POOL RESOLVES COMPLETELY -- 33 distinct (player, team), 31
   exact, 2 DST, zero unresolved, zero ambiguous -- when the artifact is
   present. When it is absent this is BLOCKED, not passed.
"""
import glob
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs.identity_crosswalk import (  # noqa: E402
    CrosswalkError,
    assert_complete,
    crosswalk,
    normalise,
)

PASSED = FAILED = BLOCKED = 0

DK_SLICE = os.path.join(_ROOT, 'nfl', 'dfs', 'vintage',
                        'dk_showdown_2026_03_ATL_GB.slice.csv')
SNAPSHOTS = sorted(glob.glob(os.path.join(
    _ROOT, 'nfl', 'truth', 'snapshots', '2026_03_ATL_GB', '*.json')))


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def raises(fn, needle):
    """True when `fn` raises CrosswalkError whose message contains `needle`."""
    try:
        fn()
    except CrosswalkError as exc:
        return needle in str(exc)
    return False


def _snap(*players):
    return {'players': [dict(zip(('gsis_id', 'full_name', 'team'), p))
                        for p in players]}


def _row(name, team, pos, salary='1000'):
    return {'Player': name, 'Team': team, 'Pos': pos, 'Salary': salary}


def test_normalisation_joins_one_human_and_separates_two():
    check('A.J. Brown and AJ Brown are one key',
          normalise('A.J. Brown') == normalise('AJ Brown'))
    check('a trailing generational suffix is dropped',
          normalise('Marvin Harrison Jr.') == normalise('Marvin Harrison'))
    check('an interior period is removed, not the word',
          normalise('Amon-Ra St. Brown') == 'amonra st brown')
    # The over-collapse direction. These two are real 2026 RBs and both are in
    # the ATL pool; a normalisation that fused them would be catastrophic and
    # invisible.
    check('Brian Robinson and Bijan Robinson stay distinct',
          normalise('Brian Robinson') != normalise('Bijan Robinson'))
    check('normalisation of an empty name does not raise',
          normalise(None) == '')


def test_exact_match_within_team():
    art = crosswalk([_row('Jordan Love', 'GB', 'QB')],
                    _snap(('00-0036264', 'Jordan Love', 'GB')))
    check('a clean name resolves to exactly one gsis_id',
          art['counts'] == {'EXACT_WITHIN_TEAM': 1}
          and art['entries'][0]['gsis_id'] == '00-0036264')
    check('a fully resolved crosswalk passes the gate',
          assert_complete(art) is None)


def test_team_scoping_is_load_bearing():
    art = crosswalk([_row('Jordan Love', 'ATL', 'QB')],
                    _snap(('00-0036264', 'Jordan Love', 'GB')))
    check('the same name on the other team does not match',
          art['counts'] == {'UNRESOLVED_NO_MATCH': 1}
          and art['entries'][0]['gsis_id'] is None)
    check('an unresolved row fails the gate by name and count',
          raises(lambda: assert_complete(art), 'UNRESOLVED_NO_MATCH=1'))


def test_ambiguity_is_reported_never_guessed():
    art = crosswalk([_row('Mike Williams', 'ATL', 'WR')],
                    _snap(('00-0000001', 'Mike Williams', 'ATL'),
                          ('00-0000002', 'Mike Williams', 'ATL')))
    entry = art['entries'][0]
    check('two same-named teammates yield AMBIGUOUS, not a pick',
          entry['resolution'] == 'AMBIGUOUS_WITHIN_TEAM'
          and entry['gsis_id'] is None)
    check('both candidates are surfaced for a human to resolve',
          sorted(entry['candidates']) == ['00-0000001', '00-0000002'])
    check('an ambiguous row fails the gate by name and count',
          raises(lambda: assert_complete(art), 'AMBIGUOUS_WITHIN_TEAM=1'))


def test_dst_sits_on_its_own_axis():
    art = crosswalk([_row('Packers', 'GB', 'DST'), _row('Packers', 'GB', 'CPTN')],
                    _snap(('00-0036264', 'Jordan Love', 'GB')))
    entry = art['entries'][0]
    check('a team defence is classified, not matched',
          entry['resolution'] == 'TEAM_DST_AXIS' and entry['gsis_id'] is None)
    check('its CPTN and DST rows are one entry',
          entry['dk_row_count'] == 2)
    check('DST does not fail the completeness gate',
          assert_complete(art) is None)


def test_captain_slot_is_pricing_not_identity():
    art = crosswalk([_row('Jordan Love', 'GB', 'QB', '10000'),
                     _row('Jordan Love', 'GB', 'CPTN', '15000')],
                    _snap(('00-0036264', 'Jordan Love', 'GB')))
    check('CPTN collapses to one identity carrying both salaries',
          art['dk_distinct_player_team'] == 1
          and art['entries'][0]['dk_salaries'] == [10000, 15000])


def test_unnamed_roster_rows_are_counted_not_dropped_silently():
    art = crosswalk([_row('Jordan Love', 'GB', 'QB')],
                    _snap(('00-0036264', 'Jordan Love', 'GB'),
                          ('00-0099999', None, 'GB')))
    check('an unnamed roster row is excluded and counted',
          art['roster_players_unnamed_excluded'] == 1)


def test_empty_inputs_raise_rather_than_returning_a_clean_zero():
    check('an empty DK slice raises',
          raises(lambda: crosswalk([], _snap(('00-0036264', 'Jordan Love', 'GB'))),
                 'no rows'))
    check('a snapshot with no named players raises',
          raises(lambda: crosswalk([_row('Jordan Love', 'GB', 'QB')], _snap()),
                 'no named players'))


def test_the_real_atl_gb_pool_resolves_completely():
    if not os.path.exists(DK_SLICE):
        return blocked('real ATL/GB pool', f'DK slice absent: {DK_SLICE}')
    named = [p for p in SNAPSHOTS if 'CORRECTED_names' in p]
    if not named:
        return blocked('real ATL/GB pool',
                       'no name-corrected truth snapshot under '
                       'nfl/truth/snapshots/2026_03_ATL_GB/')
    from nfl.dfs.identity_crosswalk import build
    art = build(pathlib.Path(DK_SLICE), pathlib.Path(named[-1]))
    check('33 distinct (player, team) in the ATL/GB Showdown pool',
          art['dk_distinct_player_team'] == 33,
          f"got {art['dk_distinct_player_team']}")
    check('31 exact, 2 DST, nothing else',
          art['counts'] == {'EXACT_WITHIN_TEAM': 31, 'TEAM_DST_AXIS': 2},
          json.dumps(art['counts'], sort_keys=True))
    check('no roster player was dropped for want of a name',
          art['roster_players_unnamed_excluded'] == 0,
          str(art['roster_players_unnamed_excluded']))
    check('every resolved gsis_id is distinct',
          len({e['gsis_id'] for e in art['entries'] if e['gsis_id']})
          == art['counts']['EXACT_WITHIN_TEAM'])
    check('the real pool passes the completeness gate',
          assert_complete(art) is None)


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
