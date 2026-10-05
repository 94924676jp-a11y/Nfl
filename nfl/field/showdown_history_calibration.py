#!/usr/bin/env python3.12
"""Showdown ownership / field / duplication calibration on two HISTORICAL DK Showdown standings files.

    nice -n 10 python3.12 nfl/field/showdown_history_calibration.py

RESEARCH ONLY. POSTGAME ONLY. Never a football input; nothing in the projection or simulator reads this,
and nothing here is promoted. Two contests on two slates are TWO OBSERVATIONS: games are not independent,
a single contest is one draw of one field's behaviour, and nothing below is a rule.

INPUTS (all read-only; the raw standings are sha256-checked against their PROVENANCE.jsonl):
  PIT@CLE 2026-10-01, contest 196187080  nfl/postgame/raw/showdown_history/196187080_PIT_CLE/
  PHI@CHI 2026-09-28, contest 196036243  nfl/postgame/raw/showdown_history/196036243_PHI_CHI/
  PIT@CLE player metadata: the owner's DKEntries export (DK pool: salaries, positions, clubs) parsed with
    nfl/tools/showdown_to_portfolio.s1_ingest / s2_slate_identity (imported, not re-implemented)
  PIT@CLE public projection (E4 only): THIRDPARTY FantasyCruncher CONTEXT_ONLY csv
  PHI@CHI player metadata: nflverse roster_weekly (no salary file exists -> every salary metric for PHI@CHI is
    NOT_AVAILABLE, and so are E3 / E4, which need salaries)

WHAT IS ASSUMED, AND ITS SOURCE (no constant here is fitted):
  - ETR seeds in E2: imported from nfl/field/showdown_archetype_field.CORR_SEED (ETR Showdown 101, SEEDED_NOT_FITTED)
  - E3 / E4 sizes and seeds: imported from the two field modules (K, SEED, PHI_REPORTED, SIGMAS)
  - verdict tolerances (TOL below) are ASSUMED and DECLARED HERE BEFORE ANY RESULT WAS READ; they are reporting
    margins for words like "~90%", not estimates
  - descriptive reporting bins (salary rank bins, the 10% FLEX floor in the CPT=0.5xFLEX check) are reporting
    choices, labelled, not fitted

Every stage asserts non-empty, schema-correct output and raises ShowdownHistoryError(<NAMED CODE>) otherwise.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from nfl.field import showdown_archetype_field as AF  # noqa: E402
from nfl.field import showdown_shadow_field as SF  # noqa: E402

LABEL = 'RESEARCH_ONLY_POSTGAME_NOT_PROMOTED'
OUT = _REPO / 'nfl/postgame/showdown_history'
RAW = _REPO / 'nfl/postgame/raw/showdown_history'
CAP = S.SALARY_CAP
EXPECTED_HEADER = ['Rank', 'EntryId', 'EntryName', 'TimeRemaining', 'Points', 'Lineup', '', 'Player',
                   'Roster Position', '%Drafted', 'FPTS']
PIT_EXPORT = _REPO / 'nfl/dfs/salaries/raw/DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv'
PIT_FC = _REPO / 'nfl/dfs/salaries/raw/THIRDPARTY_showdown_PIT_CLE_2026W4_CONTEXT_ONLY.csv'
PIT_INACTIVES = _REPO / 'nfl/dfs/salaries/raw/OFFICIAL_INACTIVES_PIT_CLE_2026W4.json'
ROSTER = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/roster_weekly_2026.0f72f882f3974ff2.csv'
LEDGER = _REPO / 'nfl/research/external/2026-10-05_cycle1/ledger.jsonl'
METHODS = _REPO / 'nfl/research/external/2026-10-05_addendum/METHOD_CANDIDATES.json'
ATL_NO_STACKS = [_REPO / 'nfl/dfs/salaries/showdown_atl_no/BASE/SHOWDOWN_ATL_NO_DUPE_STACK_BLEND.json',
                 _REPO / 'nfl/dfs/salaries/showdown_atl_no/BASE/SHOWDOWN_ATL_NO_DUPE_STACK_BLEND_SAL_FC08_90PCT_LE_500.json',
                 _REPO / 'nfl/dfs/salaries/showdown_atl_no/FANT_OUT/SHOWDOWN_ATL_NO_DUPE_STACK_BLEND.json',
                 _REPO / 'nfl/dfs/salaries/showdown_atl_no/FANT_OUT/SHOWDOWN_ATL_NO_DUPE_STACK_BLEND_SAL_FC08_90PCT_LE_500.json']
ATL_NO_TWO_ENTRY_CONTEST = '196285161'

#: ASSUMED reporting tolerances, declared before any result was read. Not estimates.
TOL = {
    'OWNERSHIP_POINT_PCT_PTS': 2.0,     # source: ledger DATA-05 'falsification': "differ materially (>2 pts)"
    'RECOUNT_FLAG_PCT_PTS': 0.5,        # source: task instruction (flag recomputed-vs-DK diff > 0.5 pts)
    'SHARE_CLAIM_PCT_PTS': 5.0,         # ASSUMED: margin for "~90%" / "~80%" style share claims
    'R2_CLAIM_ABS': 0.05,               # ASSUMED: margin for an R^2 claim (.16 / .43 / .55)
    'LOG_EFFECT_NEGLIGIBLE': 0.10,      # ASSUMED: |log ratio| < 0.10 (~10%) reads as "hardly" any effect
    'E1_TOP_DECILE_BIAS_RATIO': 2.0,    # source: task instruction (falsify E1 if biased > 2x in top chalk decile)
    'E1_E3_FLAG_RATIO': AF.FLAG_RATIO,  # source: showdown_archetype_field.FLAG_RATIO (2.0)
}
SAL_BUCKETS = (('0', 0, 0), ('100-500', 100, 500), ('600-900', 600, 900), ('1000-1900', 1000, 1900),
               ('2000-2900', 2000, 2900), ('3000+', 3000, CAP))
#: descriptive salary-rank bins (reporting choice, not fitted)
SAL_RANK_BINS = (('rank_1-5', 1, 5), ('rank_6-10', 6, 10), ('rank_11-20', 11, 20), ('rank_21+', 21, 10 ** 6))
CPT_HALF_RULE_FLEX_FLOOR = 10.0     # reporting choice: players with FLEX %Drafted >= 10 (descriptive)
DST_NAMES = {'PHI_CHI': {'Eagles': 'PHI', 'Bears': 'CHI'}}   # source: task instruction (DK DST naming)
SUFFIX = re.compile(r'\s+(Jr\.?|Sr\.?|II|III|IV|V)$')

CONTESTS = [
    {'label': 'PIT_CLE', 'contest_id': '196187080', 'dir': RAW / '196187080_PIT_CLE', 'metadata': 'DK_POOL',
     'nflverse_game_id': '2026_04_PIT_CLE'},
    {'label': 'PHI_CHI', 'contest_id': '196036243', 'dir': RAW / '196036243_PHI_CHI', 'metadata': 'NFLVERSE_ROSTER',
     'nflverse_game_id': '2026_03_PHI_CHI', 'roster_week': '3'},
]


class ShowdownHistoryError(RuntimeError):
    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def need(cond, code, detail=''):
    if not cond:
        raise ShowdownHistoryError(code, detail)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def rel(p):
    try:
        return str(pathlib.Path(p).relative_to(_REPO))
    except ValueError:
        return str(p)


def NA(reason):
    return {'status': 'NOT_AVAILABLE', 'reason': reason}


def r4(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 4)


# ------------------------------------------------------------------------------------------- stage 1: raw
def load_raw(c):
    pv = c['dir'] / 'PROVENANCE.jsonl'
    need(pv.exists() and pv.stat().st_size > 0, 'PROVENANCE_ABSENT', str(pv))
    recs = [json.loads(x) for x in pv.read_text().splitlines() if x.strip()]
    need(len(recs) == 1, 'PROVENANCE_NOT_ONE_RECORD', f'{pv}: {len(recs)} records')
    rec = recs[0]
    need(rec.get('contest_id') == c['contest_id'], 'PROVENANCE_CONTEST_MISMATCH', f"{rec.get('contest_id')}")
    p = _REPO / rec['file']
    need(p.exists() and p.stat().st_size > 0, 'RAW_STANDINGS_EMPTY', str(p))
    h = sha(p)
    need(h == rec['sha256'], 'RAW_SHA256_MISMATCH', f'{p}: {h} != {rec["sha256"]}')
    rows = list(csv.reader(p.open(newline='', encoding='utf-8-sig')))
    need(rows, 'STANDINGS_NO_ROWS', str(p))
    need(rows[0] == EXPECTED_HEADER, 'STANDINGS_SCHEMA', f'header {rows[0]}')
    away, home = rec['game'].split('@')
    entries, empty, slot_rows = [], 0, {}
    for i, r in enumerate(rows[1:], start=2):
        need(len(r) in (9, 11), 'STANDINGS_ROW_WIDTH', f'line {i}: {len(r)} columns')
        if r[1].strip():
            lu = r[5].strip()
            if not lu:
                empty += 1
                continue
            m = re.match(r'^(.*) \((\d+)/(\d+)\)$', r[2].strip())
            user, nmax = (m.group(1), int(m.group(3))) if m else (r[2].strip(), 1)
            cpt, flex = parse_lineup(lu, i)
            entries.append({'rank': int(r[0]), 'entry_id': r[1].strip(), 'user': user, 'max_entries': nmax,
                            'points': float(r[4]), 'cpt': cpt, 'flex': flex})
        if len(r) == 11 and r[7].strip():
            key = (r[7].strip(), r[8].strip())
            need(key[1] in ('CPT', 'FLEX'), 'STANDINGS_SLOT_UNKNOWN', f'line {i}: {key}')
            need(key not in slot_rows, 'STANDINGS_PLAYER_SLOT_TWICE', f'line {i}: {key}')
            slot_rows[key] = {'pct': float(r[9].rstrip('%')), 'fpts': float(r[10]) if r[10] not in ('', None) else None}
    need(entries, 'STANDINGS_NO_FILLED_ENTRIES', str(p))
    need(slot_rows, 'STANDINGS_OWNERSHIP_BLOCK_EMPTY', str(p))
    n_all = len(entries) + empty
    return {'rec': rec, 'path': p, 'sha256': h, 'away': away, 'home': home, 'entries': entries,
            'n_all_entries': n_all, 'n_empty_lineup': empty, 'n_filled': len(entries), 'dk_slot': slot_rows}


def parse_lineup(s, line):
    toks = re.split(r'(?:^|\s+)(CPT|FLEX)\s+', ' ' + s)
    need(toks[0].strip() == '', 'LINEUP_PARSE', f'line {line}: leading text {toks[0]!r}')
    slots, names = toks[1::2], [t.strip() for t in toks[2::2]]
    need(slots == ['CPT'] + ['FLEX'] * 5, 'LINEUP_PARSE', f'line {line}: slots {slots}')
    need(all(names) and len(set(names)) == 6, 'LINEUP_PARSE', f'line {line}: names {names}')
    return names[0], tuple(sorted(names[1:]))


# -------------------------------------------------------------------------------------- stage 2: metadata
def pit_metadata():
    ing = S.s1_ingest(PIT_EXPORT)
    need(ing.state.value == 'PASS', 'PIT_EXPORT_INGEST_' + ing.code, ing.detail)
    si = S.s2_slate_identity(ing.value['pool'])
    need(si.state.value == 'PASS', 'PIT_SLATE_IDENTITY_' + si.code, si.detail)
    slate = si.value
    by_name = collections.defaultdict(list)
    for k, v in slate['players'].items():
        by_name[v['name']].append(k)
    need(all(len(v) == 1 for v in by_name.values()), 'PIT_POOL_NAME_NOT_UNIQUE',
         str([n for n, v in by_name.items() if len(v) > 1]))
    meta = {n: {'key': v[0], 'team': slate['players'][v[0]]['dk_team'], 'position': slate['players'][v[0]]['position'],
                'flex_salary': slate['players'][v[0]]['flex']['salary'], 'cpt_salary': slate['players'][v[0]]['cpt']['salary'],
                'source': 'DK_POOL'} for n, v in by_name.items()}
    entry_ids = {e['entry_id'] for e in ing.value['entries'] if e['contest_id'] == CONTESTS[0]['contest_id']}
    contest_names = sorted({e['contest_name'] for e in ing.value['entries'] if e['contest_id'] == CONTESTS[0]['contest_id']})
    need(len(contest_names) == 1, 'PIT_CONTEST_NAME_NOT_UNIQUE', str(contest_names))
    return meta, slate, {'export': rel(PIT_EXPORT), 'sha256': sha(PIT_EXPORT), 'contest_names': contest_names,
                         'owner_entry_ids': entry_ids, 'away': slate['away'], 'home': slate['home']}


def phi_metadata(names, week):
    rows = list(csv.DictReader(ROSTER.open(newline='', encoding='utf-8')))
    need(rows, 'ROSTER_EMPTY', str(ROSTER))
    for col in ('team', 'week', 'position', 'full_name', 'football_name', 'last_name', 'gsis_id', 'status'):
        need(col in rows[0], 'ROSTER_SCHEMA', col)

    def index(wk):
        ix = collections.defaultdict(set)
        for r in rows:
            if r['team'] in ('PHI', 'CHI') and r['week'] == wk:
                v = (r['team'], r['position'], r['gsis_id'], r['status'])
                ix[r['full_name']].add(v)
                ix[f"{r['football_name']} {r['last_name']}"].add(v)
                ix[SUFFIX.sub('', r['full_name'])].add(v)
        return ix
    ix = index(week)
    need(ix, 'ROSTER_NO_PHI_CHI_ROWS', f'week {week}')
    meta, unmapped, ambiguous = {}, [], []
    for n in sorted(names):
        if n in DST_NAMES['PHI_CHI']:
            meta[n] = {'team': DST_NAMES['PHI_CHI'][n], 'position': 'DST', 'source': 'DST_NAME_TASK_INSTRUCTION'}
            continue
        hit = ix.get(n) or ix.get(SUFFIX.sub('', n))
        if not hit:
            unmapped.append(n)
            meta[n] = {'team': None, 'position': 'UNMAPPED', 'source': 'UNMAPPED'}
        elif len({(t, p) for t, p, _g, _s in hit}) > 1:
            ambiguous.append({'name': n, 'candidates': sorted(hit)})
            meta[n] = {'team': None, 'position': 'UNMAPPED', 'source': 'AMBIGUOUS'}
        else:
            t, p, g, s = sorted(hit)[0]
            meta[n] = {'team': t, 'position': p, 'gsis_id': g, 'roster_status': s, 'source': f'NFLVERSE_ROSTER_WEEK_{week}'}
    # the other week, as a stability check (the task named week 4; the game id says week 3)
    other = '4' if week == '3' else '3'
    ix2 = index(other)
    diff = []
    for n, m in meta.items():
        if m['source'].startswith('NFLVERSE'):
            h2 = ix2.get(n) or ix2.get(SUFFIX.sub('', n))
            if not h2 or {(t, p) for t, p, _g, _s in h2} != {(m['team'], m['position'])}:
                diff.append(n)
    # candidates for each unmapped name, by last name on PHI/CHI in this week (for the owner to confirm; NOT used)
    cands = {}
    for n in unmapped:
        ln = n.split()[-1]
        cands[n] = sorted({(r['full_name'], r['team'], r['position'], r['status']) for r in rows
                           if r['team'] in ('PHI', 'CHI') and r['week'] == week and r['last_name'] == ln})
    return meta, {'roster_file': rel(ROSTER), 'sha256': sha(ROSTER), 'week_used': week,
                  'week_note': ('nflverse game id 2026_03_PHI_CHI (present in this repository) places the 2026-09-28 '
                                'game in week 3; the task named week 4. Week 3 is used; the mapping is re-checked '
                                f'against week {other}.'),
                  'names_whose_team_or_position_differs_in_week_' + other: diff,
                  'unmapped': unmapped, 'ambiguous': ambiguous,
                  'unmapped_lastname_candidates_NOT_USED': cands,
                  'UNMAPPED_POLICY': ('an unmapped name keeps position UNMAPPED and team None; it is never guessed. '
                                      'Lineup features that need its team/position exclude that lineup and the '
                                      'exclusion is counted')}


def pit_favorite():
    rows = list(csv.reader(PIT_FC.open(newline='', encoding='utf-8-sig')))
    hdr = next((i for i, r in enumerate(rows) if 'Player' in r and 'VegasPts' in r), None)
    need(hdr is not None, 'FC_SCHEMA', 'no Player/VegasPts header')
    H = {h: j for j, h in enumerate(rows[hdr])}
    tt = collections.defaultdict(set)
    for r in rows[hdr + 1:]:
        # DST rows print the OPPONENT's implied total (measured in this file), so they are skipped
        if len(r) >= len(H) and r[H['Team']] and r[H['Pos']] != 'DST':
            tt[r[H['Team']]].add(float(r[H['VegasPts']]))
    need(len(tt) == 2 and all(len(v) == 1 for v in tt.values()), 'FC_TEAM_TOTALS_NOT_CLEAN', str(dict(tt)))
    t = {k: v.pop() for k, v in tt.items()}
    fav = max(t, key=t.get) if len(set(t.values())) == 2 else None
    return {'implied_team_totals': t, 'favorite': fav,
            'source': (f'{rel(PIT_FC)} column VegasPts (third-party CONTEXT_ONLY file; implied team total as '
                       'printed there; DST rows carry the opponent total and are skipped). favorite = club with the '
                       'higher implied total. No spread is invented.')}


# ------------------------------------------------------------------------------------------ helpers
def rankdata(a):
    a = np.asarray(a, dtype=float)
    o = np.argsort(a, kind='mergesort')
    r = np.empty(len(a))
    r[o] = np.arange(1, len(a) + 1)
    s = a[o]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            r[o[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3:
        return None
    rx, ry = rankdata(x), rankdata(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def ols(y, cols, names):
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in cols])
    need(len(y) > X.shape[1], 'OLS_TOO_FEW_ROWS', f'n={len(y)}, k={X.shape[1]}')
    keep = [0] + [j for j in range(1, X.shape[1]) if X[:, j].std() > 0]
    X = X[:, keep]
    nm = ['intercept'] + [names[j - 1] for j in keep[1:]]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n, k = X.shape
    XtXi = np.linalg.pinv(X.T @ X)
    V = XtXi @ (X.T * (e ** 2)) @ X @ XtXi * n / (n - k)
    se = np.sqrt(np.diag(V))
    r2 = 1 - float(e @ e) / float(((y - y.mean()) ** 2).sum())
    return {'n': n, 'r2': r4(r2), 'coef': {a: r4(b) for a, b in zip(nm, beta)},
            'hc1_se': {a: r4(b) for a, b in zip(nm, se)},
            'dropped_constant_columns': [names[j - 1] for j in range(1, len(names) + 1) if j not in keep],
            'SE_CAVEAT': 'HC1 standard errors treat lineups as independent; they are not (one slate, one field)'}


def sal_bucket(left):
    need(left % 100 == 0, 'SALARY_LEFT_NOT_MULTIPLE_OF_100', str(left))
    for b, lo, hi in SAL_BUCKETS:
        if lo <= left <= hi:
            return b
    raise ShowdownHistoryError('SALARY_LEFT_OUT_OF_RANGE', str(left))


def share(rows, f):
    rows = list(rows)
    return None if not rows else round(100.0 * sum(1 for r in rows if f(r)) / len(rows), 2)


def dist(rows, key, cats=None):
    rows = [r for r in rows if r[key] is not None]
    if not rows:
        return NA('no rows with this feature known')
    c = collections.Counter(r[key] for r in rows)
    keys = cats or sorted(c, key=str)
    return {'n': len(rows), 'pct': {str(k): round(100.0 * c.get(k, 0) / len(rows), 2) for k in keys}}


# ------------------------------------------------------------------------------- stage 3: per contest
def analyse(c):
    R = load_raw(c)
    ent = R['entries']
    N_all, N = R['n_all_entries'], R['n_filled']
    names = {e['cpt'] for e in ent} | {f for e in ent for f in e['flex']} | {k[0] for k in R['dk_slot']}
    if c['metadata'] == 'DK_POOL':
        meta, slate, minfo = pit_metadata()
        need(R['away'] == minfo['away'] and R['home'] == minfo['home'], 'PIT_GAME_DISAGREES_WITH_POOL',
             f"{R['away']}@{R['home']} vs {minfo['away']}@{minfo['home']}")
        miss = sorted(names - set(meta))
        need(not miss, 'PIT_NAMES_NOT_IN_DK_POOL', str(miss))
        fav = pit_favorite()
        minfo_out = {k: v for k, v in minfo.items() if k != 'owner_entry_ids'}
        owner_in_field = sum(1 for e in ent if e['entry_id'] in minfo['owner_entry_ids'])
        minfo_out['owner_entries_in_this_field'] = owner_in_field
        minfo_out['OWNER_NOTE'] = ('the owner DKEntries export is for this same contest; the owner\'s entries found in '
                                   'the standings are part of the field and are NOT excluded')
    else:
        meta, minfo_out = phi_metadata(names, c['roster_week'])
        slate = None
        fav = {'favorite': None, 'status': 'NOT_AVAILABLE',
               'reason': 'no spread or implied team total for PHI@CHI exists in this repository; none is invented'}
    has_sal = c['metadata'] == 'DK_POOL'
    away = R['away']

    # ---- ownership: DK %Drafted (authoritative) and the recount from lineups
    cnt_c = collections.Counter(e['cpt'] for e in ent)
    cnt_f = collections.Counter(f for e in ent for f in e['flex'])
    sh_c = {n: cnt_c[n] / N for n in names}          # filled-lineup shares: sum 1 / sum 5 (estimator targets)
    sh_f = {n: cnt_f[n] / N for n in names}
    dk = R['dk_slot']
    recount = []
    for n in sorted(names):
        for slot, cnt in (('CPT', cnt_c), ('FLEX', cnt_f)):
            d = dk.get((n, slot))
            recount.append({'player': n, 'slot': slot, 'dk_pct': d['pct'] if d else None,
                            'recount_pct_over_all_entries': round(100.0 * cnt[n] / N_all, 3),
                            'recount_pct_over_filled': round(100.0 * cnt[n] / N, 3)})
    need(recount, 'OWNERSHIP_RECOUNT_EMPTY')
    missing_dk = [r for r in recount if r['dk_pct'] is None and r['recount_pct_over_all_entries'] > 0]
    diffs_all = [abs((r['dk_pct'] or 0) - r['recount_pct_over_all_entries']) for r in recount]
    diffs_fil = [abs((r['dk_pct'] or 0) - r['recount_pct_over_filled']) for r in recount]
    sum_dk = {s: round(sum(v['pct'] for k, v in dk.items() if k[1] == s), 2) for s in ('CPT', 'FLEX')}
    players = []
    for n in sorted(names, key=lambda x: -((dk.get((x, 'FLEX')) or {'pct': 0})['pct'])):
        m = meta[n]
        cp = (dk.get((n, 'CPT')) or {'pct': 0.0})['pct']
        fp = (dk.get((n, 'FLEX')) or {'pct': 0.0})['pct']
        fpts = (dk.get((n, 'FLEX')) or dk.get((n, 'CPT')) or {}).get('fpts')
        players.append({'player': n, 'team': m['team'], 'position': m['position'],
                        'flex_salary': m.get('flex_salary'), 'dk_cpt_pct': cp, 'dk_flex_pct': fp,
                        'cpt_to_flex_ratio': r4(cp / fp) if fp > 0 else None, 'fpts_flex_basis': fpts,
                        'favorite_team': (None if not fav.get('favorite') or not m['team'] else m['team'] == fav['favorite'])})
    if has_sal:
        sal_order = sorted(players, key=lambda p: -p['flex_salary'])
        for i, p in enumerate(sal_order):
            p['salary_rank'] = 1 + sum(1 for q in sal_order if q['flex_salary'] > p['flex_salary'])

    def agg_ratio(rows):
        cs, fs = sum(p['dk_cpt_pct'] for p in rows), sum(p['dk_flex_pct'] for p in rows)
        return {'n_players': len(rows), 'sum_cpt_pct': round(cs, 2), 'sum_flex_pct': round(fs, 2),
                'cpt_to_flex_ratio': r4(cs / fs) if fs > 0 else None}
    by_pos = {pos: agg_ratio([p for p in players if p['position'] == pos])
              for pos in sorted({p['position'] for p in players})}
    by_salrank = ({b: agg_ratio([p for p in players if lo <= p['salary_rank'] <= hi]) for b, lo, hi in SAL_RANK_BINS}
                  if has_sal else NA('no salary file for this slate'))
    by_fav = ({'favorite_' + str(fav['favorite']): agg_ratio([p for p in players if p['favorite_team'] is True]),
               'underdog': agg_ratio([p for p in players if p['favorite_team'] is False]), 'favorite_source': fav}
              if fav.get('favorite') else NA(fav.get('reason', 'favorite unknown')))
    elig = [p for p in players if p['dk_flex_pct'] >= CPT_HALF_RULE_FLEX_FLOOR]
    ratios = [p['cpt_to_flex_ratio'] for p in elig]
    half_rule = {'MASS_IDENTITY': ('every lineup has 1 CPT and 5 FLEX, so sum(CPT %)/sum(FLEX %) = 100/500 = 0.2 '
                                   'exactly; a uniform CPT = 0.5 x FLEX is arithmetically impossible across a pool'),
                 'dk_sum_cpt_over_sum_flex': r4(sum_dk['CPT'] / sum_dk['FLEX']),
                 'players_with_flex_ge_10pct': len(elig),
                 'FLOOR_NOTE': 'FLEX >= 10% is a descriptive reporting floor, not fitted',
                 'median_ratio': r4(float(np.median(ratios))) if ratios else None,
                 'share_within_0.4_0.6': share(ratios, lambda r: 0.4 <= r <= 0.6) if ratios else None,
                 'ratios': {p['player']: p['cpt_to_flex_ratio'] for p in elig}}

    # ---- per-entry features
    def pos(n):
        return meta[n]['position']

    def team(n):
        return meta[n]['team']
    for e in ent:
        seats = [e['cpt']] + list(e['flex'])
        known = all(team(n) for n in seats)
        e['key'] = (e['cpt'], e['flex'])
        e['away_count'] = sum(team(n) == away for n in seats) if known else None
        e['split'] = f"{e['away_count']}-{6 - e['away_count']}" if known else None
        e['qb_count'] = sum(pos(n) == 'QB' for n in seats) if all(pos(n) != 'UNMAPPED' for n in seats) else None
        e['kd_count'] = sum(pos(n) in ('K', 'DST') for n in seats) if all(pos(n) != 'UNMAPPED' for n in seats) else None
        e['no_k_no_dst'] = None if e['kd_count'] is None else e['kd_count'] == 0
        e['cpt_pos'] = pos(e['cpt'])
        if pos(e['cpt']) in ('WR', 'TE') and team(e['cpt']):
            e['cpt_pc_own_qb'] = any(pos(f) == 'QB' and team(f) == team(e['cpt']) for f in e['flex'])
        elif pos(e['cpt']) == 'UNMAPPED':
            e['cpt_pc_own_qb'] = None
        else:
            e['cpt_pc_own_qb'] = False
        e['cpt_dk_pct'] = (dk.get((e['cpt'], 'CPT')) or {'pct': 0.0})['pct']
        lp = math.log(sh_c[e['cpt']]) + sum(math.log(sh_f[f]) for f in e['flex'])
        e['log_prod_own'] = lp
        e['geo_own_pct'] = 100.0 * math.exp(lp / 6)
        if has_sal:
            s_ = meta[e['cpt']]['cpt_salary'] + sum(meta[f]['flex_salary'] for f in e['flex'])
            e['salary'] = s_
            e['salary_left'] = CAP - s_
    dup = collections.Counter(e['key'] for e in ent)
    for e in ent:
        e['dupes'] = dup[e['key']]
    cap_viol = sum(1 for e in ent if has_sal and e['salary_left'] < 0) if has_sal else None
    if has_sal:
        need(cap_viol == 0, 'SALARY_CAP_VIOLATION_IN_STANDINGS', f'{cap_viol} entries over the cap')
        for e in ent:
            e['sal_bucket'] = sal_bucket(e['salary_left'])
    top_cut = math.ceil(0.01 * N_all)
    top = [e for e in ent if e['rank'] <= top_cut]
    win = [e for e in ent if e['rank'] == 1]
    need(top and win, 'TOP1_OR_WINNER_EMPTY', f'top {len(top)}, winner {len(win)}')
    cohorts = {'field': ent, 'top_1pct': top, 'winner': win}

    # ---- duplication
    ulines = list(dup)
    nu = len(ulines)
    dup_dist = {'n_entries_filled': N, 'n_distinct_lineups': nu,
                'share_of_distinct_lineups_played_once': round(100.0 * sum(1 for k in ulines if dup[k] == 1) / nu, 2),
                'share_of_entries_unique': share(ent, lambda e: e['dupes'] == 1),
                'share_of_entries_in_lineups_dup_ge_2': share(ent, lambda e: e['dupes'] >= 2),
                'share_of_entries_in_lineups_dup_ge_10': share(ent, lambda e: e['dupes'] >= 10),
                'share_of_entries_in_lineups_dup_ge_50': share(ent, lambda e: e['dupes'] >= 50),
                'max_copies': max(dup.values())}
    top20 = [{'cpt': k[0], 'flex': list(k[1]), 'copies': v,
              'salary_left': (CAP - meta[k[0]]['cpt_salary'] - sum(meta[f]['flex_salary'] for f in k[1])) if has_sal else None,
              'best_rank': min(e['rank'] for e in ent if e['key'] == k)}
             for k, v in dup.most_common(20)]
    win_keys = collections.Counter(e['key'] for e in win)
    winner_dupes = [{'cpt': k[0], 'flex': list(k[1]), 'copies_in_field': dup[k], 'tied_rank1_entries_with_it': v}
                    for k, v in win_keys.items()]
    top_keys = {e['key'] for e in top}
    top_dupes = {'n_entries': len(top), 'n_distinct_lineups': len(top_keys),
                 'copies_in_field_of_top1pct_entries': {'median': float(np.median([e['dupes'] for e in top])),
                                                        'mean': r4(float(np.mean([e['dupes'] for e in top]))),
                                                        'share_unique': share(top, lambda e: e['dupes'] == 1),
                                                        'share_dup_ge_10': share(top, lambda e: e['dupes'] >= 10)}}

    # ---- salary
    if has_sal:
        sal = {}
        for nm_, rows in cohorts.items():
            sal[nm_] = {'n': len(rows), 'bucket_pct': {b: share(rows, lambda e, b=b: e['sal_bucket'] == b) for b, _l, _h in SAL_BUCKETS},
                        'mean_salary_left': r4(float(np.mean([e['salary_left'] for e in rows]))),
                        'share_ge_49500_used': share(rows, lambda e: e['salary_left'] <= 500),
                        'share_exactly_50000': share(rows, lambda e: e['salary_left'] == 0)}
        # dupes vs salary on UNIQUE lineups
        U = [{'key': k, 'n': dup[k]} for k in ulines]
        firsts = {}
        for e in ent:
            firsts.setdefault(e['key'], e)
        for u in U:
            f = firsts[u['key']]
            u['left'], u['lp'], u['b'] = f['salary_left'], f['log_prod_own'], f['sal_bucket']
            u['logc'] = math.log(u['n'])
        y = [u['logc'] for u in U]
        lp = [u['lp'] for u in U]
        bnames = [b for b, _l, _h in SAL_BUCKETS[1:]]
        bd = [[1.0 if u['b'] == b else 0.0 for u in U] for b in bnames]
        m_own = ols(y, [lp], ['log_prod_own'])
        m_own_b = ols(y, [lp] + bd, ['log_prod_own'] + [f'left_{b}' for b in bnames])
        m_sal_lin = ols(y, [[CAP - u['left'] for u in U]], ['salary_used'])
        m_sal_b = ols(y, bd, [f'left_{b}' for b in bnames])
        grp = lambda left: ('exactly_50000' if left == 0 else 'exactly_49900' if left == 100
                            else '49500_49800' if 200 <= left <= 500 else 'other_le_49400')
        gnames = ['exactly_49900', '49500_49800', 'other_le_49400']
        gd = [[1.0 if grp(u['left']) == g else 0.0 for u in U] for g in gnames]
        m_dup06 = ols(y, [lp] + gd, ['log_prod_own'] + gnames)
        a0, a1 = m_own['coef']['intercept'], m_own['coef']['log_prod_own']
        gsum = {}
        for g in ['exactly_50000'] + gnames:
            us = [u for u in U if grp(u['left']) == g]
            es = [e for e in ent if grp(e['salary_left']) == g]
            gsum[g] = {'n_unique_lineups': len(us), 'n_entries': len(es),
                       'mean_copies_per_unique_lineup': r4(float(np.mean([u['n'] for u in us]))) if us else None,
                       'mean_copies_per_entry': r4(float(np.mean([e['dupes'] for e in es]))) if es else None,
                       'mean_resid_log_count_given_log_prod_own': r4(float(np.mean([u['logc'] - a0 - a1 * u['lp'] for u in us]))) if us else None}
        salary = {'by_cohort': sal, 'cap_violations': cap_viol,
                  'dupes_on_salary': {'MODEL_log_count_on_log_prod_own': m_own,
                                      'MODEL_log_count_on_log_prod_own_plus_salary_left_buckets(ref $0)': m_own_b,
                                      'DUP-01_log_count_on_salary_used_linear': m_sal_lin,
                                      'DUP-01_log_count_on_salary_left_buckets': m_sal_b,
                                      'DUP-06_vs_DUP-01_log_count_on_log_prod_own_plus_groups(ref exactly $50,000)': m_dup06,
                                      'DUP-06_vs_DUP-01_group_summary': gsum,
                                      'SELECTION_CAVEAT': ('only lineups somebody played are observed: every unique '
                                                           'lineup has count >= 1, lineups nobody played (count 0) are '
                                                           'missing, so log(count) is truncated at 0 and the slopes '
                                                           'describe played lineups only')}}
    else:
        salary = NA('no salary file exists for PHI@CHI; salary left, cap checks and every salary regression are not computed')

    # ---- construction
    def construction(rows):
        return {'n': len(rows), 'team_split_away_home': dist(rows, 'split', ['5-1', '4-2', '3-3', '2-4', '1-5']),
                'qb_count': dist(rows, 'qb_count', [0, 1, 2, 3]),
                'k_plus_dst_count': dist(rows, 'kd_count', [0, 1, 2, 3, 4]),
                'cpt_position': dist(rows, 'cpt_pos'),
                'cpt_pass_catcher_with_own_qb_in_flex': dist(rows, 'cpt_pc_own_qb', [True, False]),
                'given_cpt_wr_te_share_with_own_qb_in_flex': dist([r for r in rows if r['cpt_pos'] in ('WR', 'TE')],
                                                                  'cpt_pc_own_qb', [True, False])}
    cons = {k: construction(v) for k, v in cohorts.items()}
    cons['winner']['distinct_lineups'] = len(win_keys)
    cons['NOTE'] = ('top-1% and winner are OUTCOME-CONDITIONED: their construction mix records who scored that night, '
                    'not what the field should have built')
    cons['excluded_for_unmapped_players'] = sum(1 for e in ent if e['split'] is None)

    # ---- entrant cohorts
    maxm = max(e['max_entries'] for e in ent)
    per_user = collections.Counter(e['user'] for e in ent)
    user_n = {}
    for e in ent:
        user_n.setdefault(e['user'], set()).add(e['max_entries'])
    incons = sum(1 for u, n in per_user.items() if user_n[u] != {n})
    ech = {'1': lambda m: m == 1, '2-20': lambda m: 2 <= m <= 20, '21-150': lambda m: 21 <= m <= 150,
           f'at_contest_max_{maxm}': lambda m: m == maxm}
    ent_c = {}
    for nm_, f in ech.items():
        rows = [e for e in ent if f(e['max_entries'])]
        if not rows:
            ent_c[nm_] = NA(f'no entrant in this contest has {nm_} entries (largest observed: {maxm})')
            continue
        d = {'n_entries': len(rows), 'n_users': len({e['user'] for e in rows}),
             'cpt_position': dist(rows, 'cpt_pos'),
             'sub_5pct_owned_cpt_share': share(rows, lambda e: e['cpt_dk_pct'] < 5.0),
             'no_k_no_dst_share': dist(rows, 'no_k_no_dst', [True, False]),
             'mean_log10_product_ownership': r4(float(np.mean([e['log_prod_own'] for e in rows])) / math.log(10)),
             'mean_geomean_ownership_pct': r4(float(np.mean([e['geo_own_pct'] for e in rows]))),
             'mean_copies_of_own_lineup': r4(float(np.mean([e['dupes'] for e in rows]))),
             'share_unique': share(rows, lambda e: e['dupes'] == 1)}
        if has_sal:
            d['mean_salary_left'] = r4(float(np.mean([e['salary_left'] for e in rows])))
            d['share_exactly_50000'] = share(rows, lambda e: e['salary_left'] == 0)
        else:
            d['salary_left'] = NA('no salary file')
        ent_c[nm_] = d
    ent_c['contest_max_entries_observed'] = maxm
    ent_c['users_whose_entry_count_differs_from_their_N_in_(k/N)'] = incons
    ent_c['NOTE'] = ('max entries is read from EntryName "(k/N)": N entries for that user; a bare name is 1. Entries '
                     'with an empty lineup were dropped before this count, so a user can show fewer than N.')

    # ---- estimators on unique lineups
    seedc = AF.CORR_SEED
    rows_u = []
    first = {}
    for e in ent:
        first.setdefault(e['key'], e)
    in_top = {e['key'] for e in top}
    in_win = set(win_keys)

    def e2_factor(cpt, flex):
        pc, why = pos(cpt), []
        fac = 1.0
        if pc == 'UNMAPPED' or any(pos(x) == 'UNMAPPED' for x in flex):
            return 1.0, ['UNMAPPED_PLAYER_FACTOR_1.0']
        if pc == 'WR' and any(pos(x) == 'QB' and team(x) == team(cpt) for x in flex):
            fac *= seedc['CPT_WR_WITH_OWN_QB']
            why.append('CPT_WR_WITH_OWN_QB')
        if pc == 'QB' and any(pos(x) == 'DST' and team(x) != team(cpt) for x in flex):
            fac *= seedc['CPT_QB_WITH_OPPOSING_DST']
            why.append('CPT_QB_WITH_OPPOSING_DST')
        return fac, why

    def lp_of(cpt, flex):
        v = sh_c.get(cpt, 0.0) * math.prod(sh_f.get(x, 0.0) for x in flex)
        return v
    for k, n in dup.items():
        f = first[k]
        e1 = N * math.exp(f['log_prod_own'])
        fac, why = e2_factor(*k)
        rows_u.append({'cpt': k[0], 'flex': k[1], 'actual': n, 'in_top1pct': k in in_top, 'winner': k in in_win,
                       'best_rank': None, 'salary_left': f.get('salary_left'),
                       'log_prod_own': f['log_prod_own'], 'geomean_own_pct': f['geo_own_pct'],
                       'E1': e1, 'E2': e1 * fac, 'E2_factors': '+'.join(why) or 'none'})
    best = {}
    for e in ent:
        best[e['key']] = min(best.get(e['key'], 10 ** 9), e['rank'])
    for r in rows_u:
        r['best_rank'] = best[(r['cpt'], r['flex'])]
    need(rows_u, 'UNIQUE_LINEUPS_EMPTY')
    est_names = ['E1', 'E2']
    gen = {}
    unobserved = []
    if has_sal:
        gen = generated_fields(slate, meta, ent, sh_c, sh_f, N, away)
        for r in rows_u:
            key = (meta[r['cpt']]['key'], tuple(sorted(meta[x]['key'] for x in r['flex'])))
            for nm_, g in gen['fields'].items():
                r[nm_] = g['counts'].get(key, 0) * N / g['k']
        est_names += list(gen['fields'])
        # lineups the generated fields predict that nobody played
        obs = {(meta[r['cpt']]['key'], tuple(sorted(meta[x]['key'] for x in r['flex']))) for r in rows_u}
        k2n = {v['key']: n for n, v in meta.items()}
        allgen = set()
        for g in gen['fields'].values():
            allgen |= set(g['counts'])
        for key in sorted(allgen - obs):
            cpt, flex = k2n[key[0]], tuple(sorted(k2n[x] for x in key[1]))
            lpv = lp_of(cpt, flex)
            e1 = N * lpv
            fac, why = e2_factor(cpt, flex)
            rr = {'cpt': cpt, 'flex': flex, 'actual': 0, 'in_top1pct': False, 'winner': False, 'best_rank': None,
                  'salary_left': CAP - meta[cpt]['cpt_salary'] - sum(meta[x]['flex_salary'] for x in flex),
                  'log_prod_own': math.log(lpv) if lpv > 0 else None,
                  'geomean_own_pct': 100.0 * lpv ** (1 / 6), 'E1': e1, 'E2': e1 * fac, 'E2_factors': '+'.join(why) or 'none'}
            for nm_, g in gen['fields'].items():
                rr[nm_] = g['counts'].get(key, 0) * N / g['k']
            unobserved.append(rr)
    else:
        gen = {'E3': NA('E3 needs salaries (cap legality in the generator); no salary file exists for PHI@CHI'),
               'E4': NA('E4 needs salaries and a public projection for this slate; neither exists for PHI@CHI')}

    # ---- estimator metrics
    def evaluate(rows, label):
        if not rows:
            return NA(f'{label}: empty set')
        out = {'n_lineups': len(rows), 'sum_actual': int(sum(r['actual'] for r in rows))}
        a = np.array([r['actual'] for r in rows], float)
        for nm_ in est_names:
            p = np.array([r[nm_] for r in rows], float)
            err = np.abs(np.log((p + 1) / (a + 1)))
            o = np.argsort(p, kind='mergesort')
            dec = np.array_split(o, 10) if len(rows) >= 10 else [o]
            cal = [{'decile': i + 1, 'n': int(len(d)), 'mean_pred': r4(p[d].mean()), 'mean_actual': r4(a[d].mean())}
                   for i, d in enumerate(dec) if len(d)]
            td = dec[-1]
            ratio = (a[td].mean() / p[td].mean()) if p[td].mean() > 0 else None
            out[nm_] = {'median_abs_log_err': r4(np.median(err)), 'mean_abs_log_err': r4(err.mean()),
                        'spearman_with_actual': r4(spearman(p, a)), 'sum_pred': r4(p.sum()),
                        'calibration_by_decile_of_estimator': cal,
                        'top_decile_actual_over_pred': r4(ratio),
                        'top_decile_biased_gt_2x': (None if ratio is None else
                                                    bool(ratio > TOL['E1_TOP_DECILE_BIAS_RATIO'] or ratio < 1 / TOL['E1_TOP_DECILE_BIAS_RATIO']))}
        return out
    top50 = sorted(rows_u, key=lambda r: -r['actual'])[:50]
    winset = [r for r in rows_u if r['in_top1pct'] or r['winner']]
    evals = {'OBSERVED_ALL_UNIQUE': evaluate(rows_u, 'all'), 'TOP50_MOST_DUPLICATED': evaluate(top50, 'top50'),
             'WINNER_AND_TOP1PCT_LINEUPS': evaluate(winset, 'top1')}
    if has_sal:
        evals['OBSERVED_PLUS_GENERATED_UNOBSERVED(actual=0)'] = evaluate(rows_u + unobserved, 'union')
        over = {}
        for nm_ in gen['fields']:
            pr = [r for r in rows_u + unobserved if r[nm_] > 0]
            zero = [r for r in pr if r['actual'] == 0]
            over[nm_] = {'n_lineups_predicted': len(pr), 'n_predicted_but_unplayed': len(zero),
                         'share_predicted_lineups_unplayed': share(pr, lambda r: r['actual'] == 0),
                         'pred_copies_on_unplayed': r4(sum(r[nm_] for r in zero)),
                         'share_of_pred_mass_on_unplayed': r4(sum(r[nm_] for r in zero) / max(1e-9, sum(r[nm_] for r in pr))),
                         'set_metrics': evaluate(pr, nm_).get(nm_)}
        evals['OVER_PREDICTION_ON_EACH_GENERATED_FIELDS_OWN_PREDICTIONS'] = over
        # the E1-vs-E3 flag, as the archetype module defines it
        flag = {}
        for nm_ in [x for x in gen['fields'] if x.startswith('E3')]:
            res = N / gen['fields'][nm_]['k']
            for setname, rows in (('observed', rows_u), ('observed_plus_generated', rows_u + unobserved)):
                both = [r for r in rows if r[nm_] > 0 and r['E1'] > 0]
                dis = [r for r in both if max(r['E1'], r[nm_]) / min(r['E1'], r[nm_]) > TOL['E1_E3_FLAG_RATIO']]
                below = [r for r in rows if r[nm_] == 0 and r['E1'] >= res]
                big = [r for r in both if r[nm_] / r['E1'] >= 5.0]
                # ATL@NO-sized: E3 at least 20 copies AND >= 5x E1 (ATL@NO 2-entry lineups: E1 4-7 vs E3 42-115).
                # 20 and 5x are descriptive reporting cuts chosen to resemble that case, not fitted
                big20 = [r for r in big if r[nm_] >= 20.0]
                flag[f'{nm_}|{setname}'] = {
                    'n_lineups': len(rows), 'n_both_positive': len(both),
                    'share_E1_E3_differ_gt_2x_of_both_positive': share(both, lambda r: max(r['E1'], r[nm_]) / min(r['E1'], r[nm_]) > TOL['E1_E3_FLAG_RATIO']),
                    'n_E3_below_resolution_E1_not': len(below),
                    'n_disagree_gt_2x': len(dis),
                    'share_of_disagreements_where_actual_closer_to_E3': share(dis, lambda r: abs(math.log((r['actual'] + 1) / (r[nm_] + 1))) < abs(math.log((r['actual'] + 1) / (r['E1'] + 1)))),
                    'E3_over_E1_ge_5x(ATL@NO-like)': {
                        'n': len(big),
                        'median_actual': float(np.median([r['actual'] for r in big])) if big else None,
                        'median_E1': r4(float(np.median([r['E1'] for r in big]))) if big else None,
                        'median_E3': r4(float(np.median([r[nm_] for r in big]))) if big else None,
                        'share_actual_closer_to_E3': share(big, lambda r: abs(math.log((r['actual'] + 1) / (r[nm_] + 1))) < abs(math.log((r['actual'] + 1) / (r['E1'] + 1))))},
                    'E3_ge_20_and_ge_5x_E1(ATL@NO-sized)': {
                        'n': len(big20),
                        'median_actual': float(np.median([r['actual'] for r in big20])) if big20 else None,
                        'median_E1': r4(float(np.median([r['E1'] for r in big20]))) if big20 else None,
                        'median_E3': r4(float(np.median([r[nm_] for r in big20]))) if big20 else None,
                        'share_unplayed': share(big20, lambda r: r['actual'] == 0),
                        'share_actual_closer_to_E3': share(big20, lambda r: abs(math.log((r['actual'] + 1) / (r[nm_] + 1))) < abs(math.log((r['actual'] + 1) / (r['E1'] + 1))))}}
        evals['E1_vs_E3_FLAG_TEST'] = flag
    else:
        for nm_ in ('E3', 'E4'):
            evals[nm_] = gen[nm_]

    # ---- CF-2 / CF-3 on unique observed lineups
    y = [math.log(r['actual']) for r in rows_u]
    cf2 = ols(y, [[r['log_prod_own'] for r in rows_u]], ['log_prod_own'])
    cf3_c = ols(y, [[math.log(sh_c[r['cpt']]) for r in rows_u]], ['log_cpt_share'])
    cf3_f = ols(y, [[sum(math.log(sh_f[x]) for x in r['flex']) for r in rows_u]], ['log_flex_product'])
    cf3_b = ols(y, [[math.log(sh_c[r['cpt']]) for r in rows_u], [sum(math.log(sh_f[x]) for x in r['flex']) for r in rows_u]],
                ['log_cpt_share', 'log_flex_product'])
    # entry-weighted variant (each ENTRY is a row carrying its lineup's count): ETR's unit of analysis is not stated
    ye = [math.log(e['dupes']) for e in ent]
    cf2e = ols(ye, [[e['log_prod_own'] for e in ent]], ['log_prod_own'])
    cf = {'CF-2_log_count_on_log_prod_own': cf2, 'CF-2_entry_weighted_variant': cf2e, 'CF-3_log_count_on_log_cpt_share_only': cf3_c,
          'CF-3_log_count_on_log_flex_product_only': cf3_f, 'CF-3_both': cf3_b,
          'SELECTION_CAVEAT': 'observed lineups only (count >= 1); unplayed lineups are unobserved'}

    # ---- outputs: per-contest CSV
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ['cpt', 'flex1', 'flex2', 'flex3', 'flex4', 'flex5', 'actual_copies', 'observed', 'best_rank', 'in_top1pct',
            'winner', 'salary_left', 'log_prod_own', 'geomean_own_pct', 'E1', 'E2', 'E2_factors'] + \
           [x for x in est_names if x not in ('E1', 'E2')]
    csv_path = OUT / f"UNIQUE_LINEUPS_{c['label']}.csv"
    with csv_path.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in sorted(rows_u, key=lambda r: (-r['actual'], r['best_rank'])) + sorted(unobserved, key=lambda r: -r['E1']):
            w.writerow([r['cpt'], *r['flex'], r['actual'], int(r['actual'] > 0), r['best_rank'], int(r['in_top1pct']),
                        int(r['winner']), r['salary_left'], r4(r['log_prod_own']), r4(r['geomean_own_pct']),
                        r4(r['E1']), r4(r['E2']), r['E2_factors']] + [r4(r[x]) for x in est_names if x not in ('E1', 'E2')])
    need(csv_path.stat().st_size > 0, 'CSV_WRITE_EMPTY', str(csv_path))

    out = {'contest_id': c['contest_id'], 'game': R['rec']['game'], 'game_date': R['rec']['game_date'],
           'nflverse_game_id': c['nflverse_game_id'],
           'raw': {'file': R['rec']['file'], 'sha256': R['sha256'], 'zip_sha256': R['rec'].get('zip_sha256'),
                   'provenance_captured_at': R['rec'].get('captured_at')},
           'N_all_entries': N_all, 'N_filled_lineups': N, 'N_empty_lineup_excluded': R['n_empty_lineup'],
           'EMPTY_LINEUP_NOTE': ('entries with an empty Lineup are counted here and excluded from every lineup '
                                 'statistic; DK %Drafted uses all entries (empty included) as its denominator'),
           'top_1pct_cut_rank': top_cut, 'n_top_1pct_entries': len(top), 'n_winner_entries': len(win),
           'metadata': minfo_out, 'favorite': fav,
           'ownership': {'dk_sum_pct': sum_dk,
                         'recount_max_abs_diff_pct_pts_over_all_entries': r4(max(diffs_all)),
                         'recount_max_abs_diff_pct_pts_over_filled': r4(max(diffs_fil)),
                         'recount_flag_gt_0.5': bool(max(diffs_all) > TOL['RECOUNT_FLAG_PCT_PTS']),
                         'player_slots_in_lineups_but_absent_from_dk_block': [r['player'] + '/' + r['slot'] for r in missing_dk],
                         'players': players, 'by_position': by_pos, 'by_salary_rank': by_salrank,
                         'by_favorite': by_fav, 'cpt_half_flex_rule': half_rule,
                         'ESTIMATOR_TARGETS': ('E1/E2/E3 use slot shares counted over FILLED lineups (CPT sums to 1, '
                                               'FLEX to 5); DK %Drafted differs only by the factor filled/all')},
           'duplication': {'distribution': dup_dist, 'top20': top20, 'winner_lineups': winner_dupes,
                           'top_1pct': top_dupes},
           'salary': salary, 'construction': cons, 'entrant_cohorts': ent_c,
           'estimators': {'definitions': {
               'E1': 'N_filled x CPT share x product of FLEX shares, ACTUAL ownership (ORACLE ownership)',
               'E2': f'E1 x ETR seeds {seedc} (SEEDED_NOT_FITTED, ETR Showdown 101, via showdown_archetype_field.CORR_SEED)',
               'GEO': 'geomean of the six slot shares; N x GEO^6 == E1 identically, so GEO carries no separate error metric',
               'E3*': 'archetype-first generated field, ORACLE configuration (targets = actual slot ownership, archetype '
                      'prior = actual field archetype rates), copies x N/K',
               'E4*': 'optimizer-exposure field over the FC projection, copies x N/K, every sigma reported, none chosen'},
               'generated_fields': gen if not has_sal else {k: {kk: vv for kk, vv in v.items() if kk != 'counts'}
                                                            for k, v in gen['fields'].items()},
               'generator_notes': gen.get('notes') if has_sal else None,
               'evaluation': evals, 'correlation_claims': cf,
               'n_generated_unobserved_lineups': len(unobserved),
               'SELECTION_CAVEAT': ('only played lineups have observable counts; on OBSERVED sets every actual >= 1, so '
                                    'low-predicted played lineups are necessarily under-predicted. The generated-field '
                                    'sets add lineups predicted but unplayed (actual 0) so over-prediction is visible.')},
           'unique_lineups_csv': rel(csv_path)}
    return out


# --------------------------------------------------------------------------- E3 / E4 (PIT@CLE only)
def generated_fields(slate, meta, ent, sh_c, sh_f, N, away):
    own = {}
    for n, m in meta.items():
        c_, f_ = 100.0 * sh_c.get(n, 0.0), 100.0 * sh_f.get(n, 0.0)
        own[m['key']] = {'cpt': c_, 'flex': f_, 'total': c_ + f_}
    need(any(v['total'] > 0 for v in own.values()), 'E3_TARGETS_EMPTY')
    P = slate['players']
    arche = collections.Counter()
    for e in ent:
        seats = [meta[e['cpt']]['key']] + [meta[x]['key'] for x in e['flex']]
        arche[(sum(P[x]['dk_team'] == slate['away'] for x in seats), sum(AF._cat(P[x]['position']) == 'QB' for x in seats),
               sum(AF._cat(P[x]['position']) == 'KD' for x in seats))] += 1
    arche = {a: v / len(ent) for a, v in arche.items()}
    need(abs(sum(arche.values()) - 1) < 1e-9, 'E3_ARCHETYPE_PRIOR_NOT_NORMALISED')
    pool = AF.Pool(slate, own)
    need(len(pool.keys) >= 6, 'E3_POOL_TOO_SMALL', str(len(pool.keys)))
    fields, notes = {}, {}
    for an in ('NONE', 'FC08_90PCT_LE_500'):
        anchor = AF.SALARY_ANCHORS[an]
        rng = np.random.default_rng(AF.SEED)
        wc, wf, hist = AF.calibrate(pool, arche, AF.PHI_REPORTED, rng, anchor)
        L, rej = AF.generate(pool, arche, wc, wf, AF.K, AF.PHI_REPORTED, rng, anchor)
        need(len(L) == AF.K, 'E3_FIELD_SHORT', f'{an}: {len(L)} of {AF.K}')
        last = dict(AF.generate.last)
        rc, rf = AF.realised(pool, L)
        cnts = collections.Counter((pool.keys[c], tuple(sorted(pool.keys[x] for x in f))) for c, f in L)
        left = np.array([CAP - (pool.csal[c] + pool.sal[list(f)].sum()) for c, f in L])
        fields[f'E3_{an}'] = {
            'k': AF.K, 'phi': AF.PHI_REPORTED, 'seed': AF.SEED, 'counts': cnts,
            'configuration': 'ORACLE: targets = ACTUAL slot ownership; archetype prior = ACTUAL field archetype rates',
            'salary_anchor': an, 'rejected': rej, 'accept_rate': round(AF.K / (AF.K + rej), 4),
            'final_residual_rmse_pts': {'cpt': round(float(np.sqrt(np.mean((100 * (rc - pool.tc)) ** 2))), 3),
                                        'flex': round(float(np.sqrt(np.mean((100 * (rf - pool.tf)) ** 2))), 3)},
            'calibration_last_round': hist[-1],
            'archetype_shortfall': {str(a): v for a, v in last['archetype_shortfall'].items()},
            'distinct_lineups': len(cnts), 'max_copies_in_K': max(cnts.values()),
            'resolution_copies': round(N / AF.K, 3),
            'generated_salary_left_bucket_pct': {b: round(100.0 * float(np.mean((left >= lo) & (left <= hi))), 2)
                                                 for b, lo, hi in SAL_BUCKETS}}
    notes['E3_archetype_prior_from_actual_field'] = {f'{a[0]}away_{a[1]}QB_{a[2]}KD': round(v, 4)
                                                     for a, v in sorted(arche.items(), key=lambda x: -x[1])}
    # E4: FC projection; DK-pool name reconciliation by suffix (same club, unique) -- reported, never silent
    fc = SF.fc_projection(PIT_FC)
    need(fc, 'FC_PROJECTION_EMPTY')
    pk = {(v['name'], v['dk_team']) for v in P.values()}
    alias, unres = {}, []
    fc2 = {}
    for (n, t), v in fc.items():
        if (n, t) in pk:
            fc2[(n, t)] = v
            continue
        hit = [(pn, pt) for pn, pt in pk if pt == t and SUFFIX.sub('', pn) == SUFFIX.sub('', n)]
        if len(hit) == 1:
            alias[f'{n}|{t}'] = f'{hit[0][0]}|{t}'
            fc2[hit[0]] = v
        else:
            unres.append(f'{n}|{t}')
    inact = json.loads(PIT_INACTIVES.read_text())
    need(isinstance(inact, list) and inact, 'INACTIVES_EMPTY', str(PIT_INACTIVES))
    absent = {k for k, v in P.items() if v['name'] in set(inact)}
    for s in SF.SIGMAS:
        L = SF.field(slate, absent, fc2, s, k=SF.K, seed=SF.SEED)
        need(len(L) > 0, 'E4_FIELD_EMPTY', f'sigma {s}')
        cnts = collections.Counter((c, tuple(sorted(f))) for c, f in L)
        o = SF.ownership(L, slate)
        err_c = [o.get(meta[n]['key'], {}).get('cpt', 0.0) - 100 * sh_c.get(n, 0.0) for n in meta]
        err_f = [o.get(meta[n]['key'], {}).get('flex', 0.0) - 100 * sh_f.get(n, 0.0) for n in meta]
        left = np.array([CAP - (P[c]['cpt']['salary'] + sum(P[x]['flex']['salary'] for x in f)) for c, f in L])
        fields[f'E4_sigma{s}'] = {
            'k': len(L), 'sigma': s, 'seed': SF.SEED, 'counts': cnts, 'distinct_lineups': len(cnts),
            'max_copies_in_K': max(cnts.values()), 'resolution_copies': round(N / len(L), 3),
            'ownership_rmse_vs_actual_pts': {'cpt': round(float(np.sqrt(np.mean(np.square(err_c)))), 3),
                                             'flex': round(float(np.sqrt(np.mean(np.square(err_f)))), 3)},
            'generated_salary_left_bucket_pct': {b: round(100.0 * float(np.mean((left >= lo) & (left <= hi))), 2)
                                                 for b, lo, hi in SAL_BUCKETS},
            'NOT_CHOSEN': 'no PIT@CLE ownership anchors exist; all three sigmas are reported and none is selected'}
    notes['E4_fc_name_aliases_by_suffix_same_club'] = alias
    notes['E4_fc_names_unresolved'] = unres
    notes['E4_ALIAS_NOTE'] = ('showdown_shadow_field.field() looks up FC by exact (name, club); without these aliases '
                              'KC Concepcion Jr., Michael Pittman Jr. and Lew Nichols would carry projection 0 and be '
                              'dropped from the optimizer field')
    notes['E4_absent_official_inactives'] = sorted(P[k]['name'] for k in absent)
    notes['E4_inputs'] = {'fc': rel(PIT_FC), 'fc_sha256': sha(PIT_FC), 'inactives': rel(PIT_INACTIVES),
                          'inactives_sha256': sha(PIT_INACTIVES)}
    return {'fields': fields, 'notes': notes}


# --------------------------------------------------------------------------------- ledger + verdicts
def ledger():
    L = {}
    for ln in LEDGER.read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            L[r['claim_id']] = r
    need(L, 'LEDGER_EMPTY')
    cf = {x['id']: x for x in json.loads(METHODS.read_text()).get('conflicts_to_settle_on_our_standings', [])}
    need(cf, 'METHOD_CANDIDATES_CF_EMPTY')
    return L, cf


def verdicts(res, L, CF):
    V = []
    P, Q = res['PIT_CLE'], res['PHI_CHI']

    def own(cn, name):
        for p in res[cn]['ownership']['players']:
            if p['player'] == name:
                return p
        raise ShowdownHistoryError('LEDGER_PLAYER_NOT_IN_STANDINGS', f'{cn}: {name}')

    def point(cid, cn, name, cpt, flex):
        p = own(cn, name)
        dc, df = p['dk_cpt_pct'] - cpt, p['dk_flex_pct'] - flex
        ok = abs(dc) <= TOL['OWNERSHIP_POINT_PCT_PTS'] and abs(df) <= TOL['OWNERSHIP_POINT_PCT_PTS']
        V.append({'claim': cid, 'text': f'{name} CPT {cpt} / FLEX {flex} ({cn})',
                  'verdict': 'CONFIRMED' if ok else 'FALSIFIED',
                  'numbers': f"DK file: CPT {p['dk_cpt_pct']} / FLEX {p['dk_flex_pct']} (diff {dc:+.2f} / {df:+.2f} pts; "
                             f"tolerance {TOL['OWNERSHIP_POINT_PCT_PTS']} pts from DATA-05's own criterion)",
                  'n': f"N_all {res[cn]['N_all_entries']}"})
    for name, cpt, flex in (('Jaylen Warren', 27.4, 51.1), ('Deshaun Watson', 13.4, 57.1), ('Aaron Rodgers', 6.1, 50.9)):
        point('DATA-06', 'PIT_CLE', name, cpt, flex)
    point('DATA-05', 'PHI_CHI', 'Jalen Hurts', 23.7, 61.9)
    V.append({'claim': 'DATA-04', 'text': L['DATA-04']['claim'][:90] + '...', 'verdict': 'UNRESOLVED',
              'numbers': 'different slate (ATL vs GB); neither file here can test it', 'n': '0 matching contests'})
    hr = [res[c]['ownership']['cpt_half_flex_rule'] for c in ('PIT_CLE', 'PHI_CHI')]
    V.append({'claim': 'CPT = 0.5 x FLEX (chanzer0 default; DATA-06 conflicting_evidence)', 'text': 'CPT ownership is half of FLEX',
              'verdict': 'FALSIFIED',
              'numbers': '; '.join(f"{c}: median ratio {h['median_ratio']} over {h['players_with_flex_ge_10pct']} players with FLEX>=10%, "
                                   f"{h['share_within_0.4_0.6']}% within 0.4-0.6; pool mass ratio {h['dk_sum_cpt_over_sum_flex']}"
                                   for c, h in zip(('PIT@CLE', 'PHI@CHI'), hr)) + ' (0.2 is forced by 1 CPT + 5 FLEX)',
              'n': 'players per contest as shown'})
    # salary claims (PIT only)
    sf = P['salary']['by_cohort']['field']
    for cid, key, claim in (('FC-08', 'share_ge_49500_used', 90.0), ('FC-09', 'share_exactly_50000', 80.0)):
        v = sf[key]
        V.append({'claim': cid, 'text': f'~{claim:.0f}% of the field {"uses >= $49,500" if cid == "FC-08" else "spends exactly $50,000"}',
                  'verdict': 'CONFIRMED' if abs(v - claim) <= TOL['SHARE_CLAIM_PCT_PTS'] else 'FALSIFIED',
                  'numbers': f'PIT@CLE field: {v}% (tolerance +/-{TOL["SHARE_CLAIM_PCT_PTS"]} pts, ASSUMED); PHI@CHI NOT_AVAILABLE (no salaries)',
                  'n': f"{sf['n']} filled entries, 1 contest"})
    w = P['salary']['by_cohort']['winner']
    V.append({'claim': 'FC-08 (winners)', 'text': 'only ~45% of winning lineups use >= $49,500',
              'verdict': 'UNRESOLVED', 'numbers': f"PIT@CLE winner entries: {w['share_ge_49500_used']}% (n={w['n']} tied entries); one winner is one observation",
              'n': '1 contest'})
    d = P['salary']['dupes_on_salary']
    r2l, r2b = d['DUP-01_log_count_on_salary_used_linear']['r2'], d['DUP-01_log_count_on_salary_left_buckets']['r2']
    V.append({'claim': 'DUP-01 (R^2)', 'text': 'salary used vs dupes is weak (R^2 ~.16) and nonlinear',
              'verdict': ('CONFIRMED' if abs(r2l - 0.16) <= TOL['R2_CLAIM_ABS'] else 'FALSIFIED') + (' (weak); nonlinear: '
                         + ('YES' if r2b - r2l > TOL['R2_CLAIM_ABS'] else 'NOT SHOWN')),
              'numbers': f'PIT@CLE unique lineups: linear-in-salary R^2 {r2l} vs .16 (tolerance +/-{TOL["R2_CLAIM_ABS"]}, ASSUMED); '
                         f'salary-left bucket R^2 {r2b} (nonlinear if it beats linear by > the same margin); observed lineups only (selection)',
              'n': f"{d['DUP-01_log_count_on_salary_used_linear']['n']} unique lineups"})
    m = d['DUP-06_vs_DUP-01_log_count_on_log_prod_own_plus_groups(ref exactly $50,000)']
    b, se = m['coef'].get('exactly_49900'), m['hc1_se'].get('exactly_49900')
    if b is None:
        vv = 'UNRESOLVED'
    elif abs(b) < TOL['LOG_EFFECT_NEGLIGIBLE'] and abs(b) + 1.96 * se < 2 * TOL['LOG_EFFECT_NEGLIGIBLE']:
        vv = 'DUP-01 SIDE (no $49,900 effect)'
    elif b <= -TOL['LOG_EFFECT_NEGLIGIBLE'] and b + 1.96 * se < 0:
        vv = 'DUP-06 SIDE ($49,900 less duplicated)'
    else:
        vv = 'UNRESOLVED'
    g = d['DUP-06_vs_DUP-01_group_summary']
    V.append({'claim': 'DUP-06 vs DUP-01', 'text': 'does $49,900 reduce dupes vs $50,000, holding ownership?',
              'verdict': vv,
              'numbers': (f"coef(log count | $49,900 vs $50,000, given log prod own) = {b} (HC1 se {se}); "
                          f"$49,500-49,800 coef {m['coef'].get('49500_49800')}; mean copies per unique lineup "
                          f"50,000: {g['exactly_50000']['mean_copies_per_unique_lineup']}, 49,900: {g['exactly_49900']['mean_copies_per_unique_lineup']}, "
                          f"49,500-49,800: {g['49500_49800']['mean_copies_per_unique_lineup']}"),
              'n': f"{g['exactly_50000']['n_unique_lineups']} / {g['exactly_49900']['n_unique_lineups']} / {g['49500_49800']['n_unique_lineups']} unique lineups; 1 contest"})
    # CF-1
    parts, dirs = [], []
    for cn, lab in (('PIT_CLE', 'PIT@CLE'), ('PHI_CHI', 'PHI@CHI')):
        f_ = res[cn]['construction']['field']['cpt_position']['pct'].get('QB', 0.0)
        t_ = res[cn]['construction']['top_1pct']['cpt_position']['pct'].get('QB', 0.0)
        parts.append(f'{lab}: field QB CPT {f_}% vs top-1% {t_}%')
        dirs.append(f_ > t_)
    in_range = [28 <= res[c]['construction']['field']['cpt_position']['pct'].get('QB', 0) <= 35 for c in ('PIT_CLE', 'PHI_CHI')]
    V.append({'claim': 'CF-1', 'text': CF['CF-1']['question'] + ' (A: DFS Army field 28-35% QB CPT; B: ETR QB 24.1% of top-1%)',
              'verdict': 'UNRESOLVED',
              'numbers': '; '.join(parts) + f'; field QB-CPT share inside 28-35%: {in_range}. Top-1% is outcome-conditioned, '
                         'so a field-vs-top-1% gap records who scored, not a captaining mistake',
              'n': '2 contests'})
    # CF-2
    r2s = {c: res[c]['estimators']['correlation_claims']['CF-2_log_count_on_log_prod_own']['r2'] for c in ('PIT_CLE', 'PHI_CHI')}
    near = lambda v, t: abs(v - t) <= TOL['R2_CLAIM_ABS']
    lab = []
    for c, v in r2s.items():
        lab.append('0.55' if near(v, 0.55) else '0.43' if near(v, 0.43) else 'neither')
    V.append({'claim': 'CF-2', 'text': 'product ownership vs dupes R^2: 0.55 (ETR 2022) vs 0.43 (ETR current)',
              'verdict': ('CONFIRMED ' + lab[0]) if lab[0] == lab[1] and lab[0] != 'neither' else 'UNRESOLVED' if lab[0] != lab[1] else 'FALSIFIED (both)',
              'numbers': (f"R^2 PIT@CLE {r2s['PIT_CLE']}, PHI@CHI {r2s['PHI_CHI']} (log count ~ log product, unique observed lineups; "
                          f"nearest: {lab}); entry-weighted variant R^2 PIT@CLE "
                          f"{res['PIT_CLE']['estimators']['correlation_claims']['CF-2_entry_weighted_variant']['r2']}, PHI@CHI "
                          f"{res['PHI_CHI']['estimators']['correlation_claims']['CF-2_entry_weighted_variant']['r2']}; ETR unit of analysis not stated"),
              'n': f"{P['duplication']['distribution']['n_distinct_lineups']} / {Q['duplication']['distribution']['n_distinct_lineups']} unique lineups"})
    # CF-3
    parts, sup = [], []
    for c, lab_ in (('PIT_CLE', 'PIT@CLE'), ('PHI_CHI', 'PHI@CHI')):
        cc = res[c]['estimators']['correlation_claims']
        a_, b_ = cc['CF-3_log_count_on_log_cpt_share_only']['r2'], cc['CF-3_log_count_on_log_flex_product_only']['r2']
        parts.append(f'{lab_}: R^2 CPT-only {a_} vs FLEX-product-only {b_}')
        sup.append(a_ < b_)
    V.append({'claim': 'CF-3', 'text': 'does CPT ownership drive dupes? (ETR: minimal)',
              'verdict': 'CONFIRMED (CPT explains less than FLEX product)' if all(sup) else 'FALSIFIED' if not any(sup) else 'UNRESOLVED',
              'numbers': '; '.join(parts), 'n': '2 contests'})
    # FC-05
    parts, d_rb, d_s5 = [], [], []
    for c, lab_ in (('PIT_CLE', 'PIT@CLE'), ('PHI_CHI', 'PHI@CHI')):
        ec = res[c]['entrant_cohorts']
        mx = ec[f"at_contest_max_{ec['contest_max_entries_observed']}"]
        one = ec['1']
        rb_m, rb_1 = mx['cpt_position']['pct'].get('RB', 0.0), one['cpt_position']['pct'].get('RB', 0.0)
        s_m, s_1 = mx['sub_5pct_owned_cpt_share'], one['sub_5pct_owned_cpt_share']
        parts.append(f"{lab_} (max={ec['contest_max_entries_observed']}): CPT RB max-entry {rb_m}% vs single {rb_1}%; "
                     f"sub-5% CPT max-entry {s_m}% vs single {s_1}% (n {mx['n_entries']} / {one['n_entries']})")
        d_rb.append(rb_m > rb_1)
        d_s5.append(s_1 > s_m)
    for nm, dd, txt in (('FC-05 (CPT RB)', d_rb, 'max-entry players captain RBs more than single-entry (31.1 vs 24.9)'),
                        ('FC-05 (sub-5% CPT)', d_s5, 'single-entry over-indexes sub-5% CPTs (25.4 vs 16.3)')):
        V.append({'claim': nm, 'text': txt,
                  'verdict': 'CONFIRMED (direction, both contests)' if all(dd) else 'FALSIFIED (direction, both contests)' if not any(dd) else 'UNRESOLVED (contests disagree)',
                  'numbers': '; '.join(parts), 'n': '2 contests; ETR sample was 37-max high-stakes'})
    # E1 top-decile test
    for c, lab_ in (('PIT_CLE', 'PIT@CLE'), ('PHI_CHI', 'PHI@CHI')):
        ev = res[c]['estimators']['evaluation']['OBSERVED_ALL_UNIQUE']['E1']
        V.append({'claim': f'E1 top-chalk-decile bias ({lab_})', 'text': 'falsify E1 if biased > 2x in the top decile of E1',
                  'verdict': 'FALSIFIED' if ev['top_decile_biased_gt_2x'] else 'NOT FALSIFIED (within 2x)',
                  'numbers': f"actual/pred in E1 top decile {ev['top_decile_actual_over_pred']}; Spearman {ev['spearman_with_actual']}; "
                             f"median |log((p+1)/(a+1))| {ev['median_abs_log_err']}",
                  'n': f"{res[c]['estimators']['evaluation']['OBSERVED_ALL_UNIQUE']['n_lineups']} observed unique lineups"})
    # E1-vs-E3 flag
    fl = P['estimators']['evaluation']['E1_vs_E3_FLAG_TEST']
    for k in ('E3_NONE|observed', 'E3_NONE|observed_plus_generated', 'E3_FC08_90PCT_LE_500|observed_plus_generated'):
        f = fl[k]
        sh = f['share_of_disagreements_where_actual_closer_to_E3']
        V.append({'claim': f'E1-vs-E3 >2x flag ({k})', 'text': 'when E1 and E3 disagree by >2x, is actual closer to E3?',
                  'verdict': 'UNRESOLVED' if sh is None else ('CONFIRMED (E3 closer in a majority)' if sh > 50 else 'FALSIFIED (E1 closer in a majority)'),
                  'numbers': f"{f['n_disagree_gt_2x']} disagreements; actual closer to E3 in {sh}%; ORACLE configuration",
                  'n': f"{f['n_lineups']} lineups, PIT@CLE only"})
    return V


def atl_no_context(P):
    ctx = []
    for p in ATL_NO_STACKS:
        if not p.exists():
            ctx.append({'file': rel(p), 'status': 'ABSENT'})
            continue
        d = json.loads(p.read_text())
        b = d['by_phi'].get(str(AF.PHI_REPORTED)) or d['by_phi'].get(f'{AF.PHI_REPORTED}')
        c = (b or {}).get('contests', {}).get(ATL_NO_TWO_ENTRY_CONTEST)
        if not c or not c.get('lineups'):
            ctx.append({'file': rel(p), 'status': 'NO_TWO_ENTRY_LINEUPS'})
            continue
        ctx.append({'file': rel(p), 'sha256': sha(p), 'lineups': [
            {'captain': r['captain'], 'E1': r['E1_independent_product'], 'E3': r['E3_archetype_field'],
             'E4': r['E4_optimizer_field'],
             'log_E3_over_E1': r4(math.log(float(r['E3_archetype_field']) / r['E1_independent_product']))
             if isinstance(r['E3_archetype_field'], (int, float)) and r['E1_independent_product'] > 0 else None}
            for r in c['lineups']]})
    ev = P['estimators']['evaluation']['OBSERVED_ALL_UNIQUE']
    errs = {k: ev[k]['median_abs_log_err'] for k in ev if isinstance(ev[k], dict) and 'median_abs_log_err' in ev[k]}
    return {'atl_no_two_entry_contest': ATL_NO_TWO_ENTRY_CONTEST, 'atl_no_board_values': ctx,
            'pit_cle_median_abs_log_err_observed': errs,
            'pit_cle_E3_over_E1_ge_5x': {k: v['E3_over_E1_ge_5x(ATL@NO-like)'] for k, v in P['estimators']['evaluation']['E1_vs_E3_FLAG_TEST'].items()},
            'pit_cle_E3_ge_20_and_ge_5x_E1': {k: v['E3_ge_20_and_ge_5x_E1(ATL@NO-sized)'] for k, v in P['estimators']['evaluation']['E1_vs_E3_FLAG_TEST'].items()},
            'NOT_SCORED': 'ATL@NO is a different slate and is not scored here; this is context only'}


def write_findings(doc):
    P, Q = doc['contests']['PIT_CLE'], doc['contests']['PHI_CHI']
    L = []
    a = L.append
    a('# Showdown history calibration: PIT@CLE (2026-10-01) and PHI@CHI (2026-09-28)')
    a('')
    a(f"Generated by `nfl/field/showdown_history_calibration.py` at {doc['as_of_utc']}. RESEARCH ONLY; nothing here is "
      'promoted, and nothing here is a football input.')
    a('')
    a('**Two slates are two observations.** Games are not independent, each contest is one draw of one field, and the '
      'field sizes (~47.5k entries each) make within-contest standard errors tiny while saying nothing about the next '
      'slate. Every verdict below is a statement about these two files only.')
    a('')
    a('| contest | raw sha256 | N entries | empty lineups (excluded) | filled | top-1% cut (rank <=) | rank-1 entries |')
    a('|---|---|---|---|---|---|---|')
    for c in (P, Q):
        a(f"| {c['game']} {c['contest_id']} | `{c['raw']['sha256']}` | {c['N_all_entries']} | {c['N_empty_lineup_excluded']} | "
          f"{c['N_filled_lineups']} | {c['top_1pct_cut_rank']} | {c['n_winner_entries']} |")
    a('')
    a('## Verdicts on ledger / addendum claims')
    a('')
    a('| claim | what it says | verdict | numbers | n |')
    a('|---|---|---|---|---|')
    for v in doc['verdicts']:
        a(f"| {v['claim']} | {v['text'].replace('|', '/')} | **{v['verdict']}** | {v['numbers'].replace('|', '/')} | {v['n']} |")
    a('')
    a('Tolerances used for the verdicts were declared in the script before any result was read: '
      + ', '.join(f'{k} = {v}' for k, v in doc['TOLERANCES'].items()) + '. The ownership-point tolerance comes from '
      "ledger DATA-05's own falsification rule; the share and R^2 margins are ASSUMED.")
    a('')
    a('## Ownership')
    for c in (P, Q):
        o = c['ownership']
        a(f"- {c['game']}: DK %Drafted sums CPT {o['dk_sum_pct']['CPT']} / FLEX {o['dk_sum_pct']['FLEX']}; recount from lineups "
          f"max |diff| {o['recount_max_abs_diff_pct_pts_over_all_entries']} pts over all entries "
          f"({o['recount_max_abs_diff_pct_pts_over_filled']} over filled); flag >0.5: {o['recount_flag_gt_0.5']}.")
        bp = ', '.join(f"{k} {v['cpt_to_flex_ratio']}" for k, v in o['by_position'].items())
        a(f"  CPT:FLEX ratio by position: {bp}.")
        if isinstance(o['by_salary_rank'], dict) and o['by_salary_rank'].get('status') != 'NOT_AVAILABLE':
            a('  by FLEX-salary rank: ' + ', '.join(f"{k} {v['cpt_to_flex_ratio']}" for k, v in o['by_salary_rank'].items()) + '.')
        else:
            a('  by salary rank: NOT_AVAILABLE (no salary file).')
        bf = o['by_favorite']
        if bf.get('status') == 'NOT_AVAILABLE':
            a(f"  favorite: NOT_AVAILABLE ({bf['reason']}).")
        else:
            a('  favorite vs underdog: ' + ', '.join(f"{k} {v['cpt_to_flex_ratio']}" for k, v in bf.items() if k != 'favorite_source')
              + f" (favorite from {bf['favorite_source']['implied_team_totals']}, third-party VegasPts).")
        top = sorted(o['players'], key=lambda p: -p['dk_flex_pct'])[:8]
        a('  top FLEX: ' + '; '.join(f"{p['player']} ({p['position']}) {p['dk_cpt_pct']}/{p['dk_flex_pct']} = {p['cpt_to_flex_ratio']}" for p in top) + '.')
    a('')
    a('## Duplication')
    for c in (P, Q):
        d = c['duplication']['distribution']
        a(f"- {c['game']}: {d['n_distinct_lineups']} distinct lineups over {d['n_entries_filled']} entries; entries unique "
          f"{d['share_of_entries_unique']}%, in lineups duplicated >=2 {d['share_of_entries_in_lineups_dup_ge_2']}%, >=10 "
          f"{d['share_of_entries_in_lineups_dup_ge_10']}%, >=50 {d['share_of_entries_in_lineups_dup_ge_50']}%; max copies {d['max_copies']}.")
        for wl in c['duplication']['winner_lineups']:
            a(f"  winner lineup CPT {wl['cpt']} + {', '.join(wl['flex'])}: {wl['copies_in_field']} copies in the field.")
        t = c['duplication']['top_1pct']
        a(f"  top-1%: {t['n_entries']} entries, {t['n_distinct_lineups']} distinct lineups; copies of their lineups "
          f"median {t['copies_in_field_of_top1pct_entries']['median']}, unique {t['copies_in_field_of_top1pct_entries']['share_unique']}%.")
    a('')
    a('## Salary left (PIT@CLE only; PHI@CHI NOT_AVAILABLE, no salary file)')
    s = P['salary']['by_cohort']
    a('| cohort | n | ' + ' | '.join(b for b, _l, _h in SAL_BUCKETS) + ' | >= $49,500 used | exactly $50,000 |')
    a('|---|---|' + '---|' * len(SAL_BUCKETS) + '---|---|')
    for k, v in s.items():
        a(f"| {k} | {v['n']} | " + ' | '.join(str(v['bucket_pct'][b]) for b, _l, _h in SAL_BUCKETS) +
          f" | {v['share_ge_49500_used']} | {v['share_exactly_50000']} |")
    ds = P['salary']['dupes_on_salary']
    m1 = ds['MODEL_log_count_on_log_prod_own']
    m2 = ds['MODEL_log_count_on_log_prod_own_plus_salary_left_buckets(ref $0)']
    a(f"- log(count) ~ log(product ownership): slope {m1['coef'].get('log_prod_own')}, R^2 {m1['r2']}, n {m1['n']}.")
    a(f"- plus salary-left buckets (ref $0): R^2 {m2['r2']}; coefficients {m2['coef']}.")
    a(f"- {ds['SELECTION_CAVEAT']}")
    a('')
    a('## Construction (field vs top-1% vs winner; top-1% and winner are outcome-conditioned)')
    for c in (P, Q):
        cn = c['construction']
        a(f"- {c['game']}:")
        for k in ('field', 'top_1pct', 'winner'):
            x = cn[k]
            a(f"  - {k} (n {x['n']}): split {x['team_split_away_home'].get('pct')}; QB count {x['qb_count'].get('pct')}; "
              f"K+DST {x['k_plus_dst_count'].get('pct')}; CPT pos {x['cpt_position'].get('pct')}; "
              f"CPT WR/TE with own QB {x['cpt_pass_catcher_with_own_qb_in_flex'].get('pct', {}).get('True')}% of all entries "
              f"({x['given_cpt_wr_te_share_with_own_qb_in_flex'].get('pct', {}).get('True')}% of WR/TE-captained entries)")
    a('')
    a('## Entrant cohorts')
    for c in (P, Q):
        a(f"- {c['game']} (largest N in (k/N): {c['entrant_cohorts']['contest_max_entries_observed']}):")
        for k, v in c['entrant_cohorts'].items():
            if isinstance(v, dict) and 'n_entries' in v:
                a(f"  - {k}: n {v['n_entries']} ({v['n_users']} users); CPT pos {v['cpt_position'].get('pct')}; sub-5% CPT "
                  f"{v['sub_5pct_owned_cpt_share']}%; no K/DST {v['no_k_no_dst_share'].get('pct', {}).get('True')}%; "
                  f"geomean own {v['mean_geomean_ownership_pct']}%; mean copies {v['mean_copies_of_own_lineup']}; unique "
                  f"{v['share_unique']}%" + (f"; mean salary left {v['mean_salary_left']}" if 'mean_salary_left' in v else ''))
            elif isinstance(v, dict) and v.get('status') == 'NOT_AVAILABLE':
                a(f"  - {k}: NOT_AVAILABLE ({v['reason']})")
    a('')
    a('## Dupe estimators vs actual counts')
    a('E1 uses ACTUAL ownership (an oracle); E3 is an ORACLE configuration (actual ownership targets and actual archetype '
      'rates). Neither is a forecast. GEO is identical to E1 (N x GEO^6) and has no separate metric.')
    for c in (P, Q):
        a(f"- {c['game']}:")
        for setn, ev in c['estimators']['evaluation'].items():
            if not isinstance(ev, dict) or 'n_lineups' not in ev:
                continue
            a(f"  - {setn} (n {ev['n_lineups']}, actual copies {ev['sum_actual']}):")
            for k, m in ev.items():
                if isinstance(m, dict) and 'median_abs_log_err' in m:
                    a(f"    - {k}: median|logerr| {m['median_abs_log_err']}, mean {m['mean_abs_log_err']}, Spearman "
                      f"{m['spearman_with_actual']}, top-decile actual/pred {m['top_decile_actual_over_pred']}, sum pred {m['sum_pred']}")
        if 'E3' in c['estimators']['evaluation']:
            a(f"  - E3/E4: {c['estimators']['evaluation']['E3']['reason']}; {c['estimators']['evaluation']['E4']['reason']}")
    for c in (P, Q):
        sp = c['estimators']['evaluation']['OBSERVED_ALL_UNIQUE']['E1']['sum_pred']
        a(f"- {c['game']}: E1 is not normalised. Summed over the OBSERVED lineups alone it predicts {sp} copies against "
          f"{c['N_filled_lineups']} entries: CPT share x product of FLEX shares is not a probability distribution over "
          'lineups (nothing in it requires the other players to be absent), so its level is not a count.')
    gf = P['estimators']['generated_fields']
    a('- PIT@CLE generated-field diagnostics: ' + '; '.join(
        f"{k}: K {v['k']}, distinct {v['distinct_lineups']}"
        + (f", accept {v['accept_rate']}, ownership residual RMSE {v['final_residual_rmse_pts']}" if 'accept_rate' in v else '')
        + (f", ownership RMSE vs actual {v['ownership_rmse_vs_actual_pts']}" if 'ownership_rmse_vs_actual_pts' in v else '')
        + f", generated salary-left {v['generated_salary_left_bucket_pct']}" for k, v in gf.items()))
    ov = P['estimators']['evaluation'].get('OVER_PREDICTION_ON_EACH_GENERATED_FIELDS_OWN_PREDICTIONS', {})
    if ov:
        a('- PIT@CLE over-prediction (lineups each generated field predicts, including those nobody played):')
        for k, v in ov.items():
            a(f"  - {k}: {v['n_lineups_predicted']} predicted lineups, {v['share_predicted_lineups_unplayed']}% unplayed, "
              f"{v['share_of_pred_mass_on_unplayed']} of predicted copies on unplayed lineups")
    a('')
    a('## Context: ATL@NO E1-vs-E3 disagreement (NOT scored; different slate)')
    ctx = doc['atl_no_context']
    for f in ctx['atl_no_board_values']:
        if 'lineups' in f:
            a(f"- {f['file']}: " + '; '.join(f"CPT {r['captain']} E1 {r['E1']} vs E3 {r['E3']} (log ratio {r['log_E3_over_E1']})" for r in f['lineups']))
    a(f"- PIT@CLE median |log((pred+1)/(actual+1))| on observed lineups: {ctx['pit_cle_median_abs_log_err_observed']}")
    for k, v in ctx['pit_cle_E3_over_E1_ge_5x'].items():
        a(f"- PIT@CLE lineups where E3 >= 5x E1 ({k}): n {v['n']}, median actual {v['median_actual']}, median E1 {v['median_E1']}, "
          f"median E3 {v['median_E3']}, actual closer to E3 in {v['share_actual_closer_to_E3']}%")
    for k, v in ctx['pit_cle_E3_ge_20_and_ge_5x_E1'].items():
        a(f"- PIT@CLE ATL@NO-sized disagreements, E3 >= 20 copies and >= 5x E1 ({k}): n {v['n']}, median actual {v['median_actual']}, "
          f"median E1 {v['median_E1']}, median E3 {v['median_E3']}, unplayed {v['share_unplayed']}%, actual closer to E3 in "
          f"{v['share_actual_closer_to_E3']}%")
    a('')
    a('## NOT_AVAILABLE, and why')
    for x in doc['NOT_AVAILABLE']:
        a(f'- {x}')
    a('')
    a('## Caveats')
    for x in doc['CAVEATS']:
        a(f'- {x}')
    a('')
    a('Nothing in this file is promoted. No estimator, prior or tolerance here changes a production lineup, and no '
      'wager is recommended.')
    p = OUT / 'FINDINGS.md'
    p.write_text('\n'.join(L) + '\n')
    return p


def main():
    before = {rel(c['dir'] / x.name): sha(x) for c in CONTESTS for x in c['dir'].iterdir()}
    L, CF = ledger()
    res = {}
    for c in CONTESTS:
        print('analysing', c['label'], flush=True)
        res[c['label']] = analyse(c)
    V = verdicts(res, L, CF)
    doc = {'ARTIFACT': 'SHOWDOWN_HISTORY_CALIBRATION', 'label': LABEL,
           'as_of_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'script': 'nfl/field/showdown_history_calibration.py',
           'TWO_OBSERVATIONS': ('two contests on two slates: two observations; games are not independent; nothing '
                                'here is promoted or validated'),
           'TOLERANCES': TOL, 'contests': res, 'verdicts': V, 'atl_no_context': atl_no_context(res['PIT_CLE']),
           'NOT_AVAILABLE': [
               'PHI@CHI salary left, cap checks, salary regressions, DUP-01/DUP-06 tests: no salary file exists',
               'PHI@CHI E3 (archetype field) and E4 (optimizer field): need salaries / a public projection for that slate',
               'PHI@CHI favorite flag: no spread or implied total in the repository; none invented',
               'PHI@CHI CPT:FLEX by salary rank: no salaries',
               'DATA-04 (ATL vs GB 238K contest): different slate, not testable on these files',
               'payouts / ROI: the standings export carries no prize table'],
           'CAVEATS': [
               'Only lineups somebody played have observable counts; on observed sets low-predicted lineups are '
               'necessarily under-predicted. Generated-field sets add predicted-but-unplayed lineups (actual 0).',
               'E1 and E3 here use ACTUAL ownership and ACTUAL archetype rates (ORACLE). Their errors are a lower bound '
               'on what a pre-lock estimate with forecast ownership would achieve.',
               'Top-1% and winner cohorts are conditioned on the realised outcome; their construction mix is not a '
               'statement about what the field should have built.',
               'Both contests are large-field (~47.5k), 20-max DK Showdowns (PIT@CLE contest name from the owner export: '
               + 'see metadata.contest_names; PHI@CHI contest name is not on file); ledger sources describe other '
               'contest types (e.g. ETR FC-05: 37-max high-stakes, 1,000-1,500 entries).',
               'Ledger FTA ownership (DATA-05/06) does not state which contest it comes from; a difference from this '
               'contest can be a contest difference rather than an error.',
               'HC1 standard errors treat lineups as independent; they are not.',
               'Median |log((pred+1)/(actual+1))| is resolution-bound for E3/E4: a generated field of K lineups cannot '
               'predict fewer than N/K copies except 0, so a played-once lineup it missed scores log 2 = 0.6931 and '
               'a lineup nobody played that it also missed scores 0. Read Spearman, the decile calibration, the '
               'top-50 set and the over-prediction block alongside the medians.']}
    for c in res.values():
        for k in ('players',):
            need(c['ownership'][k], 'OWNERSHIP_PLAYERS_EMPTY', c['game'])
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / 'SHOWDOWN_HISTORY_CALIBRATION.json'
    jp.write_text(json.dumps(doc, indent=1, default=str))
    need(jp.stat().st_size > 0, 'JSON_WRITE_EMPTY')
    fp = write_findings(doc)
    after = {rel(c['dir'] / x.name): sha(x) for c in CONTESTS for x in c['dir'].iterdir()}
    need(before == after, 'RAW_INPUT_CHANGED_DURING_RUN', str(set(before.items()) ^ set(after.items())))
    print(rel(jp))
    print(rel(fp))
    for v in V:
        print(f"{v['claim']:<50} {v['verdict']:<45} {v['numbers'][:160]}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ShowdownHistoryError as e:
        print('REFUSED', e.code, str(e))
        raise SystemExit(2)
