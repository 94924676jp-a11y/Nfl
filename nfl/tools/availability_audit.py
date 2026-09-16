"""Every opportunity-pool player's availability evidence, channel by channel.

WHY A SEPARATE TOOL AND NOT A LINE IN A TEST. "P(appear) looks low" is not a
finding; "this player has N injury rows, M of them matched, the latest lawful
one is dated X, and here is the resulting probability and the fallback that
produced it" is. The columns exist so that a number nobody can explain cannot
survive being looked at.

THE THREE ABSENCE STATES ARE NEVER COLLAPSED, because they demand different
responses and this project has already been burned by merging them:

    NO_EVIDENCE_EXISTS      nothing anywhere carries this week for him.
                            Nothing to fix; the world has not spoken yet.
    EXISTS_BUT_DID_NOT_JOIN a capture holds it and the mechanism never saw
                            it. A defect in us, and the expensive one.
    EXISTS_BUT_AFTER_CLOCK  it is real and it is later than the forecast
                            cutoff. Using it would be leakage.

`fallback_used` names what the mechanism fell back ON, not merely that it
did. "No injury row, so the two prediction-time feature groups are absent and
the probability rests on appearance history alone" is a different situation
from "no history either, so this is the cold-start prior".
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'availability-audit-1'

#: The official report the appearance mechanism consumes today.
OFFICIAL = 'nflverse_injuries_csv'
#: The feed it does NOT consume. Named so its absence is a measurement.
SECONDARY = 'espn_injuries_json'


def _parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return None


def official_rows(season, cut):
    """Every 2026 row in every injuries capture, with its week, ignoring the
    per-team vintage composition -- the question here is what EXISTS."""
    out = []
    for f in sorted(_REPO.glob('nfl/vintage/injuries.*.csv*')):
        op = gzip.open if f.name.endswith('.gz') else open
        try:
            rows = list(csv.DictReader(op(f, 'rt', errors='ignore')))
        except OSError:
            continue
        for r in rows:
            if str(r.get('season')) != str(season):
                continue
            out.append({'blob': f.name, 'week': r.get('week'),
                        'gsis_id': (r.get('gsis_id') or '').strip(),
                        'team': r.get('team'),
                        'report_status': r.get('report_status'),
                        'practice_status': r.get('practice_status'),
                        'date_modified': r.get('date_modified')})
    return out


def secondary_items(cut):
    """The ESPN feed's newest capture lawful at `cut`, flattened per athlete.

    Selected by the capture's OWN `timestamp`, never by file mtime: every
    blob in this checkout shares a mtime from the clone, so sorting on it
    picks an arbitrary capture. That mistake chose a 2026-09-11 file over the
    2026-09-15 one and nearly produced the conclusion that no post-week-1
    evidence existed.
    """
    best = None
    n_caps = 0
    for f in _REPO.glob('nfl/vintage/espn_injuries_json.*.json*'):
        try:
            d = json.loads(gzip.open(f, 'rt', errors='ignore').read()
                           if f.name.endswith('.gz') else f.read_text())
        except (OSError, ValueError):
            continue
        n_caps += 1
        t = _parse_ts(d.get('timestamp'))
        if t is None or t > cut:
            continue
        if best is None or t > best[0]:
            best = (t, f, d)
    if best is None:
        return None, [], n_caps
    t, f, d = best
    items = []
    for club in d.get('injuries') or []:
        for it in club.get('injuries') or []:
            a = it.get('athlete') or {}
            items.append({
                'club': club.get('displayName'),
                'name': a.get('displayName'),
                'position': (a.get('position') or {}).get('abbreviation'),
                'status': it.get('status'),
                'date': it.get('date'),
                'detail': (it.get('shortComment') or '')[:200]})
    return {'timestamp': t.isoformat(), 'blob': f.name}, items, n_caps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    cut = _parse_ts(a.as_of)

    from nfl.production.nonqb import appearance_model as AM
    from nfl.production.nonqb import readiness as RD

    man = json.load(open(pathlib.Path(a.run_dir) / 'player_draws_manifest.json'))
    art = json.load(open(pathlib.Path(a.run_dir) / 'forecast_artifact.json'))
    board = json.load(open(pathlib.Path(a.run_dir) / 'board.json'))
    meta = {p['gsis_id']: p for p in board.get('players') or []}
    for g, v in ((art.get('kicking') or {}).get('resolved') or {}).items():
        meta.setdefault(g, {'gsis_id': g, 'name': v.get('name'),
                            'team': v.get('team'), 'position': 'K'})
    for g, v in ((art.get('gadget_rush') or {}).get('rows') or {}).items():
        meta.setdefault(g, {'gsis_id': g, 'name': v.get('name'),
                            'team': v.get('team'),
                            'position': v.get('position')})
    pool = sorted({g for lay, spec in (man.get('layers') or {}).items()
                   if spec.get('row_axis') == 'gsis_id'
                   for g in spec['row_ids']})

    AM.stage_inputs()
    feed = RD.latest_injuries_rows(a.season, as_of=a.as_of)
    joined = AM.parse_injuries_rows(feed, a.season)
    off = official_rows(a.season, cut)
    sec_meta, sec_items, n_sec_caps = secondary_items(cut)
    sec_by_name = {}
    for it in sec_items:
        if it['name']:
            sec_by_name.setdefault(it['name'], []).append(it)

    players = [{'gsis_id': g, 'team': meta.get(g, {}).get('team'),
                'position': meta.get(g, {}).get('position')}
               for g in pool if meta.get(g, {}).get('team')]
    pred = AM.predict(a.season, a.week, players, feed)
    pev = pred.as_dict()['evidence'] if pred.ok else {}
    pmap = {g: float(np.mean(v)) for g, v in (pred.value or {}).items()} \
        if pred.ok else {}
    pros = AM._prospective(a.season, a.week, players, feed)
    frow = {r['gsis_id']: r for r in pros.value['target']} if pros.ok else {}

    rows = []
    for g in pool:
        m = meta.get(g, {})
        nm = m.get('name') or g
        mine_off = [r for r in off if r['gsis_id'] == g]
        weeks = sorted({r['week'] for r in mine_off})
        matched = [k for k in joined
                   if k[3] == g and k[1] == a.week]
        sec = sec_by_name.get(nm) or []
        sec_dates = sorted([s['date'] for s in sec if s['date']])
        after = [s for s in sec
                 if _parse_ts(s['date']) and _parse_ts(s['date']) > cut]
        fr = frow.get(g) or {}
        if matched:
            state = 'JOINED'
        elif sec:
            state = 'EXISTS_BUT_DID_NOT_JOIN'
        elif after:
            state = 'EXISTS_BUT_AFTER_CLOCK'
        elif mine_off:
            state = 'EXISTS_FOR_ANOTHER_WEEK_ONLY'
        else:
            state = 'NO_EVIDENCE_EXISTS'
        rows.append({
            'player': nm, 'gsis_id': g, 'team': m.get('team'),
            'position': m.get('position'),
            'official_rows_any_week': len(mine_off),
            'official_weeks_present': weeks,
            'official_rows_this_week': len(
                [r for r in mine_off if str(r['week']) == str(a.week)]),
            'matched_rows': len(matched),
            'secondary_items': len(sec),
            'secondary_latest_lawful': sec_dates[-1] if sec_dates else None,
            'secondary_status': sec[0]['status'] if sec else None,
            'secondary_detail': sec[0]['detail'] if sec else None,
            'secondary_items_after_clock': len(after),
            'evidence_state': state,
            'f_inj_available': fr.get('f_inj_available'),
            'f_prev_snap': fr.get('f_prev_snap'),
            'f_snap_ewma': fr.get('f_snap_ewma'),
            'f_rate_ewma': fr.get('f_rate_ewma'),
            'f_weeks_since_appear': fr.get('f_weeks_since_appear'),
            'p_appear': round(pmap[g], 4) if g in pmap else None,
            'fallback_used': (
                'NONE -- an injury row joined' if matched else
                'APPEARANCE_HISTORY_ONLY -- no injury row joined, so the '
                'practice_progression and teammate_availability feature '
                'groups are absent and the probability rests on absence '
                'history and snap share alone'),
        })
    rows.sort(key=lambda r: (r['team'] or '', r['p_appear'] or 0))

    doc = {
        'spec_version': SPEC_VERSION, 'run_dir': a.run_dir,
        'run_id': man.get('run_id'), 'season': a.season, 'week': a.week,
        'as_of': a.as_of,
        'official_source': OFFICIAL, 'secondary_source': SECONDARY,
        'official_feed_rows_reaching_the_model': len(feed),
        'official_feed_weeks': sorted(
            {r.get('week') for r in feed}),
        'official_2026_rows_in_all_captures': len(off),
        'official_2026_weeks_in_all_captures': sorted(
            {r['week'] for r in off}),
        'secondary_captures_scanned': n_sec_caps,
        'secondary_newest_lawful': sec_meta,
        'secondary_items_in_that_capture': len(sec_items),
        'secondary_is_consumed_by_the_model': False,
        'n_pool_players': len(rows),
        'evidence_state_counts': dict(collections.Counter(
            r['evidence_state'] for r in rows)),
        'rows': rows,
    }
    out = json.dumps(doc, indent=1)
    if a.out:
        pathlib.Path(a.out).write_text(out)
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
