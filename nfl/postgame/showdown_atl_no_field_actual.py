#!/usr/bin/env python3.12
"""ATL@NO full-field standings -- the PRE-REGISTERED field measurements (docs/NFL_SHOWDOWN_ATL_NO_POSTGAME_PREREGISTRATION.md).

    python3.12 nfl/postgame/showdown_atl_no_field_actual.py [--phis 200 50 1000]

LAYER: POSTGAME_ACTUAL (the field) + POSTGAME_DIAGNOSIS (the scoring). Observation #1 for every shadow ownership /
field / dupe method. Nothing is promoted, retuned or relabelled on it; no coefficient is refitted on ATL@NO.

INPUTS
  standings  nfl/postgame/raw/showdown_history/<cid>_ATL_NO/ (content-addressed, PROVENANCE.jsonl)
  frozen predictions (committed 9736516d, 2026-10-05 23:47Z, before the 00:15Z lock):
    SHADOW_RW_INACTIVES_CHARTFIX{,_BLEND}/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv   ownership (FC_ONLY, BLEND)
    SHADOW_RW_INACTIVES_CHARTFIX{,_BLEND}/shadow_field_lineups.npy               optimizer field (E4, archetype prior)
    RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_DUPE_STACK_{FC_ONLY,BLEND}.json        E1..E4 per lineup (stored for the
                                                                                  20-max and 2-entry; MEANS + top-10
                                                                                  only for the 150-max)

RECOMPUTED-FROM-FROZEN-INPUTS. For the 150-max the per-lineup stack was not stored. It is recomputed here with the
frozen code path (showdown_archetype_field: targets -> Pool -> calibrate -> generate -> stack, same SEED, same k) from
the frozen inputs above, never from an outcome. It is USED ONLY IF it reproduces every stored number exactly: the three
contests' E1/E2/E3/E4 means, the 150-max top-10 rows, and every stored 20-max / 2-entry row. Otherwise the run stops.

MEASUREMENTS (per contest, separately; numbered as pre-registered)
  1 ownership  CPT and FLEX separately, FC_ONLY and BLEND vs DK %Drafted: RMSE, MAE (pct pts), Spearman, and the
               share-weighted log-loss reported as KL(actual || predicted) over shares normalised within the slot;
               players above 5% actual listed individually
  2 dupes      our lineups and the 50 most-duplicated lineups: copies by OTHER entrants (our own entries removed) vs E1,
               E2, E3 (phi 200; other phis as sensitivity when run), E4; median |log((pred+1)/(actual+1))|, Spearman,
               and among E1_E3_DISAGREE_GT_2X flags the share where the actual sits closer to E3
  3 archetypes team split (ATL-NO count), QB count, K+DST count, CPT pass-catcher with own QB: field vs optimizer prior
  4 salary     field salary-left buckets vs the archetype field and the optimizer field
  5 conflicts  CF-1 CPT position field vs top 1%; CF-2 R^2 log(product own) vs log(copies); CF-3 CPT-only vs FLEX-product
Plus the autopsy items that waited on this file: winner / top 10 / top 100 / top 1% vs our best lineup, its copies and
ownership, and the realised duplicate counts of every owner entry.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_archetype_field as AF  # noqa: E402
from nfl.field import showdown_history_calibration as HC  # noqa: E402
from nfl.tools import showdown_portfolio_audit as PA  # noqa: E402

ATL = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
V2 = ATL / 'RW_INACTIVES_CHARTFIX'
SHADOW = {'FC_ONLY': ATL / 'SHADOW_RW_INACTIVES_CHARTFIX', 'BLEND': ATL / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND'}
RAWH = _REPO / 'nfl/postgame/raw/showdown_history'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
CONTESTS = {'196285137': '150-max', '196285160': '20-max', '196285161': '2-entry'}
OWN_LIST_FLOOR = 5.0
TOP_DUP = 50


class FieldActualError(RuntimeError):
    pass


def need(c, code, detail=''):
    if not c:
        raise FieldActualError(f'{code}: {detail}')


# ------------------------------------------------------------------------------------------------ standings
def load_standings(cid):
    d = RAWH / f'{cid}_ATL_NO'
    recs = [json.loads(x) for x in (d / 'PROVENANCE.jsonl').read_text().splitlines() if x.strip()]
    need(len(recs) == 1 and recs[0]['contest_id'] == cid, 'PROVENANCE', str(d))
    rec = recs[0]
    b = gzip.decompress((_REPO / rec['file']).read_bytes())
    need(hashlib.sha256(b).hexdigest() == rec['sha256'], 'SHA256_MISMATCH', rec['file'])
    rows = list(csv.reader(io.StringIO(b.decode('utf-8-sig'))))
    need(rows and rows[0] == HC.EXPECTED_HEADER, 'SCHEMA', str(rows[0] if rows else None))
    entries, empty, slot = [], 0, {}
    for i, r in enumerate(rows[1:], start=2):
        need(len(r) in (9, 11), 'ROW_WIDTH', f'{cid} line {i}')
        if r[1].strip():
            if not r[5].strip():
                empty += 1
            else:
                c, f = HC.parse_lineup(r[5].strip(), i)
                user = r[2].rsplit(' (', 1)[0].strip()
                entries.append({'rank': int(r[0]), 'entry_id': r[1].strip(), 'user': user, 'points': float(r[4]),
                                'cpt': c, 'flex': f})
        if len(r) == 11 and r[7].strip():
            slot[(r[7].strip(), r[8].strip())] = float(r[9].rstrip('%'))
    need(entries and slot, 'EMPTY_STANDINGS', cid)
    return {'rec': rec, 'entries': entries, 'n_all': len(entries) + empty, 'n_empty': empty, 'dk_pct': slot}


# ------------------------------------------------------------------------------------------ frozen stack
def frozen_stacks(phis):
    """Recompute the frozen per-lineup dupe stack with the frozen code path; verify against every stored number."""
    sc = json.loads((V2 / 'SCENARIO.json').read_text())
    R = PA.rebuild(_REPO / sc['export'], V2)
    slate = R['L']['slate']
    out = {}
    for src, sd in SHADOW.items():
        stored = json.loads((V2 / f'SHOWDOWN_ATL_NO_DUPE_STACK_{src}.json').read_text())
        sdoc = json.loads((sd / 'SHOWDOWN_ATL_NO_SHADOW_FIELD.json').read_text())
        own, arche, opt_field = AF.targets(sd, slate)
        pool = AF.Pool(slate, own)
        kidx = {k: i for i, k in enumerate(pool.keys)}
        opt_counts = collections.Counter(opt_field)
        sizes = sdoc['field_size_estimates']
        out[src] = {'own': own, 'opt_field': opt_field, 'opt_counts': opt_counts, 'arche': arche, 'pool': pool,
                    'kidx': kidx, 'sizes': sizes, 'by_phi': {}}
        for phi in phis:
            rng = np.random.default_rng(AF.SEED)
            wc, wf, _ = AF.calibrate(pool, arche, phi, rng, None)
            L, _ = AF.generate(pool, arche, wc, wf, stored['k'], phi, rng, None)
            gen = collections.Counter(L)
            sal = [AF.CAP - (pool.csal[c] + pool.sal[list(f)].sum()) for c, f in L]
            st = stored['by_phi'][str(float(phi))]
            need(len(gen) == st['distinct_lineups'], 'E3_REPRO_DISTINCT', f'{src} phi {phi}: {len(gen)} != {st["distinct_lineups"]}')
            rows_by = {}
            for cid, chosen in R['finals'].items():
                ours = [R['cands'][i] for i in chosen]
                rows = AF.stack(ours, kidx, pool, gen, stored['k'], opt_counts, len(opt_field), own, slate, sizes[cid])
                num = lambda v: v if isinstance(v, (int, float)) else 0.0
                mean = {'E1': round(float(np.mean([r['E1_independent_product'] for r in rows])), 2),
                        'E2': round(float(np.mean([r['E2_adjusted_product'] for r in rows])), 2),
                        'E3_lower_bound_mean': round(float(np.mean([num(r['E3_archetype_field']) for r in rows])), 2),
                        'E4': round(float(np.mean([r['E4_optimizer_field'] for r in rows])), 2)}
                sc_ = st['contests'][cid]
                need(mean == sc_['mean'], 'STACK_REPRO_MEAN', f'{src} phi {phi} {cid}: {mean} != {sc_["mean"]}')
                if sc_.get('lineups'):
                    need(json.loads(json.dumps(rows)) == sc_['lineups'], 'STACK_REPRO_ROWS', f'{src} phi {phi} {cid}')
                if sc_.get('top10_by_E1'):
                    top = sorted(rows, key=lambda r: -r['E1_independent_product'])[:10]
                    need(json.loads(json.dumps(top)) == sc_['top10_by_E1'], 'STACK_REPRO_TOP10', f'{src} phi {phi} {cid}')
                rows_by[cid] = list(zip(ours, rows))
            out[src]['by_phi'][phi] = {'gen': gen, 'k': stored['k'], 'rows': rows_by, 'salary_left': np.array(sal)}
    return R, slate, out


# ------------------------------------------------------------------------------------------- measurements
def _spear(a, b):
    return HC.spearman(list(a), list(b))


def m1_ownership(S, F, name_key):
    out = {}
    for src, f in F.items():
        own = f['own']
        res = {}
        for slot, col in (('CPT', 'cpt'), ('FLEX', 'flex')):
            names = sorted({n for (n, s) in S['dk_pct'] if s == slot} | {own_name for own_name in name_key})
            act = np.array([S['dk_pct'].get((n, slot), 0.0) for n in names])
            pred = np.array([own.get(name_key.get(n), {}).get(col, 0.0) for n in names])
            a, p = act / act.sum(), np.maximum(pred / pred.sum(), 1e-4)
            p = p / p.sum()
            kl = float(np.sum(np.where(a > 0, a * np.log(np.maximum(a, 1e-12) / p), 0.0)))
            res[slot] = {'n_players': len(names), 'rmse_pts': round(float(np.sqrt(np.mean((pred - act) ** 2))), 3),
                         'mae_pts': round(float(np.mean(np.abs(pred - act))), 3), 'spearman': HC.r4(_spear(pred, act)),
                         'kl_actual_vs_pred': round(kl, 4),
                         'players_above_5pct': sorted([{'player': n, 'actual': round(float(x), 2), 'pred': round(float(y), 2),
                                                        'err': round(float(y - x), 2)}
                                                       for n, x, y in zip(names, act, pred) if x >= OWN_LIST_FLOOR],
                                                      key=lambda r: -r['actual'])}
        out[src] = res
    return out


def _lineup_counts(S, name_key):
    cnt = collections.Counter()
    for e in S['entries']:
        cnt[(name_key[e['cpt']], tuple(sorted(name_key[x] for x in e['flex'])))] += 1
    return cnt


def _e_for(lineup, f, phi_block, N, slate):
    """E1/E2/E3/E4 for an arbitrary lineup, via the frozen stack function itself."""
    (r,) = AF.stack([lineup], f['kidx'], f['pool'], phi_block['gen'], phi_block['k'], f['opt_counts'],
                    len(f['opt_field']), f['own'], slate, N)
    return r


def _score(pairs):
    if not pairs:
        return None
    pred = np.array([p for p, _ in pairs], float)
    act = np.array([a for _, a in pairs], float)
    return {'n': len(pairs), 'median_abs_log_ratio': round(float(np.median(np.abs(np.log((pred + 1) / (act + 1))))), 4),
            'spearman': HC.r4(_spear(pred, act)), 'sum_pred': round(float(pred.sum()), 1), 'sum_actual': int(act.sum())}


def m2_dupes(S, cid, F, slate, name_key, our_lineups, phis):
    cnt = _lineup_counts(S, name_key)
    ours_c = collections.Counter(our_lineups)
    out = {}
    num = lambda v: v if isinstance(v, (int, float)) else 0.0
    for src, f in F.items():
        N = f['sizes'][cid]
        blk = {}
        for phi in phis:
            pb = f['by_phi'][phi]
            rows = pb['rows'][cid]
            ours = []
            for (c, fl), r in rows:
                key = (c, tuple(sorted(fl)))
                others = cnt[key] - ours_c[key]
                need(others >= 0, 'OWNER_LINEUP_NOT_IN_STANDINGS', str(key))
                ours.append((r, others))
            flagged = [(r, a) for r, a in ours if r['FLAG'] == 'E1_E3_DISAGREE_GT_2X']
            closer = [abs(math.log((num(r['E3_archetype_field']) + 1) / (a + 1))) <
                      abs(math.log((r['E1_independent_product'] + 1) / (a + 1))) for r, a in flagged]
            top = [k for k, _ in cnt.most_common(TOP_DUP)]
            trows = [(_e_for(k, f, pb, N, slate), cnt[k] - ours_c[k]) for k in top]
            sc = lambda P_, field: _score([(num(r[field]), a) for r, a in P_])
            blk[str(float(phi))] = {
                'our_lineups': {e: sc(ours, fld) for e, fld in (('E1', 'E1_independent_product'), ('E2', 'E2_adjusted_product'),
                                                               ('E3', 'E3_archetype_field'), ('E4', 'E4_optimizer_field'))},
                'top50_most_duplicated': {e: sc(trows, fld) for e, fld in (('E1', 'E1_independent_product'), ('E2', 'E2_adjusted_product'),
                                                                          ('E3', 'E3_archetype_field'), ('E4', 'E4_optimizer_field'))},
                'flag_E1_E3_disagree': {'n_flagged': len(flagged),
                                        'share_actual_closer_to_E3': None if not flagged else round(float(np.mean(closer)), 4)},
                'E3_resolution_copies': round(N / pb['k'], 2)}
        out[src] = blk
    return out


def _shape(lineups, P):
    split, qb, kd, cpw = (collections.Counter() for _ in range(4))
    for c, f in lineups:
        seats = [c] + list(f)
        atl = sum(P[x]['dk_team'] == 'ATL' for x in seats)
        split[f'{atl}-{6 - atl}'] += 1
        qb[str(sum(P[x]['position'] == 'QB' for x in seats))] += 1
        n = sum(P[x]['position'] in ('K', 'DST') for x in seats)
        kd['2+' if n >= 2 else str(n)] += 1
        cpw[str(P[c]['position'] in ('WR', 'TE') and any(P[x]['position'] == 'QB' and P[x]['dk_team'] == P[c]['dk_team'] for x in f))] += 1
    n = len(lineups)
    pc = lambda C: {k: round(100 * v / n, 2) for k, v in sorted(C.items())}
    return {'n': n, 'team_split_ATL_NO': pc(split), 'qb_count': pc(qb), 'k_plus_dst_count': pc(kd),
            'cpt_pass_catcher_with_own_qb': pc(cpw)}


def _tvd(a, b):
    return round(0.5 * sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b)) / 100, 4)


def _sal_buckets(left):
    left = np.asarray(left)
    return {'0': round(100 * float(np.mean(left == 0)), 2), '<=900': round(100 * float(np.mean((left > 0) & (left <= 900))), 2),
            '1000-1900': round(100 * float(np.mean((left >= 1000) & (left <= 1900))), 2),
            '>=2000': round(100 * float(np.mean(left >= 2000)), 2), 'mean': round(float(left.mean()), 1)}


def run(phis):
    R, slate, F = frozen_stacks(phis)
    P = slate['players']
    name_key = {}
    for k, v in P.items():
        need(v['name'] not in name_key, 'AMBIGUOUS_NAME', v['name'])
        name_key[v['name']] = k
    sal = lambda c, f: AF.CAP - (P[c]['cpt']['salary'] + sum(P[x]['flex']['salary'] for x in f))
    graded = list(csv.DictReader(open(OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv')))
    doc = {'ARTIFACT': 'ATL_NO_FIELD_ACTUAL_PREREGISTERED', 'LAYER': 'POSTGAME_ACTUAL + POSTGAME_DIAGNOSIS',
           'OBSERVATION': '#1 for every shadow ownership / field / dupe method; promotes nothing, refits nothing',
           'prereg': 'docs/NFL_SHOWDOWN_ATL_NO_POSTGAME_PREREGISTRATION.md',
           'frozen_predictions': {s: {'ownership': str((d / 'SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv').relative_to(_REPO)),
                                      'sha256': hashlib.sha256((d / 'SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv').read_bytes()).hexdigest()}
                                  for s, d in SHADOW.items()},
           'STACK_RECOMPUTE': f'verified against every stored mean / row / top-10 for phis {list(phis)}', 'contests': {}}
    loso_blocks = {}
    for cid, label in CONTESTS.items():
        S = load_standings(cid)
        mine = {r['entry_id'] for r in graded if r['contest_id'] == cid}
        found = {e['entry_id'] for e in S['entries']} & mine
        need(len(found) == len(mine), 'OWNER_ENTRIES_MISSING_FROM_STANDINGS', f'{cid} {len(found)}/{len(mine)}')
        ents = S['entries']
        lines = [(name_key[e['cpt']], tuple(sorted(name_key[x] for x in e['flex']))) for e in ents]
        cnt = collections.Counter(lines)
        ours = [lines[i] for i, e in enumerate(ents) if e['entry_id'] in mine]
        n = len(ents)
        top1 = max(1, int(math.ceil(0.01 * n)))
        order = sorted(range(n), key=lambda i: ents[i]['rank'])
        cut = ents[order[top1 - 1]]['rank']
        top_idx = [i for i in range(n) if ents[i]['rank'] <= cut]
        # owner entries' realised copies
        own_rows = []
        for i, e in enumerate(ents):
            if e['entry_id'] in mine:
                own_rows.append({'entry_id': e['entry_id'], 'rank': e['rank'], 'points': e['points'],
                                 'copies_total': cnt[lines[i]], 'copies_by_others': cnt[lines[i]] - collections.Counter(ours)[lines[i]]})
        best = min(own_rows, key=lambda r: r['rank'])
        # field comparisons
        def desc(i):
            c, f = lines[i]
            return {'rank': ents[i]['rank'], 'points': ents[i]['points'], 'captain': P[c]['name'],
                    'flex': [P[x]['name'] for x in f], 'copies': cnt[lines[i]], 'salary_left': int(sal(c, f)),
                    'cpt_own': S['dk_pct'].get((P[c]['name'], 'CPT')),
                    'log10_product_own': round(float(np.log10(max(S['dk_pct'].get((P[c]['name'], 'CPT'), 0), 1e-3) / 100)
                                                     + sum(np.log10(max(S['dk_pct'].get((P[x]['name'], 'FLEX'), 0), 1e-3) / 100) for x in f)), 3)}
        uniq_top = []
        seen = set()
        for i in order:
            if lines[i] not in seen:
                seen.add(lines[i])
                uniq_top.append(desc(i))
            if len(uniq_top) >= 10:
                break
        c = {'contest': label, 'n_entries_all': S['n_all'], 'n_filled': n, 'n_empty': S['n_empty'],
             'distinct_lineups': len(cnt), 'raw_sha256': S['rec']['sha256'],
             'winner': desc(order[0]), 'top10_distinct_lineups': uniq_top,
             'top_1pct': {'n_entries': len(top_idx), 'rank_cut': cut, 'distinct_lineups': len({lines[i] for i in top_idx}),
                          'shape': _shape([lines[i] for i in top_idx], P),
                          'median_copies': float(np.median([cnt[lines[i]] for i in top_idx]))},
             'top_100_shape': _shape([lines[i] for i in order[:100]], P),
             'owner_best': best | {'lineup': desc(next(i for i, e in enumerate(ents) if e['entry_id'] == best['entry_id']))},
             'owner_best_tied_entries_at_its_rank': sum(e['rank'] == best['rank'] for e in ents),
             'owner_realised_copies': {'entries': len(own_rows),
                                       'unique_in_field': sum(r['copies_total'] == 1 for r in own_rows),
                                       'median_copies_total': float(np.median([r['copies_total'] for r in own_rows])),
                                       'max_copies_total': max(r['copies_total'] for r in own_rows),
                                       'rows': sorted(own_rows, key=lambda r: r['rank'])}}
        lp_all = np.array([desc(i)['log10_product_own'] for i in range(n)])
        c['owner_best']['field_percentile_of_log10_product_own'] = round(float(np.mean(lp_all <= c['owner_best']['lineup']['log10_product_own'])), 4)
        c['field_log10_product_own_percentiles'] = {f'p{q}': round(float(np.percentile(lp_all, q)), 3) for q in (10, 25, 50, 75, 90)}
        c['M1_ownership'] = m1_ownership(S, F, name_key)
        c['M2_duplication'] = m2_dupes(S, cid, F, slate, name_key, ours, phis)
        lp_of = lambda cc, ff: math.log(max(S['dk_pct'].get((P[cc]['name'], 'CPT'), 0), 1e-3) / 100) + sum(
            math.log(max(S['dk_pct'].get((P[x]['name'], 'FLEX'), 0), 1e-3) / 100) for x in ff)
        oc = collections.Counter(ours)
        e1_actual_own = sum(n * math.exp(lp_of(cc, ff)) for cc, ff in ours)
        others = sum(cnt[l_] - oc[l_] for l_ in ours)
        blend = c['M2_duplication']['BLEND']['200.0']['our_lineups']
        fc = c['M2_duplication']['FC_ONLY']['200.0']['our_lineups']
        c['M2_decomposition_our_lineups'] = {
            'actual_copies_by_others': others,
            'E1_forecast_ownership': {'FC_ONLY': fc['E1']['sum_pred'], 'BLEND': blend['E1']['sum_pred']},
            'E1_ACTUAL_ownership': round(e1_actual_own, 1),
            'E4_optimizer_field': {'FC_ONLY': fc['E4']['sum_pred'], 'BLEND': blend['E4']['sum_pred']},
            'ownership_forecast_factor': {k: (round(e1_actual_own / v, 2) if v >= 0.05 else 'FORECAST_ZERO') for k, v in
                                          (('FC_ONLY', fc['E1']['sum_pred']), ('BLEND', blend['E1']['sum_pred']))},
            'independence_factor': round(others / max(e1_actual_own, 1e-9), 2),
            'MEANING': ('actual / E1(actual ownership) is what the independence assumption misses for lineups like ours; '
                        'E1(actual) / E1(forecast) is what the ownership forecast misses. Their product is the total miss.')}
        field_shape = _shape(lines, P)
        opt_shape = {s: _shape(F[s]['opt_field'], P) for s in F}
        c['M3_archetypes'] = {'field': field_shape, 'optimizer_prior': opt_shape,
                              'tvd_field_vs_prior': {s: {k: _tvd(field_shape[k], opt_shape[s][k])
                                                         for k in ('team_split_ATL_NO', 'qb_count', 'k_plus_dst_count', 'cpt_pass_catcher_with_own_qb')}
                                                     for s in F}}
        c['M4_salary_left'] = {'field': _sal_buckets([sal(*l) for l in lines]),
                               'top_1pct': _sal_buckets([sal(*lines[i]) for i in top_idx]),
                               'optimizer_field': {s: _sal_buckets([sal(cc, ff) for cc, ff in F[s]['opt_field']]) for s in F},
                               'archetype_field': {s: {str(float(phi)): _sal_buckets(F[s]['by_phi'][phi]['salary_left']) for phi in phis} for s in F}}
        cpos = lambda idx: {k: round(100 * v / len(idx), 2) for k, v in
                            sorted(collections.Counter(P[lines[i][0]]['position'] for i in idx).items())}
        U = list(cnt)
        lp = np.array([np.log(max(S['dk_pct'].get((P[cc]['name'], 'CPT'), 0), 1e-3) / 100)
                       + sum(np.log(max(S['dk_pct'].get((P[x]['name'], 'FLEX'), 0), 1e-3) / 100) for x in ff) for cc, ff in U])
        lc = np.array([np.log(max(S['dk_pct'].get((P[cc]['name'], 'CPT'), 0), 1e-3) / 100) for cc, _ in U])
        lf = lp - lc
        y = np.log(np.array([cnt[u] for u in U], float))
        r2 = lambda x: round(float(np.corrcoef(x, y)[0, 1] ** 2), 4)
        c['M5_conflicts'] = {'CF1_cpt_position': {'field': cpos(range(n)), 'top_1pct': cpos(top_idx)},
                             'CF2_r2_log_product_vs_log_copies_unique_lineups': r2(lp),
                             'CF3_r2': {'cpt_only': r2(lc), 'flex_product_only': r2(lf)},
                             'NOTE': 'one slate; observed unique lineups only (copies >= 1)'}
        doc['contests'][cid] = c
        # LOSO export in the archived slates' shapes (nfl/postgame/showdown_history): actual ownership, observed lineups
        hist_dir = _REPO / 'nfl/postgame/showdown_history'
        with open(hist_dir / f'UNIQUE_LINEUPS_ATL_NO_{cid}.csv', 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['cpt', 'flex1', 'flex2', 'flex3', 'flex4', 'flex5', 'actual_copies', 'observed', 'log_prod_own', 'E1'])
            for (cc, ff), k in sorted(cnt.items(), key=lambda t: -t[1]):
                l_ = math.log(max(S['dk_pct'].get((P[cc]['name'], 'CPT'), 0), 1e-3) / 100) + sum(
                    math.log(max(S['dk_pct'].get((P[x]['name'], 'FLEX'), 0), 1e-3) / 100) for x in ff)
                w.writerow([P[cc]['name'], *[P[x]['name'] for x in ff], k, 1, round(l_, 4), round(n * math.exp(l_), 4)])
        pos_of = lambda nm: P[name_key[nm]]['position'] if nm in name_key else 'UNMAPPED'
        fs = c['M3_archetypes']['field']
        loso_blocks[cid] = {'construction': {'field': {
            'team_split_away_home': {'pct': fs['team_split_ATL_NO']}, 'qb_count': {'pct': fs['qb_count']},
            'k_plus_dst_count': {'pct': {k: v for k, v in fs['k_plus_dst_count'].items()}},
            'cpt_position': {'pct': c['M5_conflicts']['CF1_cpt_position']['field']}}},
            'ownership': {'players': [{'player': nm, 'position': pos_of(nm), 'dk_cpt_pct': S['dk_pct'].get((nm, 'CPT'), 0.0),
                                       'dk_flex_pct': S['dk_pct'].get((nm, 'FLEX'), 0.0)}
                                      for nm in sorted({n_ for (n_, _) in S['dk_pct']})]},
            'contest_id': cid, 'raw': {'sha256': S['rec']['sha256']},
            'unique_lineups_csv': f'nfl/postgame/showdown_history/UNIQUE_LINEUPS_ATL_NO_{cid}.csv'}
    (_REPO / 'nfl/postgame/showdown_history/ATL_NO_LOSO_BLOCKS.json').write_text(json.dumps(
        {'ARTIFACT': 'ATL_NO_LOSO_BLOCKS', 'NOTE': 'k_plus_dst_count buckets 0/1/2+; team split = ATL-NO (ATL is away)',
         'contests': loso_blocks}, indent=1, default=float))
    doc['written_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    p = OUT / 'ATL_NO_FIELD_ACTUAL_PREREGISTERED.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    return p, doc


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phis', type=float, nargs='+', default=[200.0])
    a = ap.parse_args()
    p, doc = run(a.phis)
    print(p)
    for cid, c in doc['contests'].items():
        print(cid, c['contest'], 'filled', c['n_filled'], 'distinct', c['distinct_lineups'])
        print('  winner', c['winner'])
        print('  owner best', {k: v for k, v in c['owner_best'].items() if k != 'lineup'}, 'copies', c['owner_best']['lineup']['copies'])
        print('  owner copies', {k: v for k, v in c['owner_realised_copies'].items() if k != 'rows'})
        for s, r in c['M1_ownership'].items():
            print('  M1', s, {sl: {k: v for k, v in x.items() if k != 'players_above_5pct'} for sl, x in r.items()})
        for s, r in c['M2_duplication'].items():
            print('  M2', s, json.dumps(r)[:700])
        print('  M3 tvd', c['M3_archetypes']['tvd_field_vs_prior'])
        print('  M4', c['M4_salary_left']['field'], c['M4_salary_left']['optimizer_field'])
        print('  M5', c['M5_conflicts'])
