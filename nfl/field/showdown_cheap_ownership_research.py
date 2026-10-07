#!/usr/bin/env python3.12
"""Cheap rotation-player OWNERSHIP successor (SC-OWN-ROTATION-1), leave-one-slate-out. SHADOW_ONLY. EXPLORATORY.

    python3.12 nfl/field/showdown_cheap_ownership_research.py      # -> nfl/postgame/dupe_research/CHEAP_OWNERSHIP_LOSO.json

Pre-registration: docs/NFL_SHOWDOWN_CHEAP_OWNERSHIP_PREREGISTRATION.md, written and hashed BEFORE this module was
written or run (PREREG_SHA256_AT_WRITE below). The run refuses if the document is missing, empty, or no longer
hashes to that value -- a changed pre-registration is a different experiment.

WHAT IT IS. A few-parameter multiplicative correction of the existing shadow ownership forecast
(nfl/field/showdown_shadow_field.py) by prelock bucket and role features:

    q_i ~ exp(t0 log(b_i + kappa) + t1 CHEAP_i + t2 FRINGE_i + t3 snap_share_i + t4 injury_opp_i),  pct = q_i * M

fitted per slot (CPT, FLEX) on the training slate's realised shares, scored on the held-out slate.

WHAT IT IS NOT. Not a football input; not on the execution path; nothing in production, the simulator, the
optimizer or the portfolio imports it. Realised ownership of the slate being predicted is never a feature:
`prelock_features` does not accept contest entries at all; entries reach only `actual_ownership`, which feeds the
fit (training slate) and the score (test slate).

FC BOUNDARY. FantasyCruncher enters only through the baseline shadow ownership, exactly as it already does in
showdown_shadow_field.py (the FLEX `FC` projection column). No FC column is a successor feature.

Every stage asserts non-empty, schema-correct output and raises CheapOwnershipError(<NAMED CODE>) otherwise.
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

LABEL = 'SHADOW_ONLY'
STATUS = 'SHADOW_ONLY -- EXPLORATORY (ATL@NO is development data; two testable folds)'
PREREG = _REPO / 'docs/NFL_SHOWDOWN_CHEAP_OWNERSHIP_PREREGISTRATION.md'
#: sha256 of the pre-registration, computed 2026-10-07T04:30:59Z, after it was written and before any fit
PREREG_SHA256_AT_WRITE = '8e70ab1bfe6ad6a948d15e1909043d02a9e0e2bbacd3e0c31a1ce9cb7fdd0ff5'
OUT = _REPO / 'nfl/postgame/dupe_research'
ARTIFACT = OUT / 'CHEAP_OWNERSHIP_LOSO.json'

RAW = _REPO / 'nfl/dfs/salaries/raw'
RAW_ATL = RAW / 'showdown_atl_no_2026W4'
ATL_DIR = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
SNAPS = RAW_ATL / 'snap_counts_2026.53720f396f9c2bfa.csv'
ROSTER = RAW_ATL / 'roster_weekly_2026.0f72f882f3974ff2.csv'
USAGE = _REPO / 'nfl/derived/USAGE_HISTORY_2021_2026.json'
SEASON = '2026'

# ----------------------------------------------------------------------------- pre-registered constants
CAP = 50000
CHEAP_SALARY = 1000          # source: nfl/dfs/showdown/candidates.CHEAP_SALARY (punt line)
MID_SALARY = 4000            # PRIOR (prereg section 3)
STAR_SALARY = 8000           # PRIOR (prereg section 3)
ROLE_SLOTS = {'QB': 1, 'RB': 2, 'WR': 4, 'TE': 2}       # PRIOR
STARTER_SLOTS = {'QB': 1, 'RB': 1, 'WR': 3, 'TE': 1}    # PRIOR, stored only
ROLE_SNAP_SHARE = 0.20       # PRIOR
KAPPA = 0.5                  # PRIOR, percentage points
LAMBDA = 0.01                # PRIOR, ridge toward THETA_PRIOR
THETA_PRIOR = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
FEATURES = ('log_baseline_plus_kappa', 'is_cheap_active_rotation', 'is_punt_fringe', 'snap_share_mean', 'injury_opp')
MASS = {'cpt': 100.0, 'flex': 500.0}
MARGIN = {'flex': 1.0, 'cpt': 0.5, 'total': 1.0}          # pp; sources in prereg section 7
MIN_CHEAP_N = 3
KL_FLOOR = 1e-4
BUCKETS = ('STAR', 'MIDRANGE', 'CHEAP_ACTIVE_ROTATION', 'PUNT_FRINGE', 'K_DST')
CHEAP = 'CHEAP_ACTIVE_ROTATION'
SENSITIVITY = {'lambda_0': {'lam': 0.0, 'kappa': KAPPA}, 'kappa_1.0': {'lam': LAMBDA, 'kappa': 1.0}}

#: the only fields bucket assignment may read -- all prelock
BUCKET_FIELDS = ('position', 'flex_salary', 'role_evidence')
#: fields prelock_features must emit (schema)
FEATURE_SCHEMA = ('name', 'team', 'position', 'pos_group', 'flex_salary', 'cpt_salary', 'absent', 'n_prior_weeks',
                  'snap_share_mean', 'snap_share_last', 'snap_share_sd', 'opp_share_mean', 'targets_prior',
                  'carries_prior', 'depth_rank_all', 'depth_rank_active', 'injury_opp', 'starter', 'role_evidence',
                  'salary_relief_k', 'optimizer_feasible', 'baseline_cpt', 'baseline_flex', 'bucket',
                  'scarcity_n_cheap', 'cheap_salary_rank')
SUFFIX = re.compile(r'\s+(jr|sr|ii|iii|iv|v)$')


class CheapOwnershipError(RuntimeError):
    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def need(cond, code, detail=''):
    if not cond:
        raise CheapOwnershipError(code, detail)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def rel(p):
    try:
        return str(pathlib.Path(p).resolve().relative_to(_REPO))
    except ValueError:
        return str(p)


def norm(n):
    return SUFFIX.sub('', n.replace('.', '').lower().strip()).strip()


def r4(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 4)


def pos_group(pos):
    return 'RB' if pos in ('RB', 'FB') else pos


# ==================================================================================== stage 1: prelock data
def check_prereg():
    need(PREREG.exists() and PREREG.stat().st_size > 0, 'PREREG_ABSENT', rel(PREREG))
    h = sha(PREREG)
    need(h == PREREG_SHA256_AT_WRITE, 'PREREG_CHANGED_AFTER_WRITE', f'{h} != {PREREG_SHA256_AT_WRITE}')
    return h


def load_pool(export):
    """DK pool: name -> club, position, salaries. Prelock (the owner's DK export)."""
    from nfl.tools import showdown_to_portfolio as S
    ing = S.s1_ingest(pathlib.Path(export))
    need(ing.state.value == 'PASS', 'EXPORT_INGEST', f'{export}: {ing.detail}')
    si = S.s2_slate_identity(ing.value['pool'])
    need(si.state.value == 'PASS', 'SLATE_IDENTITY', f'{export}: {si.detail}')
    pool = {}
    for v in si.value['players'].values():
        need(v['name'] not in pool, 'POOL_NAME_NOT_UNIQUE', v['name'])
        pool[v['name']] = {'team': v['dk_team'], 'position': v['position'], 'flex_salary': int(v['flex']['salary']),
                           'cpt_salary': int(v['cpt']['salary'])}
    need(pool, 'POOL_EMPTY', str(export))
    need(len({v['team'] for v in pool.values()}) == 2, 'POOL_NOT_TWO_CLUBS', str(export))
    return pool, si.value


def load_snaps(path, teams, before_week):
    """Prior-week offensive snap rows for `teams`, weeks strictly < before_week. {(norm name, team): [rows]}."""
    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8')))
    need(rows, 'SNAPS_EMPTY', rel(path))
    for c in ('season', 'game_type', 'week', 'player', 'position', 'team', 'offense_snaps', 'offense_pct'):
        need(c in rows[0], 'SNAPS_SCHEMA', c)
    out = collections.defaultdict(list)
    for r in rows:
        if r['season'] != SEASON or r['game_type'] != 'REG' or r['team'] not in teams:
            continue
        w = int(r['week'])
        if w >= before_week:
            continue
        out[(norm(r['player']), r['team'])].append({'week': w, 'pos': r['position'], 'name': r['player'],
                                                    'offense_pct': float(r['offense_pct'] or 0.0),
                                                    'offense_snaps': int(float(r['offense_snaps'] or 0))})
    need(out, 'SNAPS_NO_PRIOR_ROWS', f'{teams} before week {before_week}')
    need(all(x['week'] < before_week for v in out.values() for x in v), 'SNAPS_FUTURE_WEEK_LEAK', str(before_week))
    return dict(out)


def load_identity(path, teams):
    """(team, norm name) -> gsis_id from roster identity columns only (status is post-hoc and never read)."""
    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8')))
    need(rows, 'ROSTER_EMPTY', rel(path))
    for c in ('team', 'full_name', 'football_name', 'last_name', 'gsis_id'):
        need(c in rows[0], 'ROSTER_SCHEMA', c)
    ix = collections.defaultdict(set)
    for r in rows:
        if r['team'] in teams and r['gsis_id']:
            ix[(r['team'], norm(r['full_name']))].add(r['gsis_id'])
            ix[(r['team'], norm(f"{r['football_name']} {r['last_name']}"))].add(r['gsis_id'])
    need(ix, 'ROSTER_NO_TEAM_ROWS', str(teams))
    return {k: next(iter(v)) for k, v in ix.items() if len(v) == 1}


def load_usage(path, before_week):
    d = json.loads(pathlib.Path(path).read_text())
    need(d.get('artifact') == 'USAGE_HISTORY_2021_2026' and d.get('players') and d.get('teams'), 'USAGE_SCHEMA', rel(path))
    pl = {g: {int(w): r for w, r in v.get(SEASON, {}).items() if int(w) < before_week} for g, v in d['players'].items()}
    tm = {t: {int(w): r for w, r in v.get(SEASON, {}).items() if int(w) < before_week} for t, v in d['teams'].items()}
    need(any(pl.values()), 'USAGE_NO_PRIOR_ROWS', str(before_week))
    return pl, tm


# ========================================================================================= stage 2: baseline
def load_frozen_baseline(path):
    """Frozen prelock shadow ownership CSV -> {name: {'team', 'cpt', 'flex'}} (percentage points)."""
    rows = list(csv.DictReader(open(path, newline='')))
    need(rows, 'BASELINE_EMPTY', rel(path))
    for c in ('player', 'team', 'shadow_cpt_own_pct', 'shadow_flex_own_pct'):
        need(c in rows[0], 'BASELINE_SCHEMA', f'{rel(path)}: {c}')
    out = {r['player']: {'team': r['team'], 'cpt': float(r['shadow_cpt_own_pct']), 'flex': float(r['shadow_flex_own_pct'])}
           for r in rows}
    _baseline_mass(out, rel(path))
    return out


def _baseline_mass(b, where):
    c, f = sum(v['cpt'] for v in b.values()), sum(v['flex'] for v in b.values())
    # the CSV rounds to 2 dp; 0.5 pp total slack covers rounding over ~40 rows
    need(abs(c - 100.0) < 0.5 and abs(f - 500.0) < 0.5, 'BASELINE_MASS', f'{where}: cpt {c:.2f} flex {f:.2f}')


def _field_baseline(slate, absent_names, fc, sigma):
    from nfl.field import showdown_shadow_field as SF
    absent_keys = {k for k, v in slate['players'].items() if v['name'] in absent_names}
    L = SF.field(slate, absent_keys, fc, sigma)
    need(L, 'RECON_FIELD_EMPTY', f'sigma {sigma}')
    own = SF.ownership(L, slate)
    out = {slate['players'][k]['name']: {'team': slate['players'][k]['dk_team'], 'cpt': v['cpt'], 'flex': v['flex']}
           for k, v in own.items()}
    _baseline_mass(out, 'reconstructed field')
    return out, len(L)


def verify_reconstruction_on_atl():
    """Re-run the frozen method on ATL@NO's frozen inputs; refuse unless it reproduces the frozen FC_ONLY exactly."""
    from nfl.field import showdown_shadow_field as SF
    doc = json.loads((ATL_DIR / 'SHADOW_RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_SHADOW_FIELD.json').read_text())
    sigma = doc['sigma_chosen']
    _, slate = load_pool(ATL['export'])
    fc = SF.fc_projection(ATL['fc_official'])
    need(fc, 'FC_EMPTY', rel(ATL['fc_official']))
    rec, k = _field_baseline(slate, set(json.loads(ATL['absent'].read_text())), fc, sigma)
    frozen = load_frozen_baseline(ATL['baseline']['FC_ONLY'])
    names = set(rec) | set(frozen)
    diff = max(max(abs(rec.get(n, {}).get(s, 0.0) - frozen.get(n, {}).get(s, 0.0)) for s in ('cpt', 'flex')) for n in names)
    need(diff < 0.006, 'RECONSTRUCTION_DOES_NOT_REPRODUCE_FROZEN', f'max abs diff {diff}')  # CSV is rounded to 2 dp
    return {'sigma': sigma, 'k': k, 'players': len(names), 'max_abs_diff_pct_pts': r4(diff), 'state': 'REPRODUCES_FROZEN_FC_ONLY',
            'fc_file': rel(ATL['fc_official']), 'fc_sha256': sha(ATL['fc_official'])}


def reconstruct_pit_baseline(sigma):
    """PIT@CLE has NO frozen prelock ownership forecast. Same method, same constants, prelock-dated inputs."""
    from nfl.field import showdown_shadow_field as SF
    from nfl.field import showdown_history_calibration as HC
    _, slate = load_pool(PIT['export'])
    fc = SF.fc_projection(PIT['fc'])
    need(fc, 'FC_EMPTY', rel(PIT['fc']))
    # suffix-alias reconciliation, as showdown_history_calibration.generated_fields (E4) already does it
    pk = {(v['name'], v['dk_team']) for v in slate['players'].values()}
    fc2, alias, unres = {}, {}, []
    for (n, t), v in fc.items():
        if (n, t) in pk:
            fc2[(n, t)] = v
            continue
        hit = [(pn, pt) for pn, pt in pk if pt == t and HC.SUFFIX.sub('', pn) == HC.SUFFIX.sub('', n)]
        if len(hit) == 1:
            alias[f'{n}|{t}'] = f'{hit[0][0]}|{t}'
            fc2[hit[0]] = v
        else:
            unres.append(f'{n}|{t}')
    need(fc2, 'FC_NO_POOL_MATCH', rel(PIT['fc']))
    absent = json.loads(PIT['absent'].read_text())
    need(isinstance(absent, list) and absent, 'INACTIVES_EMPTY', rel(PIT['absent']))
    out, k = _field_baseline(slate, set(absent), fc2, sigma)
    return out, {'state': 'RECONSTRUCTED_POSTGAME_FROM_PRELOCK_INPUTS', 'sigma': sigma, 'k': k, 'seed': SF.SEED,
                 'fc_file': rel(PIT['fc']), 'fc_sha256': sha(PIT['fc']), 'fc_aliases': alias, 'fc_unresolved': unres,
                 'FC_CAPTURE_TIME': 'NOT_RECORDED (supplied by the owner on game day 2026-10-01)',
                 'absent_file': rel(PIT['absent']), 'absent_sha256': sha(PIT['absent'])}


# ================================================================================ stage 3: prelock features
def assign_bucket(row):
    """Bucket from PRELOCK fields only (BUCKET_FIELDS). Any other key in `row` is ignored."""
    for f in BUCKET_FIELDS:
        need(f in row and row[f] is not None, 'BUCKET_FIELD_MISSING', f)
    pos, sal, role = row['position'], row['flex_salary'], row['role_evidence']
    need(isinstance(sal, int) and sal > 0, 'BUCKET_SALARY_INVALID', str(sal))
    if pos in ('K', 'DST'):
        return 'K_DST'
    if sal <= CHEAP_SALARY or not role:
        return 'PUNT_FRINGE'
    if sal >= STAR_SALARY:
        return 'STAR'
    if sal >= MID_SALARY:
        return 'MIDRANGE'
    return CHEAP


def _rank(values):
    """1 = largest; dict name -> rank."""
    order = sorted(values, key=lambda k: (-values[k], k))
    return {k: i + 1 for i, k in enumerate(order)}


def prelock_features(slate_id, pool, absent, baseline, snaps, identity, usage, before_week):
    """Per-player prelock rows. Takes NO contest entries: nothing realised about this slate can enter."""
    need(pool, 'EMPTY_POOL', slate_id)
    need(isinstance(baseline, dict) and baseline, 'EMPTY_BASELINE', slate_id)
    need(snaps, 'EMPTY_SNAPS', slate_id)
    absent = set(absent)
    teams = {v['team'] for v in pool.values()}
    pl_usage, tm_usage = usage
    # per club x position group: mean prior snap share of every club player with a prior row
    agg = {}
    for (nn, team), rs in snaps.items():
        agg[(nn, team)] = {'mean': float(np.mean([r['offense_pct'] for r in rs])),
                           'last': max(rs, key=lambda r: r['week'])['offense_pct'],
                           'sd': float(np.std([r['offense_pct'] for r in rs])) if len(rs) > 1 else 0.0,
                           'n': len({r['week'] for r in rs}), 'pos': pos_group(rs[0]['pos'])}
    in_pool = {(norm(n), v['team']): n for n, v in pool.items()}
    group_all = collections.defaultdict(dict)
    group_active = collections.defaultdict(dict)
    for key, a in agg.items():
        name = in_pool.get(key)
        g = pos_group(pool[name]['position']) if name else a['pos']
        group_all[(key[1], g)][key] = a['mean']
        if name and name not in absent:
            group_active[(key[1], g)][key] = a['mean']
    rank_all = {gk: _rank(v) for gk, v in group_all.items()}
    rank_act = {gk: _rank(v) for gk, v in group_active.items()}
    rows = []
    for name, v in sorted(pool.items()):
        key = (norm(name), v['team'])
        g = pos_group(v['position'])
        a = agg.get(key)
        gk = (v['team'], g)
        if a is not None:
            ra, rc = rank_all[gk][key], rank_act.get(gk, {}).get(key)
        else:
            ra, rc = len(group_all.get(gk, {})) + 1, len(group_active.get(gk, {})) + 1
        rc = rc if rc is not None else len(group_active.get(gk, {})) + 1
        gsis = identity.get(key)
        tg = ca = None
        opp = None
        if gsis and pl_usage.get(gsis):
            wk = {w: r for w, r in pl_usage[gsis].items() if r.get('team') == v['team']}
            if wk:
                tg = int(sum(r.get('targets', 0) for r in wk.values()))
                ca = int(sum(r.get('carries', 0) for r in wk.values()))
                sh = [(r.get('targets', 0) + r.get('carries', 0)) /
                      max(1, tm_usage[v['team']][w]['targets'] + tm_usage[v['team']][w]['rush_attempts'])
                      for w, r in wk.items() if w in tm_usage.get(v['team'], {})]
                opp = float(np.mean(sh)) if sh else None
        skill = g in ROLE_SLOTS
        role = bool(name not in absent and skill and a is not None
                    and (rc <= ROLE_SLOTS[g] or a['mean'] >= ROLE_SNAP_SHARE))
        b = baseline.get(name, {'cpt': 0.0, 'flex': 0.0})
        row = {'slate': slate_id, 'name': name, 'team': v['team'], 'position': v['position'], 'pos_group': g,
               'flex_salary': v['flex_salary'], 'cpt_salary': v['cpt_salary'], 'absent': name in absent,
               'n_prior_weeks': a['n'] if a else 0, 'snap_share_mean': a['mean'] if a else 0.0,
               'snap_share_last': a['last'] if a else None, 'snap_share_sd': a['sd'] if a else None,
               'opp_share_mean': opp, 'targets_prior': tg, 'carries_prior': ca,
               'depth_rank_all': ra if skill else None, 'depth_rank_active': rc if skill else None,
               'injury_opp': int(bool(skill and a is not None and rc < ra)),
               'starter': bool(skill and a is not None and name not in absent and rc <= STARTER_SLOTS[g]),
               'role_evidence': role, 'salary_relief_k': round((CAP / 6 - v['flex_salary']) / 1000.0, 3),
               'optimizer_feasible': int(b['cpt'] + b['flex'] > 0),
               'baseline_cpt': float(b['cpt']), 'baseline_flex': float(b['flex'])}
        row['bucket'] = assign_bucket(row)
        rows.append(row)
    need(rows, 'EMPTY_FEATURES', slate_id)
    cheap = sorted((r for r in rows if r['bucket'] == CHEAP and not r['absent']), key=lambda r: -r['flex_salary'])
    rank = {r['name']: i + 1 for i, r in enumerate(cheap)}
    for r in rows:
        r['scarcity_n_cheap'] = len(cheap)
        r['cheap_salary_rank'] = rank.get(r['name'])
    for r in rows:
        missing = [f for f in FEATURE_SCHEMA if f not in r]
        need(not missing, 'FEATURE_SCHEMA', f'{slate_id} {r["name"]}: {missing}')
    leak = [b for b in baseline if b not in pool]
    need(not leak, 'BASELINE_NAME_NOT_IN_POOL', f'{slate_id}: {leak}')
    on_absent = sum(baseline[n]['cpt'] + baseline[n]['flex'] for n in baseline if n in absent)
    need(on_absent == 0, 'BASELINE_MASS_ON_ABSENT', f'{slate_id}: {on_absent}')
    return rows


# =========================================================================== stage 4: realised ownership
def actual_ownership(entries, pool):
    """Realised CPT / FLEX % of a contest's filled entries. The ONLY place entries are read."""
    need(entries, 'NO_ENTRIES', 'actual ownership needs filled entries')
    cpt, flex = collections.Counter(), collections.Counter()
    for e in entries:
        need(isinstance(e.get('cpt'), str) and len(e.get('flex', ())) == 5, 'ENTRY_SCHEMA', str(e)[:120])
        cpt[e['cpt']] += 1
        for x in e['flex']:
            flex[x] += 1
    n = len(entries)
    unmapped = sorted((set(cpt) | set(flex)) - set(pool))
    need(not unmapped, 'ENTRY_PLAYER_NOT_IN_POOL', str(unmapped[:10]))
    return {p: {'cpt': 100.0 * cpt[p] / n, 'flex': 100.0 * flex[p] / n} for p in pool}, n


def attach_actuals(rows, actual):
    """New rows = prelock features + realised ownership; the feature dicts are copied, never mutated."""
    need(rows, 'EMPTY_FEATURES', 'attach_actuals')
    need(actual, 'EMPTY_ACTUALS', 'attach_actuals')
    out = []
    for r in rows:
        need(r['name'] in actual, 'ACTUAL_MISSING_PLAYER', r['name'])
        out.append({**r, 'actual_cpt': actual[r['name']]['cpt'], 'actual_flex': actual[r['name']]['flex']})
    return out


# ================================================================================= stage 5: model
def design(rows, slot, kappa):
    need(rows, 'EMPTY_DESIGN', slot)
    X = np.array([[math.log(r[f'baseline_{slot}'] + kappa), float(r['bucket'] == CHEAP),
                   float(r['bucket'] == 'PUNT_FRINGE'), float(r['snap_share_mean']), float(r['injury_opp'])]
                  for r in rows])
    need(X.shape == (len(rows), len(FEATURES)) and np.all(np.isfinite(X)), 'DESIGN_SCHEMA', str(X.shape))
    return X


def _softmax(z):
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def fit(train_rows, slot, kappa=KAPPA, lam=LAMBDA, iters=200, tol=1e-10):
    """Penalised multinomial ML of the training slate's realised slot shares (active players only)."""
    act = [r for r in train_rows if not r['absent']]
    need(act, 'EMPTY_TRAINING', slot)
    need(all(f'actual_{slot}' in r for r in act), 'TRAINING_WITHOUT_ACTUALS', slot)
    X = design(act, slot, kappa)
    y = np.array([r[f'actual_{slot}'] for r in act])
    need(y.sum() > 0, 'TRAINING_TARGET_EMPTY', slot)
    s = y / y.sum()
    th = THETA_PRIOR.copy()

    def obj(t):
        q = _softmax(X @ t)
        return -float(np.sum(s * np.log(np.maximum(q, 1e-300)))) + 0.5 * lam * float(np.sum((t - THETA_PRIOR) ** 2))
    f0 = obj(th)
    converged = False
    for it in range(iters):
        q = _softmax(X @ th)
        g = X.T @ (q - s) + lam * (th - THETA_PRIOR)
        H = X.T @ ((np.diag(q) - np.outer(q, q)) @ X) + (lam + 1e-12) * np.eye(len(th))
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(H, g, rcond=None)[0]
        a = 1.0
        while a > 1e-8 and obj(th - a * step) > f0 + 1e-14:
            a *= 0.5
        th_new = th - a * step
        f1 = obj(th_new)
        if abs(f0 - f1) < tol and np.max(np.abs(th_new - th)) < 1e-7:
            th, f0, converged = th_new, f1, True
            break
        th, f0 = th_new, f1
    need(np.all(np.isfinite(th)), 'FIT_NOT_FINITE', slot)
    return {'theta': th, 'features': list(FEATURES), 'objective': f0, 'iterations': it + 1, 'converged': converged,
            'n_train_active': len(act), 'kappa': kappa, 'lambda': lam,
            'max_abs_theta': float(np.max(np.abs(th)))}


def predict(rows, model, slot):
    act = [r for r in rows if not r['absent']]
    need(act, 'EMPTY_PREDICTION_SET', slot)
    q = _softmax(design(act, slot, model['kappa']) @ model['theta'])
    p = q * MASS[slot]
    need(np.all(np.isfinite(p)) and abs(p.sum() - MASS[slot]) < 1e-6, 'PREDICTION_MASS', slot)
    return {r['name']: float(v) for r, v in zip(act, p)}


# =============================================================================== stage 6: evaluation
def _err(pred, rows, slot):
    e = np.array([pred[r['name']] - r[f'actual_{slot}'] for r in rows])
    return {'mae': r4(np.mean(np.abs(e))), 'bias': r4(np.mean(e))} if len(e) else None


def score(rows, base, cand):
    """Per-bucket MAE and signed bias (pp) for baseline and candidate, plus totals. rows carry actuals."""
    act = [r for r in rows if not r['absent']]
    need(act, 'EMPTY_SCORING_SET')
    out = {'buckets': {}, 'n_active': len(act)}
    for b in BUCKETS:
        rs = [r for r in act if r['bucket'] == b]
        out['buckets'][b] = {'n': len(rs), **{f'{m}_{s}': (_err(P[s], rs, s) if rs else None)
                                              for m, P in (('baseline', base), ('candidate', cand)) for s in ('cpt', 'flex')}}
    tot = lambda P: r4(np.mean([abs(P['cpt'][r['name']] + P['flex'][r['name']] - r['actual_cpt'] - r['actual_flex'])
                                for r in act]))
    out['total_ownership_mae'] = {'baseline': tot(base), 'candidate': tot(cand)}
    a = np.array([r['actual_flex'] for r in act])
    aa = a / a.sum()

    def kl(P):
        p = np.maximum(np.array([P['flex'][r['name']] for r in act]) / MASS['flex'], KL_FLOOR)
        p = p / p.sum()
        m = aa > 0
        return r4(np.sum(aa[m] * np.log(aa[m] / p[m])))
    rm = lambda P: r4(np.sqrt(np.mean([(P['flex'][r['name']] - r['actual_flex']) ** 2 for r in act])))
    out['SC_OWN_ROTATION_1_registered_metrics_REPORTED_NOT_IN_BAR'] = {
        'flex_rmse': {'baseline': rm(base), 'candidate': rm(cand)},
        'flex_kl_actual_vs_pred': {'baseline': kl(base), 'candidate': kl(cand)}}
    out['cheap_rows'] = [{'name': r['name'], 'team': r['team'], 'pos': r['position'], 'salary': r['flex_salary'],
                          'depth_rank_active': r['depth_rank_active'], 'injury_opp': r['injury_opp'],
                          'snap_share_mean': r4(r['snap_share_mean']),
                          'baseline_flex': r4(base['flex'][r['name']]), 'candidate_flex': r4(cand['flex'][r['name']]),
                          'actual_flex': r4(r['actual_flex']), 'baseline_cpt': r4(base['cpt'][r['name']]),
                          'candidate_cpt': r4(cand['cpt'][r['name']]), 'actual_cpt': r4(r['actual_cpt'])}
                         for r in act if r['bucket'] == CHEAP]
    out['absent_players_realised_pct_NOT_SCORED'] = {r['name']: {'cpt': r4(r['actual_cpt']), 'flex': r4(r['actual_flex'])}
                                                    for r in rows if r['absent'] and (r['actual_cpt'] + r['actual_flex']) > 0}
    return out


def bar(sc):
    """Pre-registered pass bar (prereg section 7) on one scored (contest, baseline)."""
    B = sc['buckets']
    if B[CHEAP]['n'] < MIN_CHEAP_N:
        return {'verdict': 'NOT_TESTABLE', 'reason': f'{B[CHEAP]["n"]} CHEAP_ACTIVE_ROTATION players < {MIN_CHEAP_N}'}
    c = B[CHEAP]
    crit = {
        '1_cheap_flex_mae_strictly_lower': c['candidate_flex']['mae'] < c['baseline_flex']['mae'],
        '2_cheap_flex_abs_bias_not_worse': abs(c['candidate_flex']['bias']) <= abs(c['baseline_flex']['bias']),
        '3_cheap_cpt_mae_within_margin': c['candidate_cpt']['mae'] <= c['baseline_cpt']['mae'] + MARGIN['cpt'],
        '5_total_ownership_mae_within_margin': (sc['total_ownership_mae']['candidate']
                                                <= sc['total_ownership_mae']['baseline'] + MARGIN['total'])}
    for b in BUCKETS:
        if b == CHEAP or B[b]['n'] == 0:
            continue
        for s in ('cpt', 'flex'):
            crit[f'4_{b}_{s}_mae_within_margin'] = B[b][f'candidate_{s}']['mae'] <= B[b][f'baseline_{s}']['mae'] + MARGIN[s]
    return {'verdict': 'PASS' if all(crit.values()) else 'FAIL', 'criteria': crit,
            'failed': sorted(k for k, v in crit.items() if not v)}


# ================================================================================ stage 7: slates + LOSO
PIT = {'export': RAW / 'DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv', 'fc': RAW / 'THIRDPARTY_showdown_PIT_CLE_2026W4_CONTEXT_ONLY.csv',
       'absent': RAW / 'OFFICIAL_INACTIVES_PIT_CLE_2026W4.json', 'week': 4, 'primary': '196187080'}
ATL = {'export': RAW_ATL / 'DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv',
       'fc_official': RAW_ATL / 'THIRDPARTY_FC_showdown_ATL_NO_2026W4_CONTEXT_ONLY.330fdd518c66ea57.csv',
       'absent': ATL_DIR / 'SHADOW_ABSENT_RW_INACTIVES_CHARTFIX.json', 'week': 4, 'primary': '196285160',
       'supplementary': ('196285137', '196285161'),
       'baseline': {'FC_ONLY': ATL_DIR / 'SHADOW_RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv',
                    'BLEND': ATL_DIR / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv'}}
TRAIN_BASELINE = 'FC_ONLY'      # the one baseline method available on both slates


def slate_features(sid, spec, baselines):
    """Prelock rows per baseline variant for one slate (no entries are passed in)."""
    pool, _ = load_pool(spec['export'])
    teams = {v['team'] for v in pool.values()}
    absent = set(json.loads(pathlib.Path(spec['absent']).read_text())) & set(pool)
    need(absent, 'ABSENT_SET_EMPTY', sid)
    snaps = load_snaps(SNAPS, teams, spec['week'])
    ident = load_identity(ROSTER, teams)
    usage = load_usage(USAGE, spec['week'])
    return {b: prelock_features(sid, pool, absent, base, snaps, ident, usage, spec['week']) for b, base in baselines.items()}, pool


def load_contest_entries(sid, cid):
    if sid == 'PIT_CLE':
        from nfl.field import showdown_history_calibration as HC
        c = next(c for c in HC.CONTESTS if c['contest_id'] == cid)
        R = HC.load_raw(c)
        return R['entries'], R['sha256']
    from nfl.postgame import showdown_atl_no_field_actual as FA
    S_ = FA.load_standings(cid)
    return S_['entries'], S_['rec']['sha256']


def run_fold(fold_id, train, test, models_by_slot):
    """Score one held-out (slate, contest, baseline). `train` names the slates the models were fitted on."""
    need(test['slate'] not in train, 'TRAIN_TEST_OVERLAP', f'{fold_id}: {test["slate"]} in {train}')
    rows = test['rows']
    act = [r for r in rows if not r['absent']]
    base = {s: {r['name']: r[f'baseline_{s}'] for r in act} for s in ('cpt', 'flex')}
    cand = {s: predict(rows, models_by_slot[s], s) for s in ('cpt', 'flex')}
    sc = score(rows, base, cand)
    return {'fold': fold_id, 'trained_on': list(train), 'test_slate': test['slate'], 'test_contest': test['contest'],
            'baseline': test['baseline'], 'baseline_state': test['baseline_state'], 'role': test['role'],
            'score': sc, 'bar': bar(sc)}


def _fit_both(rows, kappa, lam):
    return {s: fit(rows, s, kappa=kappa, lam=lam) for s in ('cpt', 'flex')}


def _model_doc(m):
    return {s: {**{k: v for k, v in m[s].items() if k != 'theta'},
                'theta': {f: r4(t) for f, t in zip(FEATURES, m[s]['theta'])}} for s in m}


def run(write=True, verify=True):
    prereg_sha = check_prereg()
    recon_check = verify_reconstruction_on_atl() if verify else {'state': 'SKIPPED'}
    sigma = json.loads((ATL_DIR / 'SHADOW_RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_SHADOW_FIELD.json').read_text())['sigma_chosen']
    pit_base, pit_base_info = reconstruct_pit_baseline(sigma)
    atl_bases = {b: load_frozen_baseline(p) for b, p in ATL['baseline'].items()}
    feats = {'PIT_CLE': slate_features('PIT_CLE', PIT, {'FC_ONLY': pit_base}),
             'ATL_NO': slate_features('ATL_NO', ATL, atl_bases)}
    contests = {'PIT_CLE': [PIT['primary']], 'ATL_NO': [ATL['primary'], *ATL['supplementary']]}
    entries, actual_n, raw_sha = {}, {}, {}
    for sid, cids in contests.items():
        pool = feats[sid][1]
        for cid in cids:
            e, h = load_contest_entries(sid, cid)
            entries[(sid, cid)], raw_sha[cid] = e, h
            actual_n[cid] = len(e)
    labelled = {}
    for sid, cids in contests.items():
        rowsets, pool = feats[sid]
        for cid in cids:
            act, _ = actual_ownership(entries[(sid, cid)], pool)
            for b, rows in rowsets.items():
                labelled[(sid, cid, b)] = attach_actuals(rows, act)
    base_state = {'PIT_CLE': 'RECONSTRUCTED_POSTGAME_FROM_PRELOCK_INPUTS', 'ATL_NO': 'FROZEN_PRELOCK_9736516'}
    fold_plan = {'A': {'train': ('PIT_CLE', PIT['primary']), 'test': 'ATL_NO'},
                 'B': {'train': ('ATL_NO', ATL['primary']), 'test': 'PIT_CLE'}}

    def do_folds(kappa, lam):
        res = {}
        for fid, fp in fold_plan.items():
            tr_sid, tr_cid = fp['train']
            m = _fit_both(labelled[(tr_sid, tr_cid, TRAIN_BASELINE)], kappa, lam)
            tests = []
            for (sid, cid, b), rows in labelled.items():
                if sid != fp['test']:
                    continue
                role = 'PRIMARY' if cid == (ATL['primary'] if sid == 'ATL_NO' else PIT['primary']) else 'SUPPLEMENTARY'
                tests.append(run_fold(fid, [tr_sid], {'slate': sid, 'contest': cid, 'baseline': b, 'rows': rows,
                                                      'baseline_state': base_state[sid], 'role': role}, m))
            prim = [t for t in tests if t['role'] == 'PRIMARY']
            need(prim, 'FOLD_NO_PRIMARY_TEST', fid)
            v = [t['bar']['verdict'] for t in prim]
            verdict = 'NOT_TESTABLE' if 'NOT_TESTABLE' in v else ('PASS' if all(x == 'PASS' for x in v) else 'FAIL')
            res[fid] = {'trained_on': [f'{tr_sid}:{tr_cid}:{TRAIN_BASELINE}'], 'test_slate': fp['test'],
                        'model': _model_doc(m), 'tests': tests, 'fold_verdict': verdict,
                        'fold_verdict_rule': 'PASS only if the bar passes on the primary contest against EVERY listed baseline'}
        return res
    folds = do_folds(KAPPA, LAMBDA)
    folds['C'] = {'test_slate': 'PHI_CHI', 'fold_verdict': 'NOT_AVAILABLE',
                  'reason': ('PHI@CHI (contest 196036243) has standings but no DK salaries (outbox request 2026-10-07) and no '
                             'public projection, so there is no baseline forecast and no salary bucket. A salary-dependent '
                             'model cannot be scored there. NOT a pass.')}
    for fid in ('A', 'B'):
        for t in folds[fid]['tests']:
            need(t['test_slate'] not in [x.split(':')[0] for x in folds[fid]['trained_on']], 'LOSO_EVALUATED_ON_TRAINING_SLATE', fid)
    testable = [f for f in ('A', 'B') if folds[f]['fold_verdict'] in ('PASS', 'FAIL')]
    fv = [folds[f]['fold_verdict'] for f in testable]
    overall = ('FAIL' if 'FAIL' in fv else
               'PASS_EXPLORATORY_SHADOW_ONLY' if len(testable) >= 2 and all(x == 'PASS' for x in fv) else 'NOT_TESTABLE')
    sens = {}
    for k, cfg in SENSITIVITY.items():
        try:
            f2 = do_folds(cfg['kappa'], cfg['lam'])
            sens[k] = {**cfg, 'fold_verdicts': {f: f2[f]['fold_verdict'] for f in f2},
                       'cheap_flex_mae_primary': {f: {t['baseline']: {'baseline': t['score']['buckets'][CHEAP]['baseline_flex']['mae'],
                                                                      'candidate': t['score']['buckets'][CHEAP]['candidate_flex']['mae']}
                                                      for t in f2[f]['tests'] if t['role'] == 'PRIMARY'} for f in f2},
                       'converged': {f: {s: f2[f]['model'][s]['converged'] for s in ('cpt', 'flex')} for f in f2}}
        except CheapOwnershipError as e:
            sens[k] = {**cfg, 'state': 'FAILED', 'error': str(e)}
    # descriptive, computed from the primary tests above (not a criterion): the sign of the baseline's cheap-bucket miss
    findings = {'baseline_cheap_flex_bias_by_test': {
        f"{t['test_slate']}:{t['test_contest']}:{t['baseline']}": {
            'baseline_bias_pp': t['score']['buckets'][CHEAP]['baseline_flex']['bias'],
            'candidate_bias_pp': t['score']['buckets'][CHEAP]['candidate_flex']['bias']}
        for fid in ('A', 'B') for t in folds[fid]['tests'] if t['role'] == 'PRIMARY'}}
    signs = {k.split(':')[0]: (v['baseline_bias_pp'] > 0) for k, v in findings['baseline_cheap_flex_bias_by_test'].items()}
    findings['baseline_cheap_miss_direction_differs_between_slates'] = len(set(signs.values())) > 1
    findings['READING'] = ('when the baseline over-owns the cheap bucket on one slate and under-owns it on the other, a '
                           'slate-invariant bucket multiplier fitted on one slate moves the other slate the wrong way'
                           if findings['baseline_cheap_miss_direction_differs_between_slates'] else
                           'the baseline misses the cheap bucket in the same direction on both slates')
    doc = {'ARTIFACT': 'CHEAP_OWNERSHIP_LOSO', 'LABEL': LABEL, 'STATUS': STATUS, 'successor_id': 'SC-OWN-ROTATION-1',
           'FINDINGS_DESCRIPTIVE_NOT_IN_BAR': findings,
           'prereg': rel(PREREG), 'prereg_sha256': prereg_sha, 'prereg_sha256_at_write': PREREG_SHA256_AT_WRITE,
           'prereg_sha256_matches': prereg_sha == PREREG_SHA256_AT_WRITE,
           'NOT_A_FOOTBALL_INPUT': True, 'ON_EXECUTION_PATH': False, 'PROSPECTIVELY_VALIDATED': False,
           'AUDIT_LADDER': 'ADVERSARIAL_TESTED (nfl/tests/test_cheap_ownership_successor.py); NOT on the execution path; NOT prospectively validated',
           'FC_BOUNDARY': ('FantasyCruncher enters only via the baseline shadow ownership (showdown_shadow_field.py, FLEX FC '
                           'column), as it already does; no FC column is a successor feature; FC is never a football input'),
           'LEAKAGE_CONTROL': ('prelock_features() takes no entries; realised ownership of the evaluated slate is used only to '
                               'score it; snap/usage history filtered to weeks < slate week; fold refuses train == test'),
           'constants': {'CHEAP_SALARY': CHEAP_SALARY, 'MID_SALARY': MID_SALARY, 'STAR_SALARY': STAR_SALARY,
                         'ROLE_SLOTS': ROLE_SLOTS, 'STARTER_SLOTS': STARTER_SLOTS, 'ROLE_SNAP_SHARE': ROLE_SNAP_SHARE,
                         'KAPPA': KAPPA, 'LAMBDA': LAMBDA, 'THETA_PRIOR': THETA_PRIOR.tolist(), 'FEATURES': FEATURES,
                         'MARGIN_PP': MARGIN, 'MIN_CHEAP_N': MIN_CHEAP_N},
           'baselines': {'PIT_CLE': pit_base_info,
                         'ATL_NO': {'state': 'FROZEN_PRELOCK (committed 9736516 before lock)',
                                    **{b: {'path': rel(p), 'sha256': sha(p)} for b, p in ATL['baseline'].items()}},
                         'PHI_CHI': {'state': 'NONE -- no salaries, no public projection'}},
           'reconstruction_method_check_on_atl': recon_check,
           'inputs': {'snaps': {'path': rel(SNAPS), 'sha256': sha(SNAPS), 'weeks_used': 'REG 2026 weeks < 4'},
                      'usage': {'path': rel(USAGE), 'sha256': sha(USAGE)}, 'roster_identity_only': {'path': rel(ROSTER), 'sha256': sha(ROSTER)},
                      'exports': {'PIT_CLE': {'path': rel(PIT['export']), 'sha256': sha(PIT['export'])},
                                  'ATL_NO': {'path': rel(ATL['export']), 'sha256': sha(ATL['export'])}},
                      'absent': {'PIT_CLE': rel(PIT['absent']), 'ATL_NO': rel(ATL['absent'])},
                      'standings_raw_sha256': raw_sha, 'filled_entries': actual_n,
                      'routes': 'NOT_AVAILABLE in this repository'},
           'bucket_counts_active': {sid: dict(collections.Counter(r['bucket'] for r in feats[sid][0][TRAIN_BASELINE] if not r['absent']))
                                    for sid in feats},
           'folds': folds, 'testable_folds': testable, 'VERDICT': overall,
           'VERDICT_RULE': ('FAIL if any testable fold fails; PASS_EXPLORATORY_SHADOW_ONLY only if every testable fold passes and '
                            '>= 2 are testable; else NOT_TESTABLE. Supplementary contests and sensitivity runs do not vote.'),
           'sensitivity_NOT_IN_VERDICT': sens,
           'LIMITATIONS': [
               'two testable folds, one slate each; the unit of evidence is the slate (n = 2), players within a slate are not independent',
               'each fold fits 10 parameters on ONE training slate',
               'ATL@NO is development data: the defect, the thresholds and the feature list were chosen after reading its postgame',
               'PIT@CLE has no frozen prelock ownership forecast; its baseline is reconstructed postgame from prelock-dated inputs with the frozen method (which reproduces the frozen ATL@NO FC_ONLY exactly)',
               'the PIT@CLE FC sheet capture time relative to lock is not recorded',
               'snap counts and usage for weeks 1-3 were captured after the PIT@CLE game; later nflverse revisions cannot be ruled out',
               'no routes data; depth rank is derived from prior-week snap share, not a published depth chart',
               'fold A trains on FC_ONLY and applies the correction to BLEND as a transfer',
               'PHI@CHI is NOT_AVAILABLE (no salaries, no baseline)',
               'bucket thresholds, kappa, lambda, role slots and margins are declared priors, not estimates'],
           'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(doc, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))
    return doc


def summary(doc):
    lines = [f"VERDICT {doc['VERDICT']}  (prereg sha256 matches: {doc['prereg_sha256_matches']})"]
    for fid in ('A', 'B'):
        f = doc['folds'][fid]
        lines.append(f"fold {fid}: train {f['trained_on']} -> test {f['test_slate']}: {f['fold_verdict']}")
        for t in f['tests']:
            B = t['score']['buckets']
            cells = []
            for b in BUCKETS:
                x = B[b]
                if not x['n']:
                    continue
                cells.append(f"{b}(n={x['n']}) flex {x['baseline_flex']['mae']}->{x['candidate_flex']['mae']} "
                             f"cpt {x['baseline_cpt']['mae']}->{x['candidate_cpt']['mae']}")
            lines.append(f"  {t['role'][:4]} {t['test_contest']} {t['baseline']}: {t['bar']['verdict']} "
                         f"failed={t['bar'].get('failed')} total {t['score']['total_ownership_mae']}")
            lines.extend('     ' + c for c in cells)
    lines.append(f"fold C: {doc['folds']['C']['fold_verdict']}")
    return '\n'.join(lines)


if __name__ == '__main__':
    d = run()
    print(rel(ARTIFACT))
    print(summary(d))
