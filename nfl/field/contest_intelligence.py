#!/usr/bin/env python3.12
"""Historical contest intelligence: what the REAL field built, by cohort, from complete DK standings.

    python3.12 nfl/field/contest_intelligence.py build

POSTGAME ONLY. This reads finished contests. It feeds the DFS decision / field layer and is never an input
to a football projection; nothing in nfl/tools/proj_v1.py or nfl/sim reads it.

Inputs: the ingested standings (nfl/postgame/raw/2026W4_standings*/, sha-checked) and the LOCKED slate
state from git (salaries, positions, clubs: classic_week.locked()). Each contest is kept separate.

Per lineup: QB stack (same-club WR/TE, and separately WR/TE/RB), bring-back (opponent skill players in the
QB's game), FLEX position, salary used/left, summed and geometric ownership, duplication count.
Per cohort (owner, field, top 0.1/0.5/1/5/10%, top 10/50/100, winner): construction distributions and
player ownership COUNTED FROM THE LINEUPS (DK's %Drafted is the cross-check).

One slate is HISTORICAL_SAMPLE_SMALL: these are observations and hypotheses, never rules.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402
from nfl.postgame import classic_week as W  # noqa: E402

OUT = _REPO / 'nfl/field/history/2026W4_EARLY'
CAP = 50000
CONTEST_META = {'196208416': {'label': 'MAX150', 'name': 'NFL $15K mini-MAX [150 Entry Max] (Early Only)', 'max_entries': 150},
                '196208417': {'label': 'MAX20', 'name': 'NFL $3K Quarter Jukebox [Just $0.25!] (Early Only)', 'max_entries': 20},
                '196208418': {'label': 'MAX3', 'name': 'NFL $1K Dime Package [Just $0.10!] (Early Only)', 'max_entries': 3}}


def _files():
    out = []
    for pv in sorted(_REPO.glob('nfl/postgame/raw/2026W4_standings*/PROVENANCE.jsonl')):
        for ln in pv.read_text().splitlines():
            r = json.loads(ln)
            p = _REPO / r['file']
            if hashlib.sha256(p.read_bytes()).hexdigest() != r['sha256']:
                raise SystemExit(f'REFUSED: {p} changed since ingest')
            out.append((p, r))
    return out


def features(lineup, pool, opp_of, own):
    slots = [(s, n) for s, n in lineup]
    names = [n for _s, n in slots]
    miss = [n for n in names if n not in pool]
    if miss:
        return None, miss
    P = [pool[n] for n in names]
    qb = next((pool[n] for s, n in slots if s == 'QB'), None)
    flex = next((pool[n] for s, n in slots if s == 'FLEX'), None)
    dst = next((pool[n] for s, n in slots if s == 'DST'), None)
    stack_wt = stack_wtr = bring = 0
    if qb:
        for p in P:
            if p is qb or p['position'] == 'DST':
                continue
            if p['team'] == qb['team']:
                stack_wt += p['position'] in ('WR', 'TE')
                stack_wtr += p['position'] in ('WR', 'TE', 'RB')
            elif p['team'] == opp_of.get(qb['team']):
                bring += p['position'] in ('WR', 'TE', 'RB')
    sal = sum(p['salary'] for p in P)
    ow = [max(own.get(n, 0.0), 0.01) for n in names]
    games = collections.Counter(tuple(sorted((p['team'], opp_of.get(p['team'], '?')))) for p in P)
    return {'qb': qb['name'] if qb else None, 'qb_stack_wr_te': stack_wt, 'qb_stack_incl_rb': stack_wtr,
            'bring_back': bring, 'flex_pos': flex['position'] if flex else None,
            'salary': sal, 'salary_left': CAP - sal,
            'qb_dst_same_team': bool(qb and dst and qb['team'] == dst['team']),
            'rb_dst_same_team': any(p['position'] == 'RB' and dst and p['team'] == dst['team'] for p in P),
            'sum_own': round(sum(ow), 2), 'geo_own': round(math.exp(sum(math.log(x) for x in ow) / len(ow)), 3),
            'n_under_5pct': sum(1 for x in ow if x < 5), 'n_over_20pct': sum(1 for x in ow if x >= 20),
            'max_game_players': max(games.values())}, []


def dist(rows, key, cats=None):
    c = collections.Counter(r[key] for r in rows)
    n = max(1, len(rows))
    keys = cats or sorted(c, key=lambda x: (str(type(x)), x))
    return {str(k): round(100.0 * c.get(k, 0) / n, 1) for k in keys}


def cohort_summary(rows):
    if not rows:
        return {'n': 0}
    n = len(rows)
    return {'n': n,
            'qb_stack_wr_te_pct': dist(rows, 'qb_stack_wr_te', [0, 1, 2, 3, 4]),
            'qb_stack_incl_rb_pct': dist(rows, 'qb_stack_incl_rb', [0, 1, 2, 3, 4]),
            'bring_back_pct': dist(rows, 'bring_back', [0, 1, 2, 3]),
            'flex_pos_pct': dist(rows, 'flex_pos', ['RB', 'WR', 'TE']),
            'mean_salary_left': round(sum(r['salary_left'] for r in rows) / n, 0),
            'pct_full_salary': round(100.0 * sum(r['salary_left'] == 0 for r in rows) / n, 1),
            'mean_sum_own': round(sum(r['sum_own'] for r in rows) / n, 1),
            'mean_geo_own': round(sum(r['geo_own'] for r in rows) / n, 2),
            'qb_dst_same_team_pct': round(100.0 * sum(r['qb_dst_same_team'] for r in rows) / n, 1),
            'rb_dst_same_team_pct': round(100.0 * sum(r['rb_dst_same_team'] for r in rows) / n, 1),
            'mean_points': round(sum(r['points'] for r in rows) / n, 2)}


def build():
    lo = W.locked()
    if lo.state.value != 'PASS':
        return lo
    st = lo.value['state']
    pool = {v['name']: v for v in st['players'].values()}
    opp_of = {}
    for g in st['games'].values():
        opp_of[g['away']], opp_of[g['home']] = g['home'], g['away']
    ours = {r[0] for r in lo.value['upload']}
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'ARTIFACT': 'CONTEST_INTELLIGENCE', 'slate': '2026W4 Early Only (8 games)', 'sport': 'NFL', 'type': 'CLASSIC',
              'HISTORICAL_SAMPLE_SMALL': 'one Classic slate, three contests; zero Showdown contests on file',
              'POSTGAME_ONLY': 'feeds the field/decision layer; never a football-projection input', 'contests': {}}
    for p, rec in _files():
        rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
        ent = [r for r in rows if r.get('EntryId')]
        own_dk = collections.defaultdict(float)
        fpts = {}
        for r in rows:
            if r.get('Player'):
                own_dk[r['Player'].strip()] += float((r['%Drafted'] or '0').rstrip('%'))
                if r.get('FPTS') not in (None, ''):
                    fpts[r['Player'].strip()] = float(r['FPTS'])
        mine = [r for r in ent if r['EntryId'] in ours]
        up = {r[0]: r[2] for r in lo.value['upload']}
        cid = up[mine[0]['EntryId']]
        meta = CONTEST_META.get(cid, {'label': cid})
        n_all = len(ent)
        lines, unresolved = [], collections.Counter()
        for r in ent:
            lu = W.parse_lineup(r['Lineup'])
            if not lu:
                continue
            f, miss = features(lu, pool, opp_of, own_dk)
            if f is None:
                for m in miss:
                    unresolved[m] += 1
                continue
            f.update({'rank': int(r['Rank']), 'entry_id': r['EntryId'], 'user': (r['EntryName'] or '').split(' (')[0],
                      'points': float(r['Points']), 'ours': r['EntryId'] in ours,
                      'players': tuple(sorted(n for _s, n in lu)), 'fee': None})
            lines.append(f)
        dupc = collections.Counter(f['players'] for f in lines)
        for f in lines:
            f['dup_count'] = dupc[f['players']]
        lines.sort(key=lambda f: f['rank'])
        nf = len(lines)
        cut = lambda q: [f for f in lines if f['rank'] <= max(1, int(round(q * n_all)))]
        cohorts = {'owner': [f for f in lines if f['ours']], 'field': lines,
                   'top_0.1pct': cut(0.001), 'top_0.5pct': cut(0.005), 'top_1pct': cut(0.01), 'top_5pct': cut(0.05),
                   'top_10pct': cut(0.10), 'top_10': [f for f in lines if f['rank'] <= 10],
                   'top_50': [f for f in lines if f['rank'] <= 50], 'top_100': [f for f in lines if f['rank'] <= 100],
                   'winner': [f for f in lines if f['rank'] == 1]}
        con = {k: cohort_summary(v) for k, v in cohorts.items()}
        # ownership by cohort, counted from lineups
        players = sorted(set(n for f in lines for n in f['players']))
        own_rows = []
        for nm in players:
            row = {'player': nm, 'team': pool[nm]['team'], 'position': pool[nm]['position'], 'salary': pool[nm]['salary'],
                   'final_fpts': fpts.get(nm), 'dk_pct_drafted': round(own_dk.get(nm, 0.0), 2)}
            for k, v in cohorts.items():
                row[f'own_{k}'] = round(100.0 * sum(nm in f['players'] for f in v) / max(1, len(v)), 2)
            row['owner_minus_field'] = round(row['own_owner'] - row['own_field'], 2)
            row['top1_minus_field'] = round(row['own_top_1pct'] - row['own_field'], 2)
            own_rows.append(row)
        own_rows.sort(key=lambda r: -r['own_field'])
        lab = meta['label']
        with (OUT / f'{lab}_OWNERSHIP_BY_COHORT.csv').open('w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(own_rows[0]))
            w.writeheader()
            w.writerows(own_rows)
        keep = ('rank', 'entry_id', 'user', 'points', 'ours', 'qb', 'qb_stack_wr_te', 'qb_stack_incl_rb', 'bring_back',
                'flex_pos', 'salary', 'salary_left', 'sum_own', 'geo_own', 'n_under_5pct', 'n_over_20pct',
                'max_game_players', 'qb_dst_same_team', 'rb_dst_same_team', 'dup_count')
        with (OUT / f'{lab}_LINEUP_FEATURES.csv').open('w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(keep + ('players',))
            for f in lines:
                w.writerow([f[k] for k in keep] + [' | '.join(f['players'])])
        pairs = collections.Counter()
        for f in cohorts['top_1pct']:
            ps = f['players']
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    pairs[(ps[i], ps[j])] += 1
        dup_by = collections.Counter(min(f['dup_count'], 10) for f in lines)
        report['contests'][cid] = {
            **meta, 'field_size_all_entries': n_all, 'filled_lineups': nf, 'unresolved_names': dict(unresolved),
            'ownership_counted_vs_dk_max_abs_diff': round(max(abs(r['own_field'] * nf / n_all - r['dk_pct_drafted'])
                                                              for r in own_rows), 2),
            'construction_by_cohort': con,
            'top_1pct_most_common_pairs': [[list(k), v] for k, v in pairs.most_common(15)],
            'field_duplication': {'lineups_by_copy_count_capped_10': {str(k): v for k, v in sorted(dup_by.items())},
                                  'share_of_entries_duplicated': round(100.0 * sum(1 for f in lines if f['dup_count'] > 1) / nf, 2),
                                  'duplication_by_salary_left': {
                                      b: round(100.0 * sum(1 for f in lines if lo_ <= f['salary_left'] <= hi and f['dup_count'] > 1)
                                               / max(1, sum(1 for f in lines if lo_ <= f['salary_left'] <= hi)), 2)
                                      for b, lo_, hi in (('0', 0, 0), ('100-500', 100, 500), ('600-1500', 600, 1500), ('1600+', 1600, 99999))}},
            'files': [str((OUT / f'{lab}_{x}').relative_to(_REPO)) for x in ('OWNERSHIP_BY_COHORT.csv', 'LINEUP_FEATURES.csv')]}
    report['HYPOTHESES_NOT_RULES'] = {
        'H1': 'did our portfolio systematically overvalue TE FLEX?',
        'H2': 'did we underuse bring-backs relative to tail constructions?',
        'H3': 'did we concentrate exposure in uncertain value/role assumptions?',
        'H4': 'did ownership-aware leverage add value, or was it projection disagreement?',
        'H5': 'did nominally unique lineups express too few distinct hypotheses?',
        'H6': 'did our tails separate volatile depth plays from high-ceiling cores?',
        'STATUS': 'each needs many slates; one slate cannot confirm or reject any of them'}
    (OUT / 'CONTEST_INTELLIGENCE_2026W4_EARLY.json').write_text(json.dumps(report, indent=1, default=str))
    return Outcome.ok('CONTEST_INTELLIGENCE_BUILT', report, f"{len(report['contests'])} contests")


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code, o.detail)
