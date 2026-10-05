#!/usr/bin/env python3.12
"""Showdown tournament portfolio from one game's joint worlds: boards, candidates, portfolios, upload.

    python3.12 nfl/tools/showdown_portfolio.py EXPORT DRAWS --out-dir DIR --prefix SHOWDOWN_ATL_NO
        [--inactives JSON] [--state STATE] [--proj PROJ] [--worlds NPZ]

ONE DISTRIBUTION PER PERSON. Every player has one vector of DK points over the shared worlds
(nfl/tools/showdown_slate_run.py). A captain scores 1.5x his own FLEX score IN THE SAME WORLD and costs
1.5x his FLEX salary (DK's CPT item). Nothing is drawn twice and no projection is multiplied by 1.5.

CANDIDATES (all lawful by construction -- they come from the exact solver, never from a repair):
  1. optimal_worlds.solve per world, plus the captain-exclusion and flex-core-drop rounds of
     showdown_to_portfolio.near_optimal_candidates (the existing audited generator);
  2. a FORCED-CAPTAIN pass: for every rosterable person -- QB, RB, WR, TE, K and DST alike -- the exact
     per-world optimum with that person as captain, so every captain archetype is in the pool on its
     own merits rather than only where it happened to be the unconstrained optimum.

THE FIRST-PLACE PROXY, declared. There is no field model and no ownership here (OWNERSHIP_STATE
UNAVAILABLE), so "would this lineup win" is approximated by "is it within the declared near-optimal
band of the world's exact optimum": score_w >= (1 - NEAR_OPTIMAL_LOSS_BAND) * optimum_w, the same
0.10 band the candidate generator already declares. It is a proxy for first place, not a probability
of winning, and every artifact says so.

PORTFOLIO OBJECTIVE, per contest, built independently: greedily add the candidate that most increases
the share of worlds in which AT LEAST ONE entry reaches the proxy (top-tail coverage), under the
declared caps of showdown_to_portfolio (player 50%, captain 30%, overlap <= 4 of 6). Coverage rewards
lineups that win in DIFFERENT worlds, which is where script diversification, captain leverage and
correlation enter -- through the worlds, not through bonuses. Ties break on the lineup's own proxy rate,
then on lower structural duplication. Ownership enters nowhere.

STRUCTURAL DUPLICATION, without invented ownership: salary left on the table (a $50,000 lineup built
from the obvious pieces is the most-duplicated shape), whether the captain is the top-mean captain,
how many of the six are the six highest-mean players, the QB double-stack, and the 5-1 split.

Fits nothing, fetches nothing, never reads FantasyCruncher or a sportsbook price. Never submits.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402
from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from nfl.dfs.showdown import optimal_worlds as OW  # noqa: E402

BAND = S.NEAR_OPTIMAL_LOSS_BAND
CAP = S.SALARY_CAP
SALARY_BANDS = (('50000', 50000, 50000), ('49500-49900', 49500, 49900), ('49000-49400', 49000, 49400),
                ('48000-48900', 48000, 48900), ('<48000', 0, 47900))
#: Per-captain forced solves keep at most this many distinct lineups, the most often world-optimal
#: first. A pool-size limit, not a model parameter: it bounds memory, and the cut is reported.
MAX_PER_FORCED_CAPTAIN = 120
TEAM_ORDER = ('AWAY', 'HOME')     # set by run() from the slate
POS_ORDER = {'QB': 0, 'RB': 1, 'WR': 2, 'TE': 3, 'K': 4, 'DST': 5}


def _pct(a, q):
    return float(np.percentile(a, q))


def load(export, draws_path, inactives=None):
    ing = S.s1_ingest(pathlib.Path(export))
    if ing.state.value != 'PASS':
        return ing
    sl = S.s2_slate_identity(ing.value['pool'])
    if sl.state.value != 'PASS':
        return sl
    slate = sl.value
    # An inactive list names players DK does not price (practice-squad, linemen). Those are recorded,
    # not dropped silently; only names on this slate go to the availability stage, which itself
    # refuses any that match nobody.
    names = {v['name'] for v in slate['players'].values()} | set(slate['players'])
    off_pool = sorted(n for n in (inactives or ()) if n not in names)
    if inactives is not None:
        inactives = [n for n in inactives if n in names]
    av = S.s3_availability(slate, official_inactives=inactives)
    absent = set((av.value or {}).get('absent') or []) if av.state.value == 'PASS' else set()
    if av.state.value not in ('PASS', 'DEFERRED'):
        return av
    doc = json.loads(pathlib.Path(draws_path).read_text())
    draws = doc.get('draws', doc)
    return Outcome.ok('LOADED', {'entries': ing.value['entries'], 'slate': slate, 'absent': absent,
                                 'draws_doc': doc, 'draws': draws, 'availability': av,
                                 'inactives_not_in_priced_pool': off_pool})


def players_table(slate, absent, draws):
    rows = []
    for k, v in slate['players'].items():
        d = draws.get(k)
        rows.append({'key': k, 'name': v.get('name') or k.split('|')[0], 'team': v['dk_team'],
                     'pos': v['position'], 'salary': v['flex']['salary'], 'cpt_salary': v['cpt']['salary'],
                     'flex_id': v['flex']['dk_id'], 'cpt_id': v['cpt']['dk_id'],
                     'absent': k in absent, 'has_draws': d is not None,
                     'draws': None if d is None else np.asarray(d, dtype=float)})
    return rows


def classify(r, proj_row=None):
    """Every DK row ends in exactly one state; nobody silently disappears."""
    if r['absent']:
        return 'INACTIVE'
    if not r['has_draws']:
        return 'BLOCKED'
    m = float(r['draws'].mean())
    if m < 0.05 and r['pos'] not in ('DST', 'K'):
        return 'ZERO_OPPORTUNITY'
    # Uncertainty is a team designation, not the pre-inactives default: before the official lists every
    # player is UNKNOWN_ACTIVE_STATE, which the `availability` column carries separately.
    if (proj_row or {}).get('designation') in ('QUESTIONABLE', 'DOUBTFUL'):
        return 'PROJECTED_WITH_UNCERTAINTY'
    return 'PROJECTED'


def solver_players(rows, forbid_captain=(), only_captain=None):
    out = []
    for r in rows:
        if r['absent'] or not r['has_draws']:
            continue
        cpt = r['cpt_salary']
        if (only_captain is not None and r['key'] != only_captain) or r['key'] in forbid_captain:
            cpt = CAP + 1000
        out.append({'name': r['key'], 'team': r['team'], 'pos': r['pos'], 'tag': S.TAG_NOT_CLAIMED,
                    'salary': r['salary'], 'cpt_salary': cpt, 'draws': r['draws']})
    return out


def world_optimum(rows):
    o = OW.solve(solver_players(rows), cap=CAP, n_flex=S.N_FLEX, require_team_coverage=True)
    if o.state.value != 'PASS':
        return o
    nm = o.value['names']
    by = {r['key']: r for r in rows}
    opt, cpt_freq, lineups = [], collections.Counter(), collections.Counter()
    for w, ln in enumerate(o.value['lineups']):
        if ln is None:
            return Outcome.fail('SHOWDOWN_WORLD_WITHOUT_LAWFUL_LINEUP', f'world {w} has no lawful lineup')
        c, f = ln
        ck, fk = nm[c], tuple(sorted(nm[i] for i in f))
        cpt_freq[ck] += 1
        lineups[(ck, fk)] += 1
        opt.append(1.5 * by[ck]['draws'][w] + sum(by[k]['draws'][w] for k in fk))
    return Outcome.ok('OPTIMUM', {'opt': np.asarray(opt), 'cpt_freq': cpt_freq, 'lineups': lineups})


#: The forced-captain solve for a person runs on the worlds where HIS OWN score is in the top quarter,
#: which is where he could be a winning captain at all; the lineups found are then scored on every
#: world. A compute bound (one exact solve is ~36 s on 2,000 worlds), not a model parameter.
FORCED_CAPTAIN_WORLD_SHARE = 0.25
_FC_ROWS = None


def _fc_init(rows):
    global _FC_ROWS
    _FC_ROWS = rows


def _fc_one(key):
    import os
    import contextlib
    rows = _FC_ROWS
    me = next(r for r in rows if r['key'] == key)
    n = len(me['draws'])
    k = max(50, int(FORCED_CAPTAIN_WORLD_SHARE * n))
    idx = np.argsort(-me['draws'], kind='stable')[:k]
    sub = [dict(r, draws=r['draws'][idx]) for r in rows if r['has_draws']]
    sp = solver_players(sub, only_captain=key)
    with open(os.devnull, 'w') as dn, contextlib.redirect_stdout(dn):
        o = OW.solve(sp, cap=CAP, n_flex=S.N_FLEX, require_team_coverage=True)
    if o.state.value != 'PASS':
        return key, o.code, []
    nm = o.value['names']
    cnt = collections.Counter()
    for ln in o.value['lineups']:
        if ln is None:
            continue
        c, f = ln
        if nm[c] == key:
            cnt[(nm[c], tuple(sorted(nm[i] for i in f)))] += 1
    kept = cnt.most_common(MAX_PER_FORCED_CAPTAIN)
    return key, {'worlds_solved': k, 'distinct': len(cnt), 'kept': len(kept)}, kept


def forced_captain_candidates(rows):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing as mp
    keys = [r['key'] for r in rows if not r['absent'] and r['has_draws']]
    pool, acct = {}, {}
    with ProcessPoolExecutor(max_workers=max(1, (mp.cpu_count() or 2)), mp_context=mp.get_context('fork'),
                             initializer=_fc_init, initargs=(rows,)) as ex:
        for key, info, kept in ex.map(_fc_one, keys):
            acct[key] = info
            for k, n in kept:
                pool[k] = max(pool.get(k, 0), n)
    return pool, acct


def score_matrix(cands, by):
    M = np.zeros((len(cands), len(next(iter(by.values()))['draws'])))
    for i, (c, f) in enumerate(cands):
        M[i] = 1.5 * by[c]['draws'] + sum(by[k]['draws'] for k in f)
    return M


def structural(c, f, by, top_mean_captain, top6):
    seats = [c] + list(f)
    teams = collections.Counter(by[k]['team'] for k in seats)
    sal = by[c]['cpt_salary'] + sum(by[k]['salary'] for k in f)
    qbs = [k for k in seats if by[k]['pos'] == 'QB']
    qb_double = False
    for q in qbs:
        mates = [k for k in seats if k != q and by[k]['team'] == by[q]['team'] and by[k]['pos'] in ('WR', 'TE', 'RB')]
        qb_double = qb_double or len(mates) >= 2
    away, home = TEAM_ORDER
    split = f"{teams.get(away, 0)}-{teams.get(home, 0)}"     # away-home, e.g. ATL-NO 4-2
    n_top6 = len(set(seats) & top6)
    dup = (int(sal == CAP) + int(c == top_mean_captain) + max(0, n_top6 - 3) + int(qb_double) + int(max(teams.values()) == 5))
    return {'salary': sal, 'split': split, 'teams': dict(teams), 'qb_double_stack': qb_double,
            'n_of_top6_mean': n_top6, 'captain_is_top_mean': c == top_mean_captain,
            'salary_band': next(b for b, lo, hi in SALARY_BANDS if lo <= sal <= hi),
            'structural_duplication_index': dup}


def scripts(doc, by, home, away):
    """World labels for the game-script board, read from the same worlds the players were drawn in."""
    wp = (doc.get('world_points') or {}).get('points')
    if not wp:
        return {}
    P = np.asarray(wp)
    hp, ap = P[:, 0], P[:, 1]
    tot, mar = hp + ap, hp - ap
    lab = {
        f'{away} leads (wins)': ap > hp, f'{home} leads (wins)': hp > ap,
        'shootout (total >= sim p75)': tot >= np.percentile(tot, 75),
        'grinder (total <= sim p25)': tot <= np.percentile(tot, 25),
        f'{away} blowout (>= 14)': (ap - hp) >= 14, f'{home} blowout (>= 14)': (hp - ap) >= 14,
        'one-score game (|margin| <= 8)': np.abs(mar) <= 8,
    }
    sw = doc.get('club_scoring_worlds') or {}
    cw = doc.get('club_worlds') or {}
    if cw.get(home) and cw.get(away):
        pa = {c: np.asarray([w[0] for w in cw[c]], float) for c in (home, away)}
        ra = {c: np.asarray([w[1] for w in cw[c]], float) for c in (home, away)}
        own_m = {home: mar, away: -mar}
        for c in (away, home):
            rs = ra[c] / np.maximum(pa[c] + ra[c], 1)
            lab[f'{c} run-control (leads by 7+, rush share >= sim p75)'] = (own_m[c] >= 7) & (rs >= np.percentile(rs, 75))
            lab[f'{c} pass-heavy comeback (trails by 7+, pass att >= sim p75)'] = (own_m[c] <= -7) & (pa[c] >= np.percentile(pa[c], 75))
    qi = doc.get('qb_interceptions') or {}
    if qi:
        ti = np.sum(np.vstack([np.asarray(v, float) for v in qi.values()]), axis=0)
        lab['turnover-heavy (QB INTs >= sim p80)'] = ti >= max(1, np.percentile(ti, 80))
    ks = [k for k, r in by.items() if r['pos'] == 'K' and r['has_draws']]
    if ks:
        kt = sum(by[k]['draws'] for k in ks)
        lab['kicker-heavy (both kickers >= sim p80)'] = kt >= np.percentile(kt, 80)
    ds = [k for k, r in by.items() if r['pos'] == 'DST' and r['has_draws']]
    if ds:
        dm = np.max(np.vstack([by[k]['draws'] for k in ds]), axis=0)
        lab['DST spike (a defence >= 10)'] = dm >= 10
    return lab


#: GOVERNED RELAXATION LADDER (owner directive 2026-10-05: FINAL_LINEUPS == PAID_ENTRIES, always).
#: Level 0 is showdown_to_portfolio's declared caps. Each later level relaxes ONE more policy cap by a
#: small declared step; salary, unique-person, inactive, CPT/FLEX identity and slate scope are never
#: relaxed (they are properties of the candidates themselves, all built lawful by the exact solver).
LADDER = (
    {'level': 0, 'overlap': S.MAX_OVERLAP, 'player': S.MAX_PLAYER_EXPOSURE, 'captain': S.MAX_CAPTAIN_EXPOSURE},
    {'level': 1, 'overlap': S.MAX_OVERLAP + 1, 'player': S.MAX_PLAYER_EXPOSURE, 'captain': S.MAX_CAPTAIN_EXPOSURE},
    {'level': 2, 'overlap': S.MAX_OVERLAP + 1, 'player': S.MAX_PLAYER_EXPOSURE + 0.15, 'captain': S.MAX_CAPTAIN_EXPOSURE},
    {'level': 3, 'overlap': S.MAX_OVERLAP + 1, 'player': S.MAX_PLAYER_EXPOSURE + 0.15, 'captain': S.MAX_CAPTAIN_EXPOSURE + 0.15},
)


def select(hit, cand_rows, seats_of, n, n_w, rung):
    cap_p = max(1, int(np.ceil(rung['player'] * n))) if n > 1 else 1
    cap_c = max(1, int(np.ceil(rung['captain'] * n))) if n > 1 else 1
    if rung['level'] == 0:
        cap_p, cap_c = (max(1, int(rung['player'] * n)), max(1, int(rung['captain'] * n))) if n > 1 else (1, 1)
    chosen, exp, cexp = [], collections.Counter(), collections.Counter()
    covered = np.zeros(n_w, dtype=bool)
    hit_i = hit.astype(np.int32)
    fp = np.array([c['first_place_proxy'] for c in cand_rows])
    dupi = np.array([c['structural_duplication_index'] for c in cand_rows])
    sets = [set(x) for x in seats_of]
    while len(chosen) < n:
        gain = (hit_i @ (~covered).astype(np.int32)) / n_w
        order = np.lexsort((dupi, -fp, -gain))      # coverage gain, own proxy, lower duplication
        best = None
        for i in order:
            i = int(i)
            seats = seats_of[i]
            if i in chosen or any(exp[k] + 1 > cap_p for k in seats) or cexp[seats[0]] + 1 > cap_c:
                continue
            if any(len(sets[i] & sets[j]) > rung['overlap'] for j in chosen):
                continue
            best = i
            break
        if best is None:
            break
        chosen.append(best)
        covered |= hit[best]
        for k in seats_of[best]:
            exp[k] += 1
        cexp[seats_of[best][0]] += 1
    return {'chosen': chosen, 'coverage': float(covered.mean()),
            'caps': {'player': cap_p, 'captain': cap_c, 'overlap': rung['overlap']},
            'short': n - len(chosen), 'relaxation_level': rung['level']}


def ladder(hit, cand_rows, seats_of, n, n_w):
    log = []
    for rung in LADDER:
        P = select(hit, cand_rows, seats_of, n, n_w, rung)
        log.append({'level': rung['level'], 'caps': P['caps'], 'built': len(P['chosen']), 'needed': n,
                    'coverage': round(P['coverage'], 4)})
        if P['short'] == 0:
            return P, log
    return P, log


def kicker_rule_b(doc, by, rows, cands, seats_of, M, contests, portfolios, n_w):
    """SCORING_B: a missed field goal costs 1 point. Same worlds, kickers' draws minus their misses."""
    kw = doc.get('kickers') or {}
    miss = {k: np.asarray(v['world_fg_missed'], dtype=float) for k, v in kw.items()
            if k in by and v.get('world_fg_missed') is not None}
    if not miss:
        return {'state': 'NOT_COMPUTED', 'why': 'draws carry no per-world kicker misses'}
    MB = M.copy()
    for i, seats in enumerate(seats_of):
        for j, k in enumerate(seats):
            if k in miss:
                MB[i] -= (1.5 if j == 0 else 1.0) * miss[k]
    rows_b = [dict(r, draws=(r['draws'] - miss[r['key']]) if r['key'] in miss else r['draws']) for r in rows]
    ob = world_optimum(rows_b)
    if ob.state.value != 'PASS':
        return {'state': 'NOT_COMPUTED', 'why': ob.code}
    hitb = MB >= ((1.0 - BAND) * ob.value['opt'])[None, :]
    out = {'state': 'COMPUTED', 'kicker_means': {}, 'contests': {}}
    for k, v in miss.items():
        out['kicker_means'][by[k]['name']] = {'SCORING_A': round(float(by[k]['draws'].mean()), 3),
                                               'SCORING_B': round(float((by[k]['draws'] - v).mean()), 3)}
    material = False
    for cid, P in portfolios.items():
        n = len(contests[cid]['entries'])
        cr_b = [{'first_place_proxy': float(hitb[i].mean()), 'structural_duplication_index': 0} for i in range(len(seats_of))]
        rung = LADDER[P['relaxation_level']]
        PB = select(hitb, cr_b, seats_of, n, n_w, rung)
        a, b = set(P['chosen']), set(PB['chosen'])
        same = len(a & b)
        ka = sum(1 for i in P['chosen'] for k in seats_of[i] if k in miss)
        kb = sum(1 for i in PB['chosen'] for k in seats_of[i] if k in miss)
        diff = 1 - same / max(1, n)
        out['contests'][cid] = {'lineups_shared_A_B': same, 'n': n, 'share_changed': round(diff, 3),
                                'kicker_slots_A': ka, 'kicker_slots_B': kb,
                                'coverage_of_A_portfolio_under_B': round(float(hitb[P['chosen']].any(axis=0).mean()), 4)
                                if P['chosen'] else 0.0,
                                'coverage_of_B_portfolio_under_B': round(PB['coverage'], 4)}
        cov_a = out['contests'][cid]['coverage_of_A_portfolio_under_B']
        regret = round(PB['coverage'] - cov_a, 4)
        out['contests'][cid]['coverage_regret_if_B_is_true'] = regret
        material = material or regret > MATERIAL_REGRET
    pa = (M >= ((1.0 - BAND) * np.asarray(doc.get('_opt_a')))[None, :]).mean(axis=1) if doc.get('_opt_a') is not None else None
    if pa is not None:
        ta, tb = set(np.argsort(-pa)[:100].tolist()), set(np.argsort(-hitb.mean(axis=1))[:100].tolist())
        out['top100_candidates_shared_A_B'] = len(ta & tb)
    out['MATERIAL'] = material
    out['MATERIAL_RULE'] = (f'the SCORING_A portfolio, scored under SCORING_B, covers more than {MATERIAL_REGRET} '
                            f'fewer worlds than a portfolio rebuilt under SCORING_B (coverage regret). '
                            f'share_changed is reported beside it as greedy-selection sensitivity: lineup '
                            f'identities can change while their value does not.')
    return out


#: Reporting rule only (not a model parameter): coverage the SCORING_A portfolio would forfeit if
#: SCORING_B were DK's real rule, above which the rule question is flagged before finalization.
#: One percentage point of worlds, declared 2026-10-05 for the owner's "materially" test.
MATERIAL_REGRET = 0.01


def dst_coherence(doc, by, home, away):
    """Same-world correlations the owner asked to see, and the declared limitation they test."""
    comps = doc.get('dst_components') or {}
    qbi = doc.get('qb_interceptions') or {}
    wp = (doc.get('world_points') or {}).get('points')
    if not wp:
        return {'state': 'NOT_COMPUTED', 'why': 'no world points in the draws'}
    P = np.asarray(wp)
    pts = {home: P[:, 0], away: P[:, 1]}
    out = {'LIMITATION': ('DST sacks/takeaways are not yet generated directly from the same '
                          'opposing-QB event process.'), 'by_dst': {}, 'warnings': []}
    def cc(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        return None if x.std() == 0 or y.std() == 0 else round(float(np.corrcoef(x, y)[0, 1]), 3)
    for k, r in by.items():
        if r['pos'] != 'DST' or not r['has_draws']:
            continue
        opp = away if r['team'] == home else home
        qbs = [q for q in by.values() if q['team'] == opp and q['pos'] == 'QB' and q['has_draws'] and not q['absent']]
        q = max(qbs, key=lambda q: q['draws'].mean()) if qbs else None
        c = comps.get(k)
        take = [t[1] for t in c] if c else None
        ints = qbi.get(q['key']) if q else None
        rec = {'opponent': opp, 'opposing_qb': q['name'] if q else None,
               'corr_dst_vs_opposing_qb_dk': cc(r['draws'], q['draws']) if q else None,
               'corr_dst_vs_opposing_offense_points': cc(r['draws'], pts[opp]),
               'corr_dst_takeaways_vs_opposing_qb_ints': cc(take, ints) if take and ints else None,
               'mean_takeaways': None if not take else round(float(np.mean(take)), 3),
               'mean_opposing_qb_ints': None if not ints else round(float(np.mean(ints)), 3)}
        out['by_dst'][r['name']] = rec
        if rec['corr_dst_vs_opposing_offense_points'] is not None and rec['corr_dst_vs_opposing_offense_points'] >= 0:
            out['warnings'].append(f"{r['name']}: DST score does not fall as the opponent scores more")
        if rec['corr_dst_vs_opposing_qb_dk'] is not None and rec['corr_dst_vs_opposing_qb_dk'] >= 0:
            out['warnings'].append(f"{r['name']}: DST score does not fall as the opposing QB scores more")
        t = rec['corr_dst_takeaways_vs_opposing_qb_ints']
        if t is None or abs(t) < 0.2:
            out['warnings'].append(f"{r['name']}: takeaways vs the opposing QB's interceptions corr {t} -- the "
                                   f"same events are drawn independently (the declared limitation)")
    out['state'] = 'SHOWDOWN_DST_MODEL_WARNING' if out['warnings'] else 'COHERENT'
    out['CPT_PROBABILITY_NOT_CALIBRATED'] = 'DST captain rates are model outputs, not calibrated probabilities'
    return out


def tail_status(r):
    if r['pos'] == 'DST':
        return 'UNVALIDATED: DST sacks/takeaways not yet generated from the same opposing-QB event process'
    if r['pos'] == 'K':
        return 'UNVALIDATED: same-world kicker, new 2026-10-05'
    return 'MODEL_OUTPUT_NOT_CALIBRATED'


def role_data(r):
    if r['pos'] in ('K', 'DST'):
        return ''
    return 'ROLE_DATA_MISSING: routes, route participation, alignment, personnel (no capture)'


def uncertainty_reasons(r, rows):
    out = []
    pj = r.get('proj') or {}
    if r.get('designation') in ('QUESTIONABLE', 'DOUBTFUL'):
        out.append('DESIGNATION_' + r['designation'])
    if isinstance(pj.get('current_season_weeks'), (int, float)) and pj['current_season_weeks'] < 3:
        out.append('SMALL_CURRENT_SAMPLE')
    if pj.get('prior_confidence') in ('LOW', 'NONE'):
        out.append('LOW_PRIOR_CONFIDENCE')
    if r['pos'] == 'QB' and not pj.get('is_predicted_starter') and r.get('depth_rank') != 1:
        out.append('BACKUP_QB')
    grp = {'RB': ('RB',), 'WR': ('WR', 'TE'), 'TE': ('WR', 'TE'), 'QB': ('QB',)}.get(r['pos'])
    if grp and any(o['absent'] and o['team'] == r['team'] and o['pos'] in grp for o in rows):
        out.append('TEAMMATE_ABSENCE_REDISTRIBUTION')
    if r.get('state') == 'ZERO_OPPORTUNITY':
        out.append('NO_MODELLED_OPPORTUNITY')
    return out


def correlation_rows(eligible, team_pts, home, away):
    def cc(x, y):
        return None if np.std(x) == 0 or np.std(y) == 0 else round(float(np.corrcoef(x, y)[0, 1]), 3)
    out = []
    top = lambda t, pos, n=1: sorted([r for r in eligible if r['team'] == t and r['pos'] in pos],
                                     key=lambda r: -r['draws'].mean())[:n]
    for t in (away, home):
        o = home if t == away else away
        qb = top(t, ('QB',))
        oqb = top(o, ('QB',))
        dst = top(t, ('DST',))
        k = top(t, ('K',))
        if qb:
            for r in top(t, ('WR',), 3) + top(t, ('TE',), 2) + top(t, ('RB',), 2):
                out.append([f'QB-{r["pos"]}', qb[0]['name'], r['name'], cc(qb[0]['draws'], r['draws'])])
        if k:
            out.append(['K-own offense points', k[0]['name'], t, cc(k[0]['draws'], team_pts[t])])
            if qb:
                out.append(['K-own QB', k[0]['name'], qb[0]['name'], cc(k[0]['draws'], qb[0]['draws'])])
        if dst:
            if oqb:
                out.append(['DST-opposing QB', dst[0]['name'], oqb[0]['name'], cc(dst[0]['draws'], oqb[0]['draws'])])
            for r in top(o, ('WR',), 2):
                out.append(['DST-opposing WR', dst[0]['name'], r['name'], cc(dst[0]['draws'], r['draws'])])
            for r in top(t, ('RB',), 1):
                out.append(['RB-own DST', r['name'], dst[0]['name'], cc(r['draws'], dst[0]['draws'])])
        wr = top(t, ('WR', 'TE'), 3)
        for i in range(len(wr)):
            for j in range(i + 1, len(wr)):
                out.append(['same-team receivers', wr[i]['name'], wr[j]['name'], cc(wr[i]['draws'], wr[j]['draws'])])
    qa, qh = top(away, ('QB',)), top(home, ('QB',))
    if qa and qh:
        out.append(['opposing QBs (shootout)', qa[0]['name'], qh[0]['name'], cc(qa[0]['draws'], qh[0]['draws'])])
    out.append(['team points (shootout)', away, home, cc(team_pts[away], team_pts[home])])
    return out


def dk_input_gate(export):
    """Hard gate on the DK file itself, independent of the builder: contests, entries, IDs, CPT/FLEX pairing."""
    rows = list(csv.reader(open(export, newline='', encoding='utf-8-sig')))
    hdr = [c.strip() for c in rows[0]]
    entries = [r for r in rows[1:] if len(r) > 3 and r[0].strip().isdigit()]
    by_contest = collections.Counter(r[hdr.index('Contest ID')].strip() for r in entries)
    names = {r[hdr.index('Contest ID')].strip(): r[hdr.index('Contest Name')].strip() for r in entries}
    pool, ph = [], None
    for i, r in enumerate(rows):
        if 'Roster Position' in r and 'ID' in r and 'Salary' in r:
            ph = {h.strip(): j for j, h in enumerate(r)}
            pool = [q for q in rows[i + 1:] if len(q) > ph['Salary'] and q[ph['ID']].strip()]
            break
    fail = []
    if not entries:
        fail.append('NO_ENTRIES')
    if not pool:
        fail.append('NO_POOL')
    ids = [q[ph['ID']].strip() for q in pool] if pool else []
    if len(ids) != len(set(ids)):
        fail.append('DUPLICATE_DK_ID')
    if any(not i.isdigit() for i in ids):
        fail.append('NON_NUMERIC_DK_ID')
    person = collections.defaultdict(dict)
    games, teams = set(), set()
    for q in pool:
        slot = q[ph['Roster Position']].strip()
        key = (q[ph['Name']].strip(), q[ph['TeamAbbrev']].strip())
        if slot not in ('CPT', 'FLEX'):
            fail.append(f'UNKNOWN_SLOT {slot}')
        if slot in person[key]:
            fail.append(f'TWO_{slot}_ROWS {key}')
        person[key][slot] = int(q[ph['Salary']])
        games.add(q[ph['Game Info']].strip().split(' ')[0])
        teams.add(key[1])
    unpaired = [k for k, v in person.items() if set(v) != {'CPT', 'FLEX'}]
    bad_ratio = [k for k, v in person.items() if set(v) == {'CPT', 'FLEX'} and v['CPT'] != int(round(1.5 * v['FLEX']))]
    if unpaired:
        fail.append(f'UNPAIRED {unpaired[:5]}')
    if bad_ratio:
        fail.append(f'CPT_NOT_1_5X {bad_ratio[:5]}')
    if len(games) != 1:
        fail.append(f'NOT_ONE_GAME {sorted(games)}')
    by_pos = collections.Counter(q[ph['Position']].strip() for q in pool if q[ph['Roster Position']].strip() == 'FLEX')
    out = {'contests': {c: {'name': names[c], 'entries': n} for c, n in by_contest.items()},
           'n_entries': len(entries), 'dk_player_rows': len(pool), 'football_players': len(person),
           'teams': sorted(teams), 'game': sorted(games), 'people_by_position': dict(by_pos),
           'unpaired': unpaired, 'cpt_ratio_violations': bad_ratio, 'failures': fail,
           'sha256': hashlib.sha256(pathlib.Path(export).read_bytes()).hexdigest()}
    return Outcome.ok('DK_INPUT_GATE_PASS', out) if not fail else Outcome.fail('DK_INPUT_GATE_FAIL', '; '.join(fail), **out)


def run(export, draws_path, out_dir, prefix, *, inactives=None, proj_path=None, state_path=None):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    L = load(export, draws_path, inactives)
    if L.state.value != 'PASS':
        return L
    V = L.value
    slate, absent, doc = V['slate'], V['absent'], V['draws_doc']
    rows = players_table(slate, absent, V['draws'])
    by = {r['key']: r for r in rows}
    proj = json.loads(pathlib.Path(proj_path).read_text()) if proj_path else None
    prow = {}
    if proj:
        for r in proj['rows'].values():
            prow[S.player_key(r['name'], r['team'])] = r
    state = json.loads(pathlib.Path(state_path).read_text()) if state_path else None
    st_by = {}
    if state:
        for v in state['players'].values():
            st_by[S.player_key(v['name'], v['team'])] = v
    n_w = len(next(r['draws'] for r in rows if r['has_draws']))
    home, away = slate['home'], slate['away']
    global TEAM_ORDER
    TEAM_ORDER = (away, home)
    gate = dk_input_gate(export)
    if gate.state.value != 'PASS':
        return gate

    # ---- 1. completeness: every DK row classified
    for r in rows:
        pr = dict(prow.get(r['key']) or {})
        stv = st_by.get(r['key']) or {}
        ca = stv.get('current_availability') or {}
        pr['availability_status'] = ca.get('status')
        pr['designation'] = ca.get('designation')
        r['state'] = classify(r, pr)
        r['availability'] = ca.get('status') or ('ABSENT' if r['absent'] else 'UNKNOWN')
        r['designation'] = ca.get('designation') or ''
        r['depth_rank'] = stv.get('depth_rank')
        r['proj'] = prow.get(r['key']) or {}
    eligible = [r for r in rows if not r['absent'] and r['has_draws']]

    # ---- 2. optimum and candidates
    OPT = world_optimum(rows)
    if OPT.state.value != 'PASS':
        return OPT
    opt = OPT.value['opt']
    doc['_opt_a'] = opt
    gen = S.near_optimal_candidates(slate, absent, V['draws'])
    if gen.state.value != 'PASS':
        return gen
    pool = {(c['captain'], tuple(sorted(c['flex']))): c['n_worlds_optimal'] for c in gen.value}
    forced, forced_acct = forced_captain_candidates(rows)
    for k, n in forced.items():
        pool.setdefault(k, 0)
    cands = sorted(pool)
    M = score_matrix(cands, by)
    thr = (1.0 - BAND) * opt
    hit = M >= thr[None, :]
    means = {r['key']: float(r['draws'].mean()) for r in eligible}
    top_cpt = max(eligible, key=lambda r: 1.5 * means[r['key']])['key']
    top6 = set(sorted(means, key=lambda k: -means[k])[:6])
    gen_keys = {(x['captain'], tuple(sorted(x['flex']))) for x in gen.value}
    cand_rows = []
    for i, (c, f) in enumerate(cands):
        s = structural(c, f, by, top_cpt, top6)
        sc = M[i]
        cand_rows.append({'idx': i, 'captain': c, 'flex': list(f), **s,
                          'mean': float(sc.mean()), 'p90': _pct(sc, 90), 'p95': _pct(sc, 95), 'p99': _pct(sc, 99),
                          'first_place_proxy': float(hit[i].mean()),
                          'n_worlds_optimal': pool[(c, f)],
                          'source': 'EXACT_OR_NEAR_OPTIMAL' if (c, f) in gen_keys else 'FORCED_CAPTAIN'})

    # ---- 3. per-contest portfolios, each built independently, on the governed relaxation ladder
    contests = collections.OrderedDict()
    for e in V['entries']:
        contests.setdefault(e['contest_id'], {'name': e['contest_name'], 'fee': e['entry_fee'], 'entries': []})['entries'].append(e)
    seats_of = [[cands[i][0]] + list(cands[i][1]) for i in range(len(cands))]
    portfolios = {}
    for cid, cdef in contests.items():
        n = len(cdef['entries'])
        P, log = ladder(hit, cand_rows, seats_of, n, n_w)
        portfolios[cid] = {'contest': cdef, **P, 'relaxation_log': log}

    # ---- 3b. kicker scoring B (missed FG -1) on the same worlds: does it move the selection?
    kick_b = kicker_rule_b(doc, by, rows, cands, seats_of, M, contests, portfolios, n_w)

    # ---- 3c. DST coherence on the same worlds
    dst_check = dst_coherence(doc, by, home, away)

    # ---- 4. write the boards
    written = {}

    def w(name, header, data):
        p = out_dir / f'{prefix}_{name}.csv'
        with p.open('w', newline='') as fh:
            wr = csv.writer(fh)
            wr.writerow(header)
            wr.writerows(data)
        written[name] = p

    pr_hdr = ['player', 'team', 'pos', 'salary', 'cpt_salary', 'flex_id', 'cpt_id', 'state', 'availability',
              'designation', 'depth_rank', 'pass_att', 'carries', 'targets', 'rec', 'pass_yds', 'rush_yds',
              'rec_yds', 'pass_td', 'rush_td', 'rec_td', 'int', 'proj_dk_points', 'sim_mean', 'p50', 'p75',
              'p90', 'p95', 'p99', 'cpt_mean', 'cpt_p95', 'p_zero', 'optimizer_eligible',
              'tail_status', 'role_data', 'uncertainty_reasons']
    data = []
    for r in sorted(rows, key=lambda r: (r['team'], POS_ORDER.get(r['pos'], 9), -(r['salary']))):
        cv = r['proj'].get('conditional_volume') or {}
        uv = r['proj'].get('volume') or r['proj'].get('unconditional_volume') or {}
        tdp = r['proj'].get('td') or {}
        d = r['draws']

        def g(*ks):
            for src in (uv, cv, r['proj']):
                for k in ks:
                    if isinstance(src.get(k), (int, float)):
                        return round(src[k], 2)
            return ''
        data.append([r['name'], r['team'], r['pos'], r['salary'], r['cpt_salary'], r['flex_id'], r['cpt_id'],
                     r['state'], r['availability'], r['designation'], r['depth_rank'],
                     g('pass_attempts'), g('carries'), g('targets'), g('receptions'),
                     g('pass_yards'), g('rush_yards'), g('rec_yards'),
                     round(tdp['pass_td'], 3) if isinstance(tdp.get('pass_td'), (int, float)) else g('pass_td'),
                     round(tdp['rush_td'], 3) if isinstance(tdp.get('rush_td'), (int, float)) else g('rush_td'),
                     round(tdp['rec_td'], 3) if isinstance(tdp.get('rec_td'), (int, float)) else g('rec_td'),
                     g('interceptions'), r['proj'].get('dk_points', ''),
                     *(['', '', '', '', '', '', '', '', ''] if d is None else
                       [round(d.mean(), 2), round(_pct(d, 50), 2), round(_pct(d, 75), 2), round(_pct(d, 90), 2),
                        round(_pct(d, 95), 2), round(_pct(d, 99), 2), round(1.5 * d.mean(), 2),
                        round(1.5 * _pct(d, 95), 2), round(float((d <= 0).mean()), 3)]),
                     r in eligible, tail_status(r), role_data(r), '|'.join(uncertainty_reasons(r, rows))])
    w('PROJECTIONS', pr_hdr, data)

    # simulation summary: one row per player with full quantiles + correlation to team/opp points
    wp = np.asarray((doc.get('world_points') or {}).get('points') or np.zeros((n_w, 2)))
    team_pts = {home: wp[:, 0], away: wp[:, 1]}
    sim = []
    for r in eligible:
        d = r['draws']
        opp = away if r['team'] == home else home
        cc = lambda x: round(float(np.corrcoef(d, x)[0, 1]), 3) if np.std(d) > 0 and np.std(x) > 0 else ''
        sim.append([r['name'], r['team'], r['pos'], round(d.mean(), 3), round(d.std(), 3)] +
                   [round(_pct(d, q), 2) for q in (5, 25, 50, 75, 90, 95, 99)] +
                   [round(float((d <= 0).mean()), 3), cc(team_pts[r['team']]), cc(team_pts[opp])])
    w('SIMULATION_SUMMARY', ['player', 'team', 'pos', 'mean', 'sd', 'p05', 'p25', 'p50', 'p75', 'p90', 'p95',
                             'p99', 'p_zero', 'corr_own_team_points', 'corr_opp_points'], sim)

    # CPT board
    labs = scripts(doc, by, home, away)
    cptb = []
    qb_of = {t: max((r for r in eligible if r['team'] == t and r['pos'] == 'QB'), key=lambda r: means[r['key']], default=None)
             for t in (home, away)}
    for r in eligible:
        d = r['draws']
        c = 1.5 * d
        q = qb_of.get(r['team'])
        corr_qb = (round(float(np.corrcoef(d, q['draws'])[0, 1]), 3) if q and q['key'] != r['key'] and np.std(d) > 0 else '')
        as_cpt = [cr for cr in cand_rows if cr['captain'] == r['key']]
        best_proxy = max((cr['first_place_proxy'] for cr in as_cpt), default=0.0)
        lead_own = labs.get(f"{r['team']} leads (wins)")
        dep = ''
        if lead_own is not None and lead_own.any() and (~lead_own).any():
            dep = round(float(d[lead_own].mean() - d[~lead_own].mean()), 2)
        cptb.append([r['name'], r['team'], r['pos'], r['cpt_salary'], r['salary'], round(c.mean(), 2),
                     round(_pct(c, 90), 2), round(_pct(c, 95), 2), round(_pct(c, 99), 2),
                     OPT.value['cpt_freq'].get(r['key'], 0) / n_w, round(best_proxy, 4), len(as_cpt),
                     corr_qb, CAP - r['cpt_salary'], round((CAP - r['cpt_salary']) / 5, 0),
                     int(r['key'] == top_cpt), dep])
    cptb.sort(key=lambda x: -x[9])
    w('CPT_BOARD', ['player', 'team', 'pos', 'cpt_salary', 'flex_salary', 'cpt_mean', 'cpt_p90', 'cpt_p95',
                    'cpt_p99', 'p_world_optimal_captain', 'best_first_place_proxy_as_cpt',
                    'n_candidates_as_cpt', 'corr_with_own_qb', 'salary_left_for_flex', 'avg_per_flex',
                    'is_top_mean_captain', 'own_team_wins_minus_loses_flex_pts'], cptb)

    # candidates
    nm = lambda k: by[k]['name']
    w('CANDIDATES', ['idx', 'captain', 'captain_pos', 'flex', 'salary', 'salary_band', 'split', 'qb_double_stack',
                     'mean', 'p90', 'p95', 'p99', 'first_place_proxy', 'n_worlds_optimal',
                     'structural_duplication_index', 'source'],
      [[c['idx'], nm(c['captain']), by[c['captain']]['pos'], ' / '.join(nm(k) for k in c['flex']), c['salary'],
        c['salary_band'], c['split'], int(c['qb_double_stack']), round(c['mean'], 2), round(c['p90'], 2),
        round(c['p95'], 2), round(c['p99'], 2), round(c['first_place_proxy'], 4), c['n_worlds_optimal'],
        c['structural_duplication_index'], c['source']]
       for c in sorted(cand_rows, key=lambda c: -c['first_place_proxy'])])

    # final lineups / exposures / cpt exposures / stacks / upload
    fl, ex, cx, sb, up = [], [], [], [], []
    for cid, P in portfolios.items():
        n = len(P['contest']['entries'])
        e_ct, c_ct = collections.Counter(), collections.Counter()
        split_ct, band_ct, stack_ct = collections.Counter(), collections.Counter(), collections.Counter()
        for slot, (e, i) in enumerate(zip(P['contest']['entries'], P['chosen'])):
            c = cand_rows[i]
            fl.append([cid, P['contest']['name'], e['entry_id'], nm(c['captain']), *[nm(k) for k in c['flex']],
                       c['salary'], c['split'], c['salary_band'], round(c['mean'], 2), round(c['p95'], 2),
                       round(c['first_place_proxy'], 4), c['structural_duplication_index']])
            up.append([e['entry_id'], e['contest_name'], e['contest_id'], e['entry_fee'],
                       by[c['captain']]['cpt_id'], *[by[k]['flex_id'] for k in c['flex']]])
            for k in [c['captain']] + c['flex']:
                e_ct[k] += 1
            c_ct[c['captain']] += 1
            split_ct[c['split']] += 1
            band_ct[c['salary_band']] += 1
            stack_ct[(by[c['captain']]['team'], c['split'], int(c['qb_double_stack']))] += 1
        for k, v in e_ct.most_common():
            ex.append([cid, nm(k), by[k]['team'], by[k]['pos'], v, round(v / n, 3)])
        for k, v in c_ct.most_common():
            cx.append([cid, nm(k), by[k]['team'], by[k]['pos'], v, round(v / n, 3)])
        for (t, s, qd), v in stack_ct.most_common():
            sb.append([cid, f'CPT {t}', s, qd, v, round(v / n, 3)])
        P['split_counts'], P['band_counts'] = dict(split_ct), dict(band_ct)
    w('FINAL_LINEUPS', ['contest_id', 'contest', 'entry_id', 'CPT', 'FLEX1', 'FLEX2', 'FLEX3', 'FLEX4', 'FLEX5',
                        'salary', 'split', 'salary_band', 'mean', 'p95', 'first_place_proxy',
                        'structural_duplication_index'], fl)
    w('EXPOSURES', ['contest_id', 'player', 'team', 'pos', 'n', 'share'], ex)
    w('CPT_EXPOSURES', ['contest_id', 'captain', 'team', 'pos', 'n', 'share'], cx)
    w('STACK_BOARD', ['contest_id', 'captain_team', 'team_split', 'qb_double_stack', 'n', 'share'], sb)

    # game-script board
    gs = []
    for lab, mask in labs.items():
        if not mask.any():
            gs.append([lab, 0.0, '', '', '', ''])
            continue
        lead = sorted(eligible, key=lambda r: -r['draws'][mask].mean())[:5]
        best_c = max(eligible, key=lambda r: r['draws'][mask].mean())
        covs = {cid: round(float(hit[P['chosen']][:, mask].any(axis=0).mean()), 4) if P['chosen'] else 0.0
                for cid, P in portfolios.items()}
        gs.append([lab, round(float(mask.mean()), 4), ' / '.join(f"{r['name']} {r['draws'][mask].mean():.1f}" for r in lead),
                   best_c['name'], round(float(opt[mask].mean()), 2), json.dumps(covs)])
    w('GAME_SCRIPT_BOARD', ['script', 'share_of_worlds', 'top5_flex_means_in_script', 'best_mean_captain_in_script',
                            'mean_world_optimum', 'portfolio_proxy_coverage_by_contest'], gs)

    w('CORRELATION', ['pair_type', 'a', 'b', 'corr_same_world'], correlation_rows(eligible, team_pts, home, away))
    script_ct = collections.Counter()
    if labs:
        names_l = list(labs)
        Mk = np.vstack([labs[x] for x in names_l]).astype(float)        # scripts x worlds
        cond = (hit.astype(float) @ Mk.T) / np.maximum(Mk.sum(axis=1), 1)[None, :]
        for i in range(len(cands)):
            script_ct[names_l[int(np.argmax(cond[i]))]] += 1
    qb_ct = collections.Counter(sum(1 for k in seats_of[i] if by[k]['pos'] == 'QB') for i in range(len(cands)))

    upload = out_dir / f'{prefix}_DK_UPLOAD.csv'
    short = {cid: P['short'] for cid, P in portfolios.items() if P['short']}
    if short:
        # FINAL_LINEUPS == PAID_ENTRIES, always: no upload file is written short.
        if upload.exists():
            upload.unlink()
        ver = Outcome.fail('FINALIZATION_BLOCKED', f'contests short after the full ladder: {short}', short=short)
    else:
        with upload.open('w', newline='') as fh:
            wr = csv.writer(fh)
            wr.writerow(list(S.ENTRY_COLUMNS) + list(S.SHOWDOWN_SLOTS))
            wr.writerows(up)
        written['DK_UPLOAD'] = upload
        ver = verify_upload(upload, export, absent_names={by[k]['name'] for k in absent},
                            inactive_keys=absent)
        if ver.state.value == 'PASS' and ver.value['n_rows'] != len(V['entries']):
            ver = Outcome.fail('UPLOAD_ROWS_NE_PAID_ENTRIES', f"{ver.value['n_rows']} rows vs {len(V['entries'])} entries")

    def pct_pack(a):
        a = np.asarray(a, float)
        return {'mean': round(float(a.mean()), 3), 'p75': round(_pct(a, 75), 2), 'p90': round(_pct(a, 90), 2),
                'p95': round(_pct(a, 95), 2)}
    kick_report = {}
    for k, v in (doc.get('kickers') or {}).items():
        if k in by and by[k]['has_draws']:
            kick_report[by[k]['name']] = {
                'SCORING_A_no_miss_deduction': {**pct_pack(by[k]['draws']),
                                                'p_zero': round(float((by[k]['draws'] == 0).mean()), 4),
                                                'p_10_plus': round(float((by[k]['draws'] >= 10).mean()), 4),
                                                'p_15_plus': round(float((by[k]['draws'] >= 15).mean()), 4)},
                'SCORING_B_minus_1_per_miss': (pct_pack(by[k]['draws'] - np.asarray(v['world_fg_missed']))
                                               if v.get('world_fg_missed') else None),
                'fg_attempts_mean': round(float(np.mean(v['world_fg_att'])), 3) if v.get('world_fg_att') else None,
                'xp_attempts_mean': round(float(np.mean(v['world_xp_att'])), 3) if v.get('world_xp_att') else None,
                'per_world_means': v.get('per_world_means'), 'made_mix': v.get('made_mix'),
                'cpt_eligible': any(c['captain'] == k for c in cand_rows),
                'VALIDATED': False}
    counts = collections.Counter(r['state'] for r in rows)
    audit = {
        'ARTIFACT': f'{prefix}_AUDIT', 'export': str(export), 'draws': str(draws_path),
        'draws_sha256': hashlib.sha256(pathlib.Path(draws_path).read_bytes()).hexdigest(),
        'n_worlds': n_w, 'home': home, 'away': away,
        'roster_completeness': {'n_dk_rows': len(rows), 'state_counts': dict(counts),
                                'by_position': {p: dict(collections.Counter(r['state'] for r in rows if r['pos'] == p))
                                                for p in POS_ORDER},
                                'unclassified': [r['name'] for r in rows if not r.get('state')]},
        'kickers_and_dst': {r['name']: {'pos': r['pos'], 'has_draws': r['has_draws'],
                                        'mean': None if r['draws'] is None else round(float(r['draws'].mean()), 3),
                                        'sd': None if r['draws'] is None else round(float(r['draws'].std()), 3),
                                        'distinct_values': None if r['draws'] is None else int(len(np.unique(r['draws']))),
                                        'cpt_candidates': sum(1 for c in cand_rows if c['captain'] == r['key']),
                                        'flex_candidates': sum(1 for c in cand_rows if r['key'] in c['flex'])}
                            for r in rows if r['pos'] in ('K', 'DST')},
        'candidates': {'n': len(cands), 'n_exact_or_near': len(gen.value), 'forced_captain': forced_acct,
                       'by_captain_pos': {p: sum(1 for c, _ in cands if by[c]['pos'] == p) for p in POS_ORDER},
                       'by_split_away_home': {f'{a}-{6 - a}': sum(1 for c in cand_rows if c['split'] == f'{a}-{6 - a}')
                                              for a in (5, 4, 3, 2, 1)},
                       'split_orientation': f'{away}-{home}',
                       'by_salary_band': {b: sum(1 for c in cand_rows if c['salary_band'] == b) for b, _l, _h in SALARY_BANDS},
                       'by_best_game_script': dict(script_ct),
                       'by_qb_count': {str(k): v for k, v in sorted(qb_ct.items())},
                       'BEST_SCRIPT_MEANING': 'the script in which the candidate most often reaches the first-place proxy'},
        'field_layer': {'P_top_1pct': 'UNAVAILABLE', 'P_top_0_1pct': 'UNAVAILABLE', 'expected_payout': 'UNAVAILABLE',
                        'WHY': ('no Showdown ownership or field model exists; nfl/field/ is classic-only and '
                                'NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP. Ownership is never invented.')},
        'not_modelled_explicitly': {'overtime': 'inside the empirical total/margin residuals, not a world label',
                                    'routes_alignment_personnel': 'ROLE_DATA_MISSING (no capture)'},
        'dk_input_gate': gate.value,
        'kickers': kick_report,
        'kicker_rule_B': kick_b,
        'dst_coherence': dst_check,
        'n_eligible': len(eligible),
        'first_place_proxy': f'score >= (1 - {BAND}) x exact world optimum; a proxy, not P(win)',
        'portfolios': {cid: {'contest': P['contest']['name'], 'n_entries': len(P['contest']['entries']),
                             'n_built': len(P['chosen']), 'short': P['short'], 'caps': P['caps'],
                             'proxy_coverage': round(P['coverage'], 4),
                             'relaxation_level': P['relaxation_level'], 'relaxation_log': P['relaxation_log'],
                             'split_counts': P.get('split_counts'), 'salary_band_counts': P.get('band_counts')}
                       for cid, P in portfolios.items()},
        'upload_verification': ver.value if ver.state.value == 'PASS' else {'state': ver.state.value, 'code': ver.code,
                                                                             'detail': ver.detail, **(ver.evidence or {})},
        'availability': {'state': V['availability'].state.value, 'code': V['availability'].code,
                         'absent': sorted(absent), 'inactives_not_in_priced_pool': V['inactives_not_in_priced_pool']},
        'OWNERSHIP': 'UNAVAILABLE; nothing here uses or invents ownership',
        'NOT_SUBMITTED': 'written to disk only; entering contests is the owner\'s action',
        'files': {k: str(p) for k, p in written.items()},
    }
    (out_dir / f'{prefix}_AUDIT.json').write_text(json.dumps(audit, indent=1, default=str))
    if ver.code == 'FINALIZATION_BLOCKED':
        return Outcome.fail('FINALIZATION_BLOCKED', ver.detail, audit=audit)
    if ver.state.value != 'PASS':
        return Outcome.fail('SHOWDOWN_UPLOAD_FAILED_VERIFICATION', ver.detail, audit=audit)
    return Outcome.ok('SHOWDOWN_PORTFOLIO_BUILT', audit, f'{len(cands)} candidates; '
                      + '; '.join(f"{P['contest']['name'][:40]} {len(P['chosen'])}/{len(P['contest']['entries'])} cov {P['coverage']:.3f}"
                                  for P in portfolios.values()))


def verify_upload(upload, export, *, absent_names=(), inactive_keys=()):
    """Independent re-check of the upload against the DK export only. Shares no state with the builder."""
    rows = list(csv.reader(open(export, newline='', encoding='utf-8-sig')))
    hdr = rows[0]
    entries = {}
    for r in rows[1:]:
        if len(r) > 3 and r[0].strip() and r[0].strip()[0].isdigit():
            entries[r[0].strip()] = (r[2].strip(), r[1].strip())
    # pool: find the header row carrying 'Roster Position' and 'ID'
    pool = {}
    for i, r in enumerate(rows):
        if 'Roster Position' in r and 'ID' in r and 'Salary' in r:
            c = {h: j for j, h in enumerate(r)}
            for q in rows[i + 1:]:
                if len(q) > c['Salary'] and q[c['ID']].strip():
                    pool[q[c['ID']].strip()] = {'name': q[c['Name']].strip(), 'slot': q[c['Roster Position']].strip(),
                                                'salary': int(q[c['Salary']]), 'team': q[c['TeamAbbrev']].strip()}
            break
    if not pool:
        return Outcome.fail('VERIFY_NO_POOL', 'no pool block in the export')
    up = list(csv.reader(open(upload, newline='', encoding='utf-8')))
    viol = []
    seen_entries = set()
    for n, r in enumerate(up[1:], 1):
        eid, cname, cid = r[0], r[1], r[2]
        if eid not in entries:
            viol.append((n, 'ENTRY_ID_NOT_IN_EXPORT'))
        elif entries[eid][0] != cid:
            viol.append((n, 'CONTEST_ID_MISMATCH'))
        if eid in seen_entries:
            viol.append((n, 'DUPLICATE_ENTRY_ID'))
        seen_entries.add(eid)
        ids = r[4:10]
        if len(ids) != 6:
            viol.append((n, 'NOT_SIX_SLOTS'))
            continue
        items = [pool.get(i) for i in ids]
        if any(x is None for x in items):
            viol.append((n, 'UNKNOWN_DK_ID'))
            continue
        if items[0]['slot'] != 'CPT' or any(x['slot'] != 'FLEX' for x in items[1:]):
            viol.append((n, 'SLOT_ID_MISMATCH'))
        people = [(x['name'], x['team']) for x in items]
        if len(set(people)) != 6:
            viol.append((n, 'DUPLICATE_PERSON'))
        if len({x['team'] for x in items}) < 2:
            viol.append((n, 'ONE_TEAM_ONLY'))
        if sum(x['salary'] for x in items) > CAP:
            viol.append((n, 'OVER_CAP'))
        flex_sal = {(x['name'], x['team']): x['salary'] for x in pool.values() if x['slot'] == 'FLEX'}
        if items[0]['salary'] != int(round(1.5 * flex_sal.get((items[0]['name'], items[0]['team']), -1))):
            viol.append((n, 'CPT_SALARY_NOT_1_5X'))
        if any(x['name'] in absent_names for x in items):
            viol.append((n, 'INACTIVE_ROSTERED'))
    lineups = [tuple(r[4:10]) for r in up[1:]]
    out = {'n_rows': len(up) - 1, 'n_unique_entries': len(seen_entries), 'violations': viol,
           'n_distinct_lineups': len(set(lineups)),
           'sha256': hashlib.sha256(pathlib.Path(upload).read_bytes()).hexdigest()}
    if viol:
        return Outcome.fail('UPLOAD_VIOLATIONS', f'{len(viol)} violations', **out)
    return Outcome.ok('UPLOAD_VERIFIED', out, f"{out['n_rows']} rows, 0 violations")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('draws')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--inactives')
    ap.add_argument('--proj')
    ap.add_argument('--state')
    a = ap.parse_args()
    ina = json.loads(pathlib.Path(a.inactives).read_text()) if a.inactives else None
    o = run(a.export, a.draws, a.out_dir, a.prefix, inactives=ina, proj_path=a.proj, state_path=a.state)
    print(o.state.value, o.code, o.detail)
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
