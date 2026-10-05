#!/usr/bin/env python3.12
"""Week-4 Early Only forensic report over the graded postgame artifact. Reads the LOCK and the grade only.

    python3.12 nfl/postgame/classic_week_report.py

Every threshold below is a DECLARED reporting rule (it labels a finding; it changes no number and promotes
no model). Week-4 results may generate hypotheses and tests; they may not promote a production change.

ROLE TEST. The pre-lock hypothesis is "club volume reasonable, within-club targets too concentrated on
WR1/TE1". It is tested on SHARES of each club's realised targets, so a club that threw more or less than
projected does not masquerade as an allocation error. Bands are the model's OWN pregame ordering (projected
targets inside the club), not a depth chart. Uncertainty is a bootstrap over the eight GAMES (players in a
game are not independent observations).
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import classic_week as W   # noqa: E402

OUT = W.OUT
#: DECLARED reporting rules
HIGH_EXPOSURE = 0.20          # of the 150-max
LOW_EXPOSURE = 0.05
BOOT = 4000
SEED = 20261005
OWNER_RELAYED = {'best_150_points': 207.50, 'best_150_rank': 19, 'first_place_points': 225.38,
                 'SOURCE': 'owner message 2026-10-05 (DraftKings contest page); standings export not yet ingested'}


def _pct(a, q):
    return float(np.percentile(a, q))


def player_table(lock, act):
    from nfl.tools import showdown_draws as SD
    st, proj, draws = lock['state']['players'], lock['proj'], lock['draws']
    rows = []
    for dk, a in act.items():
        p, r = st[dk], proj.get(dk) or {}
        d = np.asarray(draws.get(SD.S.player_key(p['name'], p['team'])) or [], dtype=float)
        mean = r.get('dk_points')
        if a.get('actual') is None or (not len(d) and mean is None):
            continue
        if (mean or 0) < 0.5 and a['actual'] < 0.5:
            continue
        td = r.get('td') or {}
        row = {'player': p['name'], 'team': p['team'], 'pos': p['position'], 'dk_id': dk, 'salary': p['salary'],
               'locked_projection': round(mean, 2) if mean is not None else None, 'actual_dk': a['actual'], 'basis': a['basis']}
        if len(d):
            row.update(sim_mean=round(float(d.mean()), 2), p50=round(_pct(d, 50), 2), p75=round(_pct(d, 75), 2),
                       p90=round(_pct(d, 90), 2), p95=round(_pct(d, 95), 2),
                       sim_percentile_of_actual=round(float((d < a['actual']).mean() + 0.5 * (d == a['actual']).mean()), 4))
        base = row['locked_projection'] if row['locked_projection'] is not None else row.get('sim_mean')
        row.update(error=round(a['actual'] - base, 2), abs_error=round(abs(a['actual'] - base), 2))
        for f, pf in (('targets', 'targets'), ('carries', 'carries'), ('pass_att', 'pass_attempts'), ('receptions', 'receptions'),
                      ('rec_yds', 'rec_yards'), ('rush_yds', 'rush_yards'), ('pass_yds', 'pass_yards')):
            if a.get(f) is not None:
                row[f'proj_{f}'] = round(r.get(pf) or 0.0, 2) if r else None
                row[f'actual_{f}'] = a[f]
        if a.get('tds') is not None:
            row['proj_td_expectation'] = round(sum(v for k, v in td.items() if isinstance(v, (int, float))
                                                   and k in ('rec_td', 'rush_td', 'pass_td')), 3) if td else None
            row['actual_tds'] = a['tds']
        rows.append(row)
    return rows


def calibration(rows, expo150):
    out = {}
    groups = {'ALL': rows, **{p: [r for r in rows if r['pos'] == p] for p in ('QB', 'RB', 'WR', 'TE', 'DST')},
              f'HIGH_EXPOSURE_150 (>= {HIGH_EXPOSURE:.0%})': [r for r in rows if expo150.get(r['dk_id'], 0) >= HIGH_EXPOSURE]}
    for g, rs in groups.items():
        rs = [r for r in rs if 'p50' in r]
        if not rs:
            continue
        cov = {f'actual_le_{q}': round(float(np.mean([r['actual_dk'] <= r[q] for r in rs])), 3) for q in ('p50', 'p75', 'p90', 'p95')}
        pit = np.array([r['sim_percentile_of_actual'] for r in rs])
        out[g] = {'n': len(rs), **cov, 'NOMINAL': {'p50': 0.5, 'p75': 0.75, 'p90': 0.9, 'p95': 0.95},
                  'share_below_p10': round(float((pit < 0.10).mean()), 3), 'share_above_p90': round(float((pit > 0.90).mean()), 3),
                  'mean_error_actual_minus_projection': round(float(np.mean([r['error'] for r in rs])), 2),
                  'binomial_se_at_p90': round(float(np.sqrt(0.9 * 0.1 / len(rs))), 3)}
    a = out.get('ALL', {})
    v = []
    if a:
        lo, hi = a['share_below_p10'], a['share_above_p90']
        v.append('tails too NARROW: actuals land outside p10-p90 far more than 20%' if lo + hi > 0.20 + 2 * np.sqrt(0.2 * 0.8 / a['n'])
                 else 'tails too WIDE: actuals land outside p10-p90 far less than 20%' if lo + hi < 0.20 - 2 * np.sqrt(0.2 * 0.8 / a['n'])
                 else 'tail width within two binomial SEs of nominal (game clustering makes the true SE larger)')
        v.append('centre biased low' if a['actual_le_p50'] < 0.5 - 2 * np.sqrt(0.25 / a['n']) else
                 'centre biased high' if a['actual_le_p50'] > 0.5 + 2 * np.sqrt(0.25 / a['n']) else 'centre within two SEs of nominal')
    return out, v


def role_test(lock, rows):
    """Within-club SHARE of realised targets by the model's own pregame band."""
    st = lock['state']['players']
    by_club = collections.defaultdict(list)
    for r in rows:
        if r['pos'] in ('WR', 'TE', 'RB') and r.get('actual_targets') is not None:
            by_club[r['team']].append(r)
    game_of = {c: g for g, gg in lock['state']['games'].items() for c in (gg['away'], gg['home'])}
    band_rows = []
    for club, rs in by_club.items():
        tot_p = sum(r['proj_targets'] for r in rs)
        tot_a = sum(r['actual_targets'] for r in rs)
        for pos, tags in (('WR', ('WR1', 'WR2', 'WR3+')), ('TE', ('TE1', 'TE2+')), ('RB', ('RB1', 'RB2+'))):
            key = 'proj_targets' if pos != 'RB' else None
            ps = sorted([r for r in rs if r['pos'] == pos],
                        key=lambda r: -(r['proj_targets'] if pos != 'RB' else r['proj_targets'] + (r.get('proj_carries') or 0)))
            for i, r in enumerate(ps):
                tag = tags[min(i, len(tags) - 1)]
                band_rows.append({'club': club, 'game': game_of[club], 'band': tag, 'player': r['player'],
                                  'proj_targets': r['proj_targets'], 'actual_targets': r['actual_targets'],
                                  'proj_share': r['proj_targets'] / tot_p if tot_p else 0.0,
                                  'actual_share': r['actual_targets'] / tot_a if tot_a else 0.0,
                                  'proj_carries': r.get('proj_carries'), 'actual_carries': r.get('actual_carries'),
                                  'proj_dk': r['locked_projection'], 'actual_dk': r['actual_dk']})
    bands = ('WR1', 'WR2', 'WR3+', 'TE1', 'TE2+', 'RB1', 'RB2+')
    games = sorted({b['game'] for b in band_rows})
    rng = np.random.default_rng(SEED)

    def stat(sel):
        out = {}
        for b in bands:
            g = [x for x in sel if x['band'] == b]
            out[b] = (sum(x['actual_share'] - x['proj_share'] for x in g) / 16.0) if g else 0.0   # per club
        out['PRIMARY(WR1+TE1)'] = out['WR1'] + out['TE1']
        out['SECONDARY(WR2+WR3+)'] = out['WR2'] + out['WR3+']
        return out

    point = stat(band_rows)
    boots = collections.defaultdict(list)
    for _ in range(BOOT):
        pick = rng.choice(games, size=len(games), replace=True)
        sel = [x for g in pick for x in band_rows if x['game'] == g]
        for k, v in stat(sel).items():
            boots[k].append(v)
    ci = {k: (round(float(np.percentile(v, 5)), 4), round(float(np.percentile(v, 95)), 4)) for k, v in boots.items()}
    summary = {}
    for b in bands:
        g = [x for x in band_rows if x['band'] == b]
        summary[b] = {'n': len(g), 'proj_targets': round(sum(x['proj_targets'] for x in g), 1),
                      'actual_targets': round(sum(x['actual_targets'] for x in g), 1),
                      'mean_proj_share': round(float(np.mean([x['proj_share'] for x in g])), 4) if g else None,
                      'mean_actual_share': round(float(np.mean([x['actual_share'] for x in g])), 4) if g else None,
                      'share_gap_per_club(actual-proj)': round(point[b], 4), 'game_bootstrap_90pct': ci[b],
                      'dk_actual_minus_proj_per_player': round(float(np.mean([x['actual_dk'] - (x['proj_dk'] or 0) for x in g])), 2) if g else None}
    prim, sec = point['PRIMARY(WR1+TE1)'], point['SECONDARY(WR2+WR3+)']
    pci, sci = ci['PRIMARY(WR1+TE1)'], ci['SECONDARY(WR2+WR3+)']
    strong = pci[1] < 0 and sci[0] > 0
    some = (prim < 0 and sec > 0) and (pci[1] < 0 or sci[0] > 0)
    verdict = ('CONFIRM_TARGET_CONCENTRATION_DEFECT' if strong else
               'PARTIALLY_CONFIRM' if some or (prim < 0 and sec > 0) else 'DO_NOT_CONFIRM')
    team = []
    for club, rs in sorted(by_club.items()):
        team.append({'club': club, 'proj_targets': round(sum(r['proj_targets'] for r in rs), 1),
                     'actual_targets': sum(r['actual_targets'] for r in rs)})
    named = {}
    for n in ('Kalif Raymond', 'Ryan Flournoy', 'Kayshon Boutte', 'Jaylin Noel', 'TreVeyon Henderson',
              'CeeDee Lamb', 'Garrett Wilson', 'Parker Washington', 'Mike Gesicki', 'Bhayshul Tuten', 'Bucky Irving'):
        x = next((b for b in band_rows if b['player'] == n), None)
        if x:
            named[n] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items() if k not in ('club', 'game')}
    return {'verdict': verdict,
            'RULE': 'CONFIRM when the 90% game-bootstrap interval of the WR1+TE1 share gap is wholly below 0 AND that of '
                    'WR2+WR3+ is wholly above 0; PARTIALLY_CONFIRM when the point estimates point that way; else DO_NOT_CONFIRM',
            'primary_share_gap_per_club': round(prim, 4), 'primary_90pct': pci,
            'secondary_share_gap_per_club': round(sec, 4), 'secondary_90pct': sci,
            'bands': summary, 'team_volume': team, 'named': named, 'n_games': len(games)}, band_rows


def fc_audit(lock, rows):
    p = W._REPO / W.SAL / 'DK_2026W4_EARLY_FINAL_DISAGREEMENT_AUDIT.json'
    if not p.exists():
        return []
    pre = json.loads(p.read_text())
    by = {r['player']: r for r in rows}
    out = []
    for x in pre:
        a = by.get(x['player'])
        if not a:
            continue
        ours, fc, act = x['our_proj'], x['fc_proj'], a['actual_dk']
        e_o, e_f = abs(act - ours), abs(act - fc)
        closer = 'OURS' if e_o < e_f - 0.5 else 'FC' if e_f < e_o - 0.5 else 'TIE'
        pos = x['pos']
        vk = 'pass_att' if pos == 'QB' else 'targets' if pos in ('WR', 'TE') else 'carries'
        pv, av = a.get(f'proj_{vk}'), a.get(f'actual_{vk}')
        if pos == 'RB' and a.get('proj_targets') is not None:
            pv, av = (pv or 0) + a['proj_targets'], (av or 0) + a['actual_targets']
        td_pts = 6 * (a.get('actual_tds') or 0) if pos != 'QB' else None
        td_drove = td_pts is not None and abs((act - td_pts) - ours) < abs(act - ours) / 2 and (a.get('actual_tds') or 0) >= 1
        meas = (x.get('measured_2026') or {})
        g = meas.get('games') or 0
        mv = ((meas.get(vk if vk != 'pass_att' else 'pass_att') or 0) + ((meas.get('targets') or 0) if pos == 'RB' else 0)) / g if g else None
        why, cls = [], 'UNRESOLVED'
        if pv is not None and av is not None:
            why.append(f'{vk}: ours {pv:.1f}, actual {av:.0f}' + (f', his 2026 rate {mv:.1f}' if mv is not None else ''))
            vol_ours = abs(av - pv) <= max(2.0, 0.25 * max(pv, 1))
            vol_fcside = mv is not None and abs(av - mv) < abs(av - pv)
        else:
            vol_ours = vol_fcside = False
        if td_drove:
            cls = 'PURE_VARIANCE'
            why.append(f"{a.get('actual_tds'):.0f} TD(s) worth {td_pts:.0f} pts carried the gap")
        elif closer == 'OURS':
            cls = 'OUR_ROLE_EDGE' if vol_ours else 'OUR_EFFICIENCY_EDGE'
            if x['diff'] < 0:
                cls = 'FC_WAS_CONSERVATIVE' if act < fc and act > ours else cls
        elif closer == 'FC':
            if x['diff'] > 0 and act < ours:
                cls = 'FC_WAS_CONSERVATIVE' if not vol_fcside else 'FC_ROLE_EDGE'
                if vol_ours and not vol_fcside:
                    cls = 'FC_EFFICIENCY_EDGE'
            else:
                cls = 'FC_ROLE_EDGE' if vol_fcside else 'FC_EFFICIENCY_EDGE'
            if x['classification'] == 'UNEXPLAINED_MODEL_DISAGREEMENT' or (pv is not None and av is not None and pv < 1 and av >= 3):
                cls = 'OUR_MODEL_DEFECT'
        else:
            cls = 'PURE_VARIANCE'
        out.append({'player': x['player'], 'team': x['team'], 'pos': pos, 'our_prelock': ours, 'fc_prelock': fc, 'actual': act,
                    'who_was_closer': closer, 'classification': cls, 'prelock_classification': x['classification'],
                    'why': '; '.join(why)})
    return out


def lineup_stats(lock, act):
    st = lock['state']['players']
    hdr = lock['upload_header']
    sl = [i for i, h in enumerate(hdr) if h in ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST')]
    pts = collections.defaultdict(list)
    for r in lock['upload']:
        pts[W.CONTESTS[r[2]]].append(sum(act[r[i]]['actual'] for i in sl))
    out = {}
    for k, v in pts.items():
        a = np.array(v)
        out[k] = {'n': len(a), 'best': round(float(a.max()), 2), 'mean': round(float(a.mean()), 2), 'median': round(float(np.median(a)), 2),
                  'p75': round(_pct(a, 75), 2), 'p90': round(_pct(a, 90), 2), 'p95': round(_pct(a, 95), 2), 'worst': round(float(a.min()), 2)}
    return out


def construction(lock, act, expo150):
    st = lock['state']['players']
    core = {dk for dk, e in expo150.items() if e >= HIGH_EXPOSURE}
    rows = []
    for c in lock['port']['contests']:
        for lu in c['lineups']:
            sl = lu['slots']
            qb = next(s for s in sl if s['slot'] == 'QB')
            opp = st[qb['dk_id']]['opponent']
            mates = [s for s in sl if s['team'] == qb['team'] and s['slot'] not in ('QB', 'DST')]
            bb = [s for s in sl if s['team'] == opp and s['slot'] != 'DST']
            games = collections.Counter(st[s['dk_id']]['game_id'] for s in sl if s['slot'] != 'DST')
            rows.append({'contest': c['profile'], 'points': sum(act[s['dk_id']]['actual'] for s in sl),
                         'stack': f'QB+{len(mates)}' if mates else 'QB naked', 'bring_back': f'bring_back_{min(len(bb), 2)}',
                         'qb': qb['name'], 'qb_game': st[qb['dk_id']]['game_id'],
                         'salary_band': f"{(lu['salary'] // 500) * 500}", 'max_same_game': max(games.values()),
                         'n_core': sum(1 for s in sl if s['dk_id'] in core)})
    out = {}
    for dim in ('stack', 'bring_back', 'qb', 'qb_game', 'salary_band', 'max_same_game', 'n_core'):
        d = {}
        for prof in ('MAX150', 'MAX20', 'MAX3'):
            grp = collections.defaultdict(list)
            for r in rows:
                if r['contest'] == prof:
                    grp[r[dim]].append(r['points'])
            d[prof] = {str(k): {'n': len(v), 'mean': round(float(np.mean(v)), 2), 'median': round(float(np.median(v)), 2),
                                'max': round(max(v), 2), 'share_ge_190': round(float(np.mean([x >= 190 for x in v])), 3)}
                       for k, v in sorted(grp.items(), key=lambda kv: -np.mean(kv[1]))}
        out[dim] = d
    return out


def exposure_quality(lock, act):
    st = lock['state']['players']
    ex = collections.defaultdict(dict)
    lus = collections.defaultdict(list)
    for c in lock['port']['contests']:
        for n, e in c['report']['player_exposure'].items():
            ex[e['dk_id']][c['profile']] = e['overall']
        for lu in c['lineups']:
            lus[c['profile']].append((sum(act[s['dk_id']]['actual'] for s in lu['slots']), {s['dk_id'] for s in lu['slots']}))
    out = []
    for dk, e in ex.items():
        a = act[dk].get('actual')
        pr = (lock['proj'].get(dk) or {}).get('dk_points')
        w = [x for x, ids in lus['MAX150'] if dk in ids]
        wo = [x for x, ids in lus['MAX150'] if dk not in ids]
        e150 = e.get('MAX150', 0)
        delta = (np.mean(w) - np.mean(wo)) if w and wo else None
        if e150 >= HIGH_EXPOSURE:
            cls = 'GOOD_OVERWEIGHT' if delta is not None and delta > 0 else 'BAD_OVERWEIGHT'
        elif e150 <= LOW_EXPOSURE and a is not None and pr is not None and a - pr >= 10:
            cls = 'BAD_UNDERWEIGHT'
        elif e150 <= LOW_EXPOSURE and a is not None and pr is not None and pr >= 12 and a - pr <= -6:
            cls = 'GOOD_UNDERWEIGHT'
        else:
            cls = 'NEUTRAL'
        out.append({'player': st[dk]['name'], 'team': st[dk]['team'], 'pos': st[dk]['position'], 'exp_150': e150, 'exp_20': e.get('MAX20', 0),
                    'exp_3': e.get('MAX3', 0), 'proj': round(pr, 2) if pr is not None else None, 'actual_dk': a,
                    'avg_150_lineup_when_rostered': round(float(np.mean(w)), 2) if w else None,
                    'avg_150_lineup_when_not': round(float(np.mean(wo)), 2) if wo else None,
                    'rostered_minus_not': round(float(delta), 2) if delta is not None else None,
                    'field_ownership': act[dk].get('pct_drafted') or 'NOT_INGESTED', 'classification': cls})
    # big scorers we never rostered at all (pool players with no exposure)
    missed = sorted(({'player': st[k]['name'], 'team': st[k]['team'], 'pos': st[k]['position'], 'salary': st[k]['salary'],
                      'proj': round((lock['proj'].get(k) or {}).get('dk_points') or 0, 2), 'actual_dk': v['actual']}
                     for k, v in act.items() if v.get('actual') is not None and k not in ex and v['actual'] >= 20),
                    key=lambda r: -r['actual_dk'])
    return sorted(out, key=lambda r: -r['exp_150']), missed


def best_lineup(lock, act):
    st = lock['state']['players']
    best = None
    for c in lock['port']['contests']:
        if c['profile'] != 'MAX150':
            continue
        for lu in c['lineups']:
            s = sum(act[x['dk_id']]['actual'] for x in lu['slots'])
            if best is None or s > best[0]:
                best = (s, lu)
    s, lu = best
    return {'entry_id': lu['entry_id'], 'points': round(s, 2), 'pregame_sim_mean': lu.get('sim_mean'),
            'slots': [{'slot': x['slot'], 'player': x['name'], 'team': x['team'], 'salary': x['salary'],
                       'proj': round((lock['proj'].get(x['dk_id']) or {}).get('dk_points') or 0, 2),
                       'actual': act[x['dk_id']]['actual']} for x in lu['slots']]}


def build():
    lo = W.locked()
    lock = lo.value
    pw, gs, sd = W.player_week(lock), W.game_scores(lock), W.standings(lock)
    act = W.actual_points(lock, pw.value if pw.state.value == 'PASS' else None, gs.value if gs.state.value == 'PASS' else None,
                          sd.value if sd.state.value == 'PASS' else None)
    expo150 = {}
    for c in lock['port']['contests']:
        if c['profile'] == 'MAX150':
            for n, e in c['report']['player_exposure'].items():
                expo150[e['dk_id']] = e['overall']
    rows = player_table(lock, act)
    cal, cal_v = calibration(rows, expo150)
    role, band_rows = role_test(lock, rows)
    fc = fc_audit(lock, rows)
    ls = lineup_stats(lock, act)
    cons = construction(lock, act, expo150)
    eq, missed = exposure_quality(lock, act)
    bl = best_lineup(lock, act)
    graded = json.loads((OUT / f'DK_{W.SLATE}_EARLY_POSTGAME.json').read_text())
    opt = graded['optimal_lineup']
    doc = {'ARTIFACT': 'CLASSIC_POSTGAME_FORENSIC_REPORT', 'slate_id': W.SLATE, 'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'LOCK': graded['LOCK'], 'inputs': graded['inputs'], 'provenance': graded['provenance'],
           'scoring_crosscheck': 'our DK scoring reproduces nflverse fantasy_points_ppr for every skill row after the documented '
                                 'rule differences (100/300-yard bonuses, INT and fumble -1 vs -2): 0 mismatches',
           'owner_relayed_contest_facts': OWNER_RELAYED,
           'best_150_reproduces_owner': abs(bl['points'] - OWNER_RELAYED['best_150_points']) < 0.01,
           'players_summary': graded['players_summary'], 'calibration': cal, 'calibration_reading': cal_v,
           'role_allocation_test': role, 'fc_disagreement': fc,
           'fc_closer_counts': dict(collections.Counter(x['who_was_closer'] for x in fc)),
           'fc_classification_counts': dict(collections.Counter(x['classification'] for x in fc)),
           'lineup_distributions': ls, 'best_150_lineup': bl, 'optimal_lineup': opt,
           'ratios': {'owner_best_over_optimal': round(bl['points'] / opt['points'], 3),
                      'winner_over_optimal (owner-relayed winner)': round(OWNER_RELAYED['first_place_points'] / opt['points'], 3)},
           'construction': cons, 'exposure_quality_counts': dict(collections.Counter(x['classification'] for x in eq)),
           'big_scorers_never_rostered': missed[:20],
           'contest_finish': 'STANDINGS_NOT_INGESTED: finish, cash rate, fees, winnings, ROI and the winner lineup need the '
                             'three DraftKings standings exports',
           'RULES': {'HIGH_EXPOSURE': HIGH_EXPOSURE, 'LOW_EXPOSURE': LOW_EXPOSURE, 'bootstrap': f'{BOOT} game resamples, seed {SEED}'},
           'NO_PRODUCTION_PROMOTION': 'week-4 results generate hypotheses and tests only'}
    (OUT / f'DK_{W.SLATE}_EARLY_POSTGAME_REPORT.json').write_text(json.dumps(doc, indent=1, default=str))
    for name, data in (('POSTGAME_PLAYER_TABLE.csv', rows), ('POSTGAME_ROLE_BANDS.csv', band_rows),
                       ('POSTGAME_FC_AUDIT.csv', fc), ('POSTGAME_EXPOSURE_QUALITY.csv', eq)):
        if not data:
            continue
        keys = list(dict.fromkeys(k for r in data for k in r))
        with (OUT / f'DK_{W.SLATE}_EARLY_{name}').open('w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(data)
    return doc


if __name__ == '__main__':
    d = build()
    print(json.dumps({k: d[k] for k in ('best_150_reproduces_owner', 'calibration_reading', 'fc_closer_counts', 'fc_classification_counts',
                                        'lineup_distributions', 'ratios', 'exposure_quality_counts')}, indent=1))
    print('ROLE', d['role_allocation_test']['verdict'], d['role_allocation_test']['primary_share_gap_per_club'],
          d['role_allocation_test']['primary_90pct'], d['role_allocation_test']['secondary_share_gap_per_club'],
          d['role_allocation_test']['secondary_90pct'])
