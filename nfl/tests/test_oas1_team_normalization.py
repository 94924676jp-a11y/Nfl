"""Team normalization, asserted TOTAL over every captured season.

NOT A UNIT TEST ON A FIXTURE. The claim gate 6 makes is about the real files,
so this reads the captured blobs and walks every team code in them. A table
that is total over a hand-written fixture and short by one code on the real
2016 schedule has proved nothing.
"""
from __future__ import annotations

import csv
import glob
import gzip
import io
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                     # noqa: E402
from nfl.research.oas1 import normalize_teams as NT                     # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []

#: The seasons OAS1 V1 declares: the prior season supplies the carryover and
#: the current season is forecast.
V1_SCOPE = (2025, 2026)


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _rows(path):
    txt = gzip.decompress(open(path, 'rb').read()).decode('utf-8')
    return list(csv.DictReader(io.StringIO(txt)))


def _codes(rows, fields):
    for r in rows:
        for f in fields:
            v = r.get(f)
            if v is not None:
                yield v


def test_A_the_table_is_well_formed():
    print('\nA. one table, no ambiguity')
    check('32 canonical codes', len(NT.CANONICAL) == 32, str(len(NT.CANONICAL)))
    check('  no duplicates', len(set(NT.CANONICAL)) == 32)
    check('  no alias is also canonical',
          not (set(NT.ALIASES) & set(NT.CANONICAL)),
          str(sorted(set(NT.ALIASES) & set(NT.CANONICAL))))
    check('  every alias maps INTO the canonical set',
          all(v['to'] in NT.CANONICAL for v in NT.ALIASES.values()))
    check('  every alias records WHY it exists',
          all(v.get('why') for v in NT.ALIASES.values()))
    check('  and whether this project has actually OBSERVED it',
          all(v.get('observed') for v in NT.ALIASES.values()))
    check('  LAR is declared as NOT OBSERVED, so its presence is not '
          'mistaken for evidence',
          'NOT OBSERVED' in NT.ALIASES['LAR']['observed'],
          NT.ALIASES['LAR']['observed'][:80])
    check('an unknown code is REFUSED, never passed through',
          NT.normalize('ZZZ').state is State.FAIL
          and NT.normalize('ZZZ').code == NT.CODE_UNRESOLVED)
    check('an empty possession team is NOT_A_CLUB, not coerced to one',
          NT.normalize('').state is State.FAIL
          and NT.normalize('').code == NT.CODE_NOT_A_CLUB)
    for a, want in (('OAK', 'LV'), ('SD', 'LAC'), ('STL', 'LA'),
                    ('LAR', 'LA')):
        o = NT.normalize(a)
        check(f'  {a} -> {want}',
              o.state is State.PASS and o.value == want,
              f'{o.state}[{o.code}] {o.value}')


def test_B_it_is_total_over_every_captured_pbp_season():
    print('\nB. total over the real pbp blobs')
    blobs = sorted(glob.glob(os.path.join(_ROOT, 'nfl/vintage/pbp_*.csv.gz')))
    check('at least one pbp blob is captured', bool(blobs), str(blobs))
    if not blobs:
        NOT_EXECUTED.append('B: no pbp capture exists yet')
        return
    for b in blobs:
        rows = _rows(b)
        name = os.path.basename(b)
        codes = list(_codes(rows, ('posteam', 'defteam', 'home_team',
                                   'away_team')))
        t = NT.assert_total(codes, label=name)
        check(f'{name}: normalization is TOTAL',
              t.state is State.PASS,
              f'{t.state}[{t.code}] unresolved={t.evidence.get("unresolved")}')
        if t.state is not State.PASS:
            continue
        n = NT.assert_thirty_two(codes, label=name)
        check(f'  and exactly 32 clubs survive', n.state is State.PASS,
              f'{n.state}[{n.code}] n={t.evidence["n_canonical_after"]}')
        check(f'  no unresolved code reaches a design matrix',
              t.evidence['unresolved'] == [])


def test_C_it_is_total_over_the_captured_schedules_which_DO_carry_aliases():
    print('\nC. total over schedules, which really does carry relocations')
    blobs = sorted(glob.glob(os.path.join(_ROOT,
                                          'nfl/vintage/schedules.*.csv.gz')))
    check('schedules blobs exist', bool(blobs), str(len(blobs)))
    if not blobs:
        NOT_EXECUTED.append('C: no schedules capture')
        return
    rows = _rows(blobs[-1])
    codes = list(_codes(rows, ('home_team', 'away_team')))
    t = NT.assert_total(codes, label='schedules')
    check('normalization is TOTAL over 1999-onward schedules',
          t.state is State.PASS,
          f'{t.state}[{t.code}] unresolved={t.evidence.get("unresolved")}')
    if t.state is not State.PASS:
        NOT_EXECUTED.append('C: schedules not total')
        return
    obs = set(t.evidence['observed'])
    # THIS IS WHAT MAKES THE TEST NON-VACUOUS. If the file carried only
    # current codes, a table with no aliases would pass and prove nothing.
    check('  the file really does carry relocation codes, so the aliases are '
          'exercised',
          {'OAK', 'SD', 'STL'} <= obs,
          str(sorted({'OAK', 'SD', 'STL'} - obs)))
    check('  and LAR is genuinely absent, as measured',
          'LAR' not in obs, 'LAR is present after all, which would make the '
                            'module note wrong')
    check('  35 observed codes collapse onto 32 franchises',
          t.evidence['n_observed'] == 35
          and t.evidence['n_canonical_after'] == 32,
          f'{t.evidence["n_observed"]} -> {t.evidence["n_canonical_after"]}')
    # Per season, exactly 32 after normalization -- the check that catches a
    # surviving undeclared alias.
    by_season = {}
    for r in rows:
        by_season.setdefault(r['season'], []).extend(
            [r.get('home_team'), r.get('away_team')])
    # 1999-2001 HELD 31 CLUBS AND THAT IS NOT A NORMALIZATION DEFECT.
    #
    # This check first asserted 32 for EVERY season and failed on 1999, 2000
    # and 2001 with 31. The refusal was right and the assertion was wrong:
    # the Houston Texans joined in 2002, so the league really had 31 teams in
    # those years. `assert_thirty_two` asserts the MODERN league and is
    # correct to refuse a 31-club frame; what was wrong was asking it about a
    # 31-club era.
    #
    # Left as a measurement rather than deleted, because "31 in 1999-2001, 32
    # from 2002" is a fact a future reader of a multi-season join needs.
    EXPANSION = 2002
    bad, pre = [], {}
    for s, cs in sorted(by_season.items()):
        n = NT.assert_thirty_two(cs, label=f'schedules {s}')
        if int(s) < EXPANSION:
            pre[s] = NT.assert_total(cs, label=s).evidence['n_canonical_after']
            continue
        if n.state is not State.PASS:
            bad.append((s, n.code, n.evidence.get('n_canonical_after')))
    check(f'  every season from {EXPANSION} on holds exactly 32 clubs after '
          f'normalization', not bad, f'{len(bad)} bad season(s): {bad[:4]}')
    check('  and the pre-expansion seasons hold 31, which is the league that '
          'existed, not a mapping failure',
          bool(pre) and set(pre.values()) == {31},
          str(pre))
    check('  each of those seasons is still TOTAL -- every code maps, there '
          'are simply fewer clubs',
          all(NT.assert_total(by_season[s], label=s).state is State.PASS
              for s in pre), str(sorted(pre)))
    check('  including the relocation years',
          all(str(y) in by_season for y in (2016, 2017, 2019, 2020)),
          str(sorted(by_season)[:4]))


def test_D_the_V1_scope_is_the_identity_map_and_says_so():
    print('\nD. at OAS1 V1 scope, normalization changes nothing')
    blobs = [p for p in sorted(glob.glob(
        os.path.join(_ROOT, 'nfl/vintage/pbp_*.csv.gz')))
        if any(str(y) in os.path.basename(p) for y in V1_SCOPE)]
    check(f'both V1-scope seasons {V1_SCOPE} are captured',
          len(blobs) == len(V1_SCOPE), str([os.path.basename(b) for b in blobs]))
    if len(blobs) != len(V1_SCOPE):
        NOT_EXECUTED.append('D: a V1-scope season is not captured')
        return
    codes = []
    for b in blobs:
        codes.extend(_codes(_rows(b), ('posteam', 'defteam', 'home_team',
                                       'away_team')))
    t = NT.assert_total(codes, label='V1 scope')
    check('it is total', t.state is State.PASS, f'{t.state}[{t.code}]')
    check('  and it is the IDENTITY map over this scope -- no code is '
          'remapped at all',
          t.evidence['is_identity_map'] is True
          and t.evidence['aliases_used'] == [],
          str(t.evidence.get('aliases_used')))
    check('  32 clubs, not 33',
          t.evidence['n_canonical_after'] == 32,
          str(t.evidence['n_canonical_after']))
    check('  which means gate 6 is satisfied here WITHOUT relying on any '
          'alias, and the relocations only bite if the scope reaches 2019',
          t.evidence['n_observed'] == 32, str(t.evidence['n_observed']))


def test_E_a_surviving_undeclared_alias_is_caught():
    print('\nE. the check that would catch a 33rd club')
    full = list(NT.CANONICAL)
    check('32 canonical codes pass the count check',
          NT.assert_thirty_two(full, label='synthetic').state is State.PASS)
    # LAR and LA both present, with LAR NOT in the table: 33 clubs.
    import copy
    saved = dict(NT.ALIASES)
    saved_map = dict(NT._MAP)
    try:
        NT.ALIASES.pop('LAR')
        NT._MAP.pop('LAR')
        o = NT.assert_total(full + ['LAR'], label='synthetic')
        check('an UNDECLARED alias is refused as unresolved',
              o.state is State.FAIL and o.code == NT.CODE_UNRESOLVED
              and o.evidence['unresolved'] == ['LAR'],
              f'{o.state}[{o.code}] {o.evidence.get("unresolved")}')
    finally:
        NT.ALIASES.clear(); NT.ALIASES.update(saved)
        NT._MAP.clear(); NT._MAP.update(saved_map)
    check('  the table was restored after the probe',
          'LAR' in NT.ALIASES and NT.normalize('LAR').value == 'LA')
    # A declared alias that duplicates a canonical club still yields 32.
    o = NT.assert_thirty_two(full + ['LAR'], label='synthetic+LAR')
    check('a DECLARED alias collapses instead of becoming a 33rd club',
          o.state is State.PASS and o.evidence['n_canonical_after'] == 32,
          f'{o.state}[{o.code}] n={o.evidence.get("n_canonical_after")}')
    # 31 clubs is not "normalized", it is incomplete, and it must not pass.
    o = NT.assert_thirty_two(full[:-1], label='synthetic-31')
    check('31 clubs is refused, because coverage is not totality',
          o.state is State.FAIL and o.code == NT.CODE_WRONG_COUNT,
          f'{o.state}[{o.code}]')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_table_is_well_formed,
               test_B_it_is_total_over_every_captured_pbp_season,
               test_C_it_is_total_over_the_captured_schedules_which_DO_carry_aliases,
               test_D_the_V1_scope_is_the_identity_map_and_says_so,
               test_E_a_surviving_undeclared_alias_is_caught):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
