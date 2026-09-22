"""A contest captured today is still verifiable years from now.

The acceptance standard for this package, tested end to end:

    raw bytes -> sha256 -> store -> parse -> ownership -> duplication
    -> manifest -> rehydrate and re-verify

and then the two ways it must fail: corrupt the file and prove the artifact
identity changes; remove entries and prove completeness cannot silently
remain COMPLETE.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import re
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.history import capability as CAP                        # noqa: E402
from nfl.dfs.history import contracts as C                           # noqa: E402
from nfl.dfs.history import derive as DV                             # noqa: E402
from nfl.dfs.history import gamecenter as GC                         # noqa: E402
from nfl.dfs.history import store as ST                              # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


#: A GameCenter-shaped fixture. Written by hand, because NO REAL EXPORT
#: EXISTS IN THIS CHECKOUT -- the column spellings are at
#: PRACTITIONER_REPORT confidence and the tests say so rather than implying
#: the shape has been verified.
HEADER = (b'Rank,EntryId,EntryName,TimeRemaining,Points,Lineup,,'
          b'Player,Roster Position,%Drafted,FPTS\n')
#: The %Drafted column is INTERNALLY CONSISTENT with the four lineups
#: below: Allen and Cook appear in 2 of 4, Nacua in 4 of 4, Hurts in 2 of 4.
#: An earlier version of this fixture carried 75/75/100/25, which does not
#: describe this field at all, and the agreement assertion further down was
#: simply false against it. A fixture whose operator column contradicts its
#: own entry table cannot test whether the two readings agree; it only
#: tests that the comparison subtracts. The DISAGREEMENT case is tested
#: separately, on a fixture built to disagree on purpose.
ROWS = [
    b'1,101,alice (1/3),0,182.5,QB Josh Allen RB James Cook WR Puka Nacua,,'
    b'Josh Allen,QB,50.0%,28.4\n',
    b'2,102,bob,0,175.0,QB Josh Allen RB James Cook WR Puka Nacua,,'
    b'James Cook,RB,50.0%,14.1\n',
    b'3,103,carol,0,170.2,QB Jalen Hurts RB Bijan Robinson WR Puka Nacua,,'
    b'Puka Nacua,WR,100.0%,19.2\n',
    b'4,104,dave,0,166.0,QB Jalen Hurts RB Bijan Robinson WR Puka Nacua,,'
    b'Jalen Hurts,QB,50.0%,22.0\n',
]
FIXTURE = HEADER + b''.join(ROWS)

CONTEST = C.DFSContestIdentity(
    contest_id='DK-TEST-1', draft_group_id='DG-9', contest_name='Test GPP',
    contest_type='GPP', slate_type='CLASSIC', entry_limit=150,
    field_size=4, entry_fee=5.0, season=2026, week=3,
    start_time_utc='2026-09-27T17:00:00Z')


def capture(raw=FIXTURE, *, root, field_size=4, snapshot=C.FINAL):
    """The whole documented procedure, as code."""
    contest = C.DFSContestIdentity(
        **{**CONTEST.as_dict(), 'field_size': field_size})
    parsed = GC.parse(raw, contest=contest, snapshot_type=snapshot,
                      raw_sha256=C.sha256_bytes(raw))
    assert parsed.state.name == 'PASS', parsed.code
    v = parsed.value
    stored = ST.store_raw(
        raw, contest=contest, artifact_type=C.CONTEST_STANDINGS,
        original_filename='contest-standings-DK-TEST-1.csv',
        snapshot_type=snapshot, schema_fingerprint=v['schema_fingerprint'],
        row_count=v['n_entries'], parser_version=v['parser_version'],
        retrieved_at='2026-09-27T23:30:00Z', root=root)
    assert stored.state.name == 'PASS', stored.code
    comp = ST.assert_completeness(n_entries_held=v['n_entries'],
                                  declared_field_size=contest.field_size)
    man = C.DFSContestManifest(
        contest=contest, artifacts=[stored.value],
        information_cut='2026-09-27T23:30:00Z', snapshot_type=snapshot,
        completeness=comp['completeness'],
        completeness_why=comp['why'])
    w = ST.write_manifest(man, root=root)
    assert w.state.name == 'PASS', w.code
    return contest, v, man, stored.value


# -- 1. the whole chain -----------------------------------------------------
def test_raw_to_manifest_to_rehydration():
    with tempfile.TemporaryDirectory() as td:
        contest, v, man, art = capture(root=td)
        ok(art.raw_sha256 == C.sha256_bytes(FIXTURE),
           f'the artifact records the sha256 of the bytes as delivered: '
           f'{art.raw_sha256[:16]}')
        p = pathlib.Path(art.stored_path)
        p = p if p.is_absolute() else _REPO / p
        ok(p.read_bytes() == FIXTURE,
           'and the stored file is byte-identical to what was handed over')
        ok(art.schema_fingerprint.startswith('rank|entryid|entryname'),
           f'the schema it actually saw is recorded: '
           f'{art.schema_fingerprint[:48]}')
        ok(man.completeness == C.COMPLETE,
           f'4 entries against a declared field of 4 is COMPLETE: '
           f'{man.completeness}')
        r = ST.rehydrate(ST.contest_dir(contest, root=td))
        ok(r.state.name == 'PASS' and r.code == 'DFS_ARCHIVE_VERIFIED',
           f'and the archive re-verifies from the manifest alone: {r.code}')
        ok(r.value['n_verified'] == 1
           and r.value['manifest_hash'] == man.manifest_hash(),
           f'{r.value["n_verified"]} artifact(s) hash true, manifest '
           f'{r.value["manifest_hash"]}')
        ok(r.value['contest_key'] == 'DRAFTKINGS:NFL:DK-TEST-1',
           f'under the operator\'s own contest id: {r.value["contest_key"]}')


def test_the_manifest_is_deterministic():
    with tempfile.TemporaryDirectory() as td1, \
            tempfile.TemporaryDirectory() as td2:
        _c1, _v1, m1, _a1 = capture(root=td1)
        _c2, _v2, m2, _a2 = capture(root=td2)
        ok(m1.manifest_hash() == m2.manifest_hash(),
           f'two captures of the same bytes produce the same manifest hash '
           f'from two different storage roots: {m1.manifest_hash()}')
        ok(_a1.stored_path != _a2.stored_path,
           'even though the two are stored at different paths -- the hash '
           'identifies the capture, not where the file happens to sit')


def test_the_manifest_hash_still_moves_when_the_capture_does():
    """`stored_path` was removed from the hashed body so the hash survives
    a reorganised archive. That removal is only safe if the hash is still
    sensitive to everything that IS identity. This test is the other half of
    `test_the_manifest_is_deterministic`: without it, a hash that ignored
    every field would pass that test perfectly."""
    with tempfile.TemporaryDirectory() as td:
        _c, _v, base, _a = capture(root=td)
        h = base.manifest_hash()

        other = C.DFSContestManifest(
            contest=base.contest,
            artifacts=[dataclasses.replace(base.artifacts[0],
                                           raw_sha256='0' * 64)],
            information_cut=base.information_cut,
            snapshot_type=base.snapshot_type,
            completeness=base.completeness,
            completeness_why=base.completeness_why)
        ok(other.manifest_hash() != h,
           'different bytes -> different manifest hash')

        snap = C.DFSContestManifest(
            contest=base.contest, artifacts=list(base.artifacts),
            information_cut=base.information_cut,
            snapshot_type=C.POST_INITIAL_LOCK,
            completeness=base.completeness,
            completeness_why=base.completeness_why)
        ok(snap.manifest_hash() != h,
           'a different snapshot of the same contest -> different hash')

        part = C.DFSContestManifest(
            contest=base.contest, artifacts=list(base.artifacts),
            information_cut=base.information_cut,
            snapshot_type=base.snapshot_type,
            completeness=C.INCOMPLETE, completeness_why='held 3 of 4')
        ok(part.manifest_hash() != h,
           'and a different completeness verdict -> different hash')

        ident = C.DFSContestManifest(
            contest=dataclasses.replace(base.contest, contest_id='DK-TEST-2'),
            artifacts=list(base.artifacts),
            information_cut=base.information_cut,
            snapshot_type=base.snapshot_type,
            completeness=base.completeness,
            completeness_why=base.completeness_why)
        ok(ident.manifest_hash() != h,
           'a different contest id -> different hash')

        moved = C.DFSContestManifest(
            contest=base.contest,
            artifacts=[dataclasses.replace(base.artifacts[0],
                                           stored_path='somewhere/else.csv')],
            information_cut=base.information_cut,
            snapshot_type=base.snapshot_type,
            completeness=base.completeness,
            completeness_why=base.completeness_why)
        ok(moved.manifest_hash() == h,
           'and ONLY the storage path may move without changing it')
        ok('stored_path' in json.dumps(moved.as_dict()),
           'the path is still written down, because a reader has to find '
           'the bytes -- it is a locator, not identity')


def test_a_disagreeing_operator_column_is_reported_not_reconciled():
    """The main fixture's %Drafted column agrees with its own entry table.
    This one is built to disagree, so the comparison is shown detecting a
    difference rather than only ever subtracting equal numbers."""
    disagreeing = HEADER + b''.join(
        r.replace(b',50.0%,', b',75.0%,') for r in ROWS)
    o = GC.parse(disagreeing, raw_sha256=C.sha256_bytes(disagreeing))
    v = o.value
    op = DV.operator_ownership(
        v['athletes'], contest_key=CONTEST.key,
        observed_at='2026-09-27T23:30:00Z', observation_type=C.FINAL)
    dv = DV.derived_ownership(
        v['entries'], contest_key=CONTEST.key,
        observed_at='2026-09-27T23:30:00Z', observation_type=C.FINAL,
        completeness=C.COMPLETE)
    cmp_ = DV.compare_ownership(op.value['observations'],
                                dv.value['observations'])
    worst = cmp_.value['largest_disagreement']
    ok(abs(cmp_.value['max_abs_difference'] - 0.25) < 1e-9,
       f'the operator says 0.75 and the four entries held say 0.50, and the '
       f'comparison reports the gap: {cmp_.value["max_abs_difference"]}')
    ok(worst['operator'] == 0.75 and worst['derived'] == 0.50,
       f'naming both numbers rather than picking one: '
       f'{worst["athlete_name"]} operator {worst["operator"]} vs derived '
       f'{worst["derived"]}')
    ok(cmp_.value['n_derived_only'] >= 1,
       f'and an athlete in the field with no operator row is counted, not '
       f'silently dropped: {cmp_.value["n_derived_only"]}')


# -- 2. it must fail when the evidence changes ------------------------------
def test_corrupting_the_file_changes_the_artifact_identity():
    with tempfile.TemporaryDirectory() as td:
        contest, _v, man, art = capture(root=td)
        p = pathlib.Path(art.stored_path)
        p = p if p.is_absolute() else _REPO / p
        p.write_bytes(FIXTURE.replace(b'182.5', b'999.9'))
        r = ST.rehydrate(ST.contest_dir(contest, root=td))
        ok(r.state.name == 'FAIL' and r.code == 'DFS_ARCHIVE_NOT_VERIFIABLE',
           f'one changed character and the archive refuses: {r.code}')
        bad = r.evidence['value']['mismatched'][0]
        ok(bad['expected'] != bad['found'],
           f'naming the hash it expected and the one it found: '
           f'{bad["expected"][:12]} vs {bad["found"][:12]}')
        corrupt = C.sha256_bytes(FIXTURE.replace(b'182.5', b'999.9'))
        ok(corrupt != C.sha256_bytes(FIXTURE),
           'and a different file is a different artifact, by construction')


def test_a_missing_file_is_not_a_clean_archive():
    with tempfile.TemporaryDirectory() as td:
        contest, _v, _m, art = capture(root=td)
        p = pathlib.Path(art.stored_path)
        p = p if p.is_absolute() else _REPO / p
        p.unlink()
        r = ST.rehydrate(ST.contest_dir(contest, root=td))
        ok(r.state.name == 'FAIL',
           f'a manifest whose raw file is gone does not verify: {r.code}')
        ok(r.evidence['value']['missing'],
           'and the absent artifact is named, not counted')


def test_removing_entries_cannot_stay_COMPLETE():
    short = HEADER + b''.join(ROWS[:2])
    with tempfile.TemporaryDirectory() as td:
        _c, v, man, _a = capture(short, root=td, field_size=4)
        ok(v['n_entries'] == 2, f'{v["n_entries"]} entries held')
        ok(man.completeness == C.INCOMPLETE,
           f'2 held against a declared field of 4 is INCOMPLETE: '
           f'{man.completeness}')
        ok('2 missing' in (man.completeness_why or ''),
           f'and it says how many: {man.completeness_why}')
    with tempfile.TemporaryDirectory() as td:
        _c, _v, man2, _a = capture(short, root=td, field_size=None)
        ok(man2.completeness == C.COMPLETENESS_UNKNOWN,
           f'and with NO declared field size it is COMPLETENESS_UNKNOWN, '
           f'never COMPLETE: {man2.completeness}')
        ok('not evidence that we have all of it' in (man2.completeness_why
                                                     or ''),
           'because absence of a field size is not evidence of completeness')


# -- 3. the parser ----------------------------------------------------------
def test_the_parser_refuses_rather_than_returning_nothing():
    o = GC.parse(b'some,unrelated,columns\n1,2,3\n')
    ok(o.state.name == 'FAIL'
       and o.code == 'GAMECENTER_ENTRY_TABLE_NOT_FOUND',
       f'a file with no entry table refuses by name: {o.code}')
    ok('PRACTITIONER_REPORT' in o.detail,
       'and says the column names it looked for are reported, not verified')
    o2 = GC.parse(b'')
    ok(o2.code == 'GAMECENTER_FILE_EMPTY', f'empty bytes refuse: {o2.code}')
    o3 = GC.parse(HEADER)
    ok(o3.state.name == 'FAIL' and o3.code == 'GAMECENTER_NO_ENTRIES',
       f'a header with no entrant rows refuses: {o3.code}')


def test_absent_columns_are_recorded_not_assumed():
    raw = (b'Rank,EntryId,EntryName,Points,Lineup\n'
           b'1,1,a,10,QB Josh Allen RB James Cook\n')
    o = GC.parse(raw)
    ok(o.state.name == 'PASS', f'a file without the athlete table parses: '
                               f'{o.code}')
    ok(o.value['athlete_table_present'] is False,
       'and says the athlete summary table was not present')
    ok('athlete_id' in o.value['athlete_columns_absent'],
       f'no DK athlete id is assumed: '
       f'{o.value["athlete_columns_absent"]}')
    ok(all(e.entry_id for e in o.value['entries']),
       'while what IS there is read')


def test_an_unparsed_lineup_is_a_stated_fact():
    raw = HEADER + b'1,1,a,0,10,,,Josh Allen,QB,50.0%,20.0\n'
    o = GC.parse(raw)
    ok(o.state.name == 'PASS', f'{o.code}')
    e = o.value['entries'][0]
    ok(e.lineup_slots == () and e.parsed is False,
       'an entry whose lineup could not be read is marked unparsed, never '
       'given a guessed roster')


# -- 4. ownership -----------------------------------------------------------
def test_operator_and_derived_ownership_are_kept_apart():
    o = GC.parse(FIXTURE, raw_sha256=C.sha256_bytes(FIXTURE))
    v = o.value
    op = DV.operator_ownership(
        v['athletes'], contest_key=CONTEST.key,
        observed_at='2026-09-27T23:30:00Z', observation_type=C.FINAL)
    dv = DV.derived_ownership(
        v['entries'], contest_key=CONTEST.key,
        observed_at='2026-09-27T23:30:00Z', observation_type=C.FINAL,
        completeness=C.COMPLETE)
    ok(op.state.name == 'PASS' and dv.state.name == 'PASS',
       f'both read: {op.code} / {dv.code}')
    ok(dv.value['denominator'] == 4,
       f'the derived denominator is the entries held: '
       f'{dv.value["denominator"]}')
    nac = next(x for x in dv.value['observations']
               if x.athlete_name == 'Puka Nacua')
    ok(nac.ownership == 1.0,
       f'an athlete in every entry derives to 1.0: {nac.ownership}')
    ok(nac.source == C.DERIVED_FROM_FIELD and nac.denominator == 4
       and nac.derivation_version,
       'carrying its source, denominator and derivation version')
    opn = next(x for x in op.value['observations']
               if x.athlete_name == 'Puka Nacua')
    ok(opn.ownership == 1.0 and opn.source == C.OPERATOR_PUBLISHED,
       f'and the operator number is stored as a FRACTION of the published '
       f'percent: {opn.ownership}')
    cmp_ = DV.compare_ownership(op.value['observations'],
                                dv.value['observations'])
    ok(cmp_.value['max_abs_difference'] == 0.0,
       f'on this fixture the two agree exactly: '
       f'{cmp_.value["max_abs_difference"]}')
    ok(cmp_.value['n_comparable'] == 4,
       f'{cmp_.value["n_comparable"]} athlete(s) comparable')


def test_an_ownership_number_is_never_a_bare_float():
    o = GC.parse(FIXTURE)
    dv = DV.derived_ownership(
        o.value['entries'], contest_key=CONTEST.key,
        observed_at='2026-09-27T23:30:00Z',
        observation_type=C.POST_INITIAL_LOCK,
        completeness=C.COMPLETENESS_UNKNOWN)
    x = dv.value['observations'][0]
    for f in ('observed_at', 'observation_type', 'denominator',
              'completeness', 'source'):
        ok(getattr(x, f) is not None,
           f'every observation carries {f}: {getattr(x, f)}')
    ok(x.observation_type == C.POST_INITIAL_LOCK,
       'so two snapshots of the same contest are comparable rather than '
       'contradictory -- an NFL Classic slate has late swap, and the field '
       'after initial lock is not the field at settlement')
    ok(x.completeness == C.COMPLETENESS_UNKNOWN,
       'and an unproven field does not claim COMPLETE')


def test_derived_ownership_refuses_an_unreadable_field():
    raw = HEADER + b'1,1,a,0,10,,,Josh Allen,QB,50.0%,20.0\n'
    o = GC.parse(raw)
    dv = DV.derived_ownership(o.value['entries'], contest_key='k',
                              observed_at='t')
    ok(dv.state.name == 'BLOCKED' and dv.code == 'NO_PARSED_LINEUP',
       f'no readable lineup means no derivation, not zero ownership: '
       f'{dv.code}')


# -- 5. duplication ---------------------------------------------------------
def test_duplication_counts_identical_rosters():
    o = GC.parse(FIXTURE)
    d = DV.duplication(o.value['entries'])
    ok(d.state.name == 'PASS', f'{d.code}')
    ok(d.value['n_distinct_lineups'] == 2,
       f'four entries, two distinct lineups: '
       f'{d.value["n_distinct_lineups"]}')
    top = d.value['lineups'][0]
    ok(top['duplicate_count'] == 2 and top['fraction_of_field'] == 0.5,
       f'the largest duplicate group is {top["duplicate_count"]} entries, '
       f'{top["fraction_of_field"]:.0%} of the parsed field')
    ok(top['lineup_hash'].startswith('LU-'),
       f'each carries a canonical hash: {top["lineup_hash"]}')
    ok(d.value['n_unique_lineups'] == 0,
       'and neither lineup on this fixture is unique')


def test_slot_order_does_not_make_two_classic_lineups_different():
    a = C.ContestEntry('1', 'a', 1, 10.0, 'x',
                       (('QB', 'Allen'), ('RB', 'Cook'), ('WR', 'Nacua')))
    b = C.ContestEntry('2', 'b', 2, 10.0, 'x',
                       (('WR', 'Nacua'), ('QB', 'Allen'), ('RB', 'Cook')))
    d = DV.duplication([a, b])
    ok(d.value['n_distinct_lineups'] == 1,
       'the same three players in a different slot order is ONE lineup')


def test_a_showdown_captain_is_position_sensitive():
    a = C.ContestEntry('1', 'a', 1, 10.0, 'x',
                       (('CPT', 'Mahomes'), ('FLEX', 'Kelce')))
    b = C.ContestEntry('2', 'b', 2, 10.0, 'x',
                       (('CPT', 'Kelce'), ('FLEX', 'Mahomes')))
    d = DV.duplication([a, b])
    ok(d.value['n_distinct_lineups'] == 2,
       'swapping the captain makes a DIFFERENT lineup -- DraftKings scores '
       'a captain at 1.5x, so the two do not score the same')
    ok('CPT' in d.value['distinguished_slots'],
       'and the distinguished slot is declared, not implicit')


# -- 6. capability ----------------------------------------------------------
def test_capability_claims_carry_their_confidence():
    dk = CAP.DRAFTKINGS_GAMECENTER
    ok(dk.claims['complete_contest_field'].confidence
       == C.PRACTITIONER_REPORT,
       'the complete-field claim is PRACTITIONER_REPORT, not verified -- no '
       'GameCenter export exists in this checkout')
    ok(dk.claims['retention_window_days'].value == 10
       and dk.claims['retention_window_days'].confidence
       == C.PRACTITIONER_REPORT,
       'the ten-day window is reported, and it is why this archive exists')
    ok(dk.claims['automated_acquisition_built'].confidence
       == C.VERIFIED_PRIMARY
       and dk.claims['automated_acquisition_built'].value is False,
       'the only VERIFIED_PRIMARY claim is one about THIS repository: no '
       'automation exists')
    ok(len(dk.unknowns()) >= 4,
       f'and unresolved subjects stay UNKNOWN: {dk.unknowns()}')
    cb = CAP.COMMERCIAL_BACKFILL
    ok(len(cb.unknowns()) == len(cb.claims) == 15,
       f'the commercial candidate has {len(cb.claims)} subjects and every '
       f'one is UNKNOWN -- the row holds the question, it does not answer '
       f'it')
    try:
        CAP.Claim('x', 1, 'PRETTY_SURE')
        ok(False, 'an undeclared confidence should be refused')
    except AssertionError as e:
        ok('is not one of' in str(e),
           'and an undeclared confidence level is refused by name')


# -- 7. isolation and manual-only ------------------------------------------
def test_the_archive_touches_no_football_model():
    pkg = _REPO / 'nfl/dfs/history'
    forbidden = {'player_universe', 'slate_state', 'registry', 'role_state',
                 'opportunity_centre', 'run_forecast', 'optimizer', 'audit',
                 'gate', 'dossier'}
    for f in sorted(pkg.glob('*.py')):
        tree = ast.parse(f.read_text())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    names.add(a.name)
                if n.module:
                    names.add(n.module.split('.')[-1])
            elif isinstance(n, ast.Import):
                for a in n.names:
                    names.add(a.name.split('.')[-1])
        hit = sorted(names & forbidden)
        ok(not hit, f'{f.name} imports no football-model module: {hit}')


#: A fetchable endpoint: a scheme, then anything, then the operator's
#: domain. `re.DOTALL` is deliberately NOT used -- a URL does not span lines.
_URL_RE = re.compile(r'\b[a-z][a-z0-9+.-]*://[^\s\'"]*draftkings[^\s\'"]*')


def test_no_site_automation_exists():
    pkg = _REPO / 'nfl/dfs/history'
    banned = ('requests', 'urllib', 'httpx', 'selenium', 'playwright',
              'webdriver', 'aiohttp', 'session', 'login', 'captcha')
    for f in sorted(pkg.glob('*.py')):
        src = f.read_text().lower()
        tree = ast.parse(f.read_text())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    mods.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split('.')[0])
        hit = sorted(mods & set(banned))
        ok(not hit, f'{f.name} imports no network or browser module: {hit}')
        # A URL, not a mention. The first version of this check was a bare
        # substring test for 'draftkings.com' and it failed on gamecenter.py's
        # own docstring SAYING it does not automate draftkings.com -- prose
        # asserting the rule read as a violation of it. That is the third
        # time a substring test has caught documentation in this migration,
        # so this one looks for a scheme-qualified endpoint, which is the
        # thing that could actually be fetched.
        urls = sorted(set(_URL_RE.findall(src)))
        ok(not urls, f'{f.name} carries no operator endpoint: {urls}')


def test_the_procedure_is_written_down():
    p = _REPO / 'nfl/dfs/history/PROCEDURE.md'
    ok(p.exists(), 'the manual operating procedure is in the repository')
    t = p.read_text()
    for token in ('salary file', 'contest id', 'field size', 'payout',
                  'GameCenter', 'ten days', 'snapshot'):
        ok(token.lower() in t.lower(),
           f'and it covers {token!r}')


def main():
    for t in (test_raw_to_manifest_to_rehydration,
              test_the_manifest_is_deterministic,
              test_the_manifest_hash_still_moves_when_the_capture_does,
              test_corrupting_the_file_changes_the_artifact_identity,
              test_a_missing_file_is_not_a_clean_archive,
              test_removing_entries_cannot_stay_COMPLETE,
              test_the_parser_refuses_rather_than_returning_nothing,
              test_absent_columns_are_recorded_not_assumed,
              test_an_unparsed_lineup_is_a_stated_fact,
              test_operator_and_derived_ownership_are_kept_apart,
              test_a_disagreeing_operator_column_is_reported_not_reconciled,
              test_an_ownership_number_is_never_a_bare_float,
              test_derived_ownership_refuses_an_unreadable_field,
              test_duplication_counts_identical_rosters,
              test_slot_order_does_not_make_two_classic_lineups_different,
              test_a_showdown_captain_is_position_sensitive,
              test_capability_claims_carry_their_confidence,
              test_the_archive_touches_no_football_model,
              test_no_site_automation_exists,
              test_the_procedure_is_written_down):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
