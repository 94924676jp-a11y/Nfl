#!/usr/bin/env python3.12
"""Independent audit of a classic slate's production chain, layer by layer, from the frozen artifacts.

    python3.12 nfl/tools/classic_production_audit.py 2026W4

It re-derives what the production tools claim, with its own code where that matters (team accounting
from projection rows, usage recounted from play-by-play, legality from DK's pool), and writes
DK_<slate>_EARLY_AUDIT.json. A section that cannot be computed says why; it is never left empty.

SECTIONS
  structure        per game, per team: QB1/QB2, RB1/RB2, pass-down RB, WR1-WR4, TE1/TE2, K, DST, and
                   every contradiction between chart, availability, role and projected volume
  role_cards       a sampled cross-check of research-book cards against an independent pbp recount
  accounting       per-team residuals for attempts, targets, carries, TDs; absent players' volume;
                   non-QB pass attempts
  yards_closure    QB passing yards vs receivers' yards per team, with the decomposition of the gap
  simulator        per-player and per-stat simulated mean vs projection; top 20 each way
  distributions    before vs after the efficiency step for representative players, and correlations
  portfolios       150 / 20 / 3: legality, exposures by slot, stacks, overlaps, intersections, and
                   proof the 20-max is not the first or best 20 of the 150-max
  reproducibility  two independent builds compared byte for byte (when the sensitivity runs exist)
  role_dependent   chart-only starters: exposure, and the portfolio with each removed
  stadiums         roof and surface from the schedule capture; weather is not held
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
#: DECLARED: a projected-volume figure at or above this is "volume" for the contradiction checks
VOLUME_FLOOR = 0.5
#: DECLARED: a contradiction is publication-blocking only for a player projected at least this many DK points
MATERIAL_DK = 3.0
#: DECLARED yards-closure tolerance for stat-specific props (fraction of the QB's passing yards).
#: 5% of a ~230-yard club is ~12 yards, about a third of one receiver's yardage SD.
YARDS_CLOSURE_TOL = 0.05


def _p(slate, n):
    return OUT_DIR / f'DK_{slate}_EARLY_{n}'


def _f(x, nd=2):
    return None if x is None else round(float(x), nd)


def _load(slate, n):
    p = _p(slate, n)
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------------------------ structure
def structure(book, state):
    from nfl.tools import classic_research_book as B
    _cid, ch = B.chart_tree(state['as_of'])
    chart_ids = {c: v['slots'] for c, v in ch.items()}
    out, flags = {}, []
    sp = state['players']
    for gid, g in book['games'].items():
        gout = {}
        for club, t in g['teams'].items():
            cards = t['players']
            by = collections.defaultdict(list)
            for c in cards:
                by[c['position']].append(c)
            for k in by:
                by[k].sort(key=lambda c: -((c['projection'].get('targets') or 0) + (c['projection'].get('carries') or 0)
                                           + (c['projection'].get('pass_attempts') or 0)))
            qbs = sorted(by['QB'], key=lambda c: -(c['projection'].get('pass_attempts') or 0))
            rbs = sorted(by['RB'], key=lambda c: -(c['projection'].get('carries') or 0))
            pass_down = max(by['RB'], key=lambda c: c['measured_2026'].get('third_down_targets') or 0, default=None)
            wrs = sorted(by['WR'], key=lambda c: -(c['projection'].get('targets') or 0))
            tes = sorted(by['TE'], key=lambda c: -(c['projection'].get('targets') or 0))

            def brief(c):
                if c is None:
                    return None
                pr = c['projection']
                return {'name': c['name'], 'dk_id': c['dk_id'], 'declared_rank': c['depth']['declared_rank'],
                        'measured_rank': c['depth']['measured_usage_rank'], 'band': pr.get('role_band'),
                        'availability': c['status']['availability'], 'designation': c['status']['designation'],
                        'starter_evidence': c['status']['reported_starter'] or ('CHART' if c['depth']['declared_rank'] == 1 else None),
                        'proj': {k: pr.get(k) for k in ('pass_attempts', 'targets', 'carries', 'rec_rz_opps', 'rush_rz_opps')},
                        'dk_mean': pr.get('dk_mean'), 'uncertainty': c['uncertainty']['role_confidence']}
            gout[club] = {
                'QB1': brief(qbs[0] if qbs else None), 'QB2': brief(qbs[1] if len(qbs) > 1 else None),
                'RB1': brief(rbs[0] if rbs else None), 'RB2': brief(rbs[1] if len(rbs) > 1 else None),
                'PASS_DOWN_RB': brief(pass_down),
                'WR1': brief(wrs[0] if wrs else None), 'WR2': brief(wrs[1] if len(wrs) > 1 else None),
                'WR3_SLOT': {**(brief(wrs[2]) or {}), 'slot_alignment': 'UNAVAILABLE_NO_CAPTURE'} if len(wrs) > 2 else None,
                'WR4': brief(wrs[3] if len(wrs) > 3 else None),
                'TE1': brief(tes[0] if tes else None), 'TE2': brief(tes[1] if len(tes) > 1 else None),
                'K': t.get('kicker'), 'DST': {'name': (t.get('dst') or {}).get('name'),
                                             'dk_mean': ((t.get('dst') or {}).get('projection') or {}).get('distribution', {}).get('dk_mean')}}
            # ---- contradictions
            for c in cards:
                pr, st_, dp = c['projection'], c['status'], c['depth']
                vol = (pr.get('targets') or 0) + (pr.get('carries') or 0) + (pr.get('pass_attempts') or 0)
                tag = f"{c['name']} ({club} {c['position']})"
                if st_['availability'] in AV.ABSENT_STATUSES and vol >= VOLUME_FLOOR:
                    flags.append({'kind': 'INACTIVE_WITH_VOLUME', 'player': tag, 'volume': _f(vol)})
                if c['position'] in ('WR', 'TE', 'RB') and dp['declared_rank'] == 1 and pr.get('role_band') in ('ROTATIONAL', 'FRINGE') \
                        and not (st_['designation'] in ('QUESTIONABLE', 'DOUBTFUL')):
                    flags.append({'kind': 'CHART_STARTER_WITH_ROTATIONAL_ROLE', 'player': tag, 'band': pr.get('role_band'),
                                  'measured_rank': dp['measured_usage_rank']})
                if c['position'] == 'QB' and (pr.get('pass_attempts') or 0) >= 15 and st_['reported_starter']:
                    flags.append({'kind': 'BACKUP_QB_WITH_STARTER_VOLUME', 'player': tag, 'pass_attempts': pr.get('pass_attempts'),
                                  'evidence': st_['reported_starter'], 'confirmed': False})
                ident = (sp.get(c['dk_id']) or {}).get('identity') or {}
                if isinstance(ident, str):
                    flags.append({'kind': 'IDENTITY_NOT_RESOLVED', 'player': tag, 'state': ident})
                elif ident.get('club_agrees') is False:
                    # DK's pool is the contest's truth for the club; the roster capture covers the weeks
                    # before the slate, so a disagreement is a move the capture has not seen yet. It is
                    # hard only where it could move a lineup.
                    material = (pr.get('dk_mean') or 0) >= MATERIAL_DK
                    flags.append({'kind': 'TEAM_MISMATCH' if material else 'ROSTER_MOVE_SINCE_LAST_CAPTURE',
                                  'player': tag, 'dk_club': club, 'roster_capture_club': ident.get('roster_team'),
                                  'dk_mean': pr.get('dk_mean')})
            # chart starters missing from the DK pool -- by gsis id, never by name ("James Cook" on the
            # roster is "James Cook III" in DK's pool; a name comparison reported him missing)
            ids_in_pool = {c.get('gsis_id') for c in cards}
            out_g = {v.get('gsis_id') for v in sp.values() if v['current_availability']['status'] in AV.ABSENT_STATUSES}
            for slot in ('QB', 'RB', 'WR', 'TE'):
                for g_ in (chart_ids.get(club, {}).get(slot) or [])[:(2 if slot == 'WR' else 1)]:
                    if g_ not in ids_in_pool and g_ not in out_g:
                        flags.append({'kind': 'CHART_STARTER_NOT_IN_DK_POOL', 'player': f'{g_} ({club} {slot})'})
        out[gid] = gout
    return out, flags


# ------------------------------------------------------------------------------------ role cards
def recount(pbp, weeks, gsis):
    """Independent recount of one player's targets, carries and attempts from play-by-play."""
    n = collections.Counter()
    wk = {str(w) for w in weeks}
    with gzip.open(pbp, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG' or r.get('week') not in wk:
                continue
            if '1' in (r.get('two_point_attempt'), r.get('qb_kneel'), r.get('qb_spike')):
                continue
            real_pass = r.get('pass_attempt') == '1' and r.get('sack') != '1'
            if real_pass and r.get('receiver_player_id') == gsis:
                n['targets'] += 1
            if real_pass and r.get('passer_player_id') == gsis:
                n['pass_att'] += 1
            if r.get('rush_attempt') == '1' and r.get('rusher_player_id') == gsis:
                n['carries'] += 1
    return dict(n)


def role_cards(book, state):
    pbp = _REPO / book['evidence']['pbp']['file']
    weeks = [int(w) for w in book['evidence']['pbp']['weeks']]
    want = {'QB': 2, 'RB': 3, 'WR': 4, 'TE': 2}
    picked, seen_games = [], collections.Counter()
    for gid, g in sorted(book['games'].items()):
        for club, t in g['teams'].items():
            for c in sorted(t['players'], key=lambda c: -(c['projection'].get('dk_mean') or 0)):
                pos = c['position']
                if want.get(pos, 0) > 0 and seen_games[(gid, pos)] < 1 and c.get('gsis_id'):
                    picked.append((gid, club, c))
                    want[pos] -= 1
                    seen_games[(gid, pos)] += 1
    rows = []
    for gid, club, c in picked:
        rc = recount(pbp, weeks, c['gsis_id'])
        m = c['measured_2026']
        ok = (rc.get('targets', 0) == m['targets'] and rc.get('carries', 0) == m['carries']
              and rc.get('pass_att', 0) == m['pass_att'])
        sp = state['players'].get(c['dk_id']) or {}
        rows.append({'game': gid, 'player': c['name'], 'team': club, 'position': c['position'],
                     'book': {'targets': m['targets'], 'carries': m['carries'], 'pass_att': m['pass_att'], 'games': m['games']},
                     'independent_recount': rc, 'usage_matches': ok,
                     'depth_evidence': {'declared_rank': c['depth']['declared_rank'], 'state_depth_source': sp.get('depth_source')},
                     'injury_evidence': {'tier': c['status']['tier'], 'designation': c['status']['designation']},
                     'starter_evidence': c['status']['reported_starter'] or c['status']['confirmed_starter'],
                     'historical': {'prior_tier': c['uncertainty']['prior_tier'], 'role_confidence': c['uncertainty']['role_confidence']},
                     'unavailable_fields_kept_unavailable': all(
                         v == 'UNAVAILABLE_NO_CAPTURE' for v in (c['playing_time']['route_participation'],
                                                                 c['measured_2026']['alignment'], c['measured_2026']['routes']))})
    k = [{'team': club, 'kicker': t['kicker']} for g in book['games'].values() for club, t in g['teams'].items()][:2]
    d = [{'team': club, 'dst': {kk: t['dst'][kk] for kk in ('name', 'projection', 'points_allowed_simulated', 'components')}}
         for g in book['games'].values() for club, t in g['teams'].items() if t.get('dst')][:2]
    return {'sampled': rows, 'all_usage_match': all(r['usage_matches'] for r in rows), 'kicker': k, 'dst': d}


# ------------------------------------------------------------------------------------ accounting
def accounting(proj, state):
    rows = proj['rows']
    tv = proj['team_volume']
    clubs = sorted({c for g in state['games'].values() for c in (g['away'], g['home'])})
    out, fails = {}, []
    out_ids = {dk for dk, p in state['players'].items() if p['current_availability']['status'] in AV.ABSENT_STATUSES}
    for club in clubs:
        mem = [r for r in rows.values() if r.get('team') == club and r.get('position') in ('QB', 'RB', 'WR', 'TE')]
        s = {f: sum(r.get(f) or 0 for r in mem) for f in ('pass_attempts', 'targets', 'carries')}
        tot = {'pass_attempts': tv[club]['proj_pass_attempts'], 'targets': tv[club]['proj_targets'],
               'carries': tv[club]['proj_rush_attempts']}
        res = {f: _f(s[f] - tot[f], 6) for f in s}
        non_qb_pa = sum(r.get('pass_attempts') or 0 for r in mem if r['position'] != 'QB')
        absent_vol = sum((rows[dk].get('targets') or 0) + (rows[dk].get('carries') or 0) + (rows[dk].get('pass_attempts') or 0)
                         for dk in out_ids if dk in rows and rows[dk].get('team') == club)
        ptd = sum((r.get('td') or {}).get('pass_td', 0) or 0 for r in mem)
        rtd = sum((r.get('td') or {}).get('rec_td', 0) or 0 for r in mem)
        ok = all(abs(v) <= 1e-6 * max(1, tot[f]) for f, v in res.items()) and absent_vol == 0 and abs(ptd - rtd) < 1e-3
        out[club] = {'residuals': res, 'non_qb_pass_attempts': _f(non_qb_pa, 3), 'absent_players_volume': _f(absent_vol, 4),
                     'pass_td_pool': _f(ptd, 3), 'receiving_td': _f(rtd, 3), 'state': 'PASS' if ok else 'FAIL'}
        if not ok:
            fails.append(club)
    return {'per_team': out, 'failures': fails, 'state': 'PASS' if not fails else 'FAIL'}


# ------------------------------------------------------------------------------------ yards closure
def pairing_changes(book):
    """Per club: a chart-only starting QB, and pass catchers out who vacate 3+ targets a game."""
    out = {}
    for g in book['games'].values():
        for club, t in g['teams'].items():
            q = t.get('qb_ecosystem') or {}
            ch = []
            if (q.get('status') or {}).get('reported_starter'):
                ch.append(f"QB {q['quarterback']} starts off the depth chart behind a reported-OUT starter")
            for c in t['injury_cascades']:
                v = c.get('vacated_per_game_2026') or {}
                if c.get('position') in ('WR', 'TE', 'RB') and (v.get('targets') or 0) >= 3:
                    ch.append(f"{c['player']} ({c['position']}) out, {v['targets']} targets a game vacated")
            out[club] = ch
    return out


def yards_closure(proj, stats, meta, book=None):
    pc = pairing_changes(book) if book else {}
    rows = proj['rows']
    F = {f: i for i, f in enumerate(meta['fields'])}
    kix = {k: i for i, k in enumerate(meta['keys'])}
    ys = meta['yard_scale']
    by = collections.defaultdict(list)
    for r in rows.values():
        if r.get('position') in ('QB', 'RB', 'WR', 'TE'):
            by[r['team']].append(r)
    table = {}
    for club, mem in sorted(by.items()):
        qb_y = sum(r.get('pass_yards') or 0 for r in mem)
        rec_y = sum(r.get('rec_yards') or 0 for r in mem)
        att = sum(r.get('pass_attempts') or 0 for r in mem)
        tgt = sum(r.get('targets') or 0 for r in mem)
        recs = sum(r.get('receptions') or 0 for r in mem)
        qb_cmp = sum((r.get('pass_attempts') or 0) * ((r.get('efficiency') or {}).get('completion_rate') or 0)
                     for r in mem if r['position'] == 'QB')
        ypa_qb = qb_y / att if att else None
        ypt_rec = rec_y / tgt if tgt else None
        # in the stored worlds: per-world QB yards minus receivers' yards
        keys = [f"{r['name']}|{r['team']}" for r in mem if f"{r['name']}|{r['team']}" in kix]
        if keys:
            A = stats[[kix[k] for k in keys]].astype(float)
            w_qb = A[:, :, F['pass_yards']].sum(0) / ys
            w_rec = A[:, :, F['rec_yards']].sum(0) / ys
            sim = {'qb_yards_mean': _f(w_qb.mean(), 1), 'rec_yards_mean': _f(w_rec.mean(), 1),
                   'per_world_gap_mean': _f((w_rec - w_qb).mean(), 1), 'per_world_gap_sd': _f((w_rec - w_qb).std(), 1)}
        else:
            sim = None
        gap = rec_y - qb_y
        table[club] = {
            'qb_passing_yards_mean': _f(qb_y, 1), 'sum_receiving_yards_mean': _f(rec_y, 1), 'difference': _f(gap, 1),
            'percent_difference': _f(100 * gap / qb_y, 1) if qb_y else None,
            'volume_closes': {'qb_attempts': _f(att, 2), 'targets': _f(tgt, 2), 'throwaways': _f(att - tgt, 2)},
            'completions_vs_receptions': {'qb_completions_implied': _f(qb_cmp, 2), 'receptions': _f(recs, 2),
                                          'difference': _f(recs - qb_cmp, 2)},
            'efficiency': {'qb_yards_per_attempt': _f(ypa_qb, 2), 'receivers_yards_per_target': _f(ypt_rec, 2),
                           'receivers_imply_qb_ypa': _f(rec_y / att, 2) if att else None},
            'simulated_worlds_after_efficiency_step': sim,
            'CAUSE': ('two independent efficiency estimates for the same yards: the QB row carries attempts x its own '
                      'yards-per-attempt prior, each receiver carries targets x its own yards-per-target prior, and '
                      'nothing in the projection ties the two. Volume closes exactly (targets + throwaways = attempts); '
                      'sacks do not enter passing yards; there is one QB with volume per club. The efficiency step '
                      'then centres each side on its own projection, so the gap survives into every world.'),
            'prop_gate': 'BLOCK_YARDS_PROPS' if qb_y and abs(gap) / qb_y > YARDS_CLOSURE_TOL else 'OPEN',
            'pairing_changed_this_week': pc.get(club, []),
        }
    return {'tolerance': YARDS_CLOSURE_TOL, 'per_team': table,
            'blocked_teams': sorted(c for c, v in table.items() if v['prop_gate'] != 'OPEN'),
            'RESOLUTION': ('NOT RESOLVED TONIGHT: choosing the QB level or the receiver level is a modelling decision with no '
                           'forward evidence yet. Passing/receiving/rush+rec yards props for blocked teams are not eligible '
                           'for attention; other markets and DFS are unaffected.')}


# ------------------------------------------------------------------------------------ simulator
def simulator(proj, draws_doc, stats, meta):
    rows = {f"{r['name']}|{r['team']}": r for r in proj['rows'].values()}
    F = {f: i for i, f in enumerate(meta['fields'])}
    ys = meta['yard_scale']
    draws = draws_doc['draws']
    dk_rows = []
    for k, v in draws.items():
        r = rows.get(k)
        if not r or (r.get('dk_points') or 0) < 5:
            continue
        m = float(np.mean(v))
        dk_rows.append({'player': r['name'], 'team': r['team'], 'pos': r['position'], 'projection': _f(r['dk_points']),
                        'sim_mean': _f(m), 'abs_diff': _f(m - r['dk_points']),
                        'pct_diff': _f(100 * (m - r['dk_points']) / r['dk_points'], 1)})
    dk_rows.sort(key=lambda x: -x['abs_diff'])
    comp = collections.defaultdict(list)
    for i, k in enumerate(meta['keys']):
        r = rows.get(k)
        if not r or (r.get('dk_points') or 0) < 5:
            continue
        for fld, src in (('pass_att', 'pass_attempts'), ('targets', 'targets'), ('carries', 'carries'),
                         ('receptions', 'receptions'), ('rec_yards', 'rec_yards'), ('rush_yards', 'rush_yards'),
                         ('pass_yards', 'pass_yards')):
            t = r.get(src)
            if not isinstance(t, (int, float)) or t <= 0.5:
                continue
            sv = stats[i, :, F[fld]].astype(float)
            if fld.endswith('yards'):
                sv = sv / ys
            comp[fld].append(float(sv.mean()) - t)
        td = (r.get('td') or {})
        tdp = (td.get('rec_td') or 0) + (td.get('rush_td') or 0)
        if tdp > 0.05:
            comp['rush_rec_td'].append(float((stats[i, :, F['rush_td']] + stats[i, :, F['rec_td']]).mean()) - tdp)
        if r['position'] == 'QB' and (td.get('pass_td') or 0) > 0.3:
            comp['pass_td'].append(float(stats[i, :, F['pass_td']].mean()) - td['pass_td'])
            comp['interceptions'].append(float(stats[i, :, F['interceptions']].mean()) - (r.get('pass_attempts') or 0) * proj['int_rate'])
    return {'dk_top20_positive': dk_rows[:20], 'dk_top20_negative': dk_rows[::-1][:20],
            'n_players': len(dk_rows),
            'component_residuals_sim_minus_projection': {k: {'n': len(v), 'mean': _f(np.mean(v), 3), 'mean_abs': _f(np.mean(np.abs(v)), 3),
                                                             'max_abs': _f(np.max(np.abs(v)), 3)} for k, v in comp.items()},
            'NOT_DRAWN': {'QB completions': 'not drawn separately; receptions are', 'K': 'no kickers on a Classic slate',
                          'DST sacks / turnovers / TDs': 'not decomposed; DST points are drawn from the opponent\'s score'}}


# ------------------------------------------------------------------------------------ distributions
def distributions(proj, draws_doc, stats, meta, book):
    from nfl.tools import classic_slate_run as R
    F = list(meta['fields'])
    ys = meta['yard_scale']
    fac = (draws_doc.get('player_mean_anchor') or {}).get('efficiency', {}).get('factors', {})
    kix = {k: i for i, k in enumerate(meta['keys'])}
    draws = draws_doc['draws']

    def before(k):
        a = stats[kix[k]].astype(float)
        f = fac.get(k) or {}
        out = []
        for w in a:
            pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd, _ints = w
            out.append(R.dk_from_stats(pa, pyd / ys / (f.get('pass_yards') or 1), ptd, car, ryd / ys / (f.get('rush_yards') or 1),
                                       rtd, tgt, rec, recyd / ys / (f.get('rec_yards') or 1), rectd, 0))
        return np.asarray(out)

    def q(v):
        return {'mean': _f(v.mean()), 'sd': _f(v.std()), **{f'p{p}': _f(np.percentile(v, p)) for p in (10, 25, 50, 75, 90, 95)}}
    reps = ['Joe Burrow|CIN', "Ja'Marr Chase|CIN", 'Zay Flowers|BAL', 'CeeDee Lamb|DAL', 'Tyson Bagent|CHI',
            'Kyren Williams|LA', 'Bucky Irving|TB', 'Mike Gesicki|CIN', 'Josh Allen|BUF', 'Derrick Henry|BAL']
    rep = {}
    for k in reps:
        if k in kix and k in draws:
            b, a = before(k), np.asarray(draws[k], dtype=float)
            rep[k] = {'before': q(b), 'after': q(a), 'corr_before_after': _f(np.corrcoef(b, a)[0, 1], 3),
                      'translated_copy': bool(abs(b.std() - a.std()) < 1e-9 and abs(np.corrcoef(b, a)[0, 1] - 1) < 1e-9)}
    cor = []
    for gid, g in book['games'].items():
        for club, t in g['teams'].items():
            q_ = (t.get('qb_ecosystem') or {}).get('quarterback')
            if not q_:
                continue
            qk = f'{q_}|{club}'
            tree = (t['qb_ecosystem'].get('target_tree') or [])[:2]
            opp = t['opponent']
            ot = g['teams'][opp]
            oq = (ot.get('qb_ecosystem') or {}).get('quarterback')
            rb = (t['rb_ecosystem']['backs'] or [{}])[0].get('name')
            row = {'team': club, 'qb': q_}
            for x in tree:
                k = f"{x['name']}|{club}"
                if qk in kix and k in kix:
                    row[f"qb_x_{x['name']}"] = {'before': _f(np.corrcoef(before(qk), before(k))[0, 1], 3),
                                                'after': _f(np.corrcoef(draws[qk], draws[k])[0, 1], 3)}
            if oq and qk in draws and f'{oq}|{opp}' in draws:
                row['qb_x_opposing_qb'] = _f(np.corrcoef(draws[qk], draws[f'{oq}|{opp}'])[0, 1], 3)
            gi = next(i for i, x in enumerate(meta['games']) if x['game_id'] == gid)
            pts = np.load(OUT_DIR / f"DK_{book['slate_id']}_EARLY_WORLDS.npz")['points'][gi]
            margin = (pts[:, 0] - pts[:, 1]) * (1 if club == meta['games'][gi]['home'] else -1)
            if rb and f'{rb}|{club}' in kix:
                car = stats[kix[f'{rb}|{club}'], :, F.index('carries')].astype(float)
                row['rb1_carries_x_own_margin'] = {'rb': rb, 'r': _f(np.corrcoef(car, margin)[0, 1], 3)}
            cor.append(row)
    return {'representative': rep, 'correlations': cor,
            'VARIANCE_NONZERO': all(v['after']['sd'] > 0 for v in rep.values()),
            'NOT_A_TRANSLATION': not any(v['translated_copy'] for v in rep.values())}


# ------------------------------------------------------------------------------------ portfolios
def portfolios(port, state, verify):
    by = {c['profile']: c for c in port['contests']}
    sets = {k: [frozenset(s['dk_id'] for s in lu['slots']) for lu in c['lineups']] for k, c in by.items()}
    out = {}
    for k, c in by.items():
        r = c['report']
        slot_expo = collections.defaultdict(dict)
        for nm, e in r['player_exposure'].items():
            for s_, v in e['by_slot'].items():
                slot_expo[s_][nm] = v
        ov = r['overlap_distribution']
        n_pairs = sum(ov.values()) or 1
        out[k] = {'contest': c['contest_name'], 'rows': len(c['lineups']), 'unique_entry_ids': len({lu['entry_id'] for lu in c['lineups']}),
                  'unique_lineups': len(set(sets[k])), 'violations': c['violations'], 'policy': c['policy'],
                  'exposure_by_slot': {s_: dict(sorted(v.items(), key=lambda t: -t[1])[:8]) for s_, v in slot_expo.items()},
                  'qb': r['qb_exposure'], 'dst': r['dst_exposure'], 'games': r['game_exposure'], 'stacks': r['stack_table'],
                  'bring_back': r['bring_back_table'], 'salary': r['salary_used'],
                  'overlap_mean': _f(sum(int(a) * b for a, b in ov.items()) / n_pairs, 2), 'overlap_max': max(int(a) for a in ov) if ov else None,
                  'max_player_exposure': max((e['overall'] for e in r['player_exposure'].values()), default=None)}
    s150, s20, s3 = sets.get('MAX150', []), sets.get('MAX20', []), sets.get('MAX3', [])
    sim150 = sorted(((lu['sim_mean'], frozenset(s['dk_id'] for s in lu['slots'])) for lu in by['MAX150']['lineups']), key=lambda t: -t[0])
    top20 = {x for _, x in sim150[:20]}
    first20 = set(s150[:20])
    out['independence'] = {
        '20max_in_150max': len(set(s20) & set(s150)), '20max_equals_first_20_of_150': set(s20) == first20,
        '20max_overlap_with_first_20_of_150': len(set(s20) & first20),
        '20max_equals_top_20_by_mean_of_150': set(s20) == top20, '20max_overlap_with_top_20_of_150': len(set(s20) & top20),
        '3entry_in_20max': len(set(s3) & set(s20)), '3entry_in_150max': len(set(s3) & set(s150)),
        'WHY_CONCENTRATION_DIFFERS': ('the 20-max and 3-entry use the CONVICTION pool (no FRINGE/ROTATIONAL, no Questionable) and '
                                      'looser caps (player 65%, QB 50%) because with few entries the objective is maximised by '
                                      'repeating the highest-upside cores; 150 entries buy coverage, so caps are 45%/35% and the '
                                      'pool is wider'),
        'WHY_3_IN_20': 'the 3-entry set draws from the same CONVICTION candidate pool as the 20-max (declared), so overlap is expected'}
    out['verifier'] = verify
    return out


def reproducibility():
    sd = OUT_DIR / 'sensitivity'
    a, b = sd / 'DK_2026W4_EARLY_UPLOAD.reproA.csv', sd / 'DK_2026W4_EARLY_UPLOAD.reproB.csv'
    prod = OUT_DIR / 'DK_2026W4_EARLY_UPLOAD.csv'
    if not (a.exists() and b.exists()):
        return {'state': 'NOT_RUN', 'why': 'the two tagged builds have not finished'}
    h = {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in (('A', a), ('B', b), ('production', prod))}
    pa = json.loads((sd / 'DK_2026W4_EARLY_PORTFOLIOS.reproA.json').read_text())
    pb = json.loads((sd / 'DK_2026W4_EARLY_PORTFOLIOS.reproB.json').read_text())
    cur = json.loads((OUT_DIR / 'DK_2026W4_EARLY_PORTFOLIOS.json').read_text()).get('inputs_sha256')
    if not (pa.get('inputs_sha256') == pb.get('inputs_sha256') == cur):
        # builds from older inputs say nothing about this run's reproducibility
        return {'state': 'STALE', 'why': 'the tagged builds were made from different inputs than production'}
    strip = lambda d: {k: v for k, v in d.items() if k not in ('built_at_utc', 'sensitivity', 'research_book_sha256')}  # noqa: E731
    same_doc = json.dumps(strip(pa), sort_keys=True) == json.dumps(strip(pb), sort_keys=True)
    return {'state': 'PASS' if h['A'] == h['B'] == h['production'] and same_doc else 'FAIL', 'upload_sha256': h,
            'portfolio_json_identical_except_timestamps': same_doc,
            'NOTE': 'two separate processes (different hash seeds), same inputs and seed'}


def role_dependent(port, state):
    sd = OUT_DIR / 'sensitivity'
    out = {}
    for tag, name in (('noBagent', 'Tyson Bagent'), ('noDaniels', 'Jalon Daniels')):
        dk = next((k for k, v in state['players'].items() if v['name'] == name), None)
        p = sd / f'DK_2026W4_EARLY_PORTFOLIOS.{tag}.json'
        sp = state['players'].get(dk) or {}
        cur = {c['profile']: next((e['overall'] for e in c['report']['player_exposure'].values() if e['dk_id'] == dk), 0.0)
               for c in port['contests']}
        row = {'player': name, 'dk_id': dk, 'current_exposure': cur,
               'starter_evidence': (sp.get('predicted_lineup_context') or {}).get('state'),
               'club_confirmation': 'NONE HELD', 'classification': 'ROLE_DEPENDENT'}
        alt = json.loads(p.read_text()) if p.exists() else None
        if alt is not None and alt.get('inputs_sha256') != port.get('inputs_sha256'):
            row['if_removed'] = 'STALE_AGAINST_CURRENT_INPUTS'
        elif alt is not None:
            turnover, qb_shift = {}, {}
            for c, a in zip(port['contests'], alt['contests']):
                s0 = {frozenset(s['dk_id'] for s in lu['slots']) for lu in c['lineups']}
                s1 = {frozenset(s['dk_id'] for s in lu['slots']) for lu in a['lineups']}
                turnover[c['profile']] = {'lineups_unchanged': len(s0 & s1), 'of': len(s0)}
                qb_shift[c['profile']] = dict(list(a['report']['qb_exposure'].items())[:5])
            row['if_removed'] = {'lineup_turnover': turnover, 'qb_exposure_without_him': qb_shift,
                                 'all_filled': all(c['FILLED'] for c in alt['contests'])}
        else:
            row['if_removed'] = 'NOT_RUN'
        out[name] = row
    return out


def stadiums(state):
    f = sorted(glob.glob(str(_REPO / 'nfl/vintage/schedules.*.csv.gz')), key=lambda p: pathlib.Path(p).stat().st_mtime)[-1]
    want = set(state['games'])
    out = {}
    with gzip.open(f, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r['game_id'] in want or r['game_id'].replace('_LA_', '_LA_') in want:
                out[r['game_id']] = {'stadium': r.get('stadium'), 'roof': r.get('roof') or 'NOT_DECLARED (retractable; set on game day)',
                                     'surface': r.get('surface'),
                                     'weather': 'NOT_CAPTURED: requested from the networked agent; CONTEXT_ONLY when it arrives'}
    return {'source': str(pathlib.Path(f).relative_to(_REPO)), 'games': out}


def build(slate):
    from nfl.tools import classic_slate_run as R
    st, pj, dr = _load(slate, 'STATE.json'), _load(slate, 'PROJ.json'), _load(slate, 'DRAWS.json')
    book, port, ver = _load(slate, 'RESEARCH_BOOK.json'), _load(slate, 'PORTFOLIOS.json'), _load(slate, 'UPLOAD_VERIFY.json')
    if not all((st, pj, dr, book, port)):
        return Outcome.blocked('AUDIT_INPUT_MISSING', 'state, projection, draws, research book and portfolios are all required',
                               cause=Cause.NOT_EXECUTED)
    stats, _pts, meta = R.load_worlds(_p(slate, 'WORLDS.npz'))
    struct, flags = structure(book, st)
    doc = {'ARTIFACT': 'CLASSIC_PRODUCTION_AUDIT', 'slate_id': slate,
           'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs_sha256': {n: hashlib.sha256(_p(slate, n).read_bytes()).hexdigest()
                             for n in ('STATE.json', 'PROJ.json', 'DRAWS.json', 'WORLDS.npz', 'RESEARCH_BOOK.json', 'PORTFOLIOS.json')},
           'structure': struct, 'contradictions': flags,
           'role_cards': role_cards(book, st), 'accounting': accounting(pj, st),
           'yards_closure': yards_closure(pj, stats, meta, book), 'simulator': simulator(pj, dr, stats, meta),
           'distributions': distributions(pj, dr, stats, meta, book),
           'portfolios': portfolios(port, st, ver), 'reproducibility': reproducibility(),
           'role_dependent': role_dependent(port, st), 'stadiums': stadiums(st)}
    _p(slate, 'AUDIT.json').write_text(json.dumps(doc, indent=1, default=str))
    hard = [f for f in flags if f['kind'] in ('INACTIVE_WITH_VOLUME', 'TEAM_MISMATCH')]
    if doc['accounting']['state'] != 'PASS' or hard:
        return Outcome.fail('AUDIT_FOUND_PUBLICATION_BLOCKERS', f"accounting {doc['accounting']['state']}; {len(hard)} hard contradiction(s)",
                            hard=hard)
    return Outcome.measured('AUDIT_COMPLETE', {'n_flags': len(flags)}, n_measured=len(flags), what='contradictions flagged',
                            detail=f"accounting PASS; {len(flags)} flag(s); yards-blocked teams {doc['yards_closure']['blocked_teams']}; "
                                   f"reproducibility {doc['reproducibility']['state']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    o = build(ap.parse_args().slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
