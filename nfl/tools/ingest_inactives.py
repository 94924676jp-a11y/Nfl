#!/usr/bin/env python3.12
"""Obtain, validate, propagate and seal the official inactive list. One command.

    python3.12 nfl/tools/ingest_inactives.py \
        --game-id 2026_01_SF_LA --bytes /path/to/inactives.html \
        --source-url https://www.nfl.com/inactives/ \
        --retrieved-at 2026-09-10T23:05:00Z [--published-at ...] \
        --out nfl/research/live/2026_01_SF_LA

WHY A SCRIPT AND NOT A SEQUENCE OF COMMANDS AT THE KEYBOARD

The list publishes about ninety minutes before kickoff and everything after it
is on a clock. Improvising the chain under time pressure is how a step gets
skipped, and the step most likely to be skipped is a refusal. Every guard the
owner's ruling names is executed here in order, and any one of them stops the
run before a projection moves.

    1  bytes preserved before parsing, hashed, content-addressed, manifested
    2  BOTH clubs required -- one club is not POST_INACTIVES_COMPLETE
    3  identity resolved before anything is modified; ambiguity refuses and no
       partial set propagates
    4  OFFICIAL_INACTIVE comes from the list; pregame ACT stays ROSTER_ACTIVE
       and nothing here promotes it to GAME_ACTIVE
    5  every perishable source re-fetched and compared on the SF@LA CONSUMED
       SLICE, not the whole-file hash
    6  all five candidates sealed at one written_at, one seed, one boundary
    7  the pre-inactives tournament is never written to

WHAT IT WILL NOT DO. It will not accept a reporter's summary, a sportsbook
line, an inferred dress list, or a retrospective INA column. `--bytes` must be
the authoritative document.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State  # noqa: E402
from nfl.production.nonqb import inactives as INA  # noqa: E402
from nfl.research.shadow import information_set as IS  # noqa: E402

MODES = ('V1_CANDIDATE', 'V1_CANDIDATE_R5', 'V1_CANDIDATE_R6',
         'V1_CANDIDATE_R7', 'V1_CANDIDATE_R8')
CONSUMED = {
    'schedules': ('game_id', 'gameday', 'gametime', 'home_team', 'away_team',
                  'stadium', 'roof', 'surface'),
    'weekly_rosters': ('gsis_id', 'position', 'team', 'status'),
    'injuries': ('gsis_id', 'team', 'report_status', 'practice_status'),
    'depth_charts': ('dt', 'team', 'gsis_id', 'pos_abb', 'pos_rank'),
}


def _iso(d):
    return d.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def _now():
    return dt.datetime.now(dt.timezone.utc)


def consumed_slice(src, sha, season, week, teams, game_id):
    """Hash only the rows this game consumes. A file hash is not a football hash."""
    hits = sorted((_REPO / 'nfl' / 'vintage').glob(f'{src}.{sha[:16]}.*'))
    if not hits:
        return None, 0
    p = hits[0]
    op = gzip.open if p.suffix == '.gz' else open
    cols = CONSUMED.get(src)
    if cols is None:
        return None, 0
    keep = []
    for r in csv.DictReader(op(p, 'rt')):
        if src == 'schedules':
            ok = r.get('game_id') == game_id
        elif src == 'depth_charts':
            ok = r.get('team') in teams
        else:
            ok = (r.get('season') == str(season) and r.get('week') == str(week)
                  and r.get('team') in teams)
        if ok:
            keep.append('|'.join(str(r.get(c)) for c in cols))
    keep.sort()
    return hashlib.sha256('\n'.join(keep).encode()).hexdigest(), len(keep)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--bytes', required=True,
                    help='the AUTHORITATIVE document, saved to disk. Not a '
                         'summary, not a transcription.')
    ap.add_argument('--source-url', required=True)
    ap.add_argument('--retrieved-at', required=True)
    ap.add_argument('--published-at', default=None)
    ap.add_argument('--http-status', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--delivery', action='store_true',
                    help='the --bytes file is an EXTERNAL AUTHORITATIVE '
                         'DELIVERY (a networked agent\'s artifact citing the '
                         'official announcement), NOT the official page '
                         'itself. Names are verified verbatim against the '
                         'delivered artifact and the provenance is recorded '
                         'as such, so no reader can mistake it for a capture '
                         'of nfl.com.')
    ap.add_argument('--delivery-source-url', default=None,
                    help='the official URL the delivery cites.')
    ap.add_argument('--delivery-published-at', default=None,
                    help='publication time the official source itself '
                         'carried, kept apart from any retrieval clock.')
    ap.add_argument('--delivered-by', default=None,
                    help='who produced the delivered artifact.')
    ap.add_argument('--names-json', default=None,
                    help='JSON {"SF": ["First Last", ...], "LA": [...]} used '
                         'ONLY when the parser cannot read the page it was '
                         'given. Every name must occur verbatim in the stored '
                         'official bytes or the whole call is refused, so '
                         'this supplies the segmentation, never the '
                         'information.')
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--draws', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--dry-run', action='store_true',
                    help='validate and report, seal nothing')
    ap.add_argument('--vintage-root', default=None,
                    help='write the capture under this root instead of the '
                         'live vintage. REHEARSAL ONLY. It exists because a '
                         'rehearsal with synthetic bytes and no such flag '
                         'already put a fake inactives blob into the live '
                         'vintage once, and the information-set selector '
                         'immediately started choosing it as the real list.')
    a = ap.parse_args(argv)

    away, home = a.game_id.split('_')[2:4]
    teams = (away, home)
    rec = {'artifact': 'NFL_OFFICIAL_INACTIVES_INGESTION',
           'game_id': a.game_id, 'teams': list(teams),
           'parser_version': INA.SPEC_VERSION, 'steps': []}

    def step(name, ok, **ev):
        rec['steps'].append({'step': name, 'ok': bool(ok), **ev})
        mark = 'ok  ' if ok else 'STOP'
        print(f'  {mark} {name}' + (f'  {ev.get("detail", "")}' if ev.get('detail') else ''))
        return ok

    from nfl.tools.make_board import kickoff_for
    ko = kickoff_for(a.season, a.week, a.game_id)
    print(f'game {a.game_id}  kickoff {ko}  now {_iso(_now())}')

    # ---- 1. preserve the source exactly ---------------------------------
    src = pathlib.Path(a.bytes)
    if not src.exists():
        step('1. authoritative bytes present', False,
             detail=f'{src} does not exist')
        return _finish(rec, a, 2)
    raw = src.read_bytes()
    st = INA.store(raw, retrieved_at=a.retrieved_at,
                   published_at=a.published_at, source_url=a.source_url,
                   game_id=a.game_id, http_status=a.http_status,
                   root=a.vintage_root)
    rec['vintage_root'] = a.vintage_root or 'LIVE'
    if a.vintage_root:
        print('  !!   REHEARSAL: capture written under '
              f'{a.vintage_root}, not the live vintage')
    if not step('1. bytes stored before parsing', st.state is State.PASS,
                code=st.code, sha256=st.evidence.get('sha256'),
                n_bytes=st.evidence.get('n_bytes'),
                blob=st.value if st.state is State.PASS else None,
                retrieved_at=a.retrieved_at, published_at=a.published_at,
                source_url=a.source_url,
                detail=f'{st.evidence.get("n_bytes")} bytes, '
                       f'sha {str(st.evidence.get("sha256"))[:16]}'
                       if st.state is State.PASS else st.detail[:120]):
        return _finish(rec, a, 2)

    # ---- 2. both teams ---------------------------------------------------
    doc = raw.decode('utf-8', 'replace')
    if a.delivery:
        # THE DELIVERED ARTIFACT IS NOT THE OFFICIAL PAGE, AND IS NOT FILED AS
        # THOUGH IT WERE.
        #
        # This executor cannot reach the game-specific announcement; the
        # generic /inactives/ page it CAN reach is a placeholder carrying no
        # list, and verifying these names against that page would be checking
        # them against the wrong document. So the delivery itself is the
        # artifact of record: its bytes are hashed and stored before anything
        # is parsed, every supplied name must occur verbatim inside it, and
        # the provenance says plainly that the chain of custody runs through a
        # networked agent rather than through bytes we hold from nfl.com.
        if not a.names_json:
            step('2. both clubs represented', False,
                 code='DELIVERY_WITHOUT_NAMES',
                 detail='--delivery requires --names-json')
            return _finish(rec, a, 2)
        supplied = json.loads(pathlib.Path(a.names_json).read_text())
        supplied = {t: supplied[t] for t in teams if t in supplied}
        pa = INA.verify_supplied_names(doc, supplied)
        rec['provenance'] = {
            'kind': 'EXTERNAL_AUTHORITATIVE_DELIVERY',
            'official_source_url': a.delivery_source_url,
            'official_published_at': a.delivery_published_at,
            'delivered_by': a.delivered_by,
            'delivered_artifact_sha256': st.evidence.get('sha256'),
            'retrieved_at': a.retrieved_at,
            'what_this_is': (
                'Every name below occurs verbatim in the delivered artifact, '
                'whose bytes are stored and hashed. That is a real check and '
                'it is NOT the same as holding the official page: this '
                'executor could not fetch the game-specific announcement '
                '(HTTP 000, gateway CONNECT denial), so the chain of custody '
                'runs official page -> networked agent -> this artifact.'),
            'what_this_is_not': (
                'This is NOT a capture of nfl.com, and these names were NOT '
                'verified against the generic /inactives/ page, which is a '
                'placeholder carrying no list and is the wrong document.'),
        }
    else:
        pa = INA.parse(doc, list(teams))
    if not a.delivery and pa.state is not State.PASS and a.names_json:
        # THE OPERATOR SUPPLIES THE SEGMENTATION, NOT THE INFORMATION.
        # Every name is checked back against the bytes just stored, so a
        # name that is not in the league's own document cannot get in here.
        supplied = json.loads(pathlib.Path(a.names_json).read_text())
        supplied = {t: supplied[t] for t in teams if t in supplied}
        rec['machine_parse_refused'] = {'code': pa.code,
                                        'detail': pa.detail[:300]}
        pa = INA.verify_supplied_names(doc, supplied)
    if not step('2. both clubs represented', pa.state is State.PASS,
                code=pa.code, n_names=pa.evidence.get('n_names'),
                segmentation=pa.evidence.get('segmentation'),
                detail=str(pa.evidence.get('n_names') or pa.detail[:120])):
        return _finish(rec, a, 2)
    rec['segmentation'] = pa.evidence.get('segmentation')

    # ---- 3. identity before any projection moves -------------------------
    # THE REDUCED VINTAGE CARRIES NO NAME, SO IT CANNOT RESOLVE AN IDENTITY.
    #
    # The reduction keeps season, week, team, gsis_id and position -- which is
    # everything the POOL needs and nothing the official list needs, because
    # the list names players and the crosswalk has to run on names. The first
    # rehearsal of this script resolved 0 of 6 for exactly that reason, half an
    # hour before the window. The RAW capture retains `full_name`, so the pool
    # comes from the reduced blob and the crosswalk from the raw one, and the
    # raw file is chosen by the same chronology rule rather than by mtime.
    info = IS.build(ko, observed_before=_iso(_now()))
    rblob = info['sources']['weekly_rosters']['blob']
    roster = {}
    for r in csv.DictReader(gzip.open(_REPO / rblob, 'rt')):
        if (r.get('season') == str(a.season) and r.get('week') == str(a.week)
                and r.get('team') in teams and r.get('gsis_id')):
            roster[r['gsis_id']] = {
                'name': '', 'team': r.get('team'),
                'position': r.get('position')}
    sha = info['sources']['weekly_rosters']['sha256']
    rawp = _REPO / 'nfl_vintage' / 'raw' / f'weekly_rosters.{sha[:16]}.csv'
    rec['name_crosswalk'] = {'raw_blob': str(rawp.name),
                             'exists': rawp.exists(),
                             'same_content_hash_as_the_pool_vintage': True}
    if rawp.exists():
        for r in csv.DictReader(open(rawp)):
            pid = r.get('gsis_id')
            if pid in roster:
                roster[pid]['name'] = (r.get('full_name')
                                       or r.get('football_name') or '')
    if not roster:
        step('3. roster vintage resolves', False,
             detail=f'no {a.season} week {a.week} rows for {teams} in {rblob}')
        return _finish(rec, a, 2)
    named = sum(1 for v in roster.values() if v['name'])
    if not named:
        step('3. name crosswalk available', False,
             raw_blob=str(rawp), detail='the raw roster capture carrying '
             'full_name is not retained for the vintage the pool uses, so no '
             'name on the official list can be resolved to a gsis_id. '
             'Refusing rather than guessing.')
        return _finish(rec, a, 2)
    rs = INA.resolve(pa.value, roster)
    if not step('3. identity resolved', rs.state is State.PASS,
                code=rs.code, roster_blob=rblob, n_roster=len(roster),
                n_roster_with_a_name=named,
                n_resolved=rs.evidence.get('n_resolved'),
                n_unmapped=rs.evidence.get('n_unmapped'),
                unmapped=rs.evidence.get('unmapped'),
                detail=(f'{rs.evidence.get("n_resolved")} resolved, '
                        f'{rs.evidence.get("n_unmapped")} unmapped'
                        if rs.state is State.PASS else rs.detail[:150])):
        return _finish(rec, a, 2)

    # ---- 4. game status, established independently of roster status ------
    se = INA.sets(rs.value, roster, list(teams), retrieved_at=a.retrieved_at,
                  kickoff_utc=ko, game_id=a.game_id)
    if not step('4. POST_INACTIVES_COMPLETE', se.state is State.PASS,
                code=se.code,
                n_inactive_by_team=se.evidence.get('n_inactive_by_team'),
                inactive_by_team=se.evidence.get('inactive_by_team'),
                hours_before_kickoff=se.evidence.get('hours_before_kickoff'),
                teams_without_a_list=se.evidence.get('teams_without_a_list'),
                detail=str(se.evidence.get('n_inactive_by_team')
                           or se.detail[:150])):
        return _finish(rec, a, 2)
    states = se.value['states']
    promoted = [p for p, v in states.items() if v == INA.GAME_ACTIVE]
    if not step('4b. no player promoted to GAME_ACTIVE', not promoted,
                n_official_inactive=se.evidence['n_official_inactive'],
                n_not_listed=se.evidence['n_not_listed_inactive'],
                detail='absence from the list carries no positive claim'):
        return _finish(rec, a, 2)

    # ---- 5. re-fetch perishables, compare the CONSUMED SLICE -------------
    subprocess.run([sys.executable, str(_REPO / 'nfl/tools/capture_vintage.py'),
                    '--season', str(a.season)], capture_output=True)
    after = IS.build(ko, observed_before=_iso(_now()))
    slices = {}
    for s in sorted(CONSUMED):
        b = info['sources'].get(s)
        c = after['sources'].get(s)
        hb, nb = consumed_slice(s, b['sha256'], a.season, a.week, teams,
                                a.game_id) if b else (None, 0)
        hc, nc = consumed_slice(s, c['sha256'], a.season, a.week, teams,
                                a.game_id) if c else (None, 0)
        slices[s] = {'file_before': (b or {}).get('sha256', '')[:16],
                     'file_after': (c or {}).get('sha256', '')[:16],
                     'file_moved': bool(b and c and b['sha256'] != c['sha256']),
                     'slice_before': (hb or '')[:16],
                     'slice_after': (hc or '')[:16],
                     'slice_moved': bool(hb and hc and hb != hc),
                     'rows': nc,
                     'observed_at': (c or {}).get('observed_at')}
    moved = [s for s, v in slices.items() if v['slice_moved']]
    step('5. perishables re-fetched, consumed slice compared', True,
         slices=slices, slices_moved=moved,
         detail=f'{len(moved)} consumed slice(s) moved: {moved or "none"}')

    # ---- 6/7. seal all five, never touching the pre-inactives boards -----
    out = pathlib.Path(a.out)
    written_at = _iso(_now() - dt.timedelta(seconds=30))
    rec['written_at'] = written_at
    rec['kickoff_utc'] = ko
    if a.dry_run:
        step('6. tournament', True, detail='DRY RUN, nothing sealed')
        return _finish(rec, a, 0)
    from nfl.tools.make_board import build_one
    fx_ids = sorted(se.value['inactive'])
    sealed = {}
    for mode in MODES:
        d = out / f'post_inactives_{mode}'
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
        try:
            summary, bd, run_dir = build_one(
                a.season, a.week, a.game_id, written_at, str(d), a.draws,
                a.seed, mode, inactive_ids=fx_ids)
        except SystemExit as e:
            step(f'6. {mode}', False, detail=str(e)[:200])
            return _finish(rec, a, 2)
        if bd is None:
            first = next((s for s in summary['stages']
                          if s['state'] not in ('PASS', 'NOT_APPLICABLE')), {})
            step(f'6. {mode}', False,
                 detail=f'{first.get("stage")}: {first.get("code")}')
            return _finish(rec, a, 2)
        art = json.loads((pathlib.Path(run_dir) /
                          'forecast_artifact.json').read_text())
        sealed[mode] = {'run_id': summary.get('run_id'),
                        'draw_artifact_sha256': art.get('draw_artifact_sha256'),
                        'dir': str(pathlib.Path(run_dir).relative_to(_REPO))
                        if str(run_dir).startswith(str(_REPO)) else str(run_dir)}
        step(f'6. {mode}', True, detail=sealed[mode]['run_id'])
    rec['sealed'] = sealed
    pre = out.glob('pre_inactives_*/forecast_artifact.json')
    step('7. pre-inactives boards untouched',
         all(json.loads(p.read_text()).get('promoted') is False for p in pre),
         detail='every pre-inactives artifact still promoted=False')
    return _finish(rec, a, 0)


def _finish(rec, a, code):
    rec['result'] = 'COMPLETE' if code == 0 else 'REFUSED'
    p = pathlib.Path(a.out) / 'INACTIVES_INGESTION.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1) + '\n')
    print(f'{rec["result"]}  record written to {p}')
    return code


if __name__ == '__main__':
    sys.exit(main())
