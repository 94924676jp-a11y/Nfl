#!/usr/bin/env python3.12
"""SC-OWN-ROTATION-2: legal-lineup Showdown ownership forecaster -- fit, solver test, FREEZE. SHADOW_ONLY.

    python3.12 nfl/research/ownership/sc_own_rotation_2.py fit       # fit + solver test -> FREEZE (write-once, 0444)
    python3.12 nfl/research/ownership/sc_own_rotation_2.py check     # verify the freeze against prereg and module hashes

Pre-registration (locked design): docs/NFL_SHOWDOWN_OWNERSHIP_SUCCESSOR_2_PREREGISTRATION.md, committed 8de91b62
(2026-10-07T14:56Z) before this module was written. PREREG_SHA256 below is that committed document; every entry point
refuses (PREREG_CHANGED) if the document no longer hashes to it.

THE MODEL (prereg section 2). Over the enumerated legal lineup universe of nfl/field/showdown_dupe_research.py (1 CPT +
5 distinct FLEX from K = 32 players, both clubs, salary <= $50,000):

    p(L) ∝ 1[L legal] · exp( u_CPT(cpt) + Σ_flex u_FLEX(i) + θ·φ(L) )
    u_s(i) = β0_s + β1_s·log(base_s(i) + ε) + β2_s·value_z(i) + β3_s·salary_rank_at_pos(i)
                  + β4_s·role(i) + β5_s·opened(i) + β6_s·cheap(i)·active(i)

and the forecast is the slot marginals of p: CPT shares sum to 1 and FLEX shares to 5 over the universe, and no slot
share can exceed 1, because every lineup holds exactly one CPT and five distinct FLEX (feasibility by construction;
asserted at every prediction).

DECLARED IMPLEMENTATION READINGS (the prereg leaves these open; each is recorded in the freeze, none was tuned):
  R1 β0_s is NOT IDENTIFIED: every legal lineup has exactly one CPT and five FLEX, so β0_CPT + 5·β0_FLEX adds the same
     constant to every lineup and cancels in the normalisation. Recorded as 0.
  R2 base is a FRACTION of entries per slot (shadow pct / 100; FLEX in [0, 1], summing to 5), so ε = 0.001 is 0.1 pp.
  R3 role is two columns sharing the β4 label: role_depth_inv = 1 / prelock depth-chart rank (0 if not listed) and
     role_snap_share = mean 2026 REG offensive snap share over weeks strictly before the slate week (0 if no row).
  R4 value = football-only projected FLEX points per $1,000 of FLEX salary, z-scored over the slate's ACTIVE pool
     players. An active player the projection lists blank or omits gets 0.0 points (the projection's own statement
     of no projected opportunity; counted in the freeze/prediction). Nothing is ever filled from outcomes.
  R5 salary_rank_at_pos = 1 + number of ACTIVE players at his DK position with a strictly lower FLEX salary.
  R6 absent ("not officially active") = official inactive list ∪ designation OUT. opened = 1 if a player listed ahead
     of him (lower pos_rank, same club, same depth position) on the latest depth-chart snapshot strictly before kickoff
     is absent.
  R7 cheap(i)·active(i) = SC-OWN-ROTATION-1's prelock bucket CHEAP_ACTIVE_ROTATION, computed by its own frozen
     prelock_features (nfl/field/showdown_cheap_ownership_research.py) unchanged.
  R8 universe (prelock, no entries): the 32 active players ranked by base total ownership, ties (including every
     zero-base player) broken by our projected points, then FLEX salary, then name. The B-family forecast universe
     rule (top-32 by forecast ownership) with a prelock tie-break instead of alphabetical padding. Entries holding a
     player outside it are outside the likelihood (coverage recorded). With fewer than 32 active players the width is
     reached with absent players PINNED at -50 in both slots (the B-family pin); their marginals are set to exactly
     0 and entries holding them are outside the likelihood.
  R9 penalty: maximise Σ_entries log p(L) - (λ/2)·||(β1..β6, θ)||², λ = 1.0. Every entry counts once, so the
     ATL@NO 150-max contest (237,105 entries) carries most of the weight; the per-contest weights are in the freeze.
  R10 an active player outside the 32-player universe has a raw forecast of 0 (he cannot appear in a modelled
     lineup); the smoothing floor gives him 0.05% per slot for the log score only, exactly as for any other model.
  R11 the PIT@CLE base is a postgame reconstruction of the BLEND from prelock-dated inputs (no frozen PIT BLEND
     exists); PIT@CLE has no designations artifact, so absent there is its inactive list alone (see NOT_AVAILABLE).

Realised ownership of a slate never reaches build_features (it takes no entries); entries reach only
entry_counts (the fit and the solver test) and the grader. No sportsbook price enters anything. FantasyCruncher
enters only through base (the BLEND shadow ownership), as in showdown_shadow_field.py.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_dupe_research as DR  # noqa: E402
from nfl.field import showdown_cheap_ownership_research as CO  # noqa: E402

CANDIDATE_ID = 'SC-OWN-ROTATION-2'
LABEL = 'SHADOW_ONLY'
PREREG = _REPO / 'docs/NFL_SHOWDOWN_OWNERSHIP_SUCCESSOR_2_PREREGISTRATION.md'
#: sha256 of the pre-registration as committed in 8de91b62, computed before this module was written
PREREG_SHA256 = '9013fb7cacaa9a12ce519eae99862475453ab93149890d3212b49217bff6e922'
HERE = pathlib.Path(__file__).resolve().parent
FREEZE_PATH = HERE / 'SC_OWN_ROTATION_2_FREEZE.json'
#: the first evaluation slate's lock (TB@DAL, nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/SLATE.json kickoff_utc)
FIRST_EVAL_LOCK = '2026-10-09T00:15:00Z'
FIRST_EVAL_SLATE = 'TB_DAL_2026W5'
DEVELOPMENT_SLATES = ('PIT_CLE', 'PHI_CHI', 'ATL_NO')

# ------------------------------------------------------------------------------- pre-registered constants
EPS = 0.001                    # prereg section 2 (unit: fraction of entries, reading R2)
LAMBDA = 1.0                   # prereg section 3, declared prior
FLOOR_PCT = 0.05               # prereg section 2, smoothing floor per slot, percentage points
MASS = {'cpt': 100.0, 'flex': 500.0}
SLOTS = ('cpt', 'flex')
K = DR.K_PLAYERS               # 32, the B-family universe width
SOLVER_TOL = 1e-6              # prereg section 5 falsification threshold on max_abs_grad
FIT_TOL = 1e-6                 # same threshold, applied to the per-entry gradient of the penalised objective
PLAYER_FEATURES = ('log_base', 'value_z', 'salary_rank_at_pos', 'role_depth_inv', 'role_snap_share', 'opened',
                   'cheap_active')
BETA_LABEL = {'log_base': 'beta1', 'value_z': 'beta2', 'salary_rank_at_pos': 'beta3', 'role_depth_inv': 'beta4_depth',
              'role_snap_share': 'beta4_snap', 'opened': 'beta5', 'cheap_active': 'beta6'}
THETA_FEATURES = ('stack_cpt_pc_own_qb', 'both_qbs', 'split_5_1', 'split_4_2', 'any_k_dst')   # B3S, salary-free
DEPTH_POS = ('QB', 'RB', 'FB', 'WR', 'TE', 'PK')
DEPTH_COLS = ('dt', 'team', 'player_name', 'pos_abb', 'pos_rank')
OUT_STATUSES = ('OUT',)
PIN = -50.0                    # the B-family pin for a player who may carry no mass (showdown_dupe_research._expfam)

#: modules whose code computes features, the model, the prediction or the grade. The predictor and the grader refuse
#: if any of these differs from the freeze.
ENFORCED_MODULES = ('nfl/research/ownership/sc_own_rotation_2.py',
                    'nfl/research/ownership/predict_sc_own_rotation_2.py',
                    'nfl/research/ownership/grade_sc_own_rotation_2.py',
                    'nfl/field/showdown_dupe_research.py',
                    'nfl/field/showdown_cheap_ownership_research.py')
#: used by the fit only (the PIT@CLE BLEND reconstruction and the archive loaders) or production ingest edited by other
#: agents; hashed and recorded in the freeze, not enforced at prediction (the predictor records the parsed pool instead)
RECORDED_MODULES = ('nfl/field/showdown_shadow_field.py', 'nfl/field/showdown_history_calibration.py',
                    'nfl/field/showdown_field_archive.py', 'nfl/postgame/showdown_atl_no_field_actual.py',
                    'nfl/tools/showdown_to_portfolio.py', 'nfl/dfs/showdown/optimal_worlds.py')

RAW = _REPO / 'nfl/dfs/salaries/raw'
ATL_DIR = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
FIT_SLATES = {
    'PIT_CLE': {
        'export': RAW / 'DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv',
        'baseline': {'state': 'RECONSTRUCTED_POSTGAME_FROM_PRELOCK_INPUTS',
                     'fc': RAW / 'THIRDPARTY_showdown_PIT_CLE_2026W4_CONTEXT_ONLY.csv',
                     'draws': _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json'},
        'projection': _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ_FOOTBALL_ONLY.json',
        'depth': _REPO / 'nfl/vintage/depth_charts.f0d38b65a6ab0439.raw.csv.gz',
        'inactives': RAW / 'OFFICIAL_INACTIVES_PIT_CLE_2026W4.json',
        'designations': None,
        'snaps': CO.SNAPS, 'week': 4, 'kickoff': '2026-10-02T00:15:00Z',
        'contests': ('196187080',)},
    'ATL_NO': {
        'export': RAW / 'showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv',
        'baseline': {'state': 'FROZEN_PRELOCK (committed 9736516d 2026-10-05T23:47Z, before the 2026-10-06T00:15Z lock)',
                     'csv': ATL_DIR / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv'},
        'projection': ATL_DIR / 'RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_PROJECTIONS.csv',
        'depth': RAW / 'showdown_atl_no_2026W4/depth_charts_2026_ATL_NO.1e6aa6437a6ae01b.csv',
        'inactives': RAW / 'showdown_atl_no_2026W4/OFFICIAL_INACTIVES_ATL_NO_2026W4.json',
        'designations': ATL_DIR / 'DESIGNATIONS_ATL_NO_2026W4_V4_RW_INACTIVES_CHARTFIX.json',
        'snaps': CO.SNAPS, 'week': 4, 'kickoff': '2026-10-06T00:15:00Z',
        'contests': ('196285160', '196285137', '196285161')},
}
ATL_BLEND_FIELD = ATL_DIR / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND/SHOWDOWN_ATL_NO_SHADOW_FIELD.json'
ATL_BLEND_INPUTS = {'fc': RAW / 'showdown_atl_no_2026W4/THIRDPARTY_FC_showdown_ATL_NO_2026W4_CONTEXT_ONLY.330fdd518c66ea57.csv',
                    'draws': ATL_DIR / 'RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_DRAWS.json',
                    'absent': ATL_DIR / 'SHADOW_ABSENT_RW_INACTIVES_CHARTFIX.json'}

NOT_AVAILABLE = {
    'PHI_CHI': ('NOT_AVAILABLE for every term: contest 196036243 has standings but no DK salaries (outbox 2026-10-07; '
                'still absent at the freeze), no frozen BLEND shadow ownership and no football-only projection, so '
                'neither base nor any salary term exists, and the salary-free θ alone is not this candidate. Used only '
                'in the solver falsification test (which needs no salaries).'),
    'PIT_CLE.designations': ('NOT_AVAILABLE: no separate designations artifact for PIT@CLE; absent = the official '
                             'inactive list only (which already carries the OUT players). Declared, not imputed.'),
    'PIT_CLE.baseline': ('NO FROZEN PRELOCK BLEND EXISTS for PIT@CLE. base is RECONSTRUCTED postgame with the frozen '
                         'BLEND method (showdown_shadow_field: mean of FC and our sim mean, K=5000, seed 20261005, '
                         'sigma = the ATL@NO BLEND sigma) from prelock-dated inputs only: the game-day FC sheet (capture '
                         'time NOT_RECORDED) and our draws committed b05e476a 2026-10-02T00:01:57Z, before the 00:15Z '
                         'lock. Exact (name, club) FC matching as SF.run does (FC rows named without the DK suffix contribute nothing, '
                         'listed in the freeze). The method is first required to reproduce the frozen ATL@NO BLEND.'),
    'PIT_CLE.depth': ('depth chart rows are the nflverse snapshot timestamped 2026-10-01 (dt < kickoff) from a vintage '
                      'file CAPTURED 2026-10-07 (postgame); the rows are timestamped prelock, the capture is not.'),
}


class RotationError(RuntimeError):
    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def need(cond, code, detail=''):
    if not cond:
        raise RotationError(code, detail)


def sha_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def sha_obj(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=_json_default).encode()).hexdigest()


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, pathlib.Path):
        return rel(o)
    return str(o)


def rel(p):
    try:
        return str(pathlib.Path(p).resolve().relative_to(_REPO))
    except ValueError:
        return str(p)


def parse_ts(s):
    need(isinstance(s, str) and s, 'TIMESTAMP_MISSING', repr(s))
    t = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    need(t.tzinfo is not None, 'TIMESTAMP_NOT_UTC', s)
    return t


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def check_prereg(path=PREREG, expected=PREREG_SHA256):
    p = pathlib.Path(path)
    need(p.exists() and p.stat().st_size > 0, 'PREREG_ABSENT', rel(p))
    h = sha_file(p)
    need(h == expected, 'PREREG_CHANGED', f'{h} != {expected}')
    return h


def module_hashes(names):
    out = {}
    for n in names:
        p = _REPO / n
        need(p.is_file() and p.stat().st_size > 0, 'MODULE_ABSENT', n)
        out[n] = sha_file(p)
    return out


# ============================================================================================= stage 1: inputs
def load_pool(export):
    pool, slate = CO.load_pool(pathlib.Path(export))
    need(pool, 'POOL_EMPTY', rel(export))
    return pool, slate


def load_baseline(path):
    return CO.load_frozen_baseline(pathlib.Path(path))


def load_projection(path):
    """Our football-only projection -> {name: FLEX points or None}. CSV (player, proj_dk_points) or PROJ.json rows."""
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, 'PROJECTION_MISSING_OR_EMPTY', rel(p))
    out, arm = {}, None
    if p.suffix.lower() == '.json':
        d = json.loads(p.read_text())
        need(isinstance(d.get('rows'), dict) and d['rows'], 'PROJECTION_SCHEMA', f'{rel(p)}: no rows')
        arm = d.get('market_arm')
        for r in d['rows'].values():
            need('name' in r and 'dk_points' in r, 'PROJECTION_SCHEMA', f'{rel(p)}: row keys')
            need(r['name'] not in out, 'PROJECTION_NAME_NOT_UNIQUE', r['name'])
            out[r['name']] = None if r['dk_points'] is None else float(r['dk_points'])
    else:
        rows = list(csv.DictReader(open(p, newline='', encoding='utf-8-sig')))
        need(rows, 'PROJECTION_EMPTY', rel(p))
        for c in ('player', 'proj_dk_points'):
            need(c in rows[0], 'PROJECTION_SCHEMA', f'{rel(p)}: {c}')
        for r in rows:
            need(r['player'] not in out, 'PROJECTION_NAME_NOT_UNIQUE', r['player'])
            v = (r['proj_dk_points'] or '').strip()
            out[r['player']] = float(v) if v else None
    need(out, 'PROJECTION_EMPTY', rel(p))
    need(any(v is not None for v in out.values()), 'PROJECTION_ALL_BLANK', rel(p))
    if arm is not None:
        need(arm == 'FOOTBALL_ONLY', 'PROJECTION_NOT_FOOTBALL_ONLY', f'{rel(p)}: market_arm {arm}')
    return out


def load_names(path, code='INACTIVES'):
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, f'{code}_MISSING_OR_EMPTY', rel(p))
    d = json.loads(p.read_text())
    if isinstance(d, dict):
        for k in ('inactives', 'official_inactives', 'players', 'names'):
            if isinstance(d.get(k), list):
                d = d[k]
                break
    need(isinstance(d, list) and d and all(isinstance(x, str) for x in d), f'{code}_SCHEMA', rel(p))
    return list(d)


def load_designations(path):
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, 'DESIGNATIONS_MISSING_OR_EMPTY', rel(p))
    d = json.loads(p.read_text())
    if isinstance(d, dict) and isinstance(d.get('designations'), dict):
        d = d['designations']
    need(isinstance(d, dict) and d and all(isinstance(k, str) and isinstance(v, str) for k, v in d.items()),
         'DESIGNATIONS_SCHEMA', rel(p))
    return dict(d)


def load_depth(path, teams, cutoff):
    """Latest nflverse depth-chart snapshot per club strictly before `cutoff`, offence + K only.
    -> {team: {'dt': str, 'rows': [(pos_abb, rank, name)]}}."""
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, 'DEPTH_MISSING_OR_EMPTY', rel(p))
    raw = p.read_bytes()
    if p.suffix == '.gz':
        raw = gzip.decompress(raw)
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    need(rows, 'DEPTH_EMPTY', rel(p))
    for c in DEPTH_COLS:
        need(c in rows[0], 'DEPTH_SCHEMA', f'{rel(p)}: {c}')
    cut = parse_ts(cutoff) if isinstance(cutoff, str) else cutoff
    out = {}
    for t in sorted(teams):
        mine = [r for r in rows if r['team'] == t and r['dt'] and parse_ts(r['dt']) < cut]
        need(mine, 'DEPTH_NO_PRELOCK_SNAPSHOT', f'{t} before {cut.isoformat()} in {rel(p)}')
        last = max(r['dt'] for r in mine)
        sel = [(r['pos_abb'], int(r['pos_rank']), r['player_name']) for r in mine
               if r['dt'] == last and r['pos_abb'] in DEPTH_POS and r['pos_rank'].strip()]
        need(sel, 'DEPTH_NO_OFFENCE_ROWS', f'{t} {last}')
        out[t] = {'dt': last, 'rows': sel}
    for t, v in out.items():
        need(parse_ts(v['dt']) < cut, 'DEPTH_SNAPSHOT_NOT_PRELOCK', f'{t} {v["dt"]}')
    return out


def reconstruct_blend(export, fc_csv, draws_json, absent, sigma):
    """The frozen BLEND method of nfl/field/showdown_shadow_field.run (FC + our sim mean, averaged), reproduced
    in-process (SF.run writes files; this does not). EXACT (name, club) matching, as SF.run does: an FC row whose
    name differs from the DK pool (e.g. a missing suffix) contributes nothing, exactly as it would have prelock.
    The unmatched FC rows are returned so the omission is visible."""
    from nfl.field import showdown_shadow_field as SF
    _, slate = load_pool(export)
    fc = SF.fc_projection(fc_csv)
    need(fc, 'FC_EMPTY', rel(fc_csv))
    pk = {(v['name'], v['dk_team']) for v in slate['players'].values()}
    unmatched = sorted(f'{n}|{t}' for (n, t) in fc if (n, t) not in pk)
    d = json.loads(pathlib.Path(draws_json).read_text())['draws']
    need(d, 'DRAWS_EMPTY', rel(draws_json))
    n_ours = 0
    for key, v in slate['players'].items():
        ours = d.get(key)
        if ours is None:
            continue
        k2 = (v['name'], v['dk_team'])
        fc[k2] = 0.5 * fc.get(k2, 0.0) + 0.5 * float(np.mean(ours))
        n_ours += 1
    need(n_ours, 'DRAWS_MATCH_NO_POOL_PLAYER', rel(draws_json))
    absent = set(absent)
    absent_keys = {k for k, v in slate['players'].items() if v['name'] in absent or k in absent}
    L = SF.field(slate, absent_keys, fc, sigma)
    need(L, 'RECON_FIELD_EMPTY', f'sigma {sigma}')
    own = SF.ownership(L, slate)
    out = {slate['players'][k]['name']: {'team': slate['players'][k]['dk_team'], 'cpt': v['cpt'], 'flex': v['flex']}
           for k, v in own.items()}
    CO._baseline_mass(out, 'reconstructed BLEND')
    return out, {'k': len(L), 'sigma': sigma, 'seed': SF.SEED, 'fc_rows_not_matching_pool_exactly': unmatched,
                 'n_players_with_our_draws': n_ours}


def verify_blend_method():
    """Refuse unless the in-process BLEND method reproduces the frozen ATL@NO BLEND (CSV rounded to 2 dp)."""
    sigma = json.loads(ATL_BLEND_FIELD.read_text())['sigma_chosen']
    need(json.loads(ATL_BLEND_FIELD.read_text()).get('field_projection') == 'MEAN_OF_FC_AND_OURS', 'ATL_BLEND_NOT_BLEND')
    absent = json.loads(ATL_BLEND_INPUTS['absent'].read_text())
    rec, info = reconstruct_blend(FIT_SLATES['ATL_NO']['export'], ATL_BLEND_INPUTS['fc'], ATL_BLEND_INPUTS['draws'],
                                  absent, sigma)
    frozen = load_baseline(FIT_SLATES['ATL_NO']['baseline']['csv'])
    names = set(rec) | set(frozen)
    diff = max(abs(rec.get(n, {}).get(s, 0.0) - frozen.get(n, {}).get(s, 0.0)) for n in names for s in SLOTS)
    need(diff < 0.006, 'BLEND_RECONSTRUCTION_DOES_NOT_REPRODUCE_FROZEN', f'max abs diff {diff}')
    return {'state': 'REPRODUCES_FROZEN_ATL_NO_BLEND', 'max_abs_diff_pct_pts': round(diff, 4), 'sigma': sigma, **info,
            'inputs': {k: {'path': rel(v), 'sha256': sha_file(v)} for k, v in ATL_BLEND_INPUTS.items()}}


# ========================================================================================= stage 2: features
def _norm(n):
    return CO.norm(n)


def absent_set(pool, inactives, designations):
    """R6: official inactive list ∪ designation OUT, restricted to the DK pool."""
    a = set(inactives or ()) & set(pool)
    a |= {n for n, s in (designations or {}).items() if n in pool and s.strip().upper() in OUT_STATUSES}
    return a


def build_features(slate_id, pool, baseline, projection, depth, absent, snaps_path, week):
    """Per-player prelock features for one slate. Takes NO contest entries and no realised ownership: nothing realised
    about the slate can enter. Returns {'rows': {name: row}, 'universe': [32 names], 'declared': {...}}."""
    need(pool, 'EMPTY_POOL', slate_id)
    need(isinstance(baseline, dict) and baseline, 'EMPTY_BASELINE', slate_id)
    need(isinstance(projection, dict) and projection, 'EMPTY_PROJECTION', slate_id)
    need(depth, 'EMPTY_DEPTH', slate_id)
    absent = set(absent)
    need(absent <= set(pool), 'ABSENT_NOT_IN_POOL', str(sorted(absent - set(pool))[:5]))
    teams = {v['team'] for v in pool.values()}
    need(set(depth) == teams, 'DEPTH_CLUBS', f'{sorted(depth)} vs {sorted(teams)}')
    snaps = CO.load_snaps(snaps_path, teams, week)
    # SC-OWN-ROTATION-1 prelock bucket, unchanged (R7). identity/usage feed only fields the bucket never reads.
    co_rows = CO.prelock_features(slate_id, pool, absent, baseline, snaps, {}, ({}, {}), week)
    bucket = {r['name']: r['bucket'] for r in co_rows}
    active = sorted(n for n in pool if n not in absent)
    need(len(active) >= 6, 'TOO_FEW_ACTIVE_PLAYERS', f'{slate_id}: {len(active)}')
    # projection (R4)
    proj, proj_state = {}, {}
    for n in active:
        v = projection.get(n)
        proj[n] = 0.0 if v is None else float(v)
        proj_state[n] = 'PROJECTED' if v is not None else ('BLANK_ZERO' if n in projection else 'MISSING_ZERO')
    val = np.array([proj[n] / (pool[n]['flex_salary'] / 1000.0) for n in active])
    need(np.all(np.isfinite(val)), 'VALUE_NOT_FINITE', slate_id)
    sd = float(val.std())
    need(sd > 0, 'VALUE_ZERO_SPREAD', slate_id)
    vz = dict(zip(active, (val - val.mean()) / sd))
    # salary rank at DK position among active players (R5)
    by_pos = collections.defaultdict(list)
    for n in active:
        by_pos[pool[n]['position']].append(pool[n]['flex_salary'])
    srank = {n: 1 + sum(s < pool[n]['flex_salary'] for s in by_pos[pool[n]['position']]) for n in active}
    # depth (R3, R6)
    pool_by_norm = collections.defaultdict(list)
    for n, v in pool.items():
        pool_by_norm[(_norm(n), v['team'])].append(n)
    listing = collections.defaultdict(list)       # pool name -> [(pos_abb, rank)]
    by_slot = collections.defaultdict(list)       # (team, pos_abb) -> [(rank, pool name or None, depth name)]
    unmatched = []
    for t, d in depth.items():
        for pos, rk, nm in d['rows']:
            hit = pool_by_norm.get((_norm(nm), t), [])
            pn = hit[0] if len(hit) == 1 else None
            if pn is None:
                unmatched.append(f'{nm}|{t}|{pos}')
            else:
                listing[pn].append((pos, rk))
            by_slot[(t, pos)].append((rk, pn, nm))
    # snaps (R3): mean offensive share over prior weeks
    snap = {}
    for n in active:
        rs = snaps.get((_norm(n), pool[n]['team']), [])
        snap[n] = float(np.mean([r['offense_pct'] for r in rs])) if rs else 0.0
    rows = {}
    for n in sorted(pool):
        v = pool[n]
        b = baseline.get(n, {'cpt': 0.0, 'flex': 0.0})
        is_act = n not in absent
        lst = listing.get(n, [])
        rk = min((r for _, r in lst), default=None)
        opened_by = sorted({pn or nm for pos, r in lst for (r2, pn, nm) in by_slot[(v['team'], pos)]
                            if r2 < r and pn is not None and pn in absent})
        row = {'name': n, 'team': v['team'], 'position': v['position'], 'flex_salary': v['flex_salary'],
               'cpt_salary': v['cpt_salary'], 'active': is_act, 'bucket': bucket[n],
               'base_cpt_pct': float(b['cpt']), 'base_flex_pct': float(b['flex'])}
        if is_act:
            row.update({'proj_pts': proj[n], 'proj_state': proj_state[n], 'value_z': float(vz[n]),
                        'salary_rank_at_pos': int(srank[n]), 'depth_rank': rk,
                        'role_depth_inv': (1.0 / rk) if rk else 0.0, 'role_snap_share': snap[n],
                        'opened': int(bool(opened_by)), 'opened_by': opened_by,
                        'cheap_active': int(bucket[n] == CO.CHEAP),
                        'log_base_cpt': math.log(b['cpt'] / 100.0 + EPS),
                        'log_base_flex': math.log(b['flex'] / 100.0 + EPS)})
        rows[n] = row
    # universe (R8)
    order = sorted(active, key=lambda n: (-(rows[n]['base_cpt_pct'] + rows[n]['base_flex_pct']), -proj[n],
                                          -pool[n]['flex_salary'], n))
    uni = order[:K]
    need(len({pool[n]['team'] for n in uni}) == 2, 'UNIVERSE_ONE_CLUB', slate_id)
    # fewer than 32 active players: pad to the fixed universe width with absent players whose utility is PINNED at
    # PIN in both slots (the B-family pinning), so they carry no mass; their marginals are then set to exactly 0 and
    # entries holding them are outside the likelihood. Deterministic: highest FLEX salary first, then name.
    pads = sorted(absent, key=lambda n: (-pool[n]['flex_salary'], n))[:K - len(uni)]
    need(len(uni) + len(pads) == K, 'UNIVERSE_CANNOT_REACH_WIDTH', f'{slate_id}: {len(uni)} + {len(pads)}')
    for n in rows:
        rows[n]['in_universe'] = n in uni
        rows[n]['universe_pad'] = n in pads
    for n in active:
        r = rows[n]
        for f in ('value_z', 'salary_rank_at_pos', 'role_depth_inv', 'role_snap_share', 'opened', 'cheap_active',
                  'log_base_cpt', 'log_base_flex'):
            need(isinstance(r[f], (int, float)) and math.isfinite(r[f]), 'FEATURE_NOT_FINITE', f'{slate_id} {n} {f}')
    declared = {'n_pool': len(pool), 'n_active': len(active), 'n_absent': len(absent), 'absent': sorted(absent),
                'projection_states': dict(collections.Counter(proj_state.values())),
                'projection_zero_filled': sorted(n for n, s in proj_state.items() if s != 'PROJECTED'),
                'depth_snapshot_dt': {t: d['dt'] for t, d in depth.items()},
                'depth_rows_unmatched_to_pool': sorted(unmatched),
                'active_listed_on_depth_chart': sum(1 for n in active if listing.get(n)),
                'opened_players': sorted(n for n in active if rows[n]['opened']),
                'cheap_active_players': sorted(n for n in active if rows[n]['cheap_active']),
                'value_mean_pts_per_k': float(val.mean()), 'value_sd_pts_per_k': sd,
                'universe_rule': 'R8', 'universe': uni, 'universe_pads_pinned_out': pads,
                'universe_zero_base_players': [n for n in uni if rows[n]['base_cpt_pct'] + rows[n]['base_flex_pct'] == 0]}
    return {'slate': slate_id, 'rows': rows, 'universe': uni + pads, 'pads': pads, 'declared': declared}


def design(feat, slot):
    """32 x 7 player design matrix for `slot`, in universe order."""
    X = []
    for n in feat['universe']:
        r = feat['rows'][n]
        if n in feat['pads']:
            X.append([0.0] * len(PLAYER_FEATURES))
            continue
        X.append([r[f'log_base_{slot}'] if f == 'log_base' else float(r[f]) for f in PLAYER_FEATURES])
    X = np.array(X, dtype=float)
    need(X.shape == (K, len(PLAYER_FEATURES)) and np.all(np.isfinite(X)), 'DESIGN_SCHEMA', str(X.shape))
    return X


def make_universe(feat, pool):
    meta = {n: {'team': v['team'], 'position': v['position'], 'flex_salary': v['flex_salary'],
                'cpt_salary': v['cpt_salary']} for n, v in pool.items()}
    U = DR.universe_from_players(feat['slate'], list(feat['universe']), meta, None, True)
    need(len(U['cpt']) > 0, 'UNIVERSE_EMPTY', feat['slate'])
    return U


# ===================================================================================== stage 3: the model
def unpack(w):
    p = len(PLAYER_FEATURES)
    return w[:p], w[p:2 * p], w[2 * p:]


def n_params():
    return 2 * len(PLAYER_FEATURES) + len(THETA_FEATURES)


def offset(feat):
    """PIN for padded (absent) universe members, 0 otherwise."""
    return np.array([PIN if n in feat['pads'] else 0.0 for n in feat['universe']])


def model_stats(U, Dc, Df, F, w, off):
    bc, bf, th = unpack(np.asarray(w, float))
    return DR._stats(U, Dc @ bc + off, Df @ bf + off, th, F)


def marginals(U, Dc, Df, F, w, off):
    _, m_c, m_f, _, _, _ = model_stats(U, Dc, Df, F, w, off)
    return m_c, m_f


def entry_counts(U, entries, exclude=()):
    """Copies of each universe lineup among `entries` (the fit and the solver test only). Entries holding an
    `exclude` player (a pinned-out pad) are outside the likelihood, like entries holding a non-universe player."""
    need(entries, 'NO_ENTRIES', U['id'])
    pidx = {p: i for i, p in enumerate(U['players']) if p not in set(exclude)}
    codes = []
    for e in entries:
        ids = [pidx.get(e['cpt'])] + [pidx.get(x) for x in e['flex']]
        if None in ids:
            continue
        f = np.sort(np.array(ids[1:], dtype=np.int8))
        codes.append(DR._code(np.array([ids[0]], dtype=np.int8), f[None, :])[0])
    need(codes, 'NO_ENTRIES_IN_UNIVERSE', U['id'])
    codes = np.array(codes, dtype=np.int64)
    loc = np.searchsorted(U['code'], codes)
    ok = (loc < len(U['code'])) & (U['code'][np.minimum(loc, len(U['code']) - 1)] == codes)
    counts = np.bincount(loc[ok], minlength=len(U['code'])).astype(float)
    n_in = float(counts.sum())
    need(n_in > 0, 'NO_ENTRIES_IN_UNIVERSE', U['id'])
    return {'counts': counts, 'n_in': n_in, 'N': len(entries), 'coverage': n_in / len(entries),
            'n_outside_universe': len(entries) - len(codes), 'n_in_universe_not_legal': int((~ok).sum()),
            't_c': np.bincount(U['cpt'], weights=counts, minlength=K) / n_in,
            't_f': sum(np.bincount(U['flex'][:, k], weights=counts, minlength=K) for k in range(5)) / n_in}


def fit(blocks, lam=LAMBDA, iters=100, tol=FIT_TOL):
    """Joint penalised ML over entries. blocks: [{'U','Dc','Df','F','contests':[{'id','n_in','t_c','t_f','e'}]}].
    Objective: Σ_contests n_in·(a·t_c + b·t_f + θ·e − log Z) − (λ/2)||w||². Concave; Newton with backtracking."""
    need(blocks, 'EMPTY_TRAINING')
    P = n_params()
    w = np.zeros(P)
    N_tot = sum(c['n_in'] for b in blocks for c in b['contests'])
    need(N_tot > 0, 'EMPTY_TRAINING', 'no entries')

    def evaluate(w):
        bc, bf, th = unpack(w)
        obj, g, H = -0.5 * lam * float(w @ w), -lam * w, -lam * np.eye(P)
        for b in blocks:
            logZ, m_c, m_f, E_F, Hs, _ = DR._stats(b['U'], b['Dc'] @ bc + b['off'], b['Df'] @ bf + b['off'], th, b['F'])
            n = sum(c['n_in'] for c in b['contests'])
            tc = sum(c['n_in'] * c['t_c'] for c in b['contests'])
            tf = sum(c['n_in'] * c['t_f'] for c in b['contests'])
            te = sum(c['n_in'] * c['e'] for c in b['contests'])
            a, bb = b['Dc'] @ bc + b['off'], b['Df'] @ bf + b['off']
            obj += float(a @ tc + bb @ tf + th @ te) - n * logZ
            J = np.zeros((2 * K + len(th), P))
            p = len(PLAYER_FEATURES)
            J[:K, :p] = b['Dc']
            J[K:2 * K, p:2 * p] = b['Df']
            J[2 * K:, 2 * p:] = np.eye(len(th))
            gr = np.concatenate([tc - n * m_c, tf - n * m_f, te - n * E_F])
            g = g + J.T @ gr
            H = H - n * (J.T @ Hs @ J)
        return obj, g, H

    obj, g, H = evaluate(w)
    hist = []
    converged = False
    for it in range(iters):
        gmax = float(np.max(np.abs(g))) / N_tot
        hist.append({'iter': it, 'objective_per_entry': obj / N_tot, 'max_abs_grad_per_entry': gmax})
        if gmax <= tol * 1e-3:
            converged = True
            break
        step = np.linalg.solve(-H, g)
        t, improved = 1.0, False
        while t >= 1e-6:
            o2, g2, H2 = evaluate(w + t * step)
            if o2 >= obj - 1e-9 * abs(obj):
                improved = True
                break
            t /= 2
        if not improved:
            break
        w, obj, g, H = w + t * step, o2, g2, H2
    gmax = float(np.max(np.abs(g))) / N_tot
    converged = converged or gmax <= tol
    need(np.all(np.isfinite(w)), 'FIT_NOT_FINITE')
    need(converged, 'FIT_NOT_CONVERGED', f'max_abs_grad_per_entry {gmax:.3e}')
    eig = np.linalg.eigvalsh(-H)
    return {'w': w, 'objective': obj, 'objective_per_entry': obj / N_tot, 'n_entries_in_likelihood': N_tot,
            'iterations': len(hist), 'max_abs_grad_per_entry': gmax, 'max_abs_grad_raw': float(np.max(np.abs(g))),
            'converged': True, 'tolerance': tol, 'hessian_min_eig': float(eig.min()), 'hessian_max_eig': float(eig.max()),
            'history': hist}


def coef_doc(w):
    bc, bf, th = unpack(np.asarray(w, float))
    out = {}
    for s, b in (('cpt', bc), ('flex', bf)):
        out[s] = {'beta0': {'value': 0.0, 'state': 'NOT_IDENTIFIED (reading R1)'},
                  **{BETA_LABEL[f]: {'feature': f, 'value': float(v)} for f, v in zip(PLAYER_FEATURES, b)}}
    out['theta'] = {f: float(v) for f, v in zip(THETA_FEATURES, th)}
    out['vector_order'] = ([f'cpt.{f}' for f in PLAYER_FEATURES] + [f'flex.{f}' for f in PLAYER_FEATURES]
                           + [f'theta.{f}' for f in THETA_FEATURES])
    out['vector'] = [float(x) for x in np.asarray(w, float)]
    return out


# ================================================================================= stage 4: prediction
def smooth(pct, active, mass, floor=FLOOR_PCT):
    """Prereg smoothing: every active player >= floor, inactive exactly 0, floor mass taken proportionally from the
    others in the slot, total preserved. For the log score only."""
    active = set(active)
    need(active, 'SMOOTH_NO_ACTIVE')
    need(len(active) * floor < mass, 'SMOOTH_FLOOR_EXCEEDS_MASS')
    p = {n: (float(pct.get(n, 0.0)) if n in active else 0.0) for n in set(pct) | active}
    tot = sum(p.values())
    need(tot > 0, 'SMOOTH_EMPTY_SLOT')
    p = {n: v * mass / tot for n, v in p.items()}
    fixed = set()
    for _ in range(len(active) + 1):
        low = {n for n in active if n not in fixed and p[n] < floor}
        if not low:
            break
        fixed |= low
        free = [n for n in active if n not in fixed]
        rest = mass - floor * len(fixed)
        s = sum(p[n] for n in free)
        need(s > 0, 'SMOOTH_NO_FREE_MASS')
        for n in fixed:
            p[n] = floor
        for n in free:
            p[n] = p[n] * rest / s
    need(abs(sum(p.values()) - mass) < 1e-6, 'SMOOTH_MASS', f'{sum(p.values())} != {mass}')
    need(all(p[n] >= floor - 1e-9 for n in active), 'SMOOTH_FLOOR')
    need(all(v == 0.0 for n, v in p.items() if n not in active), 'SMOOTH_INACTIVE_NONZERO')
    need(all(v <= 100.0 + 1e-9 for v in p.values()), 'SMOOTH_SLOT_OVER_100')
    return p


def assert_marginals(cand, active):
    """CPT totals 100, FLEX 500, every slot share <= 100, inactive exactly 0."""
    for s in SLOTS:
        tot = sum(cand[s].values())
        need(abs(tot - MASS[s]) < 1e-6, 'MARGINAL_TOTAL', f'{s} {tot}')
        need(all(0.0 <= v <= 100.0 + 1e-9 for v in cand[s].values()), 'MARGINAL_SLOT_OVER_100', s)
        need(all(v == 0.0 for n, v in cand[s].items() if n not in active), 'MARGINAL_INACTIVE_NONZERO', s)


def predict(feat, pool, w):
    U = make_universe(feat, pool)
    F = DR._F(U, list(THETA_FEATURES))
    m_c, m_f = marginals(U, design(feat, 'cpt'), design(feat, 'flex'), F, w, offset(feat))
    need(np.all(np.isfinite(m_c)) and np.all(np.isfinite(m_f)), 'PREDICTION_NOT_FINITE')
    pad = np.array([n in feat['pads'] for n in feat['universe']])
    need(float(m_c[pad].sum() + m_f[pad].sum()) < 1e-12, 'PAD_CARRIES_MASS', str(feat['pads']))
    m_c, m_f = np.where(pad, 0.0, m_c), np.where(pad, 0.0, m_f)
    m_c, m_f = m_c / m_c.sum(), m_f * 5.0 / m_f.sum()
    cand = {'cpt': {n: 0.0 for n in feat['rows']}, 'flex': {n: 0.0 for n in feat['rows']}}
    for i, n in enumerate(feat['universe']):
        cand['cpt'][n] = 100.0 * float(m_c[i])
        cand['flex'][n] = 100.0 * float(m_f[i])
    active = {n for n, r in feat['rows'].items() if r['active']}
    assert_marginals(cand, active)
    base = {s: {n: feat['rows'][n][f'base_{s}_pct'] if feat['rows'][n]['active'] else 0.0 for n in feat['rows']}
            for s in SLOTS}
    out = {'candidate': cand,
           'candidate_smoothed': {s: smooth(cand[s], active, MASS[s]) for s in SLOTS},
           'baseline': base,
           'baseline_smoothed': {s: smooth(base[s], active, MASS[s]) for s in SLOTS},
           'universe_lineups': int(len(U['cpt']))}
    return out


# ============================================================================== stage 5: fit slates
def fit_slate_inputs(sid, spec, blend_sigma):
    """Prelock features for a training slate (no entries), with the input hashes."""
    pool, _ = load_pool(spec['export'])
    teams = {v['team'] for v in pool.values()}
    inactives = load_names(spec['inactives'])
    des = load_designations(spec['designations']) if spec['designations'] else {}
    ab = absent_set(pool, inactives, des)
    need(ab, 'ABSENT_SET_EMPTY', sid)
    bspec = spec['baseline']
    if 'csv' in bspec:
        base = load_baseline(bspec['csv'])
        binfo = {'state': bspec['state'], 'path': rel(bspec['csv']), 'sha256': sha_file(bspec['csv'])}
    else:
        base, info = reconstruct_blend(spec['export'], bspec['fc'], bspec['draws'], inactives, blend_sigma)
        binfo = {'state': bspec['state'], **info, 'fc': {'path': rel(bspec['fc']), 'sha256': sha_file(bspec['fc'])},
                 'draws': {'path': rel(bspec['draws']), 'sha256': sha_file(bspec['draws'])},
                 'reconstructed_sha256': sha_obj(base)}
    proj = load_projection(spec['projection'])
    depth = load_depth(spec['depth'], teams, spec['kickoff'])
    feat = build_features(sid, pool, base, proj, depth, ab, spec['snaps'], spec['week'])
    hashes = {'export': {'path': rel(spec['export']), 'sha256': sha_file(spec['export'])}, 'baseline': binfo,
              'projection': {'path': rel(spec['projection']), 'sha256': sha_file(spec['projection'])},
              'depth': {'path': rel(spec['depth']), 'sha256': sha_file(spec['depth'])},
              'inactives': {'path': rel(spec['inactives']), 'sha256': sha_file(spec['inactives'])},
              'designations': ({'path': rel(spec['designations']), 'sha256': sha_file(spec['designations'])}
                               if spec['designations'] else 'NOT_AVAILABLE'),
              'snaps': {'path': rel(spec['snaps']), 'sha256': sha_file(spec['snaps']),
                        'weeks_used': f'2026 REG weeks < {spec["week"]}'},
              'kickoff': spec['kickoff']}
    return pool, feat, hashes


def load_contest_entries(sid, cid):
    """Archived full-field entries (the fit and the solver test only) and the raw standings sha256."""
    if sid == 'PIT_CLE':
        from nfl.field import showdown_history_calibration as HC
        c = next(c for c in HC.CONTESTS if c['contest_id'] == cid)
        R = HC.load_raw(c)
        return R['entries'], R['sha256']
    from nfl.field import showdown_field_archive as FA
    S = FA.load(cid, sid)
    return S['entries'], S['rec']['sha256']


def solver_falsification(Us, theta=None):
    """Prereg section 5: profile per-player slot utilities to each archived contest's realised marginals on the
    legal universe and require max_abs_grad <= 1e-6 (theta = 0, and with the fitted θ held fixed)."""
    out = {}
    for name, U in Us.items():
        res = {}
        for lab, th in (('theta_0', None), ('theta_fitted_fixed', theta)):
            if lab == 'theta_fitted_fixed' and th is None:
                continue
            U.pop('_ab', None)
            names = [] if th is None else list(THETA_FEATURES)
            try:
                _, _, info = DR._expfam([U], names, theta_fixed=None if th is None else np.asarray(th, float),
                                        iters=200, tol=SOLVER_TOL * 0.1)
                g = float(info['max_abs_grad'])
                res[lab] = {'max_abs_grad': g, 'iters': info['iters'], 'PASS': g <= SOLVER_TOL}
            except DR.DupeResearchError as e:
                res[lab] = {'state': 'NOT_CONVERGED', 'error': str(e), 'PASS': False}
        out[name] = {'universe': U.get('_universe_kind'), 'feasible_lineups': int(len(U['cpt'])),
                     'entries_in_universe': float(U['n_in']), 'coverage': round(float(U['coverage']), 6), **res}
    return out


def run_fit(now=None, write=True, path=FREEZE_PATH):
    """Fit, test the solver, and FREEZE. Write-once; refuses at or after the first evaluation lock."""
    t0 = now or now_utc()
    need(t0 < parse_ts(FIRST_EVAL_LOCK), 'FREEZE_AT_OR_AFTER_FIRST_EVALUATION_LOCK', f'{t0.isoformat()} >= {FIRST_EVAL_LOCK}')
    need(not pathlib.Path(path).exists(), 'FREEZE_EXISTS', rel(path))
    prereg_sha = check_prereg()
    mods = module_hashes(ENFORCED_MODULES)
    recorded = module_hashes(RECORDED_MODULES)
    blend_check = verify_blend_method()
    sigma = blend_check['sigma']
    blocks, slates_doc, prelock_U = [], {}, {}
    for sid, spec in FIT_SLATES.items():
        pool, feat, hashes = fit_slate_inputs(sid, spec, sigma)
        U = make_universe(feat, pool)
        F = DR._F(U, list(THETA_FEATURES))
        Dc, Df = design(feat, 'cpt'), design(feat, 'flex')
        contests = []
        for cid in spec['contests']:
            entries, raw_sha = load_contest_entries(sid, cid)
            c = entry_counts(U, entries, feat['pads'])
            contests.append({'id': cid, 'n_in': c['n_in'], 't_c': c['t_c'], 't_f': c['t_f'],
                             'e': (c['counts'] @ F) / c['n_in'], 'N': c['N'], 'coverage': c['coverage'],
                             'n_outside_universe': c['n_outside_universe'], 'raw_sha256': raw_sha,
                             'counts': c['counts']})
        blocks.append({'id': sid, 'U': U, 'Dc': Dc, 'Df': Df, 'F': F, 'off': offset(feat), 'contests': contests})
        slates_doc[sid] = {'inputs': hashes, 'declared_features': feat['declared'],
                           'feature_rows_sha256': sha_obj(feat['rows']),
                           'universe_feasible_lineups': int(len(U['cpt'])),
                           'contests': {c['id']: {'standings_raw_sha256': c['raw_sha256'], 'filled_entries': c['N'],
                                                  'entries_in_likelihood': c['n_in'], 'coverage': round(c['coverage'], 6),
                                                  'outside_universe': c['n_outside_universe']} for c in contests}}
        for c in contests:
            Uc = dict(U)
            Uc.update({'counts': c['counts'], 'n_in': c['n_in'], 'N': c['N'], 't_c': c['t_c'], 't_f': c['t_f'],
                       'coverage': c['coverage'], '_universe_kind': 'PRELOCK_R8'})
            Uc.pop('_ab', None)
            prelock_U[f'{sid}:{c["id"]}'] = Uc
    res = fit(blocks)
    w = res['w']
    # in-sample fitted marginals (descriptive, development data)
    insample = {}
    for b in blocks:
        m_c, m_f = marginals(b['U'], b['Dc'], b['Df'], b['F'], w, b['off'])
        for c in b['contests']:
            insample[f'{b["id"]}:{c["id"]}'] = {
                'cpt_mae_in_universe_pp': float(np.mean(np.abs(100 * m_c - 100 * c['t_c']))),
                'flex_mae_in_universe_pp': float(np.mean(np.abs(100 * m_f - 100 * c['t_f'])))}
    th = unpack(w)[2]
    solver_prelock = solver_falsification(prelock_U, th)
    archival = {}
    sl = DR.load_slates()
    for k, s in sl.items():
        U = DR.build_universe(s)
        U['_universe_kind'] = 'B_FAMILY_MOST_ENTERED_32'
        archival[k] = U
    solver_archival = solver_falsification(archival, None)
    del sl, archival
    passed = all(v.get(l, {}).get('PASS', True) for d in (solver_prelock, solver_archival) for v in d.values()
                 for l in ('theta_0', 'theta_fitted_fixed'))
    written = now_utc() if now is None else now
    need(written < parse_ts(FIRST_EVAL_LOCK), 'FREEZE_AT_OR_AFTER_FIRST_EVALUATION_LOCK', written.isoformat())
    body = {
        'ARTIFACT': 'SC_OWN_ROTATION_2_FREEZE', 'candidate_id': CANDIDATE_ID, 'LABEL': LABEL,
        'STATUS': 'FROZEN -- SHADOW_ONLY; NOT prospectively validated; nothing promoted; no refit during evaluation',
        'NOT_A_FOOTBALL_INPUT': True, 'ON_EXECUTION_PATH': False, 'INFLUENCES_SELECTION': False,
        'prereg': {'path': rel(PREREG), 'sha256': prereg_sha, 'commit': '8de91b62'},
        'modules_enforced': mods, 'modules_recorded_not_enforced': recorded,
        'constants': {'EPS': EPS, 'LAMBDA': LAMBDA, 'FLOOR_PCT': FLOOR_PCT, 'K_PLAYERS': K, 'CAP': DR.CAP,
                      'PLAYER_FEATURES': PLAYER_FEATURES, 'THETA_FEATURES': THETA_FEATURES,
                      'SOLVER_TOL': SOLVER_TOL, 'FIT_TOL': FIT_TOL},
        'readings_declared': {k: v for k, v in _readings().items()},
        'coefficients': coef_doc(w),
        'fit': {k: v for k, v in res.items() if k != 'w'},
        'fit_weights': {f'{b["id"]}:{c["id"]}': c['n_in'] for b in blocks for c in b['contests']},
        'fit_in_sample_marginal_mae_DESCRIPTIVE_NOT_EVIDENCE': insample,
        'fitting_data': slates_doc,
        'blend_method_check': blend_check,
        'NOT_AVAILABLE': NOT_AVAILABLE,
        'solver_falsification': {'threshold_max_abs_grad': SOLVER_TOL, 'prelock_universe': solver_prelock,
                                 'b_family_archival_universe': solver_archival,
                                 'VERDICT': 'PASS' if passed else 'FALSIFIED'},
        'evaluation': {'first_eval_slate': FIRST_EVAL_SLATE, 'first_eval_lock': FIRST_EVAL_LOCK,
                       'excluded_development_slates': DEVELOPMENT_SLATES,
                       'covers': ('every DK NFL Showdown slate whose lock is strictly after written_at and whose '
                                  'prediction is sealed before its lock (prereg section 4); none excluded by the '
                                  'freeze time, TB@DAL 2026-10-09T00:15:00Z included'),
                       'min_slates_for_verdict': 4},
        'written_at': written.isoformat(),
    }
    need(passed, 'SOLVER_FALSIFIED', json.dumps({'prelock': solver_prelock, 'archival': solver_archival},
                                                default=_json_default)[:600])
    body['content_sha256'] = sha_obj(body)
    if write:
        write_once(path, body)
    return body


def _readings():
    doc = __doc__.split('DECLARED IMPLEMENTATION READINGS')[1].split('Realised ownership')[0]
    out, cur = {}, None
    for line in doc.splitlines():
        s = line.strip()
        if s[:1] == 'R' and s[1:2].isdigit():
            cur = s.split()[0]
            out[cur] = s[len(cur):].strip()
        elif cur and s:
            out[cur] += ' ' + s
    return out


def write_once(path, body):
    p = pathlib.Path(path)
    need(not p.exists(), 'WRITE_ONCE_EXISTS', rel(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(body, indent=1, default=_json_default, sort_keys=False)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'w') as fh:
        fh.write(txt)
    os.chmod(p, 0o444)
    return p


def load_freeze(path=FREEZE_PATH, enforce_modules=True):
    """The freeze, verified: content hash, prereg hash, and (unless told otherwise) every enforced module hash."""
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, 'FREEZE_ABSENT', rel(p))
    d = json.loads(p.read_text())
    need(d.get('ARTIFACT') == 'SC_OWN_ROTATION_2_FREEZE', 'NOT_A_FREEZE', rel(p))
    body = {k: v for k, v in d.items() if k != 'content_sha256'}
    need(sha_obj(body) == d.get('content_sha256'), 'FREEZE_TAMPERED', rel(p))
    check_prereg(PREREG, d['prereg']['sha256'])
    need(d['prereg']['sha256'] == PREREG_SHA256, 'PREREG_CHANGED', 'freeze vs module')
    if enforce_modules:
        now = module_hashes(d['modules_enforced'])
        diff = sorted(k for k in now if now[k] != d['modules_enforced'][k])
        need(not diff, 'MODULE_CHANGED_SINCE_FREEZE', str(diff))
    need(len(d['coefficients']['vector']) == n_params(), 'FREEZE_COEFFICIENTS_SCHEMA')
    return d, sha_file(p)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('fit', 'check'))
    a = ap.parse_args()
    try:
        if a.cmd == 'fit':
            b = run_fit()
            print(rel(FREEZE_PATH), sha_file(FREEZE_PATH), b['written_at'])
            print(json.dumps(b['coefficients'], indent=1))
            print(json.dumps({k: b['fit'][k] for k in ('iterations', 'max_abs_grad_per_entry', 'converged')}))
            print('solver', b['solver_falsification']['VERDICT'])
        else:
            d, h = load_freeze()
            print('FREEZE OK', h, d['written_at'])
    except RotationError as e:
        print(f'REFUSED[{e.code}] {e}')
        sys.exit(3)
