#!/usr/bin/env python3.12
"""Automatic QB-regime detection and evidence-consumption audit, per club, for any slate. Read-only, diagnostic.

    python3.12 nfl/tools/qb_regime_audit.py SCENARIO_DIR [--alt-scenario DIR] [--out PATH]

Owner directive 2026-10-08: the engine had TB's week-4 Daniels start in its own data and did not recognise what it
meant; the owner had to point it out. This runs WITHOUT being asked, for both clubs of every slate, and reports:

  starter / dominant QB   the scenario's starting QB vs the QB who threw most of the attempts the club environment is
                          built from (current season before the week + prior season at the volume layer's 4 pseudo-games)
  starts                  the club's games this season in which the starter threw the most passes, with team volume and
                          points in those games against the rest (descriptive; tiny n is stated, never hidden)
  starter's own lines     in his starts vs in relief appearances
  consumption             for each of the starter's projection inputs (carry share, attempt share, YPA, YPC): how many
                          current-season games it pooled, how many were starts, the prior tier and its weight. A share
                          that pools relief appearances with starts is flagged RELIEF_POOLED_WITH_STARTS
  teammates               each pass catcher's projected target share against his share in the starter's starts and in
                          the other games, and how much weight the starter's games carry in the projection
  environment response    with --alt-scenario (the same slate under the other QB): how our team volume, centre and
                          every player moved
  missing dependencies    the QB-dependent edges of DEPENDENCY_GRAPH_SHOWDOWN_v0.json and their status

It changes nothing. A REGIME_CHANGE finding is a statement about evidence coverage, not a forecast.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PRIOR_GAMES = 4.0
GRAPH = _REPO / 'nfl/research/intel/DEPENDENCY_GRAPH_SHOWDOWN_v0.json'
QB_EDGES = ('QB1', 'QB2', 'QB3', 'QB4', 'QB5', 'AC1')


def _rows(pj):
    rows = pj.get('rows') or pj
    return [r for r in (rows.values() if isinstance(rows, dict) else rows) if isinstance(r, dict) and r.get('name')]


def _club_weeks(panel, club, season, before):
    return {int(w): v for w, v in ((panel['teams'].get(club) or {}).get(str(season)) or {}).items() if int(w) < before}


def _qb_lines(panel, club, season, before):
    """{week: [(gsis, line)]} for every player with a pass attempt for the club."""
    out = {}
    for g, s in panel['players'].items():
        for w, v in ((s.get(str(season)) or {}).items()):
            if int(w) < before and v.get('team') == club and (v.get('pass_attempts') or 0) > 0:
                out.setdefault(int(w), []).append((g, v))
    return out


def audit_club(panel, state, proj_rows, club, alt_rows=None, names=None):
    from nfl.tools import showdown_run_guards as G
    season, week = int(state['season']), int(state['week'])
    starters = [p for p in state['players'].values() if p.get('team') == club and p.get('position') == 'QB'
                and (p.get('predicted_lineup_context') or {}).get('in_predicted_starting_group')]
    if not starters:
        return {'club': club, 'status': 'NO_STARTING_QB_IN_STATE'}
    st = starters[0]
    sg = st.get('gsis_id')
    share = G.qb_environment_share(panel, club, sg, season, week, PRIOR_GAMES)
    qbw = _qb_lines(panel, club, season, week)
    cw = _club_weeks(panel, club, season, week)
    # who threw most in each game (the outcome-labelled primary passer of a PAST game is fine: it is history)
    primary = {w: max(lst, key=lambda t: t[1].get('pass_attempts') or 0)[0] for w, lst in qbw.items()}
    starts = sorted(w for w, g in primary.items() if g == sg)
    relief = sorted(w for w, lst in qbw.items() if w not in starts and any(g == sg for g, _ in lst))
    # attempts by QB across the current-season window
    tot = {}
    for w, lst in qbw.items():
        for g, v in lst:
            tot[g] = tot.get(g, 0) + (v.get('pass_attempts') or 0)
    allatt = sum(tot.values()) or 1
    by_qb = {(names or {}).get(g, g): round(a / allatt, 3) for g, a in sorted(tot.items(), key=lambda t: -t[1])}
    dominant = max(tot, key=tot.get) if tot else None

    def team(ws):
        rows = [cw[w] for w in ws if w in cw]
        if not rows:
            return None
        f = lambda k: round(statistics.fmean([(r.get(k) or 0) for r in rows]), 2)  # noqa: E731
        return {'games': ws, 'pass_attempts': f('pass_attempts'), 'rush_attempts': f('rush_attempts'),
                'targets': f('targets'), 'plays': f('plays')}
    others = sorted(w for w in cw if w not in starts)
    pts = {}
    try:
        from nfl.sim import football_points as FP
        tbl = FP.club_points_table(FP._rows())
        pts = {w: (tbl.get(club, {}).get(season) or {}).get(w) for w in cw}
    except Exception:  # noqa: BLE001 -- points are context only
        pass
    t_starts, t_other = team(starts), team(others)
    for t, ws in ((t_starts, starts), (t_other, others)):
        if t is not None:
            vals = [pts.get(w) for w in ws if pts.get(w) is not None]
            t['points'] = round(statistics.fmean(vals), 2) if vals else None
    own = (panel['players'].get(sg) or {}).get(str(season)) or {}
    lines = {w: {k: own[str(w)].get(k) for k in ('pass_attempts', 'pass_yards', 'pass_td', 'carries', 'rush_yards')}
             for w in starts + relief if str(w) in own}
    prow = next((r for r in proj_rows if r.get('gsis_id') == sg), {})
    consumption = {}
    for k in ('carry_share', 'pass_attempt_share', 'yards_per_attempt', 'yards_per_carry'):
        b = (prow.get('basis') or {}).get(k) or {}
        n = b.get('current_n')
        consumption[k] = {'projected_input': b, 'current_games_pooled': n, 'of_which_starts': len(starts),
                          'prior_tier': prow.get('prior_tier'), 'prior_weight': b.get('prior_weight_fraction'),
                          'flags': (['RELIEF_POOLED_WITH_STARTS'] if relief and n and n > len(starts) else [])
                          + (['GENERIC_COHORT_PRIOR'] if prow.get('prior_tier') == 'ARCHETYPE' else [])}
    # teammates: projected target share vs share in the starter's starts and in the other games
    mates = []
    for r in proj_rows:
        if r.get('team') != club or r.get('position') not in ('WR', 'TE', 'RB'):
            continue
        s = (panel['players'].get(r.get('gsis_id')) or {}).get(str(season)) or {}

        def sh(ws):
            num = sum((s.get(str(w)) or {}).get('targets') or 0 for w in ws if (s.get(str(w)) or {}).get('team') == club)
            den = sum((cw.get(w) or {}).get('targets') or 0 for w in ws)
            return round(num / den, 3) if den else None
        b = (r.get('basis') or {}).get('target_share') or {}
        n, pw = b.get('current_n'), b.get('prior_weight_fraction')
        w_starts = round((1 - (pw or 0)) * (len(starts) / n), 3) if n else None
        if (r.get('targets') or 0) < 1 and not sh(starts):
            continue
        alt = next((x for x in (alt_rows or []) if x.get('gsis_id') == r.get('gsis_id')), None)
        mates.append({'player': r['name'], 'pos': r['position'], 'proj_targets': round(r.get('targets') or 0, 2),
                      'target_share_in_starter_starts': sh(starts), 'target_share_in_other_games': sh(others),
                      'weight_of_starter_games_in_projection': w_starts,
                      'proj_dk': r.get('dk_points'), 'alt_scenario_dk': (alt or {}).get('dk_points'),
                      'dk_change_vs_alt': (round(r['dk_points'] - alt['dk_points'], 3)
                                           if alt and r.get('dk_points') is not None and alt.get('dk_points') is not None
                                           else None)})
    g = {e['id']: e['status'] for e in json.loads(GRAPH.read_text())['edges']} if GRAPH.is_file() else {}
    regime = share['blended_share'] is not None and share['blended_share'] <= G.QB_ENV_MAJORITY
    return {'club': club, 'status': 'REGIME_CHANGE' if regime else 'NO_REGIME_CHANGE',
            'starter': {'name': st['name'], 'gsis_id': sg}, 'dominant_qb_in_window': (names or {}).get(dominant, dominant),
            'starter_blended_share_of_environment': share['blended_share'], 'current_season_attempt_share_by_qb': by_qb,
            'starter_starts_this_season': starts, 'starter_relief_appearances': relief,
            'team_in_starter_starts': t_starts, 'team_in_other_games': t_other,
            'starter_lines': lines, 'starter_projection_consumption': consumption, 'teammates': mates,
            'qb_dependent_edges': {e: g.get(e, 'UNKNOWN') for e in QB_EDGES},
            'uncertainty': f'{len(starts)} start(s) for this QB with this club this season: descriptive, not an estimate'}


def run(sd, alt=None):
    from nfl.tools import player_prior as PP
    sd = pathlib.Path(sd).resolve()
    state = json.loads(next(sd.glob('SHOWDOWN_*_STATE.json')).read_text())
    proj = _rows(json.loads(next(sd.glob('SHOWDOWN_*_PROJ.json')).read_text()))
    alt_rows = _rows(json.loads(next(pathlib.Path(alt).resolve().glob('SHOWDOWN_*_PROJ.json')).read_text())) if alt else None
    panel = PP.load_panel().value
    names = {p.get('gsis_id'): p['name'] for p in state['players'].values() if p.get('gsis_id')}
    clubs = sorted({p['team'] for p in state['players'].values() if p.get('team')})
    out = {'ARTIFACT': 'QB_REGIME_AUDIT', 'scenario_dir': str(sd), 'season': state['season'], 'week': state['week'],
           'ROLE': 'DIAGNOSTIC ONLY: evidence coverage, never a forecast change', 'alt_scenario': str(alt) if alt else None,
           'clubs': {c: audit_club(panel, state, proj, c, alt_rows, names) for c in clubs}}
    out['REGIME_CHANGES'] = [c for c, v in out['clubs'].items() if v.get('status') == 'REGIME_CHANGE']
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario_dir')
    ap.add_argument('--alt-scenario')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    r = run(a.scenario_dir, a.alt_scenario)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(r, indent=1, default=str) + '\n')
    print(json.dumps({c: {k: v.get(k) for k in ('status', 'starter', 'starter_blended_share_of_environment',
                                                   'starter_starts_this_season', 'starter_relief_appearances')}
                      for c, v in r['clubs'].items()}, indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
