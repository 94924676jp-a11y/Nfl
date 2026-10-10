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


def _roster_env(rows_old, rows_new):
    from nfl.integrations import raw_slice as RS
    d = pathlib.Path(tempfile.mkdtemp(prefix='slice_test_'))
    raw, full = d / 'raw', d / 'full'
    raw.mkdir(); full.mkdir()
    hdr = 'season,team,position,status,full_name,gsis_id,week\n'
    old = hdr + ''.join(rows_old)
    (raw / f'{RS.STEM}.{"0" * 16}.slate16.csv.gz').write_bytes(gzip.compress(old.encode()))
    new = hdr + ''.join(rows_new)
    sha = hashlib.sha256(new.encode()).hexdigest()
    (full / f'weekly_rosters.{sha[:16]}.csv').write_text(new)
    man = d / 'manifest.jsonl'
    man.write_text(json.dumps({'source': 'weekly_rosters', 'state': 'PASS', 'capture_id': '20261010T074137Z',
                               'value': {'sha256': sha}}) + '\n')
    return RS, raw, full, man, sha


def test_roster_slice_refresh_keeps_slate_clubs_and_supersedes_the_old_slice():
    old = ['2026,WAS,RB,ACT,Kaytron Allen,00-1,5\n', '2026,MIA,WR,ACT,X,00-2,5\n']
    new = ['2026,MIA,RB,ACT,Kaytron Allen,00-1,5\n', '2026,MIA,WR,ACT,X,00-2,5\n', '2026,DAL,QB,ACT,Y,00-3,5\n']
    RS, raw, full, man, sha = _roster_env(old, new)
    o = RS.refresh(raw, manifest=man, full_dir=full, now='T')
    check(o.code == 'RAW_SLICE_REFRESHED', f'refreshed: {o.code} {o.detail}')
    cur = list(raw.glob(f'{RS.STEM}.*.csv.gz'))
    check(len(cur) == 1 and sha[:16] in cur[0].name, 'exactly one slice, named by the full file sha')
    text = gzip.decompress(cur[0].read_bytes()).decode()
    check('MIA,RB,ACT,Kaytron Allen' in text and 'DAL' not in text, 'kept the slate clubs only, with the move')
    check(len(list((raw / 'superseded').glob('*.csv.gz'))) == 1, 'the old slice is kept under superseded/')
    pv = json.loads((raw / 'PROVENANCE.json').read_text())
    check(pv['slice_refreshes'][-1]['full_file_sha256'] == sha, 'provenance records the source sha')
    o2 = RS.refresh(raw, manifest=man, full_dir=full)
    check(o2.code == 'RAW_SLICE_UNCHANGED', f'a second refresh is a no-op: {o2.code}')


def test_roster_slice_refuses_a_full_file_that_does_not_match_its_manifest_row():
    RS, raw, full, man, sha = _roster_env(['2026,WAS,RB,ACT,A,00-1,5\n'], ['2026,WAS,RB,ACT,A,00-1,5\n'])
    p = next(full.glob('*.csv'))
    p.write_text(p.read_text() + 'tampered\n')
    o = RS.refresh(raw, manifest=man, full_dir=full)
    check(o.code == 'RAW_SLICE_FULL_FILE_SHA_MISMATCH', f'tampered full file refused: {o.code}')


def _synthetic_dk(mutate=None):
    """A DKSalaries file built from the real W5 research universe, so identities map exactly."""
    from nfl.tools import research_universe as RU
    u = RU.build('2026W5', _REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5').value
    rp = {'QB': 'QB', 'RB': 'RB/FLEX', 'WR': 'WR/FLEX', 'TE': 'TE/FLEX', 'DST': 'DST'}
    lines = ['Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame']
    for i, r in enumerate(u):
        rec = {'pos': r['dk_pos'], 'name': r['dk_name'], 'id': str(40000000 + i), 'rp': rp[r['dk_pos']],
               'sal': '4000', 'game': f"{r['away']}@{r['home']} {r['kickoff']}", 'team': r['team']}
        if mutate:
            rec = mutate(rec)
            if rec is None:
                continue
        lines.append(f"{rec['pos']},{rec['name']} ({rec['id']}),{rec['name']},{rec['id']},{rec['rp']},{rec['sal']},"
                     f"{rec['game']},{rec['team']},0")
    return '\n'.join(lines) + '\n'


def _pool_check(text):
    from nfl.integrations import dk_pool_check as PC
    d, kw = _env()
    IB.ingest_file(_drop(d, 'DKSalaries.csv', text), **kw)
    st = json.loads((_REPO / 'nfl/dfs/salaries/classic_early_2026W5/research_projection/'
                     'rebuild_2026-10-10_designations/STATE.json').read_text())
    return PC.check('2026W5', raw_dir=_REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5', state=st,
                    inbox_rows=IB.ledger_rows(kw['ledger']))


def test_dk_pool_check_passes_a_clean_pool_and_blocks_out_players():
    o = _pool_check(_synthetic_dk())
    check(o.code == 'DK_POOL_CHECK_PASSED', f'clean synthetic pool passes: {o.code} {o.detail}')
    up = {p['dk_name']: p for p in o.value}
    check(up['Breece Hall']['upload'] == 'BLOCKED' and 'NOT_PLAYING_OUT' in up['Breece Hall']['reasons'],
          'an Out player is blocked from upload')
    check(up['Garrett Wilson']['upload'] == 'ELIGIBLE_PENDING_INACTIVES', 'others wait on inactives, never plain eligible')


def test_dk_pool_check_names_each_failure():
    def extra_game(r):
        return dict(r, game='DAL@NYG 10/11/2026 01:00PM ET') if r['name'] == 'Garrett Wilson' else r
    o = _pool_check(_synthetic_dk(extra_game))
    check(o.code == 'DK_POOL_CHECK_FAILED' and not o.evidence['checks']['GAMES_MATCH_SLATE']['pass'],
          'a game outside the slate fails GAMES_MATCH_SLATE')
    def renamed(r):
        return dict(r, name='Garrett Wilsonn') if r['name'] == 'Garrett Wilson' else r
    o = _pool_check(_synthetic_dk(renamed))
    um = o.evidence['checks']['IDENTITY_MAPPED']['unmatched']
    check(o.code == 'DK_POOL_CHECK_FAILED' and um and um[0]['dk_name'] == 'Garrett Wilsonn',
          'an unmatched name is listed, never fuzzy-matched')
    def bad_pos(r):
        return dict(r, rp='FLEX') if r['name'] == 'Garrett Wilson' else r
    o = _pool_check(_synthetic_dk(bad_pos))
    check(not o.evidence['checks']['POSITIONS_LEGAL']['pass'], 'an illegal roster position fails POSITIONS_LEGAL')


def test_reference_reads_the_builds_own_universe_record_before_a_parents():
    d = pathlib.Path(tempfile.mkdtemp(prefix='ref_test_'))
    (d / 'build').mkdir()
    st = {'as_of': '2026-10-10T15:00:00Z', 'slate_id': 'T', 'export': 'RESEARCH_UNIVERSE', 'depth': {'qb_chart': {}}}
    (d / 'build' / 'STATE.json').write_text(json.dumps(st))
    (d / 'RESEARCH_UNIVERSE_T.json').write_text(json.dumps({'evidence': {'sources': {'roster': {'sha256': 'old'}}}}))
    (d / 'build' / 'RESEARCH_UNIVERSE_T.json').write_text(json.dumps({'evidence': {'sources': {'roster': {'sha256': 'own'}}}}))
    ref = RB.reference_components(d / 'build' / 'STATE.json', [])
    check(ref['raw_dir_sources']['roster']['sha256'] == 'own', f"own record preferred: {ref['raw_dir_sources']}")


def test_dk_pool_check_names_a_cross_team_identity_conflict():
    def stale_team(r):
        return dict(r, team='WAS', game='NYG@WAS 10/11/2026 01:00PM ET') if r['name'] == 'Kaytron Allen' else r
    o = _pool_check(_synthetic_dk(stale_team))
    um = {u['dk_name']: u for u in o.evidence['checks']['IDENTITY_MAPPED']['unmatched']}
    check(o.code == 'DK_POOL_CHECK_FAILED' and um.get('Kaytron Allen', {}).get('code') == 'IDENTITY_TEAM_CONFLICT'
          and um['Kaytron Allen']['roster_club'] == ['MIA'],
          f"a DK row on WAS for a MIA player is IDENTITY_TEAM_CONFLICT and fails the pool: {um.get('Kaytron Allen')}")


def test_inactives_coverage_requires_every_club_inside_its_window():
    from nfl.integrations import inactives_coverage as IC
    st = {'kickoff': '10/11/2026 01:00PM ET', 'games': {'G1': {'away': 'CHI', 'home': 'GB'}, 'G2': {'away': 'CIN', 'home': 'MIA'}}}
    ok_t, early_t = '2026-10-11T15:31:00Z', '2026-10-11T15:00:00Z'
    full = {'source': 'OWNER_RELAYED', 'packet_id': 'p', 'clubs_with_full_list': ['CHI', 'GB', 'CIN', 'MIA'],
            'club_lists': {c: {'received_at': ok_t, 'source': 's', 'n_names': 5} for c in ('CHI', 'GB', 'CIN', 'MIA')}}
    o = IC.judge(st, full)
    check(o.code == 'SUN_INACTIVES_COVERAGE_COMPLETE', f'all four clubs in window: {o.code}')
    check(o.evidence['window_opens_utc'].startswith('2026-10-11T15:30'), f"window opens 15:30Z: {o.evidence['window_opens_utc']}")
    stale = json.loads(json.dumps(full)); stale['club_lists']['GB']['received_at'] = early_t
    v = {r['club']: r['verdict'] for r in IC.judge(st, stale).evidence['clubs']}
    check(v['GB'] == 'STALE_BEFORE_WINDOW', 'a list taken before the window is stale, not final')
    miss = json.loads(json.dumps(full)); miss['clubs_with_full_list'].remove('MIA'); del miss['club_lists']['MIA']
    o = IC.judge(st, miss)
    check(o.code == 'SUN_INACTIVES_COVERAGE_INCOMPLETE' and 'MIA=MISSING' in o.detail, 'a missing list is never everyone active')
    untimed = json.loads(json.dumps(full)); del untimed['club_lists']['CIN']
    check({r['club']: r['verdict'] for r in IC.judge(st, untimed).evidence['clubs']}['CIN'] == 'RECEIPT_TIME_UNKNOWN',
          'a list with no receipt time cannot be judged')
    reh = dict(full, source='REHEARSAL')
    o = IC.judge(st, reh)
    check(o.code == 'SUN_INACTIVES_COVERAGE_INCOMPLETE' and all(r['verdict'] == 'REHEARSAL_NOT_EVIDENCE'
                                                                for r in o.evidence['clubs']), 'a rehearsal certifies nothing')


def test_a_dkentries_pool_block_supplies_the_pool_and_the_lineups_never_do():
    from nfl.integrations import rebuild as RBD
    d, kw = _env()
    pad = ',' * 14
    ent_pool = ('Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n'
                '4400001,NFL $5 (Early Only),190001,$5,Caleb Williams (1001),,,,,,,,,,1. Column A\n'
                + pad + 'Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame\n'
                + ''.join(pad + ln + '\n' for ln in SAL.splitlines()[1:]))
    o = IB.ingest_file(_drop(d, 'DKEntries.csv', ent_pool), **kw)
    s = o.value['summary']
    check(o.value['kind'] == 'DK_ENTRIES' and o.value['privacy'] == 'ACCOUNT_PRIVATE', 'still entries, still private')
    check(s['carries_player_pool'] and s['pool']['n_players'] == 3 and s['pool']['game_type'] == 'CLASSIC',
          f"the pool block is summarised as a salary file is: {s.get('pool')}")
    ref = RBD.dk_pool_for_slate('2026W5', IB.ledger_rows(kw['ledger']))
    check(ref and ref['carrier'] == 'DK_ENTRIES' and ref['sha256'] == o.value['sha256'], f'the pool is found: {ref}')
    d2, kw2 = _env()
    IB.ingest_file(_drop(d2, 'x.csv', ENT), **kw2)
    check(RBD.dk_pool_for_slate('2026W5', IB.ledger_rows(kw2['ledger'])) is None,
          'an entries file with no pool block supplies no pool: lineups are never a pool')


def test_dk_pool_check_separates_roster_exclusions_from_identity_failures():
    def suffixed(r):
        return dict(r, name='Garrett Wilson Jr.') if r['name'] == 'Garrett Wilson' else r
    text = _synthetic_dk(suffixed)
    # A.J. Brown is on NE's week-5 roster as RES (reserve) in the capture the universe reads; DK prices him anyway.
    text += 'WR,A.J. Brown (49999001),A.J. Brown,49999001,WR/FLEX,5000,LV@NE 10/11/2026 01:00PM ET,NE,0\n'
    o = _pool_check(text)
    im = o.evidence['checks']['IDENTITY_MAPPED']
    up = {p['dk_name']: p for p in o.evidence['players']}
    check(o.code == 'DK_POOL_CHECK_PASSED' and im['matched_by'].get('SUFFIX_NORMALISED', 0) >= 1,
          f"a declared generational suffix is the same name, as in the production resolver: {o.code} {im['matched_by']}")
    check(up['Garrett Wilson Jr.']['upload'] == 'ELIGIBLE_PENDING_INACTIVES', 'the suffixed player is the same player')
    ex = {x['dk_name']: x for x in im['explained_by_roster']}
    check(ex.get('A.J. Brown', {}).get('code') == 'NOT_ON_ACTIVE_ROSTER' and ex['A.J. Brown']['week_roster_status'] == 'RES'
          and up['A.J. Brown']['upload'] == 'BLOCKED',
          f"a reserve-list player is blocked with the roster's reason and does not fail the pool: {ex.get('A.J. Brown')}")
