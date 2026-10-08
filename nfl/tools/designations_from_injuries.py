#!/usr/bin/env python3.12
"""Formal game designations for one slate, read from a captured nflverse injuries vintage. Fail-closed, no inference.

    python3.12 nfl/tools/designations_from_injuries.py --injuries nfl/vintage/injuries.<sha16>.csv.gz \
        --season 2026 --week 5 --teams TB,DAL --out DESIGNATIONS_X.json [--add "Name=OUT" ...] [--scenario-note "..."]

Only the FORMAL report_status column is a designation (Out / Doubtful / Questionable -> OUT / DOUBTFUL / QUESTIONABLE).
Practice participation (DNP / limited / full) is NOT a game designation and is never converted into one: a player who
did not practice on Wednesday and has no formal status yet is UNDESIGNATED, recorded in the provenance as
practice-only, not OUT. `--add` writes an explicit scenario hypothesis (e.g. a QB-out precompute) and is labelled
SCENARIO_HYPOTHESIS in the provenance, never as a captured designation. Writes <out> and <out>.PROVENANCE.json.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import sys

MAP = {'out': 'OUT', 'doubtful': 'DOUBTFUL', 'questionable': 'QUESTIONABLE'}


def build(injuries, season, week, teams, adds=(), note=None, counterfactual_remove=()):
    raw = pathlib.Path(injuries).read_bytes()
    text = gzip.decompress(raw).decode('utf-8') if str(injuries).endswith('.gz') else raw.decode('utf-8')
    rows = [r for r in csv.DictReader(io.StringIO(text))
            if r.get('season') == str(season) and r.get('week') == str(week) and r.get('team') in teams]
    if not rows:
        raise SystemExit(f'NO_INJURY_ROWS season {season} week {week} teams {sorted(teams)} (an empty report is not "nobody injured")')
    des, practice_only, unknown = {}, [], []
    for r in rows:
        st = (r.get('report_status') or '').strip().lower()
        if st in MAP:
            des[r['full_name']] = MAP[st]
        elif st:
            unknown.append({'player': r['full_name'], 'report_status': r['report_status']})
        else:
            practice_only.append({'player': r['full_name'], 'team': r['team'], 'practice_status': r.get('practice_status')})
    if unknown:
        raise SystemExit(f'UNRECOGNISED_REPORT_STATUS {unknown[:5]}')
    cf = {}
    for n in counterfactual_remove:
        if n not in des:
            raise SystemExit(f'COUNTERFACTUAL_TARGET_HAS_NO_FORMAL_STATUS {n}')
        cf[n] = des.pop(n)
    hyp = {}
    for a in adds:
        n, _, s = a.partition('=')
        if s not in ('OUT', 'DOUBTFUL', 'QUESTIONABLE', 'NO_OFFENSIVE_ROLE'):
            raise SystemExit(f'BAD_SCENARIO_STATUS {a}')
        des[n] = s
        hyp[n] = s
    prov = {'ARTIFACT': 'DESIGNATIONS_PROVENANCE', 'source': str(injuries), 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'season': season, 'week': week, 'teams': sorted(teams), 'n_report_rows': len(rows),
            'formal_designations': {k: v for k, v in des.items() if k not in hyp},
            'SCENARIO_HYPOTHESIS': hyp, 'scenario_note': note,
            'COUNTERFACTUAL_REMOVED_FORMAL_STATUS': cf,
            'practice_only_no_formal_status': practice_only,
            'RULE': 'formal report_status only; practice participation is never converted into a designation',
            'built_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    return des, prov


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--injuries', required=True)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--teams', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--add', action='append', default=[])
    ap.add_argument('--scenario-note')
    ap.add_argument('--counterfactual-remove', action='append', default=[],
                    help='drop a FORMAL status for a counterfactual scenario; recorded, never silent')
    a = ap.parse_args()
    des, prov = build(a.injuries, a.season, a.week, set(a.teams.split(',')), a.add, a.scenario_note, a.counterfactual_remove)
    out = pathlib.Path(a.out)
    out.write_text(json.dumps(des, indent=1, sort_keys=True) + '\n')
    prov['sha256'] = hashlib.sha256(out.read_bytes()).hexdigest()
    pathlib.Path(str(out) + '.PROVENANCE.json').write_text(json.dumps(prov, indent=1) + '\n')
    print(out, len(des), 'designations;', len(prov['practice_only_no_formal_status']), 'practice-only (not designated)')
    sys.exit(0)
