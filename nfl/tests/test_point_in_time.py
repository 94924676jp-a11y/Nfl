"""Point-in-time data-selection contract (nfl/warehouse/point_in_time.py). Owner directive 2026-10-08.

Synthetic stores are built in a throwaway git repository so every clock is controlled. Each case that activates a
manifest runs in a child process, because an audit hook cannot be removed once installed.

Covered: classification by retrieval clock (manifest, sidecar, git first commit, none); seal and immutability; the
live path is the identity; post-cutoff and deliberately injected captures never reach a reader; tampered pins refuse;
the backstop refuses unwired reads; TEAM_GAME resolves to the commit at the cutoff; a NEGATIVE CONTROL showing the
same injection does move a reader when no manifest is active; and the real ATL@NO cutoff refusing exactly the
post-lock captures the hand-built replay had to delete.
"""
import gzip
import json
import os
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.warehouse import point_in_time as PIT  # noqa: E402

PASSED = FAILED = 0
CUT = '2026-10-05T23:47:26Z'


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print('  ok  ', msg)
    else:
        FAILED += 1
        print('  FAIL', msg)


def _git(root, *a, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
               GIT_COMMITTER_EMAIL='t@t')
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(['git', *a], cwd=root, env=env, check=True, capture_output=True)


def _gz(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, 'wt') as fh:
        fh.write(text)


def store():
    """A store with one capture of every clock kind on each side of CUT."""
    r = pathlib.Path(tempfile.mkdtemp(prefix='pit_'))
    _git(r, 'init', '-q')
    pg, vi = r / 'nfl/research/postgame', r / 'nfl/vintage'
    caps = {'pbp_2026.aaaaaaaaaaaaaaaa.csv.gz': ('week,x\n1,1\n', '2026-10-01T00:00:00Z'),          # before: sidecar
            'pbp_2026.bbbbbbbbbbbbbbbb.csv.gz': ('week,x\n1,1\n4,4\n4,4\n', '2026-10-07T00:00:00Z')}  # after: sidecar
    for n, (t, ts) in caps.items():
        _gz(pg / n, t)
        (pg / (n[:-3] + '.provenance.json')).write_text(json.dumps({'retrieved_at': ts}))
    _gz(vi / 'weekly_rosters.1111111111111111.raw.csv.gz', 'name,position\nA,WR\n')               # manifest: before
    _gz(vi / 'weekly_rosters.2222222222222222.raw.csv.gz', 'name,position\nA,TE\n')               # manifest: after
    _gz(vi / 'schedules.3333333333333333.csv.gz', 'game_id\nX\n')                                  # git first commit
    rows = [{'source': 'weekly_rosters', 'state': 'PASS',
             'value': {'blob': 'nfl/vintage/weekly_rosters.1111111111111111.reduced.csv.gz',
                       'retrieved_at': '2026-10-04T00:00:00+00:00'}},
            {'source': 'weekly_rosters', 'state': 'PASS',       # a later re-fetch of the same bytes: earliest wins
             'value': {'blob': 'nfl/vintage/weekly_rosters.1111111111111111.reduced.csv.gz',
                       'retrieved_at': '2026-10-08T00:00:00+00:00'}},
            {'source': 'weekly_rosters', 'state': 'PASS',
             'value': {'blob': 'nfl/vintage/weekly_rosters.2222222222222222.reduced.csv.gz',
                       'retrieved_at': '2026-10-07T16:57:29+00:00'}}]
    (r / 'nfl/vintage_manifest.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
    tg = r / 'nfl/warehouse/TEAM_GAME.json'
    tg.parent.mkdir(parents=True)
    tg.write_text('{"v": "lock"}')
    _git(r, 'add', '-A')
    _git(r, 'commit', '-qm', 'lock', date='2026-10-01T21:28:43+00:00')
    tg.write_text('{"v": "later"}')
    _git(r, 'commit', '-qam', 'later', date='2026-10-08T13:34:12+00:00')
    _gz(pg / 'pbp_2025.cccccccccccccccc.csv.gz', 'week,x\n1,1\n')      # untracked, no sidecar: no clock at all
    (r / 'nfl/derived').mkdir(parents=True)
    (r / 'nfl/derived/DST_RATES.json').write_text('{"gen": 1}')
    return r


def child(root, manifest, code):
    """Run `code` in a fresh interpreter with the manifest active against `root`. Returns (rc, stdout+stderr)."""
    pre = (f'import sys, json, pathlib; sys.path.insert(0, {str(_REPO)!r}); '
           f'from nfl.warehouse import point_in_time as PIT; '
           f'PIT._reset_for_tests({str(manifest)!r} if {bool(manifest)!r} else None, root={str(root)!r}); '
           f'R = pathlib.Path({str(root)!r})\n')
    r = subprocess.run([sys.executable, '-c', pre + code], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != PIT.ENV})
    return r.returncode, r.stdout + r.stderr


def test_classification():
    r = store()
    p, m = PIT.build(CUT, 'T', 'test', root=r, out_dir=r / 'out')
    a, f = m['admitted'], m['refused']
    check('nfl/research/postgame/pbp_2026.aaaaaaaaaaaaaaaa.csv.gz' in a, 'capture retrieved before the cut: admitted')
    check(f.get('nfl/research/postgame/pbp_2026.bbbbbbbbbbbbbbbb.csv.gz', {}).get('reason') == 'REFUSED_AFTER_CUTOFF',
          'capture retrieved after the cut: refused')
    check(f.get('nfl/research/postgame/pbp_2025.cccccccccccccccc.csv.gz', {}).get('reason') == 'REFUSED_UNCLOCKED',
          'capture with no clock (no sidecar, untracked): refused, never assumed early')
    w1 = a.get('nfl/vintage/weekly_rosters.1111111111111111.raw.csv.gz', {})
    check(w1.get('clock', '').startswith('2026-10-04'), 'vintage capture clock = EARLIEST PASS observation of its content')
    check(f.get('nfl/vintage/weekly_rosters.2222222222222222.raw.csv.gz', {}).get('reason') == 'REFUSED_AFTER_CUTOFF',
          'post-lock roster capture refused')
    s = a.get('nfl/vintage/schedules.3333333333333333.csv.gz', {})
    check(s.get('clock_basis') == 'GIT_FIRST_COMMIT' and s.get('clock', '').startswith('2026-10-01'),
          'unmanifested committed capture: clock = first commit (upper bound on retrieval)')
    tg = m['resolved'].get('nfl/warehouse/TEAM_GAME.json', {})
    check(tg.get('clock', '').startswith('2026-10-01'), 'TEAM_GAME resolves to the last commit at or before the cut')
    check(p.name == f'PIT_MANIFEST.T.{m["seal"][:16]}.json' and PIT._seal(m) == m['seal'], 'manifest named by its seal')
    p2, m2 = PIT.build(CUT, 'T', 'test', root=r, out_dir=r / 'out')
    check(p2 == p and m2['seal'] == m['seal'], 'rebuild from the same store is deterministic (same seal)')
    return r, p


def test_seal_and_immutability(r, p):
    bad = json.loads(p.read_text())
    bad['admitted']['nfl/research/postgame/pbp_2026.bbbbbbbbbbbbbbbb.csv.gz'] = {'sha256': 'x'}
    q = r / 'out/TAMPERED.json'
    q.write_text(json.dumps(bad))
    try:
        PIT.load(q, r)
        check(False, 'a manifest edited after sealing refuses')
    except PIT.PITManifestInvalid as e:
        check(str(e).startswith('PIT_MANIFEST_SEAL_BROKEN'), f'a manifest edited after sealing refuses: {str(e)[:40]}')
    try:
        PIT.build('2026-10-05T23:47:26', 'T', 'test', root=r, out_dir=r / 'out')
        check(False, 'a cutoff without a timezone refuses')
    except PIT.PITCutoffUnresolved:
        check(True, 'a cutoff without a timezone refuses')
    try:
        PIT.build(CUT, 'T', '', root=r, out_dir=r / 'out')
        check(False, 'a cutoff without a stated basis refuses')
    except PIT.PITCutoffUnresolved:
        check(True, 'a cutoff without a stated basis refuses')


def test_live_identity(r):
    rc, out = child(r, None, "fs = sorted(str(x) for x in (R / 'nfl/research/postgame').glob('pbp_*.csv.gz'))\n"
                             "print(json.dumps([PIT.admit(fs) == fs, PIT.resolve(R / 'x/TEAM_GAME.json') == R / 'x/TEAM_GAME.json',"
                             " PIT.active() is None, open(R / 'nfl/warehouse/TEAM_GAME.json').read()]))")
    v = json.loads(out.strip().splitlines()[-1]) if rc == 0 else None
    check(v is not None and v[:3] == [True, True, True], 'no manifest: admit and resolve are the identity')
    check(v is not None and v[3] == '{"v": "later"}', 'no manifest: no read is refused (live path unchanged)')


READER = ("from nfl.tools import dst_model as D\nD.PBP_DIR = R / 'nfl/research/postgame'\n"
          "c = D._capture(2026)\nprint('PICK', c.name if c else None)\n")


def test_injection_and_negative_control(r, p):
    rc, out = child(r, p, READER)
    check(rc == 0 and 'PICK pbp_2026.aaaaaaaaaaaaaaaa.csv.gz' in out,
          f'sealed run: dst_model._capture picks the pre-cut capture, not the larger post-lock one ({out.strip()[-40:]})')
    _gz(r / 'nfl/research/postgame/pbp_2026.dddddddddddddddd.csv.gz',      # the largest capture: dst_model's rule
        'week,x\n' + ''.join(f'4,{i * 7919 % 10007}\n' for i in range(2000)))
    (r / 'nfl/research/postgame/pbp_2026.dddddddddddddddd.csv.provenance.json').write_text(
        json.dumps({'retrieved_at': '2026-10-01T00:00:00Z'}))     # an injected file that LIES about its clock
    rc, out = child(r, p, READER)
    check(rc == 0 and 'PICK pbp_2026.aaaaaaaaaaaaaaaa.csv.gz' in out,
          'sealed run: an injected capture (even one claiming a pre-cut clock) cannot reach the reader')
    rc, out = child(r, None, READER)
    check(rc == 0 and 'PICK pbp_2026.dddddddddddddddd.csv.gz' in out,
          'NEGATIVE CONTROL: with no manifest the same injection DOES move the reader (the test can detect a leak)')
    rc, out = child(r, p, "open(R / 'nfl/research/postgame/pbp_2026.dddddddddddddddd.csv.gz', 'rb').read()")
    check(rc != 0 and 'PIT_UNAUTHORIZED_READ' in out and 'NOT_IN_SEALED_MANIFEST' in out,
          'backstop: an unwired direct open of the injected capture refuses')
    rc, out = child(r, p, "open(R / 'nfl/research/postgame/pbp_2026.bbbbbbbbbbbbbbbb.csv.gz', 'rb').read()")
    check(rc != 0 and 'REFUSED_AFTER_CUTOFF' in out, 'backstop: an unwired direct open of a post-cut capture refuses')
    rc, out = child(r, p, "import gzip; gzip.open(R / 'nfl/research/postgame/pbp_2026.aaaaaaaaaaaaaaaa.csv.gz','rt').read()")
    check(rc == 0, 'backstop: an admitted capture opens')


def test_tamper_and_resolve(r, p):
    rc, out = child(r, p, "print('TG', open(PIT.resolve(R / 'nfl/warehouse/TEAM_GAME.json')).read())")
    check(rc == 0 and 'TG {"v": "lock"}' in out, 'resolve(TEAM_GAME) yields the bytes committed at the cut')
    rc, out = child(r, p, "open(R / 'nfl/warehouse/TEAM_GAME.json').read()")
    check(rc != 0 and 'PIT_UNRESOLVED_READ' in out, 'backstop: reading today\'s TEAM_GAME directly refuses')
    rc, out = child(r, p, "open(R / 'nfl/derived/DST_RATES.json').read()")
    check(rc != 0 and 'PIT_DERIVED_UNPINNED' in out, 'backstop: an unpinned derived cache refuses')
    f = r / 'nfl/research/postgame/pbp_2026.aaaaaaaaaaaaaaaa.csv.gz'
    keep = f.read_bytes()
    _gz(f, 'week,x\n1,999\n')
    rc, out = child(r, p, READER)
    check(rc != 0 and 'PIT_ADMITTED_FILE_CHANGED' in out, 'an admitted capture whose bytes changed refuses')
    f.write_bytes(keep)
    f.rename(f.with_suffix('.moved'))
    try:
        PIT.load(p, r)
        check(False, 'an admitted capture missing on disk refuses')
    except PIT.PITManifestInvalid as e:
        check(str(e).startswith('PIT_ADMITTED_FILE_MISSING'), 'an admitted capture missing on disk refuses')
    f.with_suffix('.moved').rename(f)


def test_pinned_derived():
    r = store()
    pins = r / 'pins.json'
    pins.write_text(json.dumps({'sha256': {'DST_RATES.json': PIT.sha256(r / 'nfl/derived/DST_RATES.json')}}))
    p, _ = PIT.build(CUT, 'P', 'test', root=r, derived_pins=pins, out_dir=r / 'out')
    rc, _o = child(r, p, "open(R / 'nfl/derived/DST_RATES.json').read()")
    check(rc == 0, 'a derived cache matching its declared pin opens')
    (r / 'nfl/derived/DST_RATES.json').write_text('{"gen": 2}')
    rc, out = child(r, p, "open(R / 'nfl/derived/DST_RATES.json').read()")
    check(rc != 0 and 'PIT_DERIVED_VINTAGE_MISMATCH' in out, 'a derived cache rebuilt from other vintages refuses')


def test_real_atl_cutoff():
    out = pathlib.Path(tempfile.mkdtemp(prefix='pit_real_'))
    _p, m = PIT.build('2026-10-05T23:47:26+00:00', 'ATL_NO_2026W4', 'ATL@NO production commit 9736516d',
                      out_dir=out)
    want = ('nfl/research/postgame/pbp_2026.2b3e9f2c6f92123f.csv.gz',
            'nfl/vintage/weekly_rosters.efd424c87b892728.raw.csv.gz',
            'nfl/vintage/weekly_rosters.dba8eeff1f9c0878.raw.csv.gz')
    check(all(m['refused'].get(w, {}).get('reason') == 'REFUSED_AFTER_CUTOFF' for w in want),
          'ATL@NO cutoff refuses exactly the post-lock PBP and roster captures the hand-built replay deleted')
    check(m['resolved']['nfl/warehouse/TEAM_GAME.json']['commit'].startswith('8feac0f3'),
          'ATL@NO cutoff resolves TEAM_GAME to 8feac0f3 (the version committed at lock)')
    check(m['counts']['refused_unclocked'] == 0, f"every capture on disk carries a clock ({m['counts']})")
    # The backstop must not depend on the reader importing anything wired: `import nfl` alone arms it. (Found
    # 2026-10-08: kicker_model read play-by-play through warehouse.sources and its process never armed the guard.)
    env = dict(os.environ, **{PIT.ENV: str(_p)})
    code = (f"import sys; sys.path.insert(0, {str(_REPO)!r}); import nfl; "
            f"open({str(_REPO / want[0])!r}, 'rb').read(1)")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
    check(r.returncode != 0 and 'PIT_UNAUTHORIZED_READ' in r.stderr and 'REFUSED_AFTER_CUTOFF' in r.stderr,
          'a process that only imports `nfl` cannot open the post-lock ATL@NO capture')
    code = (f"import sys; sys.path.insert(0, {str(_REPO)!r}); from nfl.warehouse import sources as S; "
            f"o = S.select(S.registry()['play_by_play'], season=2026); print('SEL', o.value['selected'])")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
    check(r.returncode == 0 and '2b3e9f2c' not in r.stdout and 'SEL ' in r.stdout,
          f"warehouse.sources selects a pre-lock 2026 capture under the ATL manifest ({r.stdout.strip()[-60:] or r.stderr[-200:]})")


if __name__ == '__main__':
    print('test_classification')
    r, p = test_classification()
    print('test_seal_and_immutability')
    test_seal_and_immutability(r, p)
    print('test_live_identity')
    test_live_identity(r)
    print('test_injection_and_negative_control')
    test_injection_and_negative_control(r, p)
    print('test_tamper_and_resolve')
    test_tamper_and_resolve(r, p)
    print('test_pinned_derived')
    test_pinned_derived()
    print('test_real_atl_cutoff')
    test_real_atl_cutoff()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
