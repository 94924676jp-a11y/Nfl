#!/usr/bin/env python3.12
"""New evidence -> the full Classic rebuild, automatically, or an escalation that says why not.

    python3.12 nfl/tools/classic_evidence_watch.py 2026W5 [--packets-dir DIR] [--launch]

WHY (task #45, owner contract 2026-10-11 clause 9 and the standing rule of 16:40 UTC). Every material change -- a player
added to a confirmed lineup, ruled inactive, or being managed -- must trigger evidence -> football state -> projection ->
fresh worlds -> whole-portfolio re-optimisation -> verified release, never a selection-only patch. On 2026-10-11 every
rebuild was started by hand, and the McLaurin restriction produced a selection-only file.

WHAT IT DOES, ONCE PER INVOCATION (a scheduler or the T-90 workflow calls it; there is no daemon loop to die silently):
  1. The newest evidence packet in the slate's packet directory, by its declared received_at (then file name).
  2. The packet the current state consumed (state.official_inactives.packet_sha256).
  3. Equal -> NO_NEW_EVIDENCE. Different -> NEW_EVIDENCE, and:
       with --launch, the governed pipeline (classic_slate_pipeline.run) with that packet, which refuses on its own
       when the clock does not leave time to finish before lock or another build of the slate is running;
       without --launch, a dry decision only.
  4. Whatever happens, the current upload's release record is recomputed against the newest packet, so a build that
     could not be refreshed in time reads STALE_FORECAST instead of keeping a CURRENT label it no longer earns.
  5. An escalation record is written whenever new evidence did not produce a completed rebuild.

It never edits a lineup, never uploads, and never chooses between portfolios. Submission stays with the owner.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'classic-evidence-watch-1'


def packets_dir(slate_id: str) -> pathlib.Path:
    """The slate's declared packet directory: nfl/dfs/salaries/classic_early_<slate>/evidence_packets."""
    return _REPO / 'nfl/dfs/salaries' / f'classic_early_{slate_id}' / 'evidence_packets'


def newest_packet(d: pathlib.Path):
    """(path, doc) of the newest packet by declared received_at, then name; (None, None) when there is none."""
    best = None
    for p in sorted(pathlib.Path(d).glob('*.json')):
        try:
            doc = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or 'received_at' not in doc or 'packet_id' not in doc:
            continue
        key = (str(doc['received_at']), p.name)
        if best is None or key > best[0]:
            best = (key, p, doc)
    return (best[1], best[2]) if best else (None, None)


def decide(slate_id: str, *, out_dir=None, pk_dir=None) -> dict:
    from nfl.tools import classic_slate_pipeline as PL
    out_dir = pathlib.Path(out_dir or PL.OUT_DIR)
    st_p = out_dir / f'DK_{slate_id}_EARLY_STATE.json'
    p, doc = newest_packet(pk_dir or packets_dir(slate_id))
    rec = {'ARTIFACT': 'CLASSIC_EVIDENCE_WATCH', 'spec_version': SPEC_VERSION, 'slate_id': slate_id,
           'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    if p is None:
        rec.update(decision='NO_PACKET', why='no evidence packet with packet_id and received_at in the packet directory')
        return rec
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    consumed = (json.loads(st_p.read_text()).get('official_inactives') or {}) if st_p.exists() else {}
    rec['newest'] = {'path': str(p), 'packet_id': doc.get('packet_id'), 'received_at': doc.get('received_at'),
                     'sha256': sha}
    rec['consumed'] = {'packet_id': consumed.get('packet_id'), 'sha256': consumed.get('packet_sha256')}
    rec['decision'] = 'NO_NEW_EVIDENCE' if consumed.get('packet_sha256') == sha else 'NEW_EVIDENCE'
    return rec


def run(slate_id: str, *, launch: bool = False, out_dir=None, pk_dir=None, now=None, page=None) -> Outcome:
    from nfl.tools import classic_release as R
    from nfl.tools import classic_slate_pipeline as PL
    out_dir = pathlib.Path(out_dir or PL.OUT_DIR)
    rec = decide(slate_id, out_dir=out_dir, pk_dir=pk_dir)
    if rec['decision'] == 'NEW_EVIDENCE':
        lk = PL.lock_check(slate_id, now=now)
        rec['lock'] = lk or 'BEFORE_LOCK'
        if launch:
            stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
            led = PL.run(slate_id, stamp, None, page or str(out_dir / f'DK_{slate_id}_EARLY_WATCH_PAGE.html'),
                         packet=rec['newest']['path'], now=now)
            rec['launched'] = {'run_id': led.get('run_id'), 'STATE': led.get('STATE'), 'FINAL': led.get('FINAL')}
            if led.get('STATE') != 'COMPLETE':
                rec['escalation'] = {'code': 'NEW_EVIDENCE_NOT_REBUILT', 'pipeline_state': led.get('STATE'),
                                     'why': (led.get('lock') or {}).get('why') if isinstance(led.get('lock'), dict)
                                     else led.get('STATE')}
        else:
            rec['escalation'] = {'code': 'NEW_EVIDENCE_REBUILD_NOT_LAUNCHED',
                                 'why': 'run without --launch; the current upload no longer reflects the newest evidence'}
    # the current upload, judged against the newest packet, whatever happened above
    if rec.get('newest'):
        rel = R.evaluate(slate_id, latest_packet=rec['newest']['path'], out_dir=out_dir, now=now)
        rec['current_release'] = {'release_state': rel.get('release_state'), 'forecast_state': rel.get('forecast_state')}
        if (out_dir / f'DK_{slate_id}_EARLY_UPLOAD.csv').exists():
            (out_dir / f'DK_{slate_id}_EARLY_RELEASE.json').write_text(json.dumps(rel, indent=1, default=str) + '\n')
    (out_dir / f'DK_{slate_id}_EARLY_EVIDENCE_WATCH.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
    if rec.get('escalation'):
        return Outcome.blocked('EVIDENCE_WATCH_ESCALATION', f"{rec['escalation']['code']}: {rec['escalation']['why']}",
                               cause=Cause.DATA, record=rec)
    return Outcome.ok(f"EVIDENCE_WATCH_{rec['decision']}", rec, rec['decision'])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--packets-dir', default=None)
    ap.add_argument('--launch', action='store_true', help='start the governed rebuild when the evidence is new')
    a = ap.parse_args()
    o = run(a.slate_id, launch=a.launch, pk_dir=pathlib.Path(a.packets_dir) if a.packets_dir else None)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
