"""The read-only integration layer: drop-folder recognition, the access matrix, status and rebuild planning.

Every fixture is synthetic and lives in a temporary directory, so nothing here reads or writes the real inbox,
the real manifest, or any platform.
"""
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.integrations import inbox as IB, matrix as MX, monitor as MO, rebuild as RB  # noqa: E402

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


SAL = ('Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame\n'
       'QB,Caleb Williams (1001),Caleb Williams,1001,QB,6400,CHI@GB 10/11/2026 01:00PM ET,CHI,20.1\n'
       'WR,DJ Moore (1002),DJ Moore,1002,WR/FLEX,5800,CHI@GB 10/11/2026 01:00PM ET,CHI,14.0\n'
       'DST,Packers (1003),Packers,1003,DST,3200,CHI@GB 10/11/2026 01:00PM ET,GB,7.0\n')
SHOWDOWN = SAL.replace(',QB,6400', ',CPT,9600')
ENT = ('Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n'
       '4400001,NFL $5 Early,190001,$5,,,,,,,,,,,\n')
STAND = ('Rank,EntryId,EntryName,TimeRemaining,Points,Lineup,,Player,Roster Position,%Drafted,FPTS\n'
         '1,55001,someuser,0,201.4,QB X RB Y,,Caleb Williams,QB,12.5%,24.1\n'
         '2,55002,other,0,199.0,QB Z,,DJ Moore,WR,20.0%,18.0\n')
FC = (',,,,,\nPlayer,Inj,Pos,Salary,Team,Opp,FC Proj,My Proj\nCaleb Williams,,QB,6400,CHI,GB,19.2,19.2\n')


def _env():
    d = pathlib.Path(tempfile.mkdtemp(prefix='inbox_test_'))
    (d / 'drop').mkdir()
    return d, dict(store=d / 'store', ledger=d / 'LEDGER.jsonl')


def _drop(d, name, text):
    p = d / 'drop' / name
    p.write_text(text)
    return p


def test_each_export_is_recognised_by_its_header_not_its_name():
    d, kw = _env()
    cases = [('anything.csv', SAL, 'DK_SALARIES'), ('x.csv', ENT, 'DK_ENTRIES'),
             ('contest-standings-190001.csv', STAND, 'DK_CONTEST_STANDINGS'),
             ('draftkings_players.csv', FC, 'FC_PLAYERS_EXPORT')]
    for name, text, kind in cases:
        o = IB.ingest_file(_drop(d, name, text), **kw)
        check(o.state.value == 'PASS' and o.value['kind'] == kind, f'{name} -> {kind} ({o.code})')
    o = IB.ingest_file(_drop(d, 'sd.csv', SHOWDOWN), **kw)
    check(o.value['summary']['game_type'] == 'SHOWDOWN', 'a CPT roster position reads as Showdown')


def test_policy_labels_travel_with_the_file():
    d, kw = _env()
    fc = IB.ingest_file(_drop(d, 'a.csv', FC), **kw).value
    st = IB.ingest_file(_drop(d, 'contest-standings-190001.csv', STAND), **kw).value
    en = IB.ingest_file(_drop(d, 'c.csv', ENT), **kw).value
    check(fc['never_model_input'] is True and fc['role'] == 'BENCHMARK_CONTEXT_ONLY', 'FC is benchmark only')
    check(st['available_prelock'] is False, 'realised ownership is labelled postlock only')
    check(st['summary']['contest_id_from_filename'] == '190001', 'contest id read from the standings name')
    check(en['privacy'] == 'ACCOUNT_PRIVATE', 'entries are account private')


def test_store_round_trips_and_the_original_is_untouched():
    d, kw = _env()
    p = _drop(d, 's.csv', SAL)
    before = p.read_bytes()
    o = IB.ingest_file(p, **kw)
    blob = pathlib.Path(o.value['blob']) if pathlib.Path(o.value['blob']).is_absolute() else _REPO / o.value['blob']
    check(hashlib.sha256(gzip.decompress(blob.read_bytes())).hexdigest() == o.value['sha256'], 'store round-trips')
    check(p.read_bytes() == before, 'the dropped file is not modified or removed')


def test_second_ingest_of_same_bytes_is_a_no_op():
    d, kw = _env()
    IB.ingest_file(_drop(d, 'one.csv', SAL), **kw)
    o = IB.ingest_file(_drop(d, 'two.csv', SAL), **kw)
    check(o.code == 'INBOX_ALREADY_INGESTED', f'duplicate bytes under a new name: {o.code}')
    check(len(IB.ledger_rows(kw['ledger'])) == 1, 'the ledger did not grow')


def test_refusals_are_named_and_recorded():
    d, kw = _env()
    cases = [('empty.csv', '   \n', 'INBOX_EMPTY_FILE'),
             ('junk.csv', 'a,b,c\n1,2,3\n', 'INBOX_UNRECOGNISED_HEADER'),
             ('hdr_only.csv', SAL.splitlines()[0] + '\n', 'INBOX_DK_POOL_EMPTY'),
             ('dup.csv', SAL + SAL.splitlines()[1] + '\n', 'INBOX_DUPLICATE_DK_ID'),
             ('bad_own.csv', STAND.replace('12.5%', 'n/a'), 'INBOX_STANDINGS_OWNERSHIP_UNPARSEABLE'),
             ('no_own.csv', 'Rank,EntryId,EntryName,TimeRemaining,Points,Lineup\n1,2,u,0,1,x\n',
              'INBOX_UNRECOGNISED_HEADER')]
    for name, text, code in cases:
        o = IB.ingest_file(_drop(d, name, text), **kw)
        check(o.state.value != 'PASS' and o.code == code, f'{name}: {o.code}')
    (d / 'drop' / 'bin.csv').write_bytes(b'\xff\xfe\x00bad')
    o = IB.ingest_file(d / 'drop' / 'bin.csv', **kw)
    check(o.code == 'INBOX_NOT_UTF8', f'binary: {o.code}')
    codes = [r['code'] for r in IB.ledger_rows(kw['ledger'])]
    check(len(codes) == len(cases) + 1, f'every refusal is in the ledger ({len(codes)})')


def test_matrix_is_sound_and_acts_on_no_account():
    check(MX.check() == [], f'matrix invariants: {MX.check()}')
    acting = [r for r in MX.MATRIX if r['action'] not in MX.IMPLEMENTED_ACTIONS]
    check(acting and all(r['build'] == 'NOT_TO_BE_BUILT' for r in acting),
          f'{len(acting)} account/entry/wager/financial rows are all NOT_TO_BE_BUILT')
    kinds = {r['inbox_kind'] for r in MX.MATRIX if r['inbox_kind']}
    check(kinds == set(IB.KIND_POLICY), f'every manual export has an inbox kind and vice versa: {kinds}')
    for a in MX.ACCESS:
        check(MX.by_access()[a], f'access class {a} has at least one row')


def _row(src, cid, state='PASS', code='CAPTURED', sha='a' * 64, unchanged=False, blob=None):
    return {'source': src, 'capture_id': cid, 'state': state, 'code': code,
            'value': ({'sha256': sha, 'blob': blob or f'nfl/vintage/{src}.x.csv.gz',
                       'content_unchanged': unchanged} if state == 'PASS' else {})}


def test_local_no_egress_does_not_disconnect_a_source():
    now = dt.datetime(2026, 10, 9, 20, 0, tzinfo=dt.timezone.utc)
    rows = [_row('official_injury_report', '20261009T152711Z'),
            _row('official_injury_report', '20261009T192103Z', state='BLOCKED', code='NO_EGRESS'),
            _row('official_inactives', '20260917T234100Z'),
            _row('official_inactives', '20261009T152711Z', state='DEFERRED', code='SOURCE_HAS_NO_ROWS_YET'),
            _row('official_inactives', '20261009T192103Z', state='BLOCKED', code='NO_EGRESS'),
            _row('pbp', '20260917T190050.592973Z.23370d5d10f8104d'),
            _row('official_transactions', '20261009T152711Z', state='BLOCKED', code='ENDPOINT_NOT_YET_VERIFIED')]
    c = {x['id']: x for x in MO.connections(rows, now, [], '2026W5')}
    check(c['I05']['status'] == 'CONNECTED', f"NO_EGRESS here does not disconnect I05: {c['I05']['status']}")
    check(c['I05']['last_local_no_egress_attempt'] == '20261009T192103Z', 'the local attempt is still shown')
    check(c['I06']['status'] == 'DEFERRED_NOT_PUBLISHED', f"inactives not yet published: {c['I06']['status']}")
    check(c['I09']['status'] == 'STALE', f"a 3-week-old pbp capture is stale: {c['I09']['status']}")
    check(c['I08']['status'] == 'BLOCKED', 'an unverified endpoint is BLOCKED')
    check(c['D01']['status'] == 'AWAITING_OWNER_EXPORT', 'no DK file is AWAITING, not zero')


def test_rebuild_compare_reads_bytes_not_capture_ids():
    ref = {'depth_charts': {'capture_id': 'A', 'sha256': 'x'}, 'injuries': ['inj.1'], 'official_inactives': [],
           'raw_dir_sources': {'g': {'sha256': 'r1'}}, 'export': 'RESEARCH_UNIVERSE'}
    same = {'depth_charts': {'capture_id': 'B', 'sha256': 'x'}, 'injuries': ['inj.1'], 'official_inactives': [],
            'raw_dir': {'g.csv.gz': 'r1'}, 'dk_pool': None}
    ch, ok, unc = RB.compare(ref, same)
    check(ch == [] and unc == [], f'a content-unchanged recapture is not a change ({ch})')
    moved = dict(same, depth_charts={'capture_id': 'B', 'sha256': 'y'}, injuries=['inj.1', 'inj.2'],
                 dk_pool={'sha256': 'd'})
    ch, ok, unc = RB.compare(ref, moved)
    check({c['component'] for c in ch} == {'depth_charts', 'injuries', 'dk_pool'}, f'changes: {ch}')
    ch, ok, unc = RB.compare(dict(ref, depth_charts={'UNCOMPARABLE': 'two ids'}, raw_dir_sources=None), same)
    check({u['component'] for u in unc} == {'depth_charts', 'raw_dir'} and not ch,
          'what cannot be compared is UNCOMPARABLE, never unchanged')


def test_execute_refuses_a_non_empty_directory():
    d = pathlib.Path(tempfile.mkdtemp(prefix='rebuild_test_'))
    (d / 'STATE.json').write_text('{}')
    o = RB.execute('2026W5', as_of='2026-10-09T20:00:00Z', raw_dir=d, out=d)
    check(o.code == 'REBUILD_OUT_NOT_EMPTY', f'a frozen build is never overwritten: {o.code}')


def test_execute_refuses_an_as_of_in_the_future():
    d = pathlib.Path(tempfile.mkdtemp(prefix='rebuild_test_'))
    o = RB.execute('2026W5', as_of='2099-01-01T00:00:00Z', raw_dir=d, out=d / 'new')
    check(o.code == 'REBUILD_AS_OF_IN_FUTURE' and not (d / 'new').exists(), f'future as-of refused: {o.code}')


def test_status_page_renders_from_json_alone():
    st = {'slate_id': 'T', 'generated_at_utc': 'now', 'reference_as_of': 'then', 'scope': 's',
          'connections': [{'id': 'I01', 'capability': 'c<script>', 'provider': 'p', 'access': 'FULLY_AUTOMATED',
                           'status': 'CONNECTED', 'owner_decision': None}],
          'missing_information': [{'what': 'w', 'status': 'STALE'}], 'qb_watch': [],
          'missing_players': {'status': 'UNKNOWN_NO_DK_SALARIES', 'detail': 'd'},
          'rebuild': {'code': 'NO_CHANGE', 'detail': 'x', 'changes': []}, 'owner_approvals': [],
          'projection_independence': 'p'}
    h = MO.render_html(st)
    check('<title>Integration Status</title>' in h and 'prefers-color-scheme: dark' in h, 'page contract')
    check('c<script>' not in h and 'c&lt;script&gt;' in h, 'external text is escaped')
