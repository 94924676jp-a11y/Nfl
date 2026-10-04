#!/usr/bin/env python3.12
"""The owner's Early Only package: player board, game board, FC comparison, readiness, change log.

    python3.12 nfl/tools/classic_owner_board.py 2026W4

Reads the frozen state, the football-only projection, the joint draws and (if built) the contest
portfolios. The FantasyCruncher numbers enter ONLY through nfl/tools/fc_context (EXTERNAL_FC_CONTEXT)
and ONLY into comparison columns, after every proprietary number on the row is already fixed. No
Hard Rock price exists in this checkout for week 4; every Hard Rock column says so rather than
showing a blank that reads as "no disagreement".
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402
from sportsplatform.governance.outcome import Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
HARD_ROCK = 'NOT_CAPTURED: no Hard Rock week-4 board in this checkout (requested in docs/AGENT_OUTBOX.md)'
ABSENT = AV.ABSENT_STATUSES   # one definition of 'not playing', including relayed and unverified absences

COLUMNS = ['player', 'team', 'opp', 'pos', 'salary', 'dk_id', 'classification', 'starter_state',
           'availability', 'designation', 'role', 'role_confidence', 'projection', 'sim_mean', 'median',
           'p75', 'p90', 'p95', 'floor_p10', 'ceiling_p99', 'targets', 'carries', 'pass_attempts',
           'receptions', 'rec_yards', 'rush_yards', 'pass_yards', 'td_expectation', 'value_per_1k',
           'exp_150max', 'exp_20max', 'exp_3entry', 'fc_proj', 'fc_diff', 'fc_floor', 'fc_ceiling',
           'hard_rock', 'key_reason', 'key_risk', 'game_id']


def _p(b, slate_id, tail):
    return OUT_DIR / f'DK_{slate_id}_EARLY_{tail}'


def _num(x, nd=2):
    return None if x is None else round(float(x), nd)


def classify(r, p, sim_mean, p90):
    av = p['current_availability']
    if av['status'] in ABSENT:
        return 'inactive'
    if r.get('projection_state') == 'PROJECTED_COLD_START' or p.get('identity') == 'IDENTITY_UNRESOLVED_NOT_PROJECTED':
        return 'unresolved'
    if r.get('projection_state') not in ('PROJECTED', 'PROJECTED_DST'):
        return 'non-playable'
    if p['position'] == 'DST':
        return 'viable'
    if av.get('designation') in ('QUESTIONABLE', 'DOUBTFUL') and (av.get('resolution') or {}).get('claim') != 'ACTIVE':
        return 'role-dependent'
    if (p.get('predicted_lineup_context') or {}).get('state') == 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT':
        return 'role-dependent'   # a starter by the depth chart alone, not confirmed by his club
    if sim_mean < 3.0 and p90 < 8.0:
        return 'non-playable'
    if r.get('role_band') in ('FRINGE', 'ROTATIONAL') or sim_mean < 6.0:
        return 'thin'
    return 'viable'


def reason_and_risk(r, p, cls):
    pos, band = p['position'], r.get('role_band')
    ctx = p.get('predicted_lineup_context') or {}
    bits, risk = [], []
    if pos == 'QB':
        bits.append(f"{_num(r.get('pass_attempts'), 1)} proj pass att")
        if ctx.get('state'):
            bits.append('next healthy QB on captured depth chart behind a reported-OUT starter')
            risk.append('starter not confirmed by the club; role rests on the depth chart')
    elif pos in ('WR', 'TE'):
        bits.append(f"{_num(r.get('targets'), 1)} proj targets, {_num(r.get('rec_yards'), 0)} rec yds")
    elif pos == 'RB':
        bits.append(f"{_num(r.get('carries'), 1)} carries, {_num(r.get('targets'), 1)} targets")
    elif pos == 'DST':
        bits.append(f"opponent football-centre points {_num(r.get('opponent_implied_total'), 1)}")
        risk.append('defensive and return TDs excluded: DST projection is a floor')
    if band:
        bits.append(f'role {band}')
    if r.get('capped'):
        risk.append('role capped by evidence ceiling')
    if r.get('role_evidence_conflict'):
        risk.append('history and current usage disagree')
    if (p['current_availability'].get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL'):
        risk.append(f"designated {p['current_availability']['designation']} "
                    f"({p['current_availability'].get('practice_status') or 'practice unknown'})")
    av = p['current_availability']
    if (av.get('designation') == 'NO_DESIGNATION'
            and (av.get('practice_status') or '').startswith('Did Not Participate')):
        risk.append('did not practise on the final report, yet carries no game designation '
                    '(listed as expected to play; reason not given)')
    if r.get('prior_confidence') in ('LOW', None) and pos != 'DST':
        risk.append('thin prior history')
    if cls == 'inactive':
        return 'reported OUT on the official injury report', 'game-day inactive not yet captured'
    if cls == 'unresolved':
        return 'identity not established from captured rosters', 'not projected'
    return '; '.join(bits), '; '.join(risk) or 'none named'


def portfolio_is_current(port, current_sha: dict) -> bool:
    """A portfolio lends its exposures to the board only when built from these exact state, projection and draws."""
    return bool(port) and (port.get('inputs_sha256') or {}) == current_sha


def build(slate_id: str, *, write: bool = True) -> Outcome:
    st = json.loads(_p(None, slate_id, 'STATE.json').read_text())
    proj = json.loads(_p(None, slate_id, 'PROJ.json').read_text())
    dr = json.loads(_p(None, slate_id, 'DRAWS.json').read_text())
    port_path = _p(None, slate_id, 'PORTFOLIOS.json')
    port = json.loads(port_path.read_text()) if port_path.exists() else None
    stale_port = None
    if port:
        now = {k: hashlib.sha256(_p(None, slate_id, f'{k.upper()}.json').read_bytes()).hexdigest()
               for k in ('state', 'proj', 'draws')}
        if not portfolio_is_current(port, now):
            # A portfolio from another projection must not lend its exposures to this board.
            stale_port, port = port.get('built_at_utc'), None
    expo = collections.defaultdict(dict)
    if port:
        for c in port['contests']:
            for _nm, e in c['report']['player_exposure'].items():
                expo[e['dk_id']][c['profile']] = e['overall']

    # FANTASYCRUNCHER IS NOT READ HERE. This process holds proprietary modules, and fc_context's
    # firewall refuses to hand external values to it -- correctly. The FC columns are attached
    # afterwards by nfl/tools/classic_fc_compare.py, in a clean process, onto the frozen board.
    fc_note = {'state': 'ATTACHED_LATER_BY_classic_fc_compare', 'WHY': 'firewall: no FC value in a proprietary process'}
    rows = []
    for dk, p in st['players'].items():
        r = proj['rows'].get(dk) or {}
        k = S.player_key(p['name'], p['team'])
        d = np.asarray(dr['draws'].get(k) or [], dtype=float)
        q = (np.percentile(d, [10, 50, 75, 90, 95, 99]) if d.size else [None] * 6)
        sim_mean = float(d.mean()) if d.size else 0.0
        cls = classify(r, p, sim_mean, float(q[3]) if d.size else 0.0)
        reason, risk = reason_and_risk(r, p, cls)
        td = r.get('td') or {}
        fc = {}
        proj_pts = r.get('dk_points')
        rows.append({
            'player': p['name'], 'team': p['team'], 'opp': p['opponent'], 'pos': p['position'],
            'salary': p['salary'], 'dk_id': dk, 'classification': cls,
            'starter_state': ((p.get('predicted_lineup_context') or {}).get('state')
                              or ('PREDICTED_STARTER' if r.get('is_predicted_starter') else
                                  f"DEPTH_RANK_{p.get('depth_rank')}" if p.get('depth_rank') else 'NO_DEPTH_EVIDENCE')),
            'availability': p['current_availability']['status'],
            'designation': p['current_availability'].get('designation'),
            'role': r.get('role_band'), 'role_confidence': r.get('prior_confidence'),
            'projection': _num(proj_pts), 'sim_mean': _num(sim_mean) if d.size else None,
            'median': _num(q[1]), 'p75': _num(q[2]), 'p90': _num(q[3]), 'p95': _num(q[4]),
            'floor_p10': _num(q[0]), 'ceiling_p99': _num(q[5]),
            'targets': _num(r.get('targets')), 'carries': _num(r.get('carries')),
            'pass_attempts': _num(r.get('pass_attempts')), 'receptions': _num(r.get('receptions')),
            'rec_yards': _num(r.get('rec_yards'), 1), 'rush_yards': _num(r.get('rush_yards'), 1),
            'pass_yards': _num(r.get('pass_yards'), 1),
            'td_expectation': _num((td.get('rec_td') or 0) + (td.get('rush_td') or 0) + (td.get('pass_td') or 0), 3)
                              if td else None,
            'value_per_1k': _num((sim_mean if d.size else 0) / (p['salary'] / 1000.0)) if p['salary'] else None,
            'exp_150max': expo[dk].get('MAX150', 0.0) if port else None,
            'exp_20max': expo[dk].get('MAX20', 0.0) if port else None,
            'exp_3entry': expo[dk].get('MAX3', 0.0) if port else None,
            'fc_proj': fc.get('FC Proj'), 'fc_diff': (_num(sim_mean - fc['FC Proj']) if fc.get('FC Proj') is not None and d.size else None),
            'fc_floor': fc.get('Floor'), 'fc_ceiling': fc.get('Ceiling'),
            'hard_rock': HARD_ROCK, 'key_reason': reason, 'key_risk': risk, 'game_id': p['game_id'],
        })
    order = {'viable': 0, 'role-dependent': 1, 'thin': 2, 'unresolved': 3, 'inactive': 4, 'non-playable': 5}
    rows.sort(key=lambda x: (order[x['classification']], -(x['sim_mean'] or 0)))

    # GAME ENVIRONMENT BOARD, from the football centre and the draws only.
    games = []
    for gid, g in sorted(st['games'].items()):
        a, h = g['away'], g['home']
        c = proj['football_centre'][f'{a}@{h}']
        tv = proj['team_volume']
        gp = [x for x in rows if x['game_id'] == gid and x['classification'] in ('viable', 'role-dependent', 'thin')]
        top = sorted(gp, key=lambda x: -(x['p95'] or 0))[:5]
        def _club(cl):
            t = tv.get(cl) or {}
            return {'proj_pass_attempts': _num(t.get('proj_pass_attempts'), 1),
                    'proj_rush_attempts': _num(t.get('proj_rush_attempts'), 1),
                    'proj_targets': _num(t.get('proj_targets'), 1)}
        games.append({'game_id': gid, 'away': a, 'home': h,
                      'football_total': _num(c['total'], 1), 'home_margin': _num(c['home_margin'], 1),
                      'away_expected': _num(c['away_expected'], 1), 'home_expected': _num(c['home_expected'], 1),
                      'away_volume': _club(a), 'home_volume': _club(h),
                      'best_ceiling_players': [f"{x['player']} {x['team']} {x['pos']} p95 {x['p95']}" for x in top],
                      'injury_sensitivity': sorted({f"{x['player']} {x['team']} ({x['designation']})"
                                                    for x in rows if x['game_id'] == gid
                                                    and x['designation'] in ('OUT', 'QUESTIONABLE', 'DOUBTFUL')}),
                      'market_comparison': HARD_ROCK})
    games.sort(key=lambda g: -(g['football_total'] or 0))

    fc_cmp = 'ATTACHED_LATER_BY_classic_fc_compare'

    counts = collections.Counter(x['classification'] for x in rows)
    readiness = {
        'CURRENT': ['DK contest universe (owner export, hash-verified)',
                    f"official injury report {st['injury_report']['retrieved_at']}",
                    f"depth charts (QB order; RB/WR/TE rank = better of usage and chart) {sorted({v['capture_id'] for v in st['depth']['qb_chart'].values()})}",
                    f"evidence covers every game the week-4 forecast consumes ({st['freshness']['n_games_scored']}/{st['freshness']['n_games_consumed']})",
                    f"football sanity gate {dr['football_sanity']['code']}"],
        # read from the state, never written as fixed text: a pending item that has arrived is not pending
        'STALE_OR_PENDING': ([] if str((st.get('official_inactives') or {}).get('STATE', '')).startswith('APPLIED')
                                and len((st.get('official_inactives') or {}).get('clubs_with_full_list') or []) ==
                                len({c for g in st['games'].values() for c in (g['away'], g['home'])})
                             else [f"game-day inactives: {(st.get('official_inactives') or {}).get('STATE')} "
                                   f"({len((st.get('official_inactives') or {}).get('clubs_with_full_list') or [])} of "
                                   f"{len({c for g in st['games'].values() for c in (g['away'], g['home'])})} clubs listed)"]),
        'CONTEXT_NOT_CAPTURED': ['Hard Rock board: not captured (downstream comparison only; no lineup depends on it)',
                                 'weather: not captured; no validated weather term in the model (context only)'],
        'UNRESOLVED': [f"{u['name']} {u['team']} {u['position']}" for u in st['identity']['unresolved']]
                      + [f"NYG injury block carries no game designation (filed, but blank)"]
                      + [f"{x['player']} {x['team']}: starter by depth chart, not confirmed by the club"
                         for x in rows if x['starter_state'] == 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT'],
        'NOT_MODELLED': ['ownership / duplication (no data)', 'defensive and return TDs (DST is a floor)',
                         'weather', 'cross-game correlation (games simulated independently)',
                         'kickers are not on a Classic slate',
                         'player-specific yards per target/carry inside the simulator; draws are '
                         + ('re-centred on our projection per player (declared step '
                            f"{(dr.get('player_mean_anchor') or {}).get('mode')}; largest gap before "
                            f"{(dr.get('player_mean_anchor') or {}).get('raw_gap_abs_max')} pts, after "
                            f"{(dr.get('player_mean_anchor') or {}).get('residual_gap_abs_max')} pts)"
                            if (dr.get('player_mean_anchor') or {}).get('mode') in ('PROJECTION_MEAN_MULTIPLICATIVE', 'PROJECTION_EFFICIENCY_PER_WORLD')
                            else 'NOT re-centred, so simulated means differ from our projection'),
                         'club passing yards do not close inside the projection (receivers vs QB, '
                         'up to about 39 yds per club)'],
        'VALIDATION_STATE': ('PROJECTION_SYSTEM_STATE NOT_VALIDATED. The proprietary arm is FOOTBALL_ONLY, '
                             'the declared candidate arm; no forward-chained evidence yet shows it beats '
                             'anything. These are research-grade numbers, not a validated edge.'),
        'BLOCKED': ([f'portfolio built {stale_port} from different inputs; rebuild it'] if stale_port else
                    ['portfolios not yet built'] if not port else
                    [f"{c['contest_name']}: {c['n_filled']}/{c['n_entries']}" for c in port['contests'] if not c['FILLED']]),
        'classification_counts': dict(counts),
    }
    # THE FOOTBALL REASON FOR EVERY MATERIAL EXPOSURE, from the research book built on these inputs.
    dfs_reasoning = None
    bp = _p(None, slate_id, 'RESEARCH_BOOK.json')
    if port and bp.exists():
        book = json.loads(bp.read_text())
        cur = {n: hashlib.sha256(_p(None, slate_id, n).read_bytes()).hexdigest() for n in ('PROJ.json', 'DRAWS.json')}
        if all((book.get('inputs_sha256') or {}).get(n) == v for n, v in cur.items()):
            from nfl.tools import classic_dfs_reasoning as DR
            dfs_reasoning = DR.reasons(book, port, dr.get('draws') or {})
            readiness['RESEARCH_BOOK'] = f"built {book['built_at_utc'][:16]}Z, accounting {book['ACCOUNTING']['state']}"
        else:
            readiness.setdefault('BLOCKED', []).append('research book built from other inputs; rebuild it')
    elif port:
        readiness.setdefault('BLOCKED', []).append('no research book: the football reason for each exposure is missing')
    doc = {'ARTIFACT': 'CLASSIC_OWNER_BOARD', 'slate_id': slate_id,
           'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs_sha256': {n: hashlib.sha256(_p(None, slate_id, n).read_bytes()).hexdigest()
                             for n in ('STATE.json', 'PROJ.json', 'DRAWS.json')},
           'portfolio_built': bool(port), 'market_arm': proj.get('market_arm'),
           'fc': fc_note, 'players': rows, 'games': games, 'fc_comparison': fc_cmp, 'readiness': readiness,
           'dfs_reasoning': dfs_reasoning}
    if write:
        _p(None, slate_id, 'OWNER_BOARD.json').write_text(json.dumps(doc, indent=1, default=str))
        with open(_p(None, slate_id, 'PLAYER_BOARD.csv'), 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            for x in rows:
                w.writerow(x)
    return Outcome.measured('CLASSIC_OWNER_BOARD_BUILT', {'n_players': len(rows)}, n_measured=len(rows),
                            what='board rows', detail=f"{len(rows)} players, {dict(counts)}; "
                                                       f"FC attached separately; portfolio {'yes' if port else 'no'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    a = ap.parse_args()
    o = build(a.slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
