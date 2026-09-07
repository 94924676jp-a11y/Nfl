"""P4E: the frozen carry pipeline, and prior-only allocation features.

Everything except the pre-reconciliation share WEIGHT is imported from P4C/P4D
and untouched. `baseline_cells` reproduces the accepted control exactly and the
runner refuses to continue if it does not.
"""
import bisect, collections, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
P5A = os.path.abspath(os.path.join(HERE, '..', 'p5a'))
for p in (P4C, P5A, HERE, '/home/user/nfl'):
    sys.path.insert(0, p)
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p5a_lib as PL                                           # noqa: E402
from run_p4c import groups_of                                  # noqa: E402

CLS = 'carries'
EVAL = [2022, 2023, 2024, 2025]

# P4C's published control. READ FROM THE ARTIFACT, never transcribed.
#
# This was a hardcoded literal until 2026-09-07 and the literal was wrong: it
# agreed with p4c_results.json to four decimal places -- the precision printed
# in run_p4c.log -- and disagreed beyond it, because it had been copied off the
# log line rather than read out of the JSON. It made a correct P4E look like a
# 1.8e-05 reproduction failure. A gate that asserts against a number nobody
# read is not a gate, so the number is now read, and the file it came from is
# hashed so the report can cite it.
RESULTS_PATH = os.path.join(P4C, 'p4c_results.json')


def _published():
    import hashlib, json
    raw = open(RESULTS_PATH, 'rb').read()
    res = json.loads(raw)
    got = {int(ev): res[CLS][ev]['scores']['C']['crps'] for ev in res[CLS]}
    missing = [e for e in EVAL if e not in got]
    if missing:
        raise RuntimeError(f'{RESULTS_PATH}: no carries/C CRPS for {missing}')
    return ({e: got[e] for e in EVAL},
            hashlib.sha256(raw).hexdigest())


PUBLISHED, PUBLISHED_SHA256 = _published()


def load_all():
    rows = CB.load_panel()
    vol = CB.load_volume()
    pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, CLS)
    D = pickle.load(open(f'{P5A}/pg.pkl', 'rb'))
    return rows, vol, pa, sub, D


def cell(rows, vol, pa, sub, ev):
    """Every frozen quantity for one evaluation season."""
    c = CL.CLASSES[CLS]
    store = vol[(c['den'], ev)]
    par = CB.fit_params(sub, CLS, ev, rows)
    te = [r for r in sub if r['season'] == ev and r.get('s_carries') is not None
          and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
          and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
    te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    n = len(te)
    starts, cg, gk = groups_of(te)
    G = len(starts)
    ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
    gti = ti[starts]
    mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                         np.random.default_rng(CL.SEED + 5002))
    avail = (1.0 - mass).astype(np.float32)
    p_app = np.array([pa[id(r)] for r in te], np.float32)
    Ad = (np.random.default_rng(CL.SEED + 1009)
          .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
    C_pre = np.array([r['_C'] for r in te], np.float32)
    W_ctrl = CB.gen_weights('C', C_pre, [r['position'] for r in te], par, CLS,
                            n, CL.M_DRAWS, np.random.default_rng(CL.SEED + 3034))
    y = np.array([r['y_carries'] for r in te], float)
    gidx = np.searchsorted(starts, np.arange(n), 'right') - 1
    Tstar = store['realized'][gti].astype(np.float64)
    Sstar = np.array([(y[i] / Tstar[gidx[i]]) if Tstar[gidx[i]] > 0 else 0.0
                      for i in range(n)], np.float64)
    return {'te': te, 'n': n, 'starts': starts, 'cg': cg, 'G': G,
            'T': store['B'][ti], 'Tg': store['B'][gti], 'Tstar': Tstar,
            'avail': avail, 'Ad': Ad, 'p_app': p_app, 'C_pre': C_pre,
            'W_ctrl': W_ctrl, 'y': y, 'gidx': gidx, 'Sstar': Sstar,
            'par': par, 'store': store,
            'A_star': np.array([1.0 if r['appeared'] else 0.0 for r in te],
                               np.float32),
            'cluster': [f"{r['team']}_{r['ord']}" for r in te]}


def counts_from_weights(cellv, W):
    """The FROZEN reconciliation. Only W differs between systems."""
    WA = W * cellv['Ad']
    tot = CL.gsum(WA, cellv['starts'])
    den = CL.gexp(tot, cellv['cg'])
    S = np.divide(WA * CL.gexp(cellv['avail'], cellv['cg']), den,
                  out=np.zeros_like(WA), where=den > 1e-12)
    S, _ = CL.waterfill(S, cellv['starts'], cellv['cg'], 1.0)
    return (cellv['T'] * S).astype(np.float32), S


# ---------------------------------------------------------------------------
# PRIOR-ONLY ALLOCATION FEATURES. Read before update, always.
# ---------------------------------------------------------------------------
def attach_features(sub):
    """Per RB player-game: history depth, hierarchy, competition, role change,
    snap relationship -- all from strictly earlier team-games."""
    by_team = collections.defaultdict(list)
    for r in sub:
        by_team[r['team']].append(r)
    hist = collections.defaultdict(list)          # player -> prior rows
    hist_ord = collections.defaultdict(list)      # the same rows' ordinals
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        # STRICTLY EARLIER ORDINALS, not merely earlier in the processing order.
        #
        # 343 player-ordinal pairs in this panel carry two rows: a player who
        # changed team mid-week appears once for each team in the same week.
        # Taking `past` as "everything appended so far" let the second row read
        # the first -- same week, so not future information, but not strictly
        # prior either, and the section 4 masking audit caught it. The prefix
        # cut here is what makes that audit come back clean.
        k = bisect.bisect_left(hist_ord[pid], r['ord'])
        past = hist[pid][:k]
        sh = [x['s_carries'] for x in past if x['appeared']]
        car = [x['y_carries'] for x in past]
        app = [1.0 if x['appeared'] else 0.0 for x in past]
        r['g_n_games'] = len(past)
        r['g_n_app'] = int(sum(app))
        r['g_car_career'] = float(sum(car))
        r['g_car_prev_season'] = float(sum(
            x['y_carries'] for x in past if x['season'] == r['season'] - 1))
        for k in (4, 8, 10):
            r[f'g_car_last{k}'] = float(sum(x['y_carries'] for x in past[-k:]))
            r[f'g_sh_last{k}'] = (float(np.mean([x['s_carries']
                                                 for x in past[-k:]
                                                 if x['appeared']]))
                                  if any(x['appeared'] for x in past[-k:])
                                  else None)
        r['g_sh_mean'] = float(np.mean(sh)) if sh else None
        # EWMA half-life 3 over prior APPEARED shares -- recomputed here
        # rather than read from `_C`, which p4c_build.fit_params only populates
        # per evaluation season. Same definition, available on every row.
        if sh:
            lam = 0.5 ** (1 / 3.0)
            num = den = 0.0
            w = 1.0
            for v in reversed(sh):
                num += w * v; den += w; w *= lam
            r['g_sh_ewma'] = num / den
        else:
            r['g_sh_ewma'] = None
        r['g_sh_sd'] = float(np.std(sh)) if len(sh) >= 3 else None
        r['g_snap_prior'] = float(np.mean(
            [x['s_snaps'] for x in past[-8:] if x.get('s_snaps') is not None]
        )) if any(x.get('s_snaps') is not None for x in past[-8:]) else None
        r['g_snap_per_carry'] = ((r['g_snap_prior'] / max(r['g_sh_ewma'], 1e-6))
                                 if (r['g_snap_prior'] is not None
                                     and r['g_sh_ewma']) else None)
        # role change: prior share step
        if len(sh) >= 4:
            r['g_sh_step'] = float(np.mean(sh[-2:]) - np.mean(sh[-4:-2]))
        else:
            r['g_sh_step'] = None
        r['g_absent_run'] = 0
        for x in reversed(past):
            if x['appeared']:
                break
            r['g_absent_run'] += 1
        r['g_returning'] = 1.0 if (r['g_absent_run'] >= 1 and sh) else 0.0
        hist[pid].append(r)
        hist_ord[pid].append(r['ord'])

    # hierarchy and competition, from the team's PREVIOUS game only
    for tm, rs in by_team.items():
        ords = sorted({x['ord'] for x in rs})
        prev = {o: (ords[i - 1] if i else None) for i, o in enumerate(ords)}
        by_ord = collections.defaultdict(list)
        for x in rs:
            by_ord[x['ord']].append(x)
        for x in rs:
            p = prev[x['ord']]
            grp = by_ord.get(p, [])
            shares = sorted(((g['s_carries'] or 0.0), g['gsis_id'])
                            for g in grp)[::-1]
            ranks = {pid: i + 1 for i, (_s, pid) in enumerate(shares)}
            x['g_prev_rank'] = ranks.get(x['gsis_id'])
            v = np.array([s for s, _ in shares], float)
            tot = v.sum()
            x['g_team_hhi'] = float(((v / tot) ** 2).sum()) if tot > 0 else None
            x['g_team_entropy'] = (float(-(np.where(v > 0, v / tot, 1)
                                           * np.log(np.where(v > 0, v / tot, 1))
                                           ).sum()) if tot > 0 else None)
            x['g_n_rb_used'] = float(sum(1 for s, _ in shares if s > 0))
            x['g_top_share_prev'] = float(v[0]) if len(v) else None
            # LEAK, FOUND AND FIXED 2026-09-07 BEFORE ANY CANDIDATE WAS JUDGED.
            # This subtracted x['s_carries'] -- the CURRENT game's realised
            # share -- from the previous game's total. The current outcome then
            # entered the design linearly and block C "improved" carry CRPS by
            # 28%. What must be removed is the player's OWN PREVIOUS-GAME
            # share, so that the feature is the prior-game usage of everyone
            # except him. The wrong version's numbers are kept in
            # p4e_leak_incident.json and are not results.
            own_prev = 0.0
            for _g in grp:
                if _g['gsis_id'] == x['gsis_id']:
                    own_prev = float(_g['s_carries'] or 0.0)
                    break
            others = [g for g in grp if g['gsis_id'] != x['gsis_id']]
            x['g_teammate_share_sum'] = (float(tot - own_prev)
                                         if p is not None else None)
            x['g_n_competitors'] = float(len(others)) if p is not None else None
            x['g_teammate_hist_depth'] = (
                float(np.mean([g.get('g_car_career') or 0.0 for g in others]))
                if others else None)
            x['g_teammate_app_rate'] = (
                float(np.mean([(g.get('g_n_app') or 0)
                               / max(g.get('g_n_games') or 0, 1)
                               for g in others])) if others else None)
    # rank persistence over the last three team-games
    for pid, past in hist.items():
        seq = []
        for r in past:
            r['g_rank_persist'] = (float(np.mean([1.0 if q == r['g_prev_rank']
                                                  else 0.0 for q in seq[-3:]]))
                                   if seq and r['g_prev_rank'] else None)
            r['g_rank_sd'] = (float(np.std(seq[-4:])) if len(seq) >= 3 else None)
            if r['g_prev_rank']:
                seq.append(r['g_prev_rank'])
    return sub


BLOCKS = {
    'A': ['g_n_games', 'g_n_app', 'g_car_career', 'g_car_prev_season',
          'g_car_last4', 'g_car_last8', 'g_car_last10'],
    'B': ['g_prev_rank', 'g_rank_persist', 'g_rank_sd', 'g_top_share_prev'],
    # Block C now carries every item predeclaration section 5 lists for it:
    # teammates' prior carry shares, their appearance behaviour, their history
    # depth, concentration, entropy, and a competitor count.
    'C': ['g_team_hhi', 'g_team_entropy', 'g_n_rb_used',
          'g_teammate_share_sum', 'g_n_competitors',
          'g_teammate_hist_depth', 'g_teammate_app_rate'],
    'D': ['g_sh_step', 'g_absent_run', 'g_returning'],
    'E': ['g_snap_prior', 'g_snap_per_carry'],
}
BASE_FEATS = ['g_sh_ewma', 'g_sh_mean', 'g_sh_last4', 'g_sh_last8',
              'g_sh_sd']


def design(rs, blocks):
    """Design row: the base share history plus the named blocks. A missing
    value is a zero PLUS an explicit missingness flag, never a silent
    imputation."""
    feats = list(BASE_FEATS)
    for b in blocks:
        feats += BLOCKS[b]
    X = np.zeros((len(rs), 2 * len(feats)), np.float64)
    for i, r in enumerate(rs):
        for j, f in enumerate(feats):
            v = r.get(f)
            X[i, 2 * j] = 0.0 if v is None else float(v)
            X[i, 2 * j + 1] = 1.0 if v is None else 0.0
    return X, feats
