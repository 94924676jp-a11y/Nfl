"""QB2: frame, the team-aggregate-then-allocate simulator, and the decomposition.

Pre-registration sha256
e69bd331bb72a3f869b8469c27f0d9782ff49c7c69874ea79585f55a9eb84ff1.

POLICY, fixed before evaluation: forecast TEAM dropbacks, allocate to QBs by a
prior-only share, then apply per-QB conversion. 22.7% of team-games carry more
than one QB with a dropback, so one-QB-per-game is wrong one time in four.

EXPLORATORY. 2022-2025 heavily mined. No promotion possible.
"""
from __future__ import annotations

import bisect, collections, itertools, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
import rc1_lib as L                                            # noqa: E402

EVAL = [2022, 2023, 2024, 2025]
SEED = 20260908
K = 4.0
HL = 2.0
M_DRAWS = 1000
PASS_COMPONENTS = ('V', 'S', 'M', 'C', 'Y')
RUSH_COMPONENTS = ('VS', 'RO', 'RY')


def load():
    d = pickle.load(open(f'{HERE}/qb.pkl', 'rb'))
    P, T = d['player'], d['team']
    rows, _ = L.load()
    qbs = [r for r in rows if r.get('position') == 'QB']
    qbs.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    for r in qbs:
        m = P.get((r['season'], r['week'], r['team'], r['gsis_id'])) or {}
        t = T.get((r['season'], r['week'], r['team'])) or {}
        r['db'] = int(m.get('dropbacks', 0))
        r['team_db'] = int(t.get('dropbacks', 0))
        r['att'] = int(m.get('attempts', 0))
        r['sacks'] = int(m.get('sacks', 0))
        r['scr'] = int(m.get('scrambles', 0))
        r['spikes'] = int(m.get('spikes', 0))
        r['cmp'] = int(m.get('completions', 0))
        r['pyds'] = float(m.get('pass_yards', 0.0))
        r['ptd'] = int(m.get('pass_td', 0))
        r['int'] = int(m.get('interceptions', 0))
        r['drush'] = int(m.get('designed_rushes', 0))
        r['ryds'] = float(m.get('rush_yards', 0.0))
        r['rtd'] = int(m.get('rush_td', 0))
        r['rush_opp'] = r['drush'] + r['scr']
    attach(qbs)
    return qbs


def attach(rs):
    """Prior-only history, strict ordinal prefix cut."""
    hist = collections.defaultdict(list); hord = collections.defaultdict(list)
    thist = collections.defaultdict(list); thord = collections.defaultdict(list)
    for r in rs:
        pid = r['gsis_id']
        i = bisect.bisect_left(hord[pid], r['ord'])
        past = [x for x in hist[pid][:i] if x['db'] > 0]
        r['h_games'] = len(past)
        r['h_db'] = sum(x['db'] for x in past)
        r['h_att'] = sum(x['att'] for x in past)
        r['h_sack'] = sum(x['sacks'] for x in past)
        r['h_scr'] = sum(x['scr'] for x in past)
        r['h_cmp'] = sum(x['cmp'] for x in past)
        r['h_pyds'] = sum(x['pyds'] for x in past)
        r['h_ptd'] = sum(x['ptd'] for x in past)
        r['h_int'] = sum(x['int'] for x in past)
        r['h_drush'] = sum(x['drush'] for x in past)
        r['h_rushopp'] = sum(x['rush_opp'] for x in past)
        r['h_ryds'] = sum(x['ryds'] for x in past)
        r['h_rtd'] = sum(x['rtd'] for x in past)
        r['h_share'] = [x['db'] / x['team_db'] for x in past if x['team_db'] > 0]
        r['h_teamdb'] = [x['team_db'] for x in past if x['team_db'] > 0]
        r['h_ypc'] = [x['pyds'] / x['cmp'] for x in past if x['cmp'] > 0]
        r['h_ypr'] = [x['ryds'] / x['rush_opp'] for x in past
                      if x['rush_opp'] > 0]
        hist[pid].append(r); hord[pid].append(r['ord'])
        tk = r['team']
        j = bisect.bisect_left(thord[tk], r['ord'])
        tp = thist[tk][:j]
        r['h_seq'] = [(x['db'], x['att'], x['sacks'], x['scr'], x['cmp'],
                       x['pyds'], x['ptd'], x['int'], x['drush'])
                      for x in past]
        r['h_team_db_series'] = [x['team_db'] for x in tp if x['team_db'] > 0]
        thist[tk].append(r); thord[tk].append(r['ord'])
    return rs


def eligible(r, ev=None):
    if ev is not None and r['season'] != ev:
        return False
    return bool(r['db'] >= 1 and r['h_games'] >= 1)


def ewma(vals, hl=HL):
    lam = 0.5 ** (1.0 / hl); num = den = 0.0; w = 1.0
    for v in reversed(vals):
        num += w * v; den += w; w *= lam
    return num / den if den > 0 else None


def pools(rs, ev):
    """QB positional pools from strictly prior seasons only."""
    a = collections.Counter(); tdb = []; shares = []; ypc = []; ypr = []
    for r in rs:
        if r['season'] >= ev or r['db'] <= 0:
            continue
        for f in ('db', 'att', 'sacks', 'scr', 'cmp', 'ptd', 'int',
                  'drush', 'rush_opp', 'rtd'):
            a[f] += r[f]
        a['pyds'] += r['pyds']; a['ryds'] += r['ryds']
        if r['team_db'] > 0:
            tdb.append(r['team_db']); shares.append(r['db'] / r['team_db'])
        if r['cmp'] > 0:
            ypc.append(r['pyds'] / r['cmp'])
        if r['rush_opp'] > 0:
            ypr.append(r['ryds'] / r['rush_opp'])
    db = max(a['db'], 1)
    return {'team_db': np.array(tdb, float) if tdb else np.array([32.0]),
            'share': np.array(shares, float) if shares else np.array([0.9]),
            'ypc': np.array(ypc, float) if ypc else np.array([11.0]),
            'ypr_draws': np.array(ypr, float) if ypr else np.array([4.0]),
            'p_att': a['att'] / db, 'p_sack': a['sacks'] / db,
            'p_scr': a['scr'] / db,
            'p_cmp': a['cmp'] / max(a['att'], 1),
            # REBASED to the causal parent. A pass TD is a completion and an
            # interception is an incompletion; rates taken per attempt let a
            # draw manufacture both.
            'p_ptd': a['ptd'] / max(a['cmp'], 1),
            'p_int': a['int'] / max(a['att'] - a['cmp'], 1),
            'drush_per_db': a['drush'] / db,
            'rush_per_db': a['rush_opp'] / db,
            'ypr': a['ryds'] / max(a['rush_opp'], 1),
            'rtd_per_rush': a['rtd'] / max(a['rush_opp'], 1)}


RUNGS = ('L0', 'L1', 'L2', 'L3')
_SEQ = {'db': 0, 'att': 1, 'sacks': 2, 'scr': 3, 'cmp': 4, 'pyds': 5,
        'ptd': 6, 'int': 7, 'drush': 8}


def _ew(n, hl=HL):
    """EWMA weights over n games, oldest first. Newest carries weight 1."""
    lam = 0.5 ** (1.0 / hl)
    return np.array([lam ** (n - 1 - i) for i in range(n)], float)


def rung_weight(r, rung):
    """How much of a QB's own history the rung uses. L0 uses none."""
    if rung == 'L0':
        return 0.0
    if rung == 'L2':
        return 1.0 if r['h_games'] > 0 else 0.0
    return r['h_games'] / (r['h_games'] + K)


def rung_rate(r, num, den, rung, pool_val, den_offset=None):
    """A conversion rate under one rung. num/den name h_seq columns.

    L0 pooled  ·  L1 shrunk pooled history  ·  L2 EWMA  ·  L3 shrunk EWMA.
    EWMA is taken over numerator and denominator separately and then divided:
    a per-game ratio is undefined whenever the denominator is zero, and
    dropping those games would quietly reweight the estimate.
    """
    w = rung_weight(r, rung)
    if w <= 0 or not r['h_seq']:
        return pool_val
    a = np.array([g[_SEQ[num]] for g in r['h_seq']], float)
    b = np.array([g[_SEQ[den]] for g in r['h_seq']], float)
    if den_offset is not None:
        b = b - np.array([g[_SEQ[den_offset]] for g in r['h_seq']], float)
    ww = _ew(len(a)) if rung in ('L2', 'L3') else np.ones(len(a))
    num_s, den_s = float((ww * a).sum()), float((ww * b).sum())
    own = num_s / den_s if den_s > 0 else pool_val
    return own if rung == 'L2' else w * own + (1 - w) * pool_val


def _mix(rng, own, pool, w, m, ewma=False):
    own = np.asarray(own, float)
    if len(own) == 0 or w <= 0:
        return pool[rng.integers(0, len(pool), m)]
    use = rng.random(m) < w
    if ewma:
        # RESAMPLED WITH RECENCY WEIGHTS, not truncated to recent games. A
        # window would throw away history; a weight keeps it and discounts it.
        q = _ew(len(own)); q = q / q.sum()
        pick = rng.choice(len(own), m, p=q)
    else:
        pick = rng.integers(0, len(own), m)
    return np.where(use, own[pick], pool[rng.integers(0, len(pool), m)])


def simulate(rs, ev, allrows, oracle=(), seed=SEED, m=M_DRAWS, rung='L1'):
    """Team-aggregate-then-allocate. Returns a dict of (n, m) draw matrices."""
    po = pools(allrows, ev)
    n = len(rs)
    out = {k: np.zeros((n, m), float) for k in
           ('db', 'att', 'sacks', 'scr', 'cmp', 'pyds', 'ptd', 'int',
            'drush', 'rush_opp', 'ryds', 'rtd')}
    for idx, r in enumerate(rs):
        rng = np.random.default_rng(
            [seed, int(r['ord']),
             int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little')])
        if rung not in RUNGS:
            raise ValueError(f'unknown ladder rung {rung!r}; the ladder is '
                             f'CLOSED at {RUNGS}')
        w = rung_weight(r, rung)
        ew = rung in ('L2', 'L3')

        # V: team dropback volume
        V = (np.full(m, r['team_db'], float) if 'V' in oracle
             else _mix(rng, r['h_team_db_series'], po['team_db'], w, m, ew))
        # S: this QB's share of it
        S = (np.full(m, (r['db'] / r['team_db']) if r['team_db'] > 0 else 1.0,
                     float) if 'S' in oracle
             else np.clip(_mix(rng, r['h_share'], po['share'], w, m, ew), 0, 1))
        DB = np.maximum(np.rint(V * S), 0).astype(int)
        if 'V' in oracle and 'S' in oracle:
            DB = np.full(m, r['db'], int)

        # M: dropback outcome mix -- attempt / sack / scramble
        if 'M' in oracle:
            d = max(r['db'], 1)
            pa, ps, psc = r['att'] / d, r['sacks'] / d, r['scr'] / d
        else:
            pa = rung_rate(r, 'att', 'db', rung, po['p_att'])
            ps = rung_rate(r, 'sacks', 'db', rung, po['p_sack'])
            psc = rung_rate(r, 'scr', 'db', rung, po['p_scr'])
        tot = max(pa + ps + psc, 1e-9)
        pa, ps, psc = pa / tot, ps / tot, psc / tot
        # DRAWN, NOT ROUNDED. Rounding DB x rate gives a point value per draw
        # and destroys the binomial spread: sacks came back at 0.715 nominal-90
        # coverage and rush opportunities at 0.724. That is R1's lesson --
        # substituting a point where a distribution belongs -- committed inside
        # my own V1 rather than by a candidate.
        SACK = rng.binomial(np.maximum(DB, 0), min(max(ps, 0.0), 1.0))
        rem = np.maximum(DB - SACK, 0)
        psc_c = psc / max(pa + psc, 1e-9)
        SCR = rng.binomial(rem, min(max(psc_c, 0.0), 1.0))
        ATT = np.maximum(rem - SCR, 0)
        if 'M' in oracle:
            # Same rule: a perfect mix applied to an exact dropback count must
            # give exact component counts.
            if 'V' in oracle and 'S' in oracle:
                ATT = np.full(m, r['att'], int)
                SACK = np.full(m, r['sacks'], int)
                SCR = np.full(m, r['scr'], int)
            else:
                SACK = np.rint(DB * ps).astype(int)
                SCR = np.rint(DB * psc).astype(int)
                ATT = np.maximum(DB - SACK - SCR, 0)

        # C: completion conversion
        pc = ((r['cmp'] / max(r['att'], 1)) if 'C' in oracle
              else rung_rate(r, 'cmp', 'att', rung, po['p_cmp']))
        # ORACLE COLLAPSES, CANDIDATE DRAWS. Oracling C means the true
        # conversion RATE is known, so with an exact attempt count the
        # completion count must be exact -- a binomial draw here broke the
        # full-oracle identity at 3.74 yards. The non-oracle path keeps its
        # binomial spread, which is what fixed the coverage.
        if 'C' in oracle:
            CMP = np.rint(ATT * min(max(pc, 0.0), 1.0)).astype(int)
        else:
            CMP = rng.binomial(np.maximum(ATT, 0), min(max(pc, 0.0), 1.0))

        # Y: passing yards per completion
        if 'Y' in oracle:
            ypc = (r['pyds'] / r['cmp']) if r['cmp'] > 0 else float(po['ypc'].mean())
            PY = CMP * ypc
        else:
            ypc_d = _mix(rng, r['h_ypc'], po['ypc'], w, m, ew)
            PY = CMP * ypc_d

        # discrete conversion, never a decomposition axis (see prereg s5).
        # DRAWN FROM THE CAUSAL PARENT, not from attempts: a passing TD is a
        # completion and an interception is an incompletion. Taken per attempt
        # these produced 84 draw cells with more TDs than completions and 189
        # with more interceptions than incompletions -- states that occur 0
        # times in 2,645 real QB games. See addendum_qb2_coherence.md.
        ptd = rung_rate(r, 'ptd', 'cmp', rung, po['p_ptd'])
        pint = rung_rate(r, 'int', 'att', rung, po['p_int'],
                         den_offset='cmp')
        PTD = rng.binomial(np.maximum(CMP, 0), min(max(ptd, 0), 1))
        INC = np.maximum(ATT - CMP, 0)
        INT = rng.binomial(INC, min(max(pint, 0), 1))

        # rushing
        # RO IS COMPOSED, NEVER DRAWN WHOLE. rush_opp == designed + scrambles
        # by construction, and the scramble count is already fixed above by the
        # dropback mix. Drawing the total independently put 18.2% of draw cells
        # below their own scramble count. The oracle supplies the DESIGNED
        # portion, which is what keeps designed rush and scramble distinct as
        # prereg s4 requires.
        if 'RO' in oracle:
            DES = np.full(m, r['drush'], int)
        else:
            dpd = rung_rate(r, 'drush', 'db', rung, po['drush_per_db'])
            DES = rng.binomial(np.maximum(DB, 0), min(max(dpd, 0.0), 1.0))
        RO = SCR + DES
        if 'RY' in oracle:
            ypr = np.full(m, (r['ryds'] / r['rush_opp'])
                          if r['rush_opp'] > 0 else po['ypr'], float)
        else:
            # RESAMPLED, not a point rate. A point yards-per-rush left rushing
            # yards at 0.198 nominal-50 coverage.
            ypr = _mix(rng, r['h_ypr'], po['ypr_draws'], w, m, ew)
        prtd = (po['rtd_per_rush'] if w <= 0 else
                w * (r['h_rtd'] / max(r['h_rushopp'], 1))
                + (1 - w) * po['rtd_per_rush'])
        RTD = rng.binomial(np.maximum(RO, 0), min(max(prtd, 0), 1))
        out['db'][idx] = DB; out['att'][idx] = ATT; out['sacks'][idx] = SACK
        out['scr'][idx] = SCR; out['cmp'][idx] = CMP; out['pyds'][idx] = PY
        out['ptd'][idx] = PTD; out['int'][idx] = INT
        out['drush'][idx] = DES
        out['rush_opp'][idx] = RO; out['ryds'][idx] = RO * ypr
        out['rtd'][idx] = RTD
    return out


def shapley(vals, comps):
    n = len(comps); phi = {}
    for c in comps:
        rest = [x for x in comps if x != c]; tot = 0.0
        for k in range(len(rest) + 1):
            for Ss in itertools.combinations(rest, k):
                fs = frozenset(Ss)
                wt = (math.factorial(k) * math.factorial(n - k - 1)
                      / math.factorial(n))
                tot += wt * (vals[fs | {c}] - vals[fs])
        phi[c] = tot
    return phi
