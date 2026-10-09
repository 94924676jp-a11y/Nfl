#!/usr/bin/env python3.12
"""Connection status, freshness, missing information, QB changes and the owner's queue, as one JSON.

    python3.12 nfl/integrations/monitor.py 2026W5 --raw-dir RAW --reference-state STATE.json \
        --out nfl/integrations/status/

Read-only. It fetches nothing: it reads the vintage manifest (what the scheduled capture brought in), the
inbox ledger (what the owner dropped), the slate's raw files and the reference build, and writes
INTEGRATION_STATUS_<slate>.json plus a self-contained HTML page rendered from that JSON.

The rules it applies are the project's: UNKNOWN is not ZERO, a missing DK file makes missing-player
counts UNKNOWN rather than empty, a deferred source is not a failed one, and a QB change is reported
against the chart the reference build used, with the injury report beside it, never inferred.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import html
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.integrations import inbox as IB, matrix as MX, rebuild as RB  # noqa: E402

SPEC_VERSION = 'integration-status-1'

#: Hours after which a source's newest PASS is STALE. Each is the publisher's refresh interval plus our
#: observed capture interval (about 7 h) with slack; a source with no in-season refresh has None.
STALE_AFTER_H = {'schedules': 12, 'weekly_rosters': 32, 'depth_charts': 32, 'injuries': 32,
                 'official_injury_report': 12, 'espn_injuries_json': 12, 'pbp': 7 * 24, 'snap_counts': None,
                 'official_inactives': None, 'official_transactions': None, 'pbp_participation': None}


LOCAL_NO_EGRESS = ('NO_EGRESS', 'LOCAL_EXECUTOR_NO_EGRESS')


def _ts(r):
    """The retrieval instant of a manifest row: value.retrieved_at, else the capture id."""
    v = (r.get('value') or {}).get('retrieved_at') or (r.get('evidence') or {}).get('retrieved_at')
    if v:
        try:
            return dt.datetime.fromisoformat(str(v).replace('Z', '+00:00')), 'retrieved_at'
        except ValueError:
            pass
    cid = str(r.get('capture_id') or '')[:15] + 'Z'
    try:
        return dt.datetime.strptime(cid, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc), 'capture_id'
    except ValueError:
        return None, 'none'


def _iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ') if t else None


def connections(rows, now, inbox_rows, slate_id):
    by = collections.defaultdict(list)
    for r in rows:
        by[r.get('source')].append(r)
    out = []
    for m in MX.MATRIX:
        src = m.get('manifest_source')
        if src:
            rs = sorted(by.get(src, []), key=lambda r: str(r.get('capture_id')))
            # An attempt from an executor with no egress says nothing about the source; the scheduled capture's
            # newest attempt does. Both are shown.
            meaningful = [r for r in rs if r.get('code') not in LOCAL_NO_EGRESS]
            local = [r for r in rs if r.get('code') in LOCAL_NO_EGRESS]
            last = meaningful[-1] if meaningful else (rs[-1] if rs else None)
            passes = [r for r in rs if r.get('state') == 'PASS']
            lp = passes[-1] if passes else None
            changed = [r for r in passes if (r.get('value') or {}).get('content_unchanged') is not True]
            t_pass, basis = _ts(lp) if lp else (None, 'none')
            t_chg = _ts(changed[-1])[0] if changed else None
            age = round((now - t_pass).total_seconds() / 3600, 1) if t_pass else None
            lim = STALE_AFTER_H.get(src)
            # A local executor's NO_EGRESS attempt does not disconnect a source the scheduled capture reaches:
            # the status is read from the newest SUCCESS first, and the newest attempt is shown beside it.
            fresh = lp is not None and age is not None and (lim is None or age <= lim)
            if last is None:
                status = 'NEVER_CAPTURED'
            elif last.get('state') == 'NOT_APPLICABLE':
                status = 'WATCH_ONLY'
            elif last.get('state') == 'DEFERRED':
                status = 'DEFERRED_NOT_PUBLISHED'
            elif last.get('state') == 'BLOCKED' and last.get('code') not in LOCAL_NO_EGRESS:
                status = 'BLOCKED'
            elif fresh:
                status = 'CONNECTED'
            elif lp is not None and age is None:
                status = 'UNRESOLVED_NO_CLOCK'
            elif lp is not None:
                status = 'STALE'
            else:
                status = 'BLOCKED'
            out.append({'id': m['id'], 'capability': m['capability'], 'provider': m['provider'],
                        'access': m['access'], 'status': status,
                        'last_attempt': last.get('capture_id') if last else None,
                        'last_attempt_code': f"{last.get('state')}[{last.get('code')}]" if last else None,
                        'last_local_no_egress_attempt': local[-1].get('capture_id') if local else None,
                        'last_success_utc': _iso(t_pass), 'last_success_basis': basis,
                        'last_content_change_utc': _iso(t_chg), 'age_hours': age, 'stale_after_hours': lim,
                        'owner_decision': m['owner_decision']})
        elif m.get('inbox_kind'):
            ks = [r for r in inbox_rows if r.get('kind') == m['inbox_kind'] and r.get('state') == 'PASS']
            lr = max(ks, key=lambda r: r['ingested_at']) if ks else None
            status = 'MANUAL_FILE_PRESENT' if lr else 'AWAITING_OWNER_EXPORT'
            if m['inbox_kind'] == 'DK_SALARIES':
                status = 'MANUAL_FILE_PRESENT' if RB.dk_pool_for_slate(slate_id, inbox_rows) else (
                    'AWAITING_OWNER_EXPORT' if not lr else 'PRESENT_BUT_NOT_THIS_SLATE')
            out.append({'id': m['id'], 'capability': m['capability'], 'provider': m['provider'],
                        'access': m['access'], 'status': status,
                        'last_success_utc': lr['ingested_at'] if lr else None,
                        'last_success_basis': 'ingested_at' if lr else 'none',
                        'last_file': lr['original_name'] if lr else None, 'owner_decision': m['owner_decision']})
    return out


def slate_clubs(state):
    return sorted({c for g in (state.get('games') or {}).values() for c in (g['away'], g['home'])})


def _depth_qb1(blob, clubs):
    rows = list(csv.DictReader(gzip.open(_REPO / blob, 'rt')))
    out = {}
    for c in clubs:
        q = [x for x in rows if x['team'] == c and x.get('pos_abb') == 'QB']
        if not q:
            continue
        last = max(x['dt'] for x in q)
        top = sorted((x for x in q if x['dt'] == last), key=lambda x: int(x['pos_rank']))
        out[c] = {'qb1': top[0]['gsis_id'], 'qb2': top[1]['gsis_id'] if len(top) > 1 else None, 'dt': last}
    return out


def _names(raw_dir, state):
    n = {}
    for p in (state.get('players') or {}).values():
        if p.get('gsis_id'):
            n[p['gsis_id']] = p.get('name')
    if raw_dir:
        for f in pathlib.Path(raw_dir).glob('NFLVERSE_ROSTER_WEEKLY_2026.*.csv.gz'):
            for r in csv.DictReader(gzip.open(f, 'rt')):
                n.setdefault(r.get('gsis_id'), r.get('full_name'))
    return n


def qb_watch(rows, state, now, raw_dir):
    """Per club: the reference build's QB1, the newest captured chart's QB1, and the QB injury lines."""
    clubs = slate_clubs(state)
    names = _names(raw_dir, state)
    cut = now.strftime('%Y%m%dT%H%M%SZ')
    dc = RB._pass(rows, 'depth_charts', cut)
    ref_qb = {}
    for k, p in (state.get('players') or {}).items():
        if p.get('position') == 'QB' and p.get('depth_rank') == 1:
            ref_qb[p['team']] = p.get('gsis_id')
    latest = _depth_qb1(dc[-1][2], clubs) if dc else {}
    used = {v.get('capture_id') for v in ((state.get('depth') or {}).get('qb_chart') or {}).values()}
    ref_blob = next((b for cid, _, b in dc if cid in used), None)
    ref_chart = _depth_qb1(ref_blob, clubs) if ref_blob else {}
    inj = {}
    for cid, sha, b in reversed(RB._pass(rows, 'injuries', cut)):
        seen_clubs = set(inj)
        for r in csv.DictReader(gzip.open(_REPO / b, 'rt')):
            if (r.get('week') == str(state.get('week')) and r.get('team') in clubs and r.get('position') == 'QB'
                    and r['team'] not in seen_clubs):
                inj.setdefault(r['team'], []).append({'name': r.get('full_name'), 'gsis_id': r.get('gsis_id'),
                                                      'report_status': r.get('report_status') or None,
                                                      'practice_status': r.get('practice_status') or None,
                                                      'capture_id': cid})
        if len(inj) == len(clubs):
            break
    out = []
    for c in clubs:
        L, R = latest.get(c), ref_chart.get(c)
        flags = []
        if L and R and L['qb1'] != R['qb1']:
            flags.append('CHART_QB1_CHANGED_SINCE_REFERENCE')
        if L and ref_qb.get(c) and L['qb1'] != ref_qb[c]:
            flags.append('PROJECTED_QB1_DIFFERS_FROM_NEWEST_CHART')
        if any((x['report_status'] or '') in ('Out', 'Doubtful', 'Questionable') for x in inj.get(c, [])):
            flags.append('QB_GAME_DESIGNATION_FILED')
        if any('Did Not' in (x['practice_status'] or '') for x in inj.get(c, [])):
            flags.append('QB_MISSED_PRACTICE')
        if not L:
            flags.append('NO_CAPTURED_CHART')
        out.append({'club': c, 'projected_qb1': names.get(ref_qb.get(c), ref_qb.get(c)),
                    'reference_chart_qb1': names.get((R or {}).get('qb1'), (R or {}).get('qb1')),
                    'newest_chart_qb1': names.get((L or {}).get('qb1'), (L or {}).get('qb1')),
                    'newest_chart_qb2': names.get((L or {}).get('qb2'), (L or {}).get('qb2')),
                    'newest_chart_dt': (L or {}).get('dt'), 'injury_lines': inj.get(c, []), 'flags': flags})
    return out


def missing_players(slate_id, raw_dir, inbox_rows):
    pool = RB.dk_pool_for_slate(slate_id, inbox_rows)
    if not pool:
        return {'status': 'UNKNOWN_NO_DK_SALARIES',
                'detail': 'No DK salary export for this slate has been dropped. Missing-player counts are UNKNOWN, '
                          'not zero. Projections run on the research universe meanwhile.'}
    from nfl.dfs.salaries import early_only as EO
    from nfl.tools import research_universe as RU
    from nfl.tools.sim_query import norm_name
    p = EO.pool(blob=_REPO / pool['blob'], sha_declared=pool['sha256'])
    u = RU.build(slate_id, raw_dir)
    if p.state.value != 'PASS' or u.state.value != 'PASS':
        return {'status': 'UNRESOLVED', 'detail': f'pool {p.code}, universe {u.code}'}
    uk = {(norm_name(r['dk_name']), r['team']) for r in u.value if r['dk_pos'] != 'DST'}
    dk = [r for r in p.value if r['dk_pos'] != 'DST']
    not_in_universe = [{'name': r['dk_name'], 'team': r['team'], 'pos': r['dk_pos'], 'salary': r['salary']}
                       for r in dk if (norm_name(r['dk_name']), r['team']) not in uk]
    dkk = {(norm_name(r['dk_name']), r['team']) for r in dk}
    not_in_dk = sorted(f'{n} ({t})' for n, t in uk - dkk)
    return {'status': 'COMPARED', 'dk_file': pool['original_name'], 'n_dk_players': len(dk),
            'n_universe_players': len(uk), 'dk_players_not_on_active_roster': not_in_universe,
            'n_active_roster_players_not_in_dk_pool': len(not_in_dk),
            'active_roster_players_not_in_dk_pool_sample': not_in_dk[:25],
            'match_rule': 'case/punctuation-normalised name plus club; nothing fuzzier'}


def designations_filed(rows, state, now):
    """Per club: injury-report rows for the week and how many carry a game designation (report_status)."""
    clubs = slate_clubs(state)
    cut = now.strftime('%Y%m%dT%H%M%SZ')
    out = {}
    for cid, sha, b in reversed(RB._pass(rows, 'injuries', cut)):
        rs = [r for r in csv.DictReader(gzip.open(_REPO / b, 'rt'))
              if r.get('week') == str(state.get('week')) and r.get('team') in clubs]
        for c in clubs:
            if c in out:
                continue
            cr = [r for r in rs if r['team'] == c]
            if cr:
                out[c] = {'rows': len(cr), 'with_game_designation': sum(1 for r in cr if (r.get('report_status')
                                                                                          or '').strip()),
                          'capture_id': cid}
        if len(out) == len(clubs):
            break
    for c in clubs:
        out.setdefault(c, {'rows': 0, 'with_game_designation': None, 'capture_id': None})
    return out


def build_status(slate_id, *, raw_dir, reference_state, now=None, rows=None, inbox_rows=None, drop=None):
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    rows = rows if rows is not None else RB.manifest_rows()
    inbox_rows = inbox_rows if inbox_rows is not None else IB.ledger_rows()
    state = json.loads(pathlib.Path(reference_state).read_text())
    conns = connections(rows, now, inbox_rows, slate_id)
    qbs = qb_watch(rows, state, now, raw_dir)
    des = designations_filed(rows, state, now)
    mp = missing_players(slate_id, raw_dir, inbox_rows)
    pl = RB.plan(slate_id, as_of=_iso(now), raw_dir=raw_dir, reference_state=reference_state, rows=rows,
                 inbox_rows=inbox_rows)
    drop = pathlib.Path(drop or IB.DROP)
    ingested = {r['sha256'] for r in inbox_rows}
    import hashlib
    waiting = [p.name for p in sorted(drop.glob('*')) if p.is_file() and p.name not in ('README.md',)
               and not p.name.startswith('.') and hashlib.sha256(p.read_bytes()).hexdigest() not in ingested]
    missing = []
    for c in conns:
        if c['status'] in ('STALE', 'BLOCKED', 'AWAITING_OWNER_EXPORT', 'PRESENT_BUT_NOT_THIS_SLATE',
                           'NEVER_CAPTURED', 'UNRESOLVED_NO_CLOCK'):
            missing.append({'what': c['capability'], 'status': c['status'], 'id': c['id']})
        elif c['status'] == 'DEFERRED_NOT_PUBLISHED':
            missing.append({'what': c['capability'], 'status': c['status'], 'id': c['id'],
                            'note': 'expected: published about 90 minutes before kickoff'})
    nodes = [c for c, d in des.items() if not d['with_game_designation']]
    if nodes:
        missing.append({'what': 'Game designations (Friday report) in the captured injury file',
                        'status': 'NOT_YET_IN_CAPTURE', 'clubs': nodes,
                        'note': 'nflverse refreshes injuries daily at 07:00 UTC; Friday designations arrive '
                                'Saturday at the earliest.'})
    if waiting:
        missing.append({'what': 'Files in the drop folder not yet ingested', 'status': 'WAITING', 'files': waiting})
    approvals = [dict(d, kind='INTEGRATION') for d in MX.OWNER_DECISIONS]
    approvals += [
        {'id': 'SUN-1', 'kind': 'SLATE', 'question': 'Who starts at QB for CHI (Caleb Williams DNP)?',
         'why': 'No official designation captured; the board carries a Bagent scenario.',
         'ref': 'nfl/dfs/salaries/classic_early_2026W5/WEEK5_SUNDAY_DECISION_BOARD.md'},
        {'id': 'SUN-2', 'kind': 'MODEL', 'question': 'DST mean: follow simulated events or the projection anchor?',
         'why': 'Decision 2 follow-up; the bounded fix is built and disabled.',
         'ref': 'nfl/research/dst_scoring/'},
        {'id': 'SUN-3', 'kind': 'FILE', 'question': 'Drop DKSalaries.csv for the Sunday Early classic slate '
                                                     '(and DKEntries.csv once entered).',
         'why': 'DK ids and salaries come only from the owner\'s manual export.', 'ref': 'nfl/dfs/inbox/drop/'},
    ]
    return {
        'artifact': 'INTEGRATION_STATUS', 'spec_version': SPEC_VERSION, 'slate_id': slate_id,
        'generated_at_utc': _iso(now), 'reference_state': str(reference_state),
        'reference_as_of': state.get('as_of'),
        'scope': 'READ_ONLY_RESEARCH and ACCOUNT_DATA_READ only. No login, entry, upload, wager or payment.',
        'connections': conns, 'missing_information': missing, 'qb_watch': qbs,
        'designations_filed': des, 'missing_players': mp,
        'rebuild': {'code': pl.code, 'detail': pl.detail, 'changes': pl.evidence.get('changes'),
                    'unchanged': pl.evidence.get('unchanged'), 'uncomparable': pl.evidence.get('uncomparable')},
        'owner_approvals': approvals,
        'projection_independence': 'Projections run on the roster-derived research universe; DraftKings and '
                                   'Fantasy Cruncher being disconnected stops pricing and benchmarking only.',
        'matrix': {a: [r['id'] for r in rs] for a, rs in MX.by_access().items()},
    }


# ------------------------------------------------------------------------------------------------ HTML
_CSS = """
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e3e2dc;--ok:#1f7a3f;--warn:#a15c00;
--bad:#b3261e;--info:#2f5d9e;--chip:#efeee9}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151514;--fg:#ecebe6;--muted:#a3a29b;
--card:#1e1e1c;--line:#33332f;--ok:#5cc184;--warn:#e0a24a;--bad:#f07167;--info:#7aa7e8;--chip:#2a2a27}}
:root[data-theme="dark"]{--bg:#151514;--fg:#ecebe6;--muted:#a3a29b;--card:#1e1e1c;--line:#33332f;--ok:#5cc184;
--warn:#e0a24a;--bad:#f07167;--info:#7aa7e8;--chip:#2a2a27}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}
h2{font-size:17px;margin:28px 0 10px}.sub{color:var(--muted);margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 12px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.s{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;background:var(--chip)}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.info{color:var(--info)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.k{font-size:26px;font-weight:700}.l{color:var(--muted);font-size:13px}ul{margin:6px 0;padding-left:20px}
code{font-size:13px}
"""

_TONE = {'CONNECTED': 'ok', 'MANUAL_FILE_PRESENT': 'ok', 'WATCH_ONLY': 'info', 'DEFERRED_NOT_PUBLISHED': 'info',
         'STALE': 'warn', 'AWAITING_OWNER_EXPORT': 'warn', 'PRESENT_BUT_NOT_THIS_SLATE': 'warn',
         'BLOCKED': 'bad', 'NEVER_CAPTURED': 'bad', 'UNRESOLVED_NO_CLOCK': 'warn', 'NOT_YET_IN_CAPTURE': 'info', 'WAITING': 'warn'}


def _e(x):
    return html.escape('' if x is None else str(x))


def _chip(s):
    return f'<span class="s {_TONE.get(s, "")}">{_e(s)}</span>'


def render_html(st):
    conns = st['connections']
    n_ok = sum(c['status'] in ('CONNECTED', 'MANUAL_FILE_PRESENT') for c in conns)
    n_attn = sum(c['status'] in ('STALE', 'BLOCKED', 'AWAITING_OWNER_EXPORT', 'NEVER_CAPTURED',
                                 'PRESENT_BUT_NOT_THIS_SLATE') for c in conns)
    rb = st['rebuild']
    h = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
         f'content="width=device-width,initial-scale=1"><title>Integration Status</title><style>{_CSS}</style>'
         f'</head><body><main>',
         f'<h1>Integration status: {_e(st["slate_id"])}</h1>',
         f'<p class="sub">Generated {_e(st["generated_at_utc"])} from the capture manifest and the inbox ledger. '
         f'Reference build as of {_e(st["reference_as_of"])}. {_e(st["scope"])}</p>',
         '<div class="grid">',
         f'<div class="card"><div class="k ok">{n_ok}</div><div class="l">sources connected or present</div></div>',
         f'<div class="card"><div class="k warn">{n_attn}</div><div class="l">need attention</div></div>',
         f'<div class="card"><div class="k">{len(st["owner_approvals"])}</div><div class="l">owner decisions'
         f'</div></div>',
         f'<div class="card"><div class="k {"warn" if rb["code"] == "REBUILD_REQUIRED" else "ok"}">'
         f'{"Yes" if rb["code"] == "REBUILD_REQUIRED" else "No"}</div><div class="l">rebuild needed</div></div>',
         '</div>']
    h.append('<h2>Needs your decision</h2><div class="card wrap"><table><tr><th>Id</th><th>Question</th>'
             '<th>Why</th><th>Agent view</th></tr>')
    for a in st['owner_approvals']:
        h.append(f'<tr><td>{_e(a["id"])}</td><td>{_e(a["question"])}</td><td>{_e(a["why"])}</td>'
                 f'<td>{_e(a.get("agent_recommendation") or a.get("ref"))}</td></tr>')
    h.append('</table></div>')
    h.append('<h2>Missing information</h2><div class="card"><ul>')
    for m in st['missing_information']:
        extra = m.get('note') or (', '.join(m.get('clubs') or m.get('files') or []))
        h.append(f'<li>{_chip(m["status"])} {_e(m["what"])}{" — " + _e(extra) if extra else ""}</li>')
    mp = st['missing_players']
    h.append(f'<li>{_chip(mp["status"])} Missing players: {_e(mp.get("detail") or "")}'
             f'{_e(len(mp.get("dk_players_not_on_active_roster", [])))if mp["status"] == "COMPARED" else ""}</li>')
    h.append('</ul></div>')
    h.append('<h2>Connections</h2><div class="card wrap"><table><tr><th>Capability</th><th>Provider</th>'
             '<th>Route class</th><th>Decision</th><th>Status</th><th>Last success (UTC)</th><th>Last content change</th>'
             '<th>Age h</th></tr>')
    for c in conns:
        h.append(f'<tr><td>{_e(c["capability"])}</td><td>{_e(c["provider"])}</td><td>{_e(c["access"])}</td>'
                 f'<td>{_e(c.get("owner_decision") or "")}</td><td>{_chip(c["status"])}</td><td>{_e(c.get("last_success_utc"))}</td>'
                 f'<td>{_e(c.get("last_content_change_utc"))}</td><td>{_e(c.get("age_hours"))}</td></tr>')
    h.append('</table></div>')
    h.append('<h2>Quarterbacks</h2><div class="card wrap"><table><tr><th>Club</th><th>Projected QB1</th>'
             '<th>Newest chart QB1 / QB2</th><th>Injury report</th><th>Flags</th></tr>')
    for q in st['qb_watch']:
        inj = '; '.join(f"{x['name']}: {x['practice_status'] or '-'}"
                        f"{' / ' + x['report_status'] if x['report_status'] else ''}" for x in q['injury_lines'])
        h.append(f'<tr><td>{_e(q["club"])}</td><td>{_e(q["projected_qb1"])}</td>'
                 f'<td>{_e(q["newest_chart_qb1"])} / {_e(q["newest_chart_qb2"])}</td><td>{_e(inj or "none filed")}'
                 f'</td><td>{" ".join(_chip(f) for f in q["flags"]) or "—"}</td></tr>')
    h.append('</table></div>')
    h.append(f'<h2>Rebuild</h2><div class="card"><p>{_chip(rb["code"])} {_e(rb["detail"])}</p><ul>')
    for c in rb.get('changes') or []:
        h.append(f'<li>{_e(c["component"])}: {_e(json.dumps({k: v for k, v in c.items() if k != "component"}))}</li>')
    h.append('</ul></div>')
    h.append(f'<p class="sub">{_e(st["projection_independence"])}</p></main></body></html>')
    return '\n'.join(h)


def export_datasets(st, out_dir):
    """Flat row tables for the published status page, one file per table. Returns {name: path}."""
    od = pathlib.Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    rb = st['rebuild']
    tables = {
        'summary': [{'slate_id': st['slate_id'], 'generated_at_utc': st['generated_at_utc'],
                     'reference_as_of': st['reference_as_of'], 'rebuild_code': rb['code'],
                     'rebuild_detail': rb['detail'], 'missing_players_status': st['missing_players']['status']}],
        'connections': [{k: c.get(k) for k in ('id', 'capability', 'provider', 'access', 'status', 'last_success_utc',
                                                'last_content_change_utc', 'age_hours', 'owner_decision')}
                        for c in st['connections']],
        'decisions': [{'id': a['id'], 'kind': a['kind'], 'question': a['question'], 'why': a['why'],
                       'agent_view': a.get('agent_recommendation') or a.get('ref')} for a in st['owner_approvals']],
        'missing': [{'what': m['what'], 'status': m['status'],
                     'detail': m.get('note') or ', '.join(m.get('clubs') or m.get('files') or [])}
                    for m in st['missing_information']],
        'quarterbacks': [{'club': q['club'], 'projected_qb1': q['projected_qb1'],
                          'newest_chart_qb1': q['newest_chart_qb1'], 'newest_chart_qb2': q['newest_chart_qb2'],
                          'injury_report': '; '.join(f"{x['name']}: {x['practice_status'] or '-'}"
                                                     f"{' / ' + x['report_status'] if x['report_status'] else ''}"
                                                     for x in q['injury_lines']) or 'none filed',
                          'flags': ' '.join(q['flags'])} for q in st['qb_watch']],
        'rebuild_changes': [{'component': c['component'],
                             'change': json.dumps({k: v for k, v in c.items() if k != 'component'}, default=str)}
                            for c in (rb.get('changes') or [])] or [{'component': 'none', 'change': rb['detail']}],
    }
    out = {}
    for name, rows in tables.items():
        p = od / f'{name}.json'
        p.write_text(json.dumps(rows, indent=1, default=str) + '\n')
        out[name] = p
    return out


def resolve_reference(slate_id, given):
    """`auto` means the newest PASS build recorded in the rebuild ledger; otherwise the path given."""
    if given != 'auto':
        return given
    b = RB.latest_ledger_build(slate_id)
    if not b:
        raise SystemExit('REFUSED: --reference-state auto, but the rebuild ledger has no PASS build for this slate')
    o = pathlib.Path(b['out'])
    return str((o if o.is_absolute() else _REPO / o) / 'STATE.json')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--reference-state', required=True, help="a build's STATE.json, or `auto` for the newest "
                                                               "build in the rebuild ledger")
    ap.add_argument('--out', default=str(_REPO / 'nfl' / 'integrations' / 'status'))
    a = ap.parse_args(argv)
    st = build_status(a.slate_id, raw_dir=a.raw_dir, reference_state=resolve_reference(a.slate_id, a.reference_state))
    od = pathlib.Path(a.out)
    export_datasets(st, od / 'datasets')
    od.mkdir(parents=True, exist_ok=True)
    (od / f'INTEGRATION_STATUS_{a.slate_id}.json').write_text(json.dumps(st, indent=1, default=str) + '\n')
    (od / f'INTEGRATION_STATUS_{a.slate_id}.html').write_text(render_html(st))
    for c in st['connections']:
        print(f"  {c['status']:<26} {c['id']:<4} {c['capability']}")
    print(f"rebuild: {st['rebuild']['code']}  missing: {len(st['missing_information'])}  "
          f"owner decisions: {len(st['owner_approvals'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
