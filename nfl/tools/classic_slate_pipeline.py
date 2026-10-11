#!/usr/bin/env python3.12
"""The lock-critical classic-slate run, in order, one process per stage, with a ledger.

    python3.12 nfl/tools/classic_slate_pipeline.py 2026W4 --as-of 2026-10-04T15:40:00Z \
        [--evidence-packet nfl/dfs/salaries/evidence/<packet>.json] --page <scratch>/page.html

Owner priority 17 (2026-10-03). Each stage is the production tool itself, run as a separate process
so a firewall that refuses on imported modules (FantasyCruncher, Hard Rock) sees a clean process.
The run STOPS at the first stage that refuses, except the two downstream comparisons (FC, Hard Rock),
whose refusal is recorded and does not touch a lineup.

  0 snapshot       copy the current artifacts to runs/<slate>/<utc>/ for the change log
  1 state          DK universe, freshness gate, identity, availability, inactives, depth
  2 run            role state -> football-only projection -> sanity gate -> 2,000 joint worlds
  3 book           research book, team accounting gate, forecast seal
  4 portfolios     150-max, 20-max, 3-entry (refused without a current book with accounting PASS),
                   built IN PARALLEL with two tagged reproducibility builds (reproA, reproB) that the
                   audit compares byte for byte; a stale pair reads STALE, never PASS
  5 verify         independent upload verifier
  5b release       release record (classic_release.py): hash chain, evidence currency, world accounting, contest
                   overlap, open defects -> one of the owner's five release states, written beside the upload
  6 book           rebuilt with exposures (the seal time stands if the worlds are unchanged)
  7 board          owner board and exposure reasoning
  8 fc             FantasyCruncher comparison, clean process, EXTERNAL_COMPARISON_ONLY
  9 props          Hard Rock comparison against the seal (BLOCKED until a post-seal board exists)
 10 audit          independent production audit
 11 prelock        does the evidence force another re-run? (recorded; feeds finalize)
 12 changes        change log against the snapshot
 13 finalize       FINAL_*_POST_INACTIVES files, only when every gate passes (classic_finalize.py)
 14 page           owner page

--evidence-packet (sunday_evidence.py) is passed to the state and prelock stages. A REHEARSAL packet
runs the whole chain and can never finalize.

TASK #45 (2026-10-11), the governed entry point:
  * LOCK CHECK before anything runs: a fresh timezone-aware clock against the slate's declared kickoff. A run that
    cannot finish before lock (declared runtime estimate, below) is REFUSED, never started and abandoned.
  * RUN ID: one per run, passed to every stage as NFL_CLASSIC_RUN_ID and written into the ledger; the release record
    names a portfolio built outside a ledgered run as NOT_ORCHESTRATED.
  * THE LEDGER IS WRITTEN AFTER EVERY STAGE, so a run that dies leaves a readable record of where it stopped.
  * THE SNAPSHOT NOW KEEPS THE WORLDS AND THE RELEASE RECORD. On 2026-10-11 the 16:08Z rebuild overwrote the 16:03Z
    build's draws and worlds in place, so that build's chain can no longer be re-verified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = _REPO / 'nfl/dfs/salaries'
PY = 'python3.12'
SNAP = ('STATE.json', 'PROJ.json', 'DRAWS.json', 'WORLDS.npz', 'RESEARCH_BOOK.json', 'PORTFOLIOS.json', 'UPLOAD.csv',
        'UPLOAD_VERIFY.json', 'RELEASE.json', 'PROP_DIAGNOSTIC.json', 'OWNER_BOARD.json', 'SEAL.json')
#: DECLARED runtime estimate for the stages up to the release record, measured 2026-10-11 on the W5 Early Only slate
#: (hand-run: state 16:05:35Z -> portfolios 16:17:29Z = 11.9 min) plus the verifier and release record (~0.2 min),
#: rounded up to 15 min. A run is refused when now + this would reach the earliest kickoff.
RUNTIME_ESTIMATE_MIN = 15.0
DOWNSTREAM_ONLY = {'fc', 'props'}
#: refusals recorded without stopping the run: the comparisons, and the two post-run verdicts
NON_STOPPING = DOWNSTREAM_ONLY | {'prelock', 'finalize'}


def stages(slate, as_of, inactives, page, packet=None):
    st = [PY, 'nfl/tools/classic_slate_state.py', slate, '--as-of', as_of]
    pre = [PY, 'nfl/tools/classic_prelock.py', slate]
    if inactives:
        st += ['--official-inactives', inactives]
        pre += ['--official-inactives', inactives]
    if packet:
        st += ['--evidence-packet', packet]
        pre += ['--evidence-packet', packet]
    port = [PY, 'nfl/opt/classic_portfolio.py', slate]
    return [('state', st),
            ('run', [PY, 'nfl/tools/classic_slate_run.py', slate]),
            ('book', [PY, 'nfl/tools/classic_research_book.py', slate]),
            # a list of commands is one stage run in parallel; the FIRST is the production build
            ('portfolios', [port, port + ['--tag', 'reproA'], port + ['--tag', 'reproB']]),
            ('verify', [PY, 'nfl/tools/classic_upload_verify.py', slate]),
            ('release', [PY, 'nfl/tools/classic_release.py', slate] + (['--latest-packet', packet] if packet else [])),
            ('book_with_exposures', [PY, 'nfl/tools/classic_research_book.py', slate]),
            ('board', [PY, 'nfl/tools/classic_owner_board.py', slate]),
            ('fc', [PY, 'nfl/tools/classic_fc_compare.py', slate]),
            ('props', [PY, 'nfl/tools/classic_prop_compare.py', slate]),
            ('audit', [PY, 'nfl/tools/classic_production_audit.py', slate]),
            ('prelock', pre),
            ('changes', [PY, 'nfl/tools/classic_change_log.py', slate]),
            ('finalize', [PY, 'nfl/tools/classic_finalize.py', slate]),
            ('page', [PY, 'nfl/tools/classic_owner_page.py', slate, '--out', page])]


def snapshot(slate):
    ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    d = OUT_DIR / 'runs' / slate / ts
    d.mkdir(parents=True, exist_ok=True)
    kept = []
    for n in SNAP:
        p = OUT_DIR / f'DK_{slate}_EARLY_{n}'
        if p.exists():
            shutil.copy2(p, d / p.name)
            kept.append(n)
    (OUT_DIR / 'runs' / slate / 'LATEST_SNAPSHOT').write_text(ts)
    return d, kept


def _verdict(out):
    lines = [ln for ln in (out or '').splitlines() if ln.strip()]
    verdicts = [ln for ln in lines if re.match(r'^(PASS|FAIL|BLOCKED)\[', ln)]
    return (verdicts[-1:] or lines[-1:] or [''])[0][:400]   # the tool's verdict line, not trailing JSON


def _exec(cmd):
    """One command, or a list of commands run in parallel (rc and verdict of each; the first leads)."""
    if isinstance(cmd[0], str):
        p = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True)
        return p.returncode, _verdict(p.stdout), (p.stderr or '')[-600:] if p.returncode else '', None
    ps = [subprocess.Popen(c, cwd=_REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for c in cmd]
    outs = [p.communicate() for p in ps]
    parts = [{'cmd': c, 'rc': p.returncode, 'result': _verdict(o)} for c, p, (o, _e) in zip(cmd, ps, outs)]
    # the stage stands or falls with the production build; a failed side build is recorded here and
    # refused downstream (the audit reads its reproducibility as NOT_RUN/STALE, and finalize needs PASS)
    rc = ps[0].returncode
    err = '\n'.join((e or '')[-300:] for p, (_o, e) in zip(ps, outs) if p.returncode)
    return rc, parts[0]['result'], err, parts


def lock_check(slate, now=None, estimate_min=None):
    """None when the run can finish before the slate's kickoff; otherwise the refusal, with both clocks named."""
    from zoneinfo import ZoneInfo
    from nfl.dfs.salaries import early_only as EO
    from nfl.tools.classic_research_book import kickoff_utc
    now = now or dt.datetime.now(dt.timezone.utc)
    est = RUNTIME_ESTIMATE_MIN if estimate_min is None else estimate_min
    try:
        ko = dt.datetime.fromisoformat(kickoff_utc(EO.slate_files(slate)['kickoff']))
    except Exception as e:  # noqa: BLE001
        return {'code': 'LOCK_UNKNOWN', 'why': f'no declared kickoff for {slate}: {type(e).__name__}: {e}'}
    rec = {'now_utc': now.isoformat(), 'now_et': now.astimezone(ZoneInfo('America/New_York')).isoformat(),
           'kickoff_utc': ko.isoformat(), 'runtime_estimate_min': est,
           'minutes_to_lock': round((ko - now).total_seconds() / 60, 1)}
    if now >= ko:
        return {'code': 'AFTER_LOCK', 'why': 'the slate has locked; a production rebuild is refused', **rec}
    if now + dt.timedelta(minutes=est) >= ko:
        return {'code': 'WOULD_NOT_FINISH_BEFORE_LOCK',
                'why': f'{rec["minutes_to_lock"]} min to lock against a {est} min runtime estimate', **rec}
    return None


def _pid_alive(pid) -> bool:
    import os
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def acquire_run_lock(slate, run_id):
    """(ok, detail). One Classic build per slate at a time; a lock left by a dead process is recovered, and the run it
    belonged to is marked CRASHED_OR_KILLED in its ledger rather than left reading RUNNING."""
    import os
    lp = OUT_DIR / f'DK_{slate}_EARLY_RUN.lock'
    if lp.exists():
        try:
            held = json.loads(lp.read_text())
        except (OSError, ValueError):
            held = {}
        if _pid_alive(held.get('pid')):
            return False, {'code': 'RUN_IN_PROGRESS', 'held_by': held}
        lg = OUT_DIR / f'DK_{slate}_EARLY_RUN_LEDGER.json'
        if lg.exists():
            try:
                old = json.loads(lg.read_text())
                if old.get('run_id') == held.get('run_id') and old.get('STATE') == 'RUNNING':
                    old['STATE'] = 'CRASHED_OR_KILLED'
                    old['recovered_by'] = run_id
                    lg.write_text(json.dumps(old, indent=1))
            except (OSError, ValueError):
                pass
        recovered = held
    else:
        recovered = None
    lp.write_text(json.dumps({'pid': os.getpid(), 'run_id': run_id,
                              'since_utc': dt.datetime.now(dt.timezone.utc).isoformat()}))
    return True, {'code': 'LOCK_ACQUIRED', 'recovered_stale_lock': recovered}


def release_run_lock(slate, run_id):
    lp = OUT_DIR / f'DK_{slate}_EARLY_RUN.lock'
    try:
        if json.loads(lp.read_text()).get('run_id') == run_id:
            lp.unlink()
    except (OSError, ValueError):
        pass


def run(slate, as_of, inactives, page, dry=False, packet=None, now=None):
    if dry:
        return _run(slate, as_of, inactives, page, dry=True, packet=packet, now=now)
    import uuid
    started = now or dt.datetime.now(dt.timezone.utc)
    run_id = f'{slate}-{started.strftime("%Y%m%dT%H%M%SZ")}-{uuid.uuid4().hex[:8]}'
    lk = lock_check(slate, now=now)
    if lk is not None:
        ledger = {'ARTIFACT': 'CLASSIC_PIPELINE_RUN', 'slate_id': slate, 'run_id': run_id, 'STATE': 'REFUSED_' + lk['code'],
                  'lock': lk, 'started_utc': started.isoformat(), 'stages': [], 'FINAL': 'NOT_REACHED'}
        (OUT_DIR / f'DK_{slate}_EARLY_RUN_LEDGER.json').write_text(json.dumps(ledger, indent=1))
        return ledger
    ok, det = acquire_run_lock(slate, run_id)
    if not ok:
        # another build of this slate is running: refuse, and do not touch its ledger
        return {'ARTIFACT': 'CLASSIC_PIPELINE_RUN', 'slate_id': slate, 'run_id': run_id, 'STATE': 'REFUSED_RUN_IN_PROGRESS',
                'run_lock': det, 'stages': [], 'FINAL': 'NOT_REACHED'}
    try:
        return _run(slate, as_of, inactives, page, dry=False, packet=packet, now=now, run_id=run_id, run_lock=det)
    finally:
        release_run_lock(slate, run_id)


def _run(slate, as_of, inactives, page, dry=False, packet=None, now=None, run_id=None, run_lock=None):
    import os
    lk = lock_check(slate, now=now)
    run_id = run_id or f'{slate}-DRY'
    os.environ['NFL_CLASSIC_RUN_ID'] = run_id
    snap, kept = (OUT_DIR / "runs" / slate / "DRY_RUN_NO_SNAPSHOT", []) if dry else snapshot(slate)
    ledger = {'ARTIFACT': 'CLASSIC_PIPELINE_RUN', 'slate_id': slate, 'run_id': run_id, 'lock': lk or 'BEFORE_LOCK',
              'run_lock': run_lock,
              'as_of': as_of, 'inactives_file': inactives,
              'evidence_packet': packet,
              'evidence_packet_sha256': (hashlib.sha256(pathlib.Path(packet).read_bytes()).hexdigest()
                                         if packet and pathlib.Path(packet).exists() else None),
              'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'snapshot': {'dir': str(snap.relative_to(_REPO)), 'files': kept}, 'stages': [], 'STATE': 'RUNNING'}
    for name, cmd in stages(slate, as_of, inactives, page, packet):
        if dry:
            ledger['stages'].append({'stage': name, 'cmd': cmd, 'rc': None, 'result': 'DRY_RUN'})
            continue
        t0 = dt.datetime.now(dt.timezone.utc)
        rc, result, err, parts = _exec(cmd)
        rec = {'stage': name, 'cmd': cmd, 'rc': rc, 'result': result,
               'seconds': round((dt.datetime.now(dt.timezone.utc) - t0).total_seconds(), 1), 'stderr_tail': err}
        if parts:
            rec['parallel'] = parts
        ledger['stages'].append(rec)
        (OUT_DIR / f'DK_{slate}_EARLY_RUN_LEDGER.json').write_text(json.dumps(ledger, indent=1))
        if rc != 0 and name not in NON_STOPPING:
            ledger['STATE'] = f'STOPPED_AT_{name.upper()}'
            break
    else:
        ledger['STATE'] = 'DRY_RUN' if dry else 'COMPLETE'
    ledger['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    fin = next((s for s in ledger['stages'] if s['stage'] == 'finalize'), None)
    ledger['FINAL'] = fin['result'] if fin and fin['rc'] is not None else 'NOT_REACHED'
    (OUT_DIR / f'DK_{slate}_EARLY_RUN_LEDGER.json').write_text(json.dumps(ledger, indent=1))
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--official-inactives', default=None)
    ap.add_argument('--evidence-packet', default=None, help='a Sunday evidence packet (sunday_evidence.py)')
    ap.add_argument('--page', required=True)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    led = run(a.slate_id, a.as_of, a.official_inactives, a.page, dry=a.dry_run, packet=a.evidence_packet)
    for s in led['stages']:
        print(f"{s['stage']:20} rc={s['rc']} {s['result']}")
    print(led['STATE'], '| FINAL:', led['FINAL'])
    return 0 if led['STATE'] in ('COMPLETE', 'DRY_RUN') else 1


if __name__ == '__main__':
    sys.exit(main())
