#!/usr/bin/env python3.12
"""Pre-lock staging: Sunday-input placeholders, Hard Rock slots, and the READY/BLOCKED table.

    python3.12 nfl/tools/classic_staging.py 2026W4

Owner directive 2026-10-04 (PRE-LOCK STAGING NOW, PLACEHOLDERS FOR SUNDAY NEWS). Writes

  DK_<slate>_EARLY_SUNDAY_INPUTS.json   every external input the post-news run consumes, each in a named
                                        AWAITING_* state until real evidence fills it. A placeholder is
                                        never evidence: projected starter, depth chart, absence from a list,
                                        FC status and sportsbook availability are never substitutes.
  DK_<slate>_EARLY_HARD_ROCK_SLOTS.json the sealed model numbers per player and market, each with
                                        hard_rock_line NOT_CAPTURED_YET. Built from the sealed worlds, so
                                        the model side exists BEFORE any price; a price is compared to it,
                                        never fed back into it.
  DK_<slate>_EARLY_STAGING_CHECK.json   the 20 staging checks and the owner's readiness table, each
                                        READY / READY_WITH_DECLARED_LIMITATION / BLOCKED / AWAITING, read
                                        from the artifacts on disk.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
READY, LIMITED, BLOCKED, AWAITING = 'READY', 'READY_WITH_DECLARED_LIMITATION', 'BLOCKED', 'AWAITING'
EVIDENCE_DIR = 'nfl/dfs/salaries/evidence'
NEVER_A_SUBSTITUTE = ['a projected starter', 'a depth-chart starter', 'absence from an inactive list',
                      'FantasyCruncher status', 'sportsbook availability']


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _j(p):
    return json.loads(p.read_text()) if p.exists() else None


def sunday_inputs(slate, A):
    st, aud = A['STATE'], A['AUDIT']
    nh = sorted((p['team'], p['name']) for p in st['players'].values()
                if (p.get('predicted_lineup_context') or {}).get('state') == 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT')
    q = sorted((p['team'], p['name'], p['current_availability']['designation']) for p in st['players'].values()
               if (p['current_availability'].get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL')
               and not p['current_availability'].get('resolution'))
    oi = (st.get('official_inactives') or {}).get('STATE')
    slots = {
        'OFFICIAL_INACTIVES': {'state': 'AWAITING_OFFICIAL_INACTIVES' if oi in (None, 'NOT_YET_PUBLISHED', 'AWAITING_OFFICIAL_INACTIVES') else oi,
                               'fills_from': f'{EVIDENCE_DIR}/<packet>.json (sunday_evidence.py); OFFICIAL_CAPTURED from the '
                                             'networked agent, or OWNER_RELAYED labelled as such',
                               'released': 'about 90 minutes before kickoff (~11:30 ET for the 13:00 ET games)',
                               'consumed_by': ['state', 'prelock', 'finalize']},
        'QUESTIONABLE_PLAYER_STATUS': {'state': 'UNRESOLVED_QUESTIONABLE' if q else 'NONE_OPEN',
                                       'players': [{'team': t, 'player': n, 'designation': d} for t, n, d in q],
                                       'fills_from': 'the same packet: ACTIVE or INACTIVE per player, with its citation'},
        'WEEK4_ROSTER_REFRESH': {'state': 'AWAITING_FRESH_CAPTURE',
                                 'why': f"{sum(1 for c in aud.get('contradictions', []) if c['kind'] == 'ROSTER_MOVE_SINCE_LAST_CAPTURE')} "
                                        'pool players carry a club the last roster capture does not',
                                 'fills_from': 'networked agent roster capture (docs/AGENT_OUTBOX.md)'},
        'HARD_ROCK_BOARD': {'state': 'AWAITING_POST_SEAL_CAPTURE',
                            'rule': 'captured AFTER the seal and compared downstream only; never fed back into a projection',
                            'slots': f'DK_{slate}_EARLY_HARD_ROCK_SLOTS.json'},
        'WEATHER': {'state': 'AWAITING_CURRENT_WEATHER', 'use': 'CONTEXT_ONLY (no weather term in the projection)',
                    'games': {g: {**v, 'weather': 'AWAITING_CURRENT_WEATHER'}
                              for g, v in ((aud.get('stadiums') or {}).get('games') or {}).items()}},
    }
    for club, name in nh:
        slots[f'{club}_STARTING_QB'] = {'state': 'ROLE_DEPENDENT_AWAITING_CONFIRMATION', 'chart_starter': name,
                                        'evidence_now': 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT (not a confirmation)',
                                        'fills_from': 'packet "starters": {"%s": "<name>"} from a club or league source' % club}
    return {'ARTIFACT': 'CLASSIC_SUNDAY_INPUTS', 'slate_id': slate,
            'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'NEVER_A_SUBSTITUTE_FOR_OFFICIAL_EVIDENCE': NEVER_A_SUBSTITUTE,
            'UNKNOWN_IS_NOT_ZERO': 'an AWAITING slot is not "no news" and not ACTIVE',
            'packet_template': {'packet_id': f'{slate}-owner-1030', 'source': 'OWNER_RELAYED',
                                'received_at': '<UTC>', 'source_detail': '<where the owner read it>',
                                'players': [{'name': '<DK name>', 'team': '<club>', 'status': 'ACTIVE|INACTIVE',
                                             'cited': 'OFFICIAL_RELEASE|AGGREGATOR|SECONDHAND', 'note': ''}],
                                'starters': {club: '<name>' for club, _ in nh}},
            'slots': slots}


def hard_rock_slots(slate, A):
    import numpy as np
    from nfl.tools import classic_slate_run as CR, classic_prop_compare as PC
    stats, _pts, meta = CR.load_worlds(OUT_DIR / f'DK_{slate}_EARLY_WORLDS.npz')
    idx = {k: i for i, k in enumerate(meta['keys'])}
    fi = {f: j for j, f in enumerate(meta['fields'])}
    _sg, tg = PC.team_gates(A['RESEARCH_BOOK'], A['PROJ'], A['STATE'])
    from nfl.tools import showdown_draws as SD
    in_lineup = {s['dk_id'] for c in A['PORTFOLIOS']['contests'] for lu in c['lineups'] for s in lu['slots']}
    rows = []
    for dk, r in sorted(A['PROJ']['rows'].items(), key=lambda kv: -(kv[1].get('dk_points') or 0)):
        if r.get('position') not in ('QB', 'RB', 'WR', 'TE'):
            continue
        if not (r.get('is_predicted_starter') or dk in in_lineup):
            continue
        k = SD.S.player_key(r['name'], r['team'])
        if k not in idx:
            continue
        for mk, parts in PC.MARKETS.items():
            if r['position'] != 'QB' and mk.startswith('player_pass') or (r['position'] == 'QB' and mk in (
                    'player_receptions', 'player_receiving_yards', 'player_rushing_+_receiving_yards')):
                continue
            if r['position'] in ('WR', 'TE') and mk in ('player_rushing_yards', 'player_rushing_attempts',
                                                        'player_rushing_+_receiving_yards', 'player_interceptions'):
                continue
            if r['position'] == 'RB' and mk == 'player_interceptions':
                continue
            v = sum(stats[idx[k], :, fi[p]].astype(float) / (meta['yard_scale'] if p in meta['yard_fields'] else 1)
                    for p in parts)
            rows.append({'player': r['name'], 'team': r['team'], 'position': r['position'], 'market': mk,
                         'model_mean': round(float(v.mean()), 2),
                         'model_p10_p50_p90': [round(float(x), 1) for x in np.percentile(v, (10, 50, 90))],
                         'hard_rock_line': 'NOT_CAPTURED_YET', 'hard_rock_price': 'NOT_CAPTURED_YET',
                         'yards_market_blocked': mk in PC.YARDS_MARKETS and not tg.get(r['team'], {}).get('yards_props_open', False),
                         'availability_current': False})
    return {'ARTIFACT': 'CLASSIC_HARD_ROCK_SLOTS', 'slate_id': slate,
            'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'worlds_sha256': _sha(OUT_DIR / f'DK_{slate}_EARLY_WORLDS.npz'),
            'seal_worlds_sha256': (A['SEAL'] or {}).get('worlds_sha256'),
            'RULE': 'model side written from the sealed worlds before any price exists; Hard Rock Bet only; '
                    'no parlays; no row is a bet (PROJECTION_SYSTEM_STATE NOT_VALIDATED)',
            'yards_blocked_clubs': sorted(c for c, t in tg.items() if not t['yards_props_open']),
            'n_rows': len(rows), 'rows': rows}


def checks(slate, A):
    f = lambda n: OUT_DIR / f'DK_{slate}_EARLY_{n}'  # noqa: E731
    st, pj, dr, bk, port, ver, aud, pre = (A[k] for k in ('STATE', 'PROJ', 'DRAWS', 'RESEARCH_BOOK', 'PORTFOLIOS',
                                                           'UPLOAD_VERIFY', 'AUDIT', 'PRELOCK'))
    fin, sc, led, rc = A['FINAL_MANIFEST'], A['SCENARIOS'], A['RUN_LEDGER'], A['RUN_CHANGES']
    up_rows = list(csv.reader(f('UPLOAD.csv').open()))[1:] if f('UPLOAD.csv').exists() else []
    proj_sha = _sha(f('PROJ.json'))
    c = []

    def add(n, item, status, evidence):
        c.append({'n': n, 'item': item, 'status': status, 'evidence': evidence})
    add(1, 'games', READY if len(st['games']) == 8 else BLOCKED, f"{len(st['games'])} games, kickoff {st['kickoff']}")
    add(2, 'pool and Entry IDs', READY if ver.get('entries_sha256') else BLOCKED,
        f"{st['identity']['n_pool']} pool rows ({len(st['players'])} in state); entries file sha {str(ver.get('entries_sha256'))[:12]}")
    add(3, '173 entries', READY if len(up_rows) == 173 else BLOCKED, f'{len(up_rows)} upload rows')
    add(4, 'salaries and IDs', READY if not ver.get('violations') else BLOCKED, f"{len(ver.get('violations') or [])} verifier violations")
    sane = (dr.get('football_sanity') or {}).get('state')
    add(5, 'projections', READY if pj.get('market_arm') == 'FOOTBALL_ONLY' and sane == 'PASS' else BLOCKED,
        f"{len(pj['rows'])} rows, market_arm {pj.get('market_arm')}, sanity {sane}")
    add(6, '2,000-world artifact', READY if dr.get('n_sims') == 2000 and dr.get('projection_sha256') == proj_sha
        and not dr.get('games_refused') and (A['SEAL'] or {}).get('worlds_sha256') == _sha(f('WORLDS.npz')) else BLOCKED,
        f"n_sims {dr.get('n_sims')}, worlds match projection and seal, {len(dr.get('games_refused') or {})} games refused")
    add(7, 'research book', READY if (bk.get('inputs_sha256') or {}).get('PROJ.json') == proj_sha and len(bk.get('games', {})) == 8 else BLOCKED,
        f"{len(bk.get('games', {}))} games; seal written {(A['SEAL'] or {}).get('written_at')}")
    acc = aud.get('accounting') or {}
    add(8, '16-team accounting', READY if acc.get('state') == 'PASS' and len(acc.get('per_team') or {}) == 16 else BLOCKED,
        f"{acc.get('state')}, {len(acc.get('per_team') or {})} teams, {len(acc.get('failures') or [])} failures")
    rcs = aud.get('role_cards') or {}
    add(9, 'role cards', READY if all(x.get('usage_matches') for x in rcs.get('sampled', [])) else BLOCKED,
        f"{len(rcs.get('sampled', []))} cards independently recounted")
    pc = ver.get('per_contest') or {}
    add(10, '150 / 20 / 3 legality', READY if [pc.get(k, {}).get('n') for k in ('196208416', '196208417', '196208418')] == [150, 20, 3]
        and not ver.get('violations') else BLOCKED, json.dumps({k: v.get('n') for k, v in pc.items()}))
    add(11, 'upload checker', READY if ver.get('state') == 'PASS' and ver.get('upload_sha256') == _sha(f('UPLOAD.csv')) else BLOCKED,
        f"{ver.get('state')}[{ver.get('code')}] {ver.get('detail')}")
    rep = (aud.get('reproducibility') or {}).get('state')
    add(12, 'reproducibility', READY if rep == 'PASS' else BLOCKED, f'{rep} (two separate processes, byte-identical upload)')
    fcb = (A['OWNER_BOARD'] or {}).get('fc') or {}
    add(13, 'FC external-only', READY if pj.get('market_arm') == 'FOOTBALL_ONLY' and fcb.get('NOT_A_MODEL_INPUT') else BLOCKED,
        f"FC {fcb.get('state')}, labelled NOT_A_MODEL_INPUT; projection market_arm {pj.get('market_arm')}")
    pd = A['PROP_DIAGNOSTIC'] or {}
    add(14, 'Hard Rock downstream-only', READY if pd.get('seal') and pj.get('market_arm') == 'FOOTBALL_ONLY' else BLOCKED,
        'prop comparison reads the seal; no board held yet (AWAITING_POST_SEAL_CAPTURE)')
    stg = [s['stage'] for s in (led or {}).get('stages', [])]
    add(15, 'one-command pipeline', LIMITED if led and led.get('STATE') == 'COMPLETE' else BLOCKED,
        f"last run {(led or {}).get('STATE')} with stages {stg}; the prelock/finalize stages and the parallel "
        'reproducibility builds are new since that run and are exercised by the rehearsal')
    add(16, 'prelock logic', READY if pre.get('code') == 'AWAITING_OFFICIAL_INACTIVES' else LIMITED,
        f"{pre.get('state')}[{pre.get('code')}]: correct before any Sunday evidence")
    add(17, 'change log', READY if rc else BLOCKED, f"against {(rc or {}).get('against')}; baseline_2026W4_pre_inactives/ preserved")
    add(18, 'page regeneration', READY if any(s['stage'] == 'page' and s['rc'] == 0 for s in (led or {}).get('stages', [])) else BLOCKED,
        'page stage rc 0 in the last run')
    add(19, 'finalize gate', READY if (fin or {}).get('STATE') == 'NOT_POPULATED' and set((fin or {}).get('failed_gates') or []) <= {'EVIDENCE', 'PRELOCK'} else BLOCKED,
        f"FINAL {(fin or {}).get('STATE')}; failing only on {(fin or {}).get('failed_gates')}")
    add(20, 'scenario cascades', READY if sc and sc['base']['projection_sha256'] == proj_sha else BLOCKED,
        f"{len((sc or {}).get('scenarios', []))} open questions, {sum(1 for s in (sc or {}).get('scenarios', []) if s.get('material'))} material")
    by = {x['n']: x for x in c}
    worst = lambda *ns: next((s for s in (BLOCKED, LIMITED) if any(by[n]['status'] == s for n in ns)), READY)  # noqa: E731
    table = {
        'DK POOL': worst(1, 2, 4), 'ENTRY MAPPING': worst(2, 3, 10), 'RESEARCH BOOK': worst(7),
        'ROLE CARDS': worst(9), 'ACCOUNTING': worst(8), 'BASE PROJECTIONS': LIMITED if worst(5) == READY else worst(5),
        'SIMULATOR': LIMITED if worst(6) == READY else worst(6),
        '150-MAX ENGINE': worst(10, 12), '20-MAX ENGINE': worst(10, 12), '3-ENTRY ENGINE': worst(10, 12),
        'UPLOAD VERIFIER': worst(11), 'CHANGE LOG': worst(17),
        'HARD ROCK COMPARISON ENGINE': LIMITED if worst(14) == READY else worst(14),
        'WEATHER SLOT': READY, 'INACTIVES SLOT': AWAITING, 'STARTER CONFIRMATIONS': AWAITING,
    }
    limits = {'BASE PROJECTIONS': 'PROJECTION_SYSTEM_STATE NOT_VALIDATED; touchdown counts not reconciled; yards non-closure blocks yards props for '
                                  + ', '.join((A.get('_yards_blocked') or [])),
              'SIMULATOR': 'games simulated independently (no cross-game dependence); TD and bonus thresholds as simulated',
              'HARD ROCK COMPARISON ENGINE': 'no board captured; every row will be NOT_A_BET; yards markets blocked for the clubs above',
              'WEATHER SLOT': 'slot ready; weather is CONTEXT_ONLY and does not enter the projection'}
    return c, table, limits


def build(slate):
    f = lambda n: OUT_DIR / f'DK_{slate}_EARLY_{n}'  # noqa: E731
    A = {n: _j(f(f'{n}.json')) for n in ('STATE', 'PROJ', 'DRAWS', 'RESEARCH_BOOK', 'PORTFOLIOS', 'UPLOAD_VERIFY', 'AUDIT',
                                         'PRELOCK', 'SEAL', 'FINAL_MANIFEST', 'SCENARIOS', 'RUN_LEDGER', 'RUN_CHANGES',
                                         'OWNER_BOARD', 'PROP_DIAGNOSTIC')}
    missing = [n for n in ('STATE', 'PROJ', 'DRAWS', 'RESEARCH_BOOK', 'PORTFOLIOS', 'UPLOAD_VERIFY', 'AUDIT', 'PRELOCK') if A[n] is None]
    if missing:
        return Outcome.fail('STAGING_ARTIFACT_MISSING', f'missing {missing}')
    si = sunday_inputs(slate, A)
    f('SUNDAY_INPUTS.json').write_text(json.dumps(si, indent=1, default=str))
    hr = hard_rock_slots(slate, A)
    f('HARD_ROCK_SLOTS.json').write_text(json.dumps(hr, indent=1, default=str))
    A['_yards_blocked'] = hr['yards_blocked_clubs']
    c, table, limits = checks(slate, A)
    external = [{'input': k, 'state': v['state']} for k, v in si['slots'].items() if v['state'] not in ('NONE_OPEN',)]
    doc = {'ARTIFACT': 'CLASSIC_STAGING_CHECK', 'slate_id': slate, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'SLATE_READY': False, 'WHY_NOT_READY': 'Sunday evidence is outstanding; FINAL files are not populated',
           'checks': c, 'readiness_table': table, 'declared_limitations': limits, 'remaining_external_inputs': external}
    f('STAGING_CHECK.json').write_text(json.dumps(doc, indent=1, default=str))
    bad = [x for x in c if x['status'] == BLOCKED]
    if bad:
        return Outcome.fail('STAGING_BLOCKED', f"{len(bad)} check(s) BLOCKED: {', '.join(x['item'] for x in bad)}", blocked=bad)
    return Outcome.ok('STAGING_COMPLETE', table, f"{len(c)} checks, 0 blocked; {len(external)} external inputs awaiting; "
                                                 f"{hr['n_rows']} Hard Rock slots")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    o = build(ap.parse_args().slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
