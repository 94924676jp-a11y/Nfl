"""The DK salary file is a universe and a price list, and nothing else.

WHAT THIS GUARDS

The delivered file carries fourteen columns of third-party projection, market
and optimizer output beside the five that name a player and his price. The
whole point of the ingest is that the first group can never reach a football
layer. A docstring saying so is not a guard; a test that the loader does not
RETURN them is.

Three further properties, each of which has a live failure mode:

  * the header is on line 2, behind a row of twenty-three commas. A reader
    that takes line 1 produces 537 rows keyed by the empty string and raises
    nothing -- the shape of the 7,926-row export this project already had to
    diagnose once;
  * eligibility is a fact about a CONTEST, and this file holds all 32 clubs.
    Inferring the main slate from the file would be a guess wearing a
    measurement's clothes, so the loader defers;
  * a DK player the model cannot project is a coverage defect. The join must
    make it impossible to paper over one with the projection sitting in the
    next column of the same row.

The counts that appear below are the DELIVERED FILE's, which is a fixed
artifact pinned by sha256 -- 537 rows is a property of those bytes, not of
today. The behavioural rules are driven by synthetic input so they hold when
a different file arrives.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs.salaries import dk_universe as DK                 # noqa: E402
from nfl.dfs.salaries import identity as ID                    # noqa: E402
from sportsplatform.governance.outcome import State            # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _synthetic(rows, leading_blank=True, header=None):
    """A DK-shaped CSV on disk, with the delivered file's quirks by default."""
    hdr = header or list(DK.KEPT_COLUMNS) + list(DK.RECONCILE_ONLY_COLUMNS) \
        + sorted(DK.FORBIDDEN_COLUMNS)
    buf = io.StringIO()
    w = csv.writer(buf)
    if leading_blank:
        w.writerow([''] * len(hdr))
    w.writerow(hdr)
    for r in rows:
        w.writerow([r.get(c, '') for c in hdr])
    fd, name = tempfile.mkstemp(suffix='.csv.gz')
    os.close(fd)
    pathlib.Path(name).write_bytes(gzip.compress(buf.getvalue().encode()))
    return name


def _row(**kw):
    d = {'Player': 'A Player', 'Pos': 'WR', 'Salary': '5000',
         'Team': 'PHI', 'Opp': '@ DAL', 'Inj': '', 'pDepth': 'WR1'}
    d.update({k: str(v) for k, v in kw.items()})
    for c in DK.FORBIDDEN_COLUMNS:
        d.setdefault(c, '99.9')
    return d


# ===================================== the column wall

def test_no_projection_column_survives_the_loader():
    """The wall. Every forbidden column is set to 99.9 and must not come back."""
    name = _synthetic([_row(Player='X'), _row(Player='Y')])
    try:
        o = DK.load(name)
        check('the file loads', o.state is State.PASS, f'{o.state} {o.code}')
        keys = set().union(*(set(r) for r in o.value))
        leaked = sorted(k for k in keys
                        if k in DK.FORBIDDEN_COLUMNS
                        or k.lower().replace(' ', '_') in
                        {c.lower().replace(' ', '_')
                         for c in DK.FORBIDDEN_COLUMNS})
        check('no forbidden column name appears in a returned row',
              not leaked, str(leaked))
        blob = json.dumps(o.value)
        check('and the value 99.9 -- which every forbidden column carried -- '
              'appears nowhere in the returned rows', '99.9' not in blob)
        check('the loader reports which columns it dropped, by name',
              set(o.evidence['columns_dropped']) == set(DK.FORBIDDEN_COLUMNS),
              str(o.evidence['columns_dropped']))
    finally:
        os.unlink(name)


def test_the_forbidden_list_covers_every_projection_and_market_field():
    """Named one by one, so adding a column to the file cannot quietly widen
    what is authorised."""
    must = ('Def v Pos', 'VegasPts', 'STDV', 'FC', 'My', 'Diff', 'Floor',
            'Ceiling', 'FC Proj', 'My Proj', 'Exp.', 'Used', 'Con.', 'Value',
            '2025 Avg', '2026 Avg')
    for c in must:
        check(f'{c} is forbidden', c in DK.FORBIDDEN_COLUMNS)
        check(f'  and says which family it belongs to',
              len(DK.FORBIDDEN_COLUMNS[c]) > 10)
    check('salary, name, position, team and opponent are the kept set',
          set(DK.KEPT_COLUMNS) == {'Player', 'Pos', 'Salary', 'Team', 'Opp'},
          str(DK.KEPT_COLUMNS))
    check('Inj and pDepth are kept for RECONCILIATION only, not as truth',
          set(DK.RECONCILE_ONLY_COLUMNS) == {'Inj', 'pDepth'})


def test_asking_for_a_projection_column_raises_rather_than_returning_one():
    try:
        DK.column_disposition('VegasPts')
        check('asking for VegasPts raises', False, 'it returned')
    except DK.ForbiddenColumn as exc:
        check('asking for VegasPts raises ForbiddenColumn', True)
        check('  and the message says there is no flag that turns it on',
              'no flag' in str(exc), str(exc)[:120])
    check('a kept column answers normally',
          DK.column_disposition('Salary') == 'KEPT_SALARY_AND_UNIVERSE')


# ===================================== the header trap

def test_the_header_is_found_not_assumed():
    with_blank = _synthetic([_row(Player='X')], leading_blank=True)
    without = _synthetic([_row(Player='X')], leading_blank=False)
    try:
        a, b = DK.load(with_blank), DK.load(without)
        check('a file with a leading blank row parses',
              a.state is State.PASS, f'{a.state} {a.code}')
        check('  and reports the header was on row 1, not row 0',
              a.evidence['header_row_index'] == 1,
              str(a.evidence['header_row_index']))
        check('a file without one parses too',
              b.state is State.PASS and b.evidence['header_row_index'] == 0)
        check('and both yield the same row content, so the blank line changes '
              'nothing but the offset', a.value == b.value)
    finally:
        os.unlink(with_blank)
        os.unlink(without)


def test_a_file_with_no_player_column_refuses_rather_than_inventing_one():
    name = _synthetic([_row()], header=['Nombre', 'Pos', 'Salary'])
    try:
        DK.load(name)
        check('a file with no Player column raises', False, 'it parsed')
    except DK.HeaderNotFound as exc:
        check('a file with no Player column raises HeaderNotFound', True)
        check('  and explains that a bad header raises nothing on its own',
              'raises nothing' in str(exc), str(exc)[:140])
    finally:
        os.unlink(name)


# ===================================== eligibility is not inferred

def test_the_main_slate_defers_without_a_contest_game_set():
    name = _synthetic([_row(Player='A', Team='PHI', Opp='@ DAL'),
                       _row(Player='B', Team='BUF', Opp='vs DET')])
    try:
        rows = DK.load(name).value
        o = DK.main_slate(rows)
        check('without a contest game set the slate DEFERS',
              o.state is State.DEFERRED, f'{o.state} {o.code}')
        check('  under a code naming what is missing',
              o.code == 'DK_MAIN_SLATE_GAME_SET_NOT_SUPPLIED', o.code)
        check('  and it says what it is owed',
              'contest' in str(o.evidence.get('owed')).lower(),
              str(o.evidence.get('owed')))
        check('it does NOT fall back on the usual shape of a main slate',
              'not inferred' in o.detail.lower()
              or 'NOT inferred' in o.detail)
    finally:
        os.unlink(name)


def test_an_already_played_game_is_excluded_on_the_clock_not_on_a_dk_rule():
    name = _synthetic([_row(Player='A', Team='BUF', Opp='vs DET'),
                       _row(Player='B', Team='PHI', Opp='@ DAL')])
    try:
        o = DK.main_slate(DK.load(name).value)
        check('the played game is named as excluded',
              [sorted(g) for g in o.evidence['excluded_already_played']]
              == [['BUF', 'DET']],
              str(o.evidence['excluded_already_played']))
        check('  and its row count is reported',
              o.evidence['excluded_already_played_rows'] == 1,
              str(o.evidence['excluded_already_played_rows']))
        check('every other game stays UNRESOLVED rather than excluded',
              o.state is State.DEFERRED)
    finally:
        os.unlink(name)


def test_a_contest_naming_a_game_the_file_lacks_is_a_coverage_defect():
    name = _synthetic([_row(Player='A', Team='PHI', Opp='@ DAL')])
    try:
        rows = DK.load(name).value
        o = DK.main_slate(rows, contest_games=[('PHI', 'DAL'), ('GB', 'NYJ')])
        check('a contest wider than the file FAILS', o.state is State.FAIL,
              f'{o.state} {o.code}')
        check('  rather than quietly returning the smaller universe',
              o.code == 'DK_CONTEST_GAME_NOT_IN_FILE', o.code)
    finally:
        os.unlink(name)


def test_a_supplied_contest_game_set_resolves_the_slate():
    name = _synthetic([_row(Player='A', Team='PHI', Opp='@ DAL'),
                       _row(Player='B', Team='GB', Opp='@ NYJ')])
    try:
        rows = DK.load(name).value
        o = DK.main_slate(rows, contest_games=[('PHI', 'DAL')])
        check('with a contest game set the slate resolves',
              o.state is State.PASS, f'{o.state} {o.code}')
        check('  to exactly the rows on that game',
              len(o.value) == 1 and o.value[0]['dk_name'] == 'A',
              str([r['dk_name'] for r in o.value]))
    finally:
        os.unlink(name)


# ===================================== identity

def _roster(*players):
    return [{'gsis_id': g, 'full_name': n, 'team': t, 'position': p,
             'status': 'ACT'} for g, n, t, p in players]


def test_every_dk_row_leaves_classified_and_none_is_dropped():
    name = _synthetic([_row(Player='Real Guy', Team='PHI'),
                       _row(Player='Nobody At All', Team='PHI'),
                       _row(Player='PHI', Pos='DST', Team='PHI')])
    try:
        rows = DK.load(name).value
        rec = ID.reconcile(rows, _roster(('00-1', 'Real Guy', 'PHI', 'WR')))
        check('as many rows out as in', rec['n_in'] == rec['n_out'] == 3)
        st = [r['status'] for r in rec['rows']]
        check('the known player is MATCHED', DK.STATUS_MATCHED in st)
        check('the unknown one is UNMATCHED, not dropped',
              DK.STATUS_UNMATCHED in st, str(st))
        check('the defence is its own class, not an unmatched person',
              DK.STATUS_DST in st, str(st))
        dst = [r for r in rec['rows'] if r['status'] == DK.STATUS_DST][0]
        check('  and says why: no team-defence outputs exist',
              'team-defence' in (dst['note'] or ''), str(dst['note']))
    finally:
        os.unlink(name)


def test_two_players_of_the_same_name_are_ambiguous_not_picked():
    name = _synthetic([_row(Player='Josh Allen', Team='BUF')])
    try:
        rows = DK.load(name).value
        rec = ID.reconcile(rows, _roster(('00-1', 'Josh Allen', 'BUF', 'QB'),
                                         ('00-2', 'Josh Allen', 'BUF', 'LB')))
        r = rec['rows'][0]
        check('two canonical players of one name give AMBIGUOUS',
              r['status'] == DK.STATUS_AMBIGUOUS, r['status'])
        check('  no gsis_id is chosen', r['gsis_id'] is None)
        check('  and both candidates are named in the note',
              '00-1' in (r['note'] or '') and '00-2' in (r['note'] or ''),
              str(r['note']))
    finally:
        os.unlink(name)


def test_matching_never_uses_edit_distance():
    """A near-miss must NOT match. This is the property a fuzzy matcher breaks."""
    name = _synthetic([_row(Player='Jalen Hurts', Team='PHI')])
    try:
        rows = DK.load(name).value
        rec = ID.reconcile(rows, _roster(('00-1', 'Jalen Hurt', 'PHI', 'QB')))
        check('a one-character difference does NOT match',
              rec['rows'][0]['status'] == DK.STATUS_UNMATCHED,
              rec['rows'][0]['status'])
    finally:
        os.unlink(name)


def test_normalisation_collapses_punctuation_and_suffixes_only():
    check("A.J. and AJ normalise together",
          DK._norm_name('A.J. Brown') == DK._norm_name('AJ Brown'))
    check('a generational suffix is stripped',
          DK._norm_name('Marvin Harrison Jr.') == DK._norm_name(
              'Marvin Harrison'))
    check('but two different surnames never collapse',
          DK._norm_name('Josh Allen') != DK._norm_name('Josh Alle'))


def test_an_alias_needs_a_unique_same_club_answer_or_it_is_not_applied():
    """A stale alias degrades to a refusal, never to a wrong join."""
    name = _synthetic([_row(Player='Hollywood Brown', Team='PHI')])
    try:
        rows = DK.load(name).value
        good = ID.reconcile(rows, _roster(
            ('00-1', 'Marquise Brown', 'PHI', 'WR')))['rows'][0]
        check('a declared alias with one same-club answer MATCHES',
              good['status'] == DK.STATUS_MATCHED, good['status'])
        check('  under its own method, not hidden inside EXACT',
              good['match_method'] == DK.MATCH_ALIAS, str(good['match_method']))
        check('  and carries the evidence that made it a fact',
              'nickname' in (good['note'] or ''), str(good['note'])[:80])
        gone = ID.reconcile(rows, _roster(
            ('00-9', 'Someone Else', 'PHI', 'WR')))['rows'][0]
        check('an alias whose target is absent does NOT match',
              gone['status'] == DK.STATUS_UNMATCHED, gone['status'])
    finally:
        os.unlink(name)


def test_every_alias_carries_its_evidence():
    check('the alias table is small and explicit',
          isinstance(DK.NAME_ALIASES, dict) and len(DK.NAME_ALIASES) < 25)
    for key, a in DK.NAME_ALIASES.items():
        check(f'{key} names a canonical target', bool(a.get('canonical')))
        check(f'{key} states the evidence, not a similarity',
              len(a.get('evidence', '')) > 60)


# ===================================== the delivered artifact

def test_the_delivered_file_is_pinned_and_reproduces():
    o = DK.load()
    if not check('the delivered blob is in the vintage store',
                 o.state is State.PASS, f'{o.state} {o.code}'):
        return
    check('its sha256 matches the one declared in the module',
          o.evidence['sha256_matches_declared'], o.evidence['sha256'])
    check('537 rows', o.evidence['n_rows'] == 537, str(o.evidence['n_rows']))
    check('24 columns', o.evidence['n_columns'] == 24,
          str(o.evidence['n_columns']))
    check('17 of them dropped as projection/market/optimizer output',
          o.evidence['n_columns_dropped'] == 17,
          str(o.evidence['n_columns_dropped']))
    u = DK.raw_universe(o.value)
    check('32 teams', u['n_teams'] == 32, str(u['n_teams']))
    check('16 matchups', u['n_matchups'] == 16, str(u['n_matchups']))
    check('no missing salary', u['n_salary_missing'] == 0)
    check('salaries span 2000 to 8500',
          (u['salary_min'], u['salary_max']) == (2000, 8500),
          f"{u['salary_min']}-{u['salary_max']}")
    check('no duplicate player name', not u['duplicate_names'],
          str(u['duplicate_names']))
    check('position counts reproduce the owner\'s own inspection',
          u['position_counts'] == {'QB': 86, 'RB': 116, 'WR': 184,
                                   'TE': 119, 'DST': 32},
          str(u['position_counts']))
    check('the raw universe declines to judge eligibility',
          'NOT_ASSESSED' in u['eligibility'], u['eligibility'])


def test_the_team_crosswalk_is_declared_and_lands_on_our_codes():
    o = DK.load()
    if o.state is not State.PASS:
        return
    ours = {'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL',
            'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV',
            'MIA', 'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA',
            'SF', 'TB', 'TEN', 'WAS'}
    got = {r['team'] for r in o.value}
    check('every normalised club code is one of ours', got <= ours,
          str(sorted(got - ours)))
    check('all 32 are present', got == ours, str(sorted(ours - got)))
    check('the crosswalk is exactly JAC->JAX and LAR->LA',
          DK.DK_TO_CANONICAL == {'JAC': 'JAX', 'LAR': 'LA'},
          str(DK.DK_TO_CANONICAL))
    opp = {r['opponent'] for r in o.value}
    check('opponents are normalised too', opp <= ours,
          str(sorted(opp - ours)))


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
