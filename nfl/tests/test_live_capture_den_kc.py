"""The live pregame capture for 2026_01_DEN_KC, tested against what it claims.

WHAT IS UNDER TEST, AND WHAT IS NOT

Not the forecast. Not the model. This module asserts that the EVIDENCE for one
specific live game -- Denver at Kansas City, kickoff 2026-09-15T00:15:00Z -- is
what the capture record says it is, on disk, right now.

Six properties, each of which has already failed once somewhere in this project:

  RETENTION      Ruling 3: raw bytes, raw hash, transformation version,
                 reduced artifact, reduced hash. And the sixth thing, which is
                 the one that actually bit: the raw bytes must not live ONLY in
                 a gitignored directory. WS-L measured raw retention as a
                 property of which machine looked -- 6 of 6 Actions-only
                 vintages lost their raw bytes, 7 of 7 seen elsewhere kept
                 them. This module checks the gitignore status by RUNNING
                 `git check-ignore`, not by reading .gitignore and believing it.

  INTEGRITY      every digest in the manifest row re-hashes to the bytes on
                 disk. A row is not evidence until its bytes match it.

  CHRONOLOGY     selection takes a cutoff and cannot be called without one.
                 A cutoff before every capture yields a refusal, not the
                 nearest file. Filesystem mtime is never consulted -- asserted
                 by TOUCHING the blobs into a misleading mtime order and
                 checking the selection does not move.

  AUTHORITY      the nflverse injuries feed is a MIRROR. nfl.com is refused by
                 this executor's proxy. The mirror standing in for it is a
                 recorded downgrade, and being the only source in hand is not
                 a promotion.

  ABSENCE        an unreachable official source is evidence with a refusal code
                 attached, and no player's status may be inferred from not
                 appearing in a feed.

  MARKET         the eight sportsbook columns are POPULATED for this game in
                 the captured file, and provably absent -- by key, by value and
                 by the ingest gate -- from anything a forecast is handed. The
                 negative control is the point: the proof is shown to FAIL when
                 a market value is planted, so passing means something.

NO NETWORK IS REQUIRED and none is used. Everything here reads the committed
capture record and the blobs it names.

Run standalone:  python3.12 nfl/tests/test_live_capture_den_kc.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome, State  # noqa: E402
from nfl.capture import live_game_evidence as LGE  # noqa: E402
from nfl.capture import registry as REG  # noqa: E402
from nfl.ingest import allowlist as ALLOW  # noqa: E402
from nfl.production.nonqb import vintage_selector as VS  # noqa: E402

GAME_ID = '2026_01_DEN_KC'
KICKOFF = '2026-09-15T00:15:00+00:00'
# A cutoff AFTER the live capture of 2026-09-14T16:16Z and well before kickoff.
# Fixed, not "now": a test whose cutoff moves is a test whose subject moves.
CUTOFF = '2026-09-14T17:00:00Z'

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
VINTAGE = _REPO / 'nfl' / 'vintage'

PASSED = FAILED = BLOCKED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(cond)


def blocked(label, why):
    """A check that could not run. Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


_BUNDLE = None


def bundle():
    """The bundle at the fixed cutoff, built once. Never with a default clock."""
    global _BUNDLE
    if _BUNDLE is None:
        _BUNDLE = LGE.bundle(GAME_ID, CUTOFF, live_probe=False)
    return _BUNDLE


def _rows():
    if not MANIFEST.exists():
        return []
    out = []
    for line in MANIFEST.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def _read(rel):
    p = _REPO / rel
    if p.name.endswith('.gz'):
        with gzip.open(p, 'rb') as fh:
            return fh.read()
    return p.read_bytes()


# --------------------------------------------------------------- the game
def test_a_the_game_is_the_one_we_think_it_is():
    print('\nA. game identity comes from a clocked schedules vintage')
    out = bundle()
    if out.state is not State.PASS:
        check('the bundle builds at the cutoff', False,
              f'{out.state.value}[{out.code}] {out.detail[:200]}')
        return
    v = out.value
    g = v['game']
    check('game_id is the live game', v['game_id'] == GAME_ID, v['game_id'])
    check('Denver at Kansas City',
          g['away_team'] == 'DEN' and g['home_team'] == 'KC', str(g)[:120])
    check('kickoff is the Monday night slot',
          v['kickoff_utc'] == KICKOFF, str(v['kickoff_utc']))
    check('and the cutoff is provably pregame',
          v['cutoff_is_pregame'] is True,
          f"cutoff {v['cutoff_utc']} vs kickoff {v['kickoff_utc']}")
    check('the venue and surface came from the capture, not from prose',
          g['stadium'] == 'GEHA Field at Arrowhead Stadium'
          and g['roof'] == 'outdoors' and g['surface'] == 'grass', str(g)[:200])
    check('it is a divisional game', g['div_game'] == '1', g['div_game'])
    check('the identity blob is a captured artifact on disk',
          (_REPO / v['game_identity_blob']).exists(), v['game_identity_blob'])


# ------------------------------------------------------------- retention
def test_b_ruling_3_retention_is_complete_for_tonight_s_capture():
    print('\nB. RAW BYTES / RAW HASH / TRANSFORM VERSION / REDUCED / REDUCED HASH')
    out = bundle()
    if out.state is not State.PASS:
        blocked('retention', f'{out.code}')
        return
    for fam in LGE.FAMILIES:
        rec = out.value['sources'][fam]
        ret = rec['retention_ruling3']
        if ret['status'] == 'RULING3_PREDATES_POLICY__RECORD_ABSENT':
            # HONEST, AND NOT A PASS. Historical rows carry no retention block
            # and cannot acquire one; the ceiling is reported and the check is
            # not counted as satisfied.
            blocked(f'{fam}: Ruling 3 record',
                    'this vintage predates the durable raw retention policy; '
                    'its raw bytes were never retained durably and cannot be '
                    'recovered by re-fetching, because a later fetch is '
                    'different bytes')
            continue
        check(f'{fam}: Ruling 3 retention is complete',
              ret['status'] == 'RULING3_COMPLETE', ret['status'])
        check(f'  {fam}: raw bytes and raw hash are both named',
              bool(ret['raw_bytes']) and bool(ret['raw_hash']),
              str(ret)[:160])
        check(f'  {fam}: the transformation version is recorded',
              bool(ret['transformation_version']),
              str(ret['transformation_version']))
        check(f'  {fam}: the raw bytes are on disk',
              ret['raw_bytes_present_on_disk'] is True, str(ret['raw_bytes']))
        check(f'  {fam}: raw retention is durable, not ephemeral',
              ret['raw_blob_durable'] is True and
              ret['raw_home_is_gitignored_only'] is False, str(ret)[:160])
        if rec['durability'] == 'reduce':
            check(f'  {fam}: the reduced artifact and its hash are recorded '
                  f'as a DERIVATIVE, beside the raw',
                  bool(ret['reduced_artifact']) and bool(ret['reduced_hash'])
                  and ret['reduced_hash'] != ret['raw_hash'],
                  str(ret)[:200])


def test_c_a_gitignored_sole_home_would_not_satisfy_ruling_3():
    print('\nC. the raw home is asked of git, not of .gitignore')
    out = bundle()
    if out.state is not State.PASS:
        blocked('gitignore status', out.code)
        return
    paths = [out.value['sources'][f]['retention_ruling3']['raw_bytes']
             for f in LGE.FAMILIES
             if out.value['sources'][f]['retention_ruling3'].get('raw_bytes')]
    if not check('there is at least one durable raw artifact to ask about',
                 bool(paths)):
        return
    for rel in paths:
        r = subprocess.run(['git', 'check-ignore', '-q', rel],
                           cwd=str(_REPO), capture_output=True)
        # exit 1 == NOT ignored. This is the whole point: the previous home,
        # nfl_vintage/raw/, exits 0 here.
        check(f'{rel} is NOT gitignored', r.returncode == 1,
              f'git check-ignore returned {r.returncode}')
    r = subprocess.run(['git', 'check-ignore', '-q', 'nfl_vintage/raw/x.csv'],
                       cwd=str(_REPO), capture_output=True)
    check('  and the OLD ephemeral home still is -- so this is a real move, '
          'not a relabelling', r.returncode == 0,
          f'git check-ignore returned {r.returncode}')


def test_d_every_digest_rehashes_to_the_bytes_on_disk():
    print('\nD. a row is not evidence until its bytes match it')
    out = bundle()
    if out.state is not State.PASS:
        blocked('integrity', out.code)
        return
    n = 0
    for fam in LGE.FAMILIES:
        av = out.value['sources'][fam]['artifact_verification']
        for label, res in av.items():
            if res.get('state') in ('VERIFIED',
                                    'VERIFIED_VIA_UPSTREAM_DIGEST__ROW_'
                                    'PREDATES_TWO_DIGEST_SCHEMA',
                                    'VERIFIED_AS_THE_SAME_OBJECT'):
                check(f'{fam}:{label} verifies ({res["state"]})', True)
                n += 1
            elif res.get('is_failure'):
                check(f'{fam}:{label} verifies', False, str(res)[:200])
                n += 1
            else:
                blocked(f'{fam}:{label}', res.get('state', '?'))
    check('the bundle records no failed artifact verification',
          not out.value['completeness']['families_with_unverified_artifacts'],
          str(out.value['completeness']))
    check('  and something was actually re-hashed -- an empty integrity '
          'check is not a clean one', n >= 4, f'{n} artifacts checked')


def test_e_the_retained_raw_depth_chart_is_the_full_series_not_one_slice():
    print('\nE. what the durable raw actually bought')
    out = bundle()
    if out.state is not State.PASS:
        blocked('depth chart raw', out.code)
        return
    rec = out.value['sources']['depth_charts']
    raw = rec['retention_ruling3'].get('raw_bytes')
    red = rec['blob']
    if not raw or not (_REPO / raw).exists():
        blocked('depth chart raw series',
                'no durable raw depth chart artifact at this cutoff')
        return
    import csv, io
    dts_raw = {r['dt'] for r in csv.DictReader(
        io.StringIO(_read(raw).decode('utf-8', 'replace'))) if r.get('dt')}
    dts_red = {r['dt'] for r in csv.DictReader(
        io.StringIO(_read(red).decode('utf-8', 'replace'))) if r.get('dt')}
    check('the REDUCED blob holds exactly one dt slice, as declared',
          len(dts_red) == 1, str(sorted(dts_red))[:120])
    # The upstream file is cumulative, so retaining it durably retains the
    # whole prior series -- which is what WS-L measured as persisted nowhere.
    check('the RAW blob holds the full cumulative dt series',
          len(dts_raw) > 100, f'{len(dts_raw)} dt slices')
    check('  and it contains the reduced slice', dts_red <= dts_raw)
    check('  the newest slice is from the day of the game',
          max(dts_raw).startswith('2026-09-14'), max(dts_raw))


# ------------------------------------------------------------- chronology
def test_f_selection_requires_a_clock_and_refuses_without_one():
    print('\nF. no clock is not any clock')
    raised = False
    try:
        VS.select('depth_charts')
    except VS.VintageClockUnresolved:
        raised = True
    check('selecting with no cutoff raises rather than defaulting to now',
          raised, 'a selector that defaults takes the newest file on disk')
    o = LGE.bundle(GAME_ID, 'not-a-timestamp')
    check('an unparseable cutoff is a named FAIL, not a silent now',
          o.state is State.FAIL and o.code == 'CUTOFF_UNPARSEABLE',
          f'{o.state.value}[{o.code}]')


def test_g_a_cutoff_before_the_captures_yields_a_refusal_not_the_nearest_file():
    print('\nG. widening the cut to reach evidence is the defect, not the fix')
    o = LGE.bundle(GAME_ID, '2026-01-01T00:00:00Z', live_probe=False)
    check('a cutoff before every capture refuses',
          o.state is not State.PASS,
          f'{o.state.value}[{o.code}] -- a PASS here means the cut was widened')
    check('  and it refuses by a named code',
          o.code in ('EVIDENCE_INCOMPLETE_AT_CUTOFF',
                     'VINTAGE_NO_LAWFUL_CAPTURE',
                     'GAME_NOT_IN_SCHEDULE_VINTAGE'), o.code)


def test_h_selection_does_not_move_when_mtime_is_made_misleading():
    print('\nH. filesystem mtime is not information time -- asserted, not hoped')
    out = bundle()
    if out.state is not State.PASS:
        blocked('mtime independence', out.code)
        return
    fam = 'depth_charts'
    before = VS.select(fam, as_of=CUTOFF)
    if not check('a vintage is selected to begin with',
                 before.state is State.PASS, before.code):
        return
    paths = sorted(VINTAGE.glob(f'{fam}.*.reduced.csv.gz'))
    if len(paths) < 2:
        blocked('mtime independence',
                f'only {len(paths)} {fam} blobs; the test needs two to '
                'reorder')
        return
    saved = {p: (p.stat().st_atime_ns, p.stat().st_mtime_ns) for p in paths}
    try:
        # Make the OLDEST-selected blob look newest, and the selected one
        # oldest. If anything in the path consulted mtime, this moves it.
        chosen = _REPO / before.value.blob
        for i, p in enumerate(paths):
            os.utime(p, ns=(saved[p][0], 1_700_000_000_000_000_000 + i))
        os.utime(chosen, ns=(saved[chosen][0], 1_000_000_000_000_000_000))
        after = VS.select(fam, as_of=CUTOFF)
        check('the selection is unchanged after mtime is inverted',
              after.state is State.PASS
              and after.value.blob == before.value.blob,
              f'{before.value.blob} -> '
              f'{after.value.blob if after.state is State.PASS else after.code}')
        b2 = LGE.bundle(GAME_ID, CUTOFF, live_probe=False)
        check('  and the whole bundle is unchanged too',
              b2.state is State.PASS
              and b2.value['sources'][fam]['blob']
              == out.value['sources'][fam]['blob'],
              f'{b2.state.value}[{b2.code}]')
    finally:
        for p, (a, m) in saved.items():
            os.utime(p, ns=(a, m))


def test_i_every_capture_preserves_the_nine_required_fields():
    print('\nI. SOURCE / URL / RAW BYTES / RAW HASH / PERSISTED HASH / '
          'RETRIEVED_AT / OBSERVATION TIME / ELIGIBILITY / AUTHORITY')
    out = bundle()
    if out.state is not State.PASS:
        blocked('required fields', out.code)
        return
    required = ('source', 'url', 'raw_bytes', 'raw_hash',
                'persisted_content_sha256', 'retrieved_at',
                'observation_time', 'forecast_cutoff_eligibility', 'authority')
    for fam in LGE.FAMILIES:
        rec = out.value['sources'][fam]
        missing = [k for k in required if not rec.get(k)]
        check(f'{fam} preserves all nine', not missing, f'missing {missing}')
        check(f'  {fam}: the observation clock is attributed, not asserted',
              bool(rec.get('observation_time_authority')),
              str(rec.get('observation_time_authority')))
        check(f'  {fam}: eligibility is stated against the cutoff',
              rec['forecast_cutoff_eligibility'] == 'LAWFUL_AT_CUTOFF'
              and rec['retrieved_at'] <= out.value['cutoff_utc'].replace(
                  '+00:00', '') or rec['forecast_cutoff_eligibility']
              == 'LAWFUL_AT_CUTOFF',
              str(rec.get('lawful_because')))


# -------------------------------------------------------------- authority
def test_j_the_mirror_does_not_occupy_the_governing_slot_silently():
    print('\nJ. a mirror is not promoted by being the only thing reachable')
    out = bundle()
    if out.state is not State.PASS:
        blocked('authority', out.code)
        return
    check('the nflverse injuries feed is registered ARCHIVE, not OFFICIAL',
          REG.BY_NAME['injuries'].authority is REG.SourceAuthority.ARCHIVE,
          REG.BY_NAME['injuries'].authority.value)
    check('  and it discharges no capture kind',
          REG.BY_NAME['injuries'].serves_kinds == ()
          and not REG.can_discharge('injuries', 'final_status')
          and not REG.can_discharge('injuries', 'inactives'),
          str(REG.BY_NAME['injuries'].serves_kinds))
    check('the governing injury source is registered OFFICIAL',
          REG.BY_NAME['official_injury_report'].authority
          is REG.SourceAuthority.OFFICIAL)
    downs = {d['slot']: d for d in out.value['authority_downgrades']}
    check('the injuries slot is recorded as DOWNGRADED',
          downs.get('injuries', {}).get('status')
          == 'DOWNGRADED__MIRROR_IN_A_GOVERNING_SLOT',
          str(downs.get('injuries', {}).get('status')))
    check('  naming the governing source it stands in for',
          downs.get('injuries', {}).get('governing_source')
          == 'official_injury_report')
    check('  and refusing the promotion explicitly',
          downs['injuries']['authority_promotion'] is False
          and downs['injuries']['stand_in_authority'] == 'ARCHIVE')
    check('the inactives slot is UNFILLED -- no source of any authority',
          downs.get('inactives', {}).get('status')
          == 'UNFILLED__NO_SOURCE_OF_ANY_AUTHORITY',
          str(downs.get('inactives', {}).get('status')))
    check('  and nothing is offered as a stand-in for it',
          downs['inactives']['stand_in_source'] is None)
    check('the mirror ceiling names what it cannot answer',
          'inactives' in downs['injuries']['ceiling']
          and 'omission is not an observation'
          in downs['injuries']['ceiling'])


def test_k_an_absent_official_source_is_evidence_with_a_code():
    print('\nK. the refusal is recorded, not the silence')
    rows = [r for r in _rows()
            if r.get('source') in ('official_injury_report',
                                   'official_inactives', 'espn_injuries_json')
            and r.get('state') == 'BLOCKED']
    if not check('the manifest holds recorded refusals for the official '
                 'sources', bool(rows), 'none found'):
        return
    latest = {}
    for r in rows:
        latest[r['source']] = r
    for name, r in sorted(latest.items()):
        ev = r.get('evidence') or {}
        check(f'{name}: the refusal carries a named code',
              bool(r.get('code')), str(r.get('code')))
        check(f'  {name}: and the URL that was attempted',
              bool(ev.get('url')), str(ev.get('url')))
        if ev.get('proxy_refusal_status'):
            check(f'  {name}: the transport\'s own status is preserved '
                  f'({ev["proxy_refusal_status"]})',
                  ev['proxy_refusal_status'] == '403',
                  str(ev.get('curl_stderr')))
        else:
            blocked(f'{name}: exact transport status',
                    'this refusal was recorded before curl stderr was kept; '
                    'the code is NO_EGRESS with no gateway status behind it')
    out = bundle()
    if out.state is not State.PASS:
        blocked('absence semantics', out.code)
        return
    for name, rec in out.value['unreachable_official_sources'].items():
        check(f'{name} is carried as evidence, not omitted',
              rec.get('is_evidence_not_a_gap') is True)
        check(f'  {name}: nothing may be inferred from its absence',
              rec.get('may_be_inferred_from_absence') is False)
        check(f'  {name}: the source is not declared dead because WE cannot '
              f'reach it',
              rec.get('source_status') != 'KNOWN_DEAD'
              and 'different facts' in rec.get('interpretation', ''),
              str(rec.get('source_status')))


# ----------------------------------------------------------------- market
def test_l_the_sportsbook_columns_are_populated_and_provably_excluded():
    print('\nL. the market is in the file and not in the forecast')
    out = bundle()
    if out.state is not State.PASS:
        blocked('market exclusion', out.code)
        return
    m = out.value['market_exclusion']
    check('all eight market columns are declared quarantined',
          sorted(m['market_columns_declared']) == sorted(
              ['away_moneyline', 'home_moneyline', 'spread_line',
               'away_spread_odds', 'home_spread_odds', 'total_line',
               'under_odds', 'over_odds']),
          str(m['market_columns_declared']))
    # THE PROOF IS NOT VACUOUS, AND THAT HAS TO BE CHECKED FIRST. Proving that
    # empty fields did not leak proves nothing at all.
    check('they are POPULATED for this game -- the proof is not over blanks',
          m['proof_is_vacuous'] is False and m['n_populated_for_this_game'] == 8,
          str(m['market_columns_populated_for_this_game']))
    check('  and the proof records digests, never the prices themselves',
          len(m['market_value_sha256']) == 8
          and all(len(d) == 64 for d in m['market_value_sha256'].values())
          and 'market_values_in_the_captured_file' not in m,
          str(sorted(m.keys()))[:200])
    check('the proof is CLOSED: re-scanning the finished object, audit block '
          'included, still finds nothing',
          m['closure_check']['verdict'] == 'MARKET_PROVABLY_EXCLUDED'
          and m['closure_check']['key_hits'] == []
          and m['closure_check']['value_hits'] == [],
          str(m['closure_check']))
    check('no market column NAME appears in the emitted bundle',
          m['key_check']['hits'] == [], str(m['key_check']['hits']))
    check(f'  across {m["key_check"]["n_emitted_keys_scanned"]} keys scanned',
          m['key_check']['n_emitted_keys_scanned'] > 50)
    check('no market VALUE appears anywhere in the emitted bundle -- the '
          'check a rename does not defeat',
          m['value_check']['hits'] == [], str(m['value_check']['hits']))
    check(f'  across {m["value_check"]["n_emitted_values_scanned"]} values '
          f'scanned', m['value_check']['n_emitted_values_scanned'] > 100)
    check('the ingest gate refuses every one of them by name for FORECAST use',
          len(m['gate_check']) == 8
          and all(g['state'] == 'FAIL' and g['code'] == 'MARKET_COLUMN_ACCESS'
                  for g in m['gate_check'].values()),
          str(m['gate_check']))
    check('  the audit block keys every column under a prefix, so the closure '
          'scan needs no carve-out for the proof itself',
          all(k.startswith(m['audit_key_prefix'])
              for k in list(m['gate_check']) + list(m['market_value_sha256'])
              + list(m['market_columns_populated_for_this_game'])),
          m['audit_key_prefix'])
    check('and the columns actually emitted clear the same gate',
          m['emitted_columns_cleared_for_forecast']['state'] == 'PASS',
          str(m['emitted_columns_cleared_for_forecast']))
    check('the verdict is a measurement, not an assertion',
          m['verdict'] == 'MARKET_PROVABLY_EXCLUDED', m['verdict'])


def test_m_the_market_proof_fails_when_a_market_value_is_planted():
    print('\nM. the negative control -- a proof that cannot fail proves nothing')
    out = bundle()
    if out.state is not State.PASS:
        blocked('market negative control', out.code)
        return
    raw_row = None
    ident = LGE.game_identity(GAME_ID, CUTOFF)
    if ident.state is State.PASS:
        raw_row = ident.value['raw']
    if not check('the raw schedule row is readable for the control',
                 raw_row is not None):
        return

    clean = LGE.market_exclusion(raw_row, out.value)
    check('the clean bundle passes', clean['verdict']
          == 'MARKET_PROVABLY_EXCLUDED', clean['verdict'])

    # 1. plant the COLUMN NAME.
    planted_key = json.loads(json.dumps(out.value))
    planted_key['game']['total_line'] = raw_row['total_line']
    r1 = LGE.market_exclusion(raw_row, planted_key)
    check('planting the column name is caught by the key check',
          r1['verdict'] == 'NOT_PROVEN' and 'total_line' in
          r1['key_check']['hits'], str(r1['key_check']['hits']))

    # 2. plant the VALUE under an innocent name -- the rename attack.
    planted_val = json.loads(json.dumps(out.value))
    planted_val['game']['home_field_prior'] = raw_row['spread_line']
    r2 = LGE.market_exclusion(raw_row, planted_val)
    check('planting the VALUE under a harmless name is caught by the value '
          'check', r2['verdict'] == 'NOT_PROVEN'
          and any(h['matches_column'] == 'spread_line'
                  for h in r2['value_check']['hits']),
          str(r2['value_check']['hits'])[:200])

    # 3. and the bundle itself refuses to return PASS on a failed proof.
    check('a failed market proof is a named FAIL code in the bundle contract',
          'MARKET_EXCLUSION_NOT_PROVEN' in
          pathlib.Path(LGE.__file__).read_text(),
          'the refusal path must exist in the module')


def test_n_the_market_is_still_retained_in_the_raw_bytes():
    print('\nN. quarantine is not deletion -- Ruling 3 and rule 1 both hold')
    out = bundle()
    if out.state is not State.PASS:
        blocked('market retention', out.code)
        return
    raw = out.value['sources']['schedules']['retention_ruling3'].get('raw_bytes')
    if not raw or not (_REPO / raw).exists():
        blocked('market retention', 'no durable schedules raw artifact')
        return
    head = _read(raw).split(b'\n', 1)[0].decode()
    cols = head.split(',')
    check('the retained raw schedules file still carries the market columns',
          all(c in cols for c in ('spread_line', 'total_line',
                                  'away_moneyline')), head[:200])
    check('  so the bytes were kept, not censored',
          out.value['market_exclusion']['captured_not_consumed'].startswith(
              'The market columns ARE captured'))


# ------------------------------------------------------ cutoff arithmetic
def test_o_the_earliest_lawful_cutoff_is_reported_and_binding():
    print('\nO. the earliest cutoff the captured set actually supports')
    out = bundle()
    if out.state is not State.PASS:
        blocked('earliest cutoff', out.code)
        return
    e = out.value['earliest_lawful_cutoff']
    check('it is computed, not asserted', e['state'] == 'PASS', str(e)[:200])
    floor = e['earliest_lawful_cutoff_utc']
    check('every required family has a vintage at or before it',
          all(v <= floor for v in
              e['per_family_earliest_retrieved_at'].values()),
          str(e['per_family_earliest_retrieved_at']))
    check('the binding family is named', bool(e['binding_family']),
          str(e['binding_family']))
    check('  and it is the one that sets the floor',
          all(e['per_family_earliest_retrieved_at'][f] == floor
              for f in e['binding_family']))
    # A cutoff one microsecond earlier must not still produce a full bundle.
    import datetime as dt
    earlier = (VS.parse_ts(floor)
               - dt.timedelta(microseconds=1)).isoformat()
    o = LGE.bundle(GAME_ID, earlier, live_probe=False)
    check('a cutoff below the floor does not produce a complete bundle',
          o.state is not State.PASS, f'{o.state.value}[{o.code}]')


def test_p_the_inactives_obligation_for_this_game_is_honestly_unmet():
    print('\nP. what tonight\'s capture CANNOT do, said out loud')
    from nfl.capture.schedule import capture_plan
    plan = capture_plan(GAME_ID, '2026-09-14', '20:15')
    kinds = {c.kind for c in plan}
    check('the game carries an inactives target', 'inactives' in kinds,
          str(sorted(kinds)))
    ina = [c for c in plan if c.kind == 'inactives'][0]
    check('  whose window opens at T-90 and closes before kickoff',
          ina.window[0].isoformat() == '2026-09-14T22:45:00+00:00'
          and ina.window[1] < VS.parse_ts(KICKOFF),
          f'{ina.window[0].isoformat()}..{ina.window[1].isoformat()}')
    check('  and only official_inactives may discharge it',
          REG.can_discharge('official_inactives', 'inactives')
          and not any(REG.can_discharge(s.name, 'inactives')
                      for s in REG.REGISTRY
                      if s.name != 'official_inactives'),
          str([s.name for s in REG.REGISTRY
               if REG.can_discharge(s.name, 'inactives')]))
    # The point of this check: the gap must be visible in the record, and it
    # must NOT be closeable by anything this executor can reach.
    ok_sources = [s.name for s in REG.REGISTRY
                  if REG.can_discharge(s.name, 'inactives')
                  and s.executor_access is REG.ExecutorAccess.REACHABLE]
    check('no source this executor can reach may discharge it -- the gap is '
          'real and is not routed around', not ok_sources, str(ok_sources))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} failing check(s)')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    sys.exit(1 if FAILED else 0)
