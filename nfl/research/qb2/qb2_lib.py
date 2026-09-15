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

# HOW THE QUARTERBACK SHARE S IS BUILT. The incumbent is the DEFAULT and is
# byte-for-byte the behaviour every sealed artifact was produced under; a
# candidate must be asked for by name.
#
# SHARE_SPEC_UNCONDITIONAL resamples this quarterback's own prior shares
# against a positional pool holding EVERY quarterback-game with a dropback,
# backups included. Measured on the 2020-2024 pool: 690 of 3,376 rows (20.4%)
# were not their team's primary passer that week and their mean share is
# 0.1233 against 0.9683 for the 2,686 primary rows. The two components are
# therefore estimates of different quantities and the mixture weight trades
# between them as though they were the same one.
#
# SHARE_SPEC_STARTER_CONDITIONED (P2 repair 3, candidate R12) puts both
# components on one conditioning basis: the own component is this
# quarterback's own prior games AS HIS TEAM'S PRIMARY PASSER, and the pool is
# stratified by `prior_primary` -- whether the pool row's passer was his
# team's primary passer in HIS OWN most recent previous appearance. Both
# labels are facts about games strictly earlier than the one being forecast,
# so no future information enters. No constant is introduced: the mixture
# weight is the module's existing `rung_weight`.
SHARE_SPEC_UNCONDITIONAL = 'unconditional'
SHARE_SPEC_STARTER_CONDITIONED = 'starter_conditioned'
SHARE_SPECS = (SHARE_SPEC_UNCONDITIONAL, SHARE_SPEC_STARTER_CONDITIONED)

# HOW PASSING YARDS ARE BUILT FROM COMPLETIONS. The incumbent is the DEFAULT
# and is byte-for-byte the behaviour every sealed artifact was produced under;
# a candidate must be asked for by name.
#
# YPC_SPEC_GAME_RATIO is the incumbent: ONE game-level yards-per-completion
# ratio is resampled whole and multiplied by an independently drawn completion
# count. The donor ratio carries no record of the completion count that
# produced it and is not weighted by it, so a ratio estimated at n = 1
# completion is applied at n = 16 with no shrinkage. That is SCALE
# NON-EXCHANGEABILITY and it is what puts 680 cells of the sealed corpus above
# the all-time single-game record of 554 yards (max 1,587) and 2,262 cells
# below zero. Measured on the 3,787-game donor pool: negative yards per
# completion exists in real football ONLY at 1-2 completions, and across the
# 3,181 games with 5 or more completions the minimum is +3.462.
#
# YPC_SPEC_COMPLETION_BLOCKS (P8 repair, candidate R13) changes the UNIT OF
# RESAMPLING from the game to the completion. A draw needing CMP completions
# draws donor games with probability proportional to their own completion
# count and consumes min(n_donor, completions still needed) completions from
# each, until CMP are covered:
#
#     PY = sum_k t_k * ypc_k,   sum_k t_k == CMP,   t_k <= n_k
#
# so no donor game ever supplies yardage for more completions than it itself
# recorded. The expectation is the ratio estimator sum(pass_yards) /
# sum(completions) over the pool -- the same quantity the incumbent estimates
# by an unweighted mean of ratios -- and the dispersion of the implied ratio
# now falls with CMP the way the realised bands do. NOTHING IS CLIPPED,
# TRUNCATED OR REJECTED: the support of the generator is unchanged and only
# the probability law moves. No constant is introduced; the mixture weight is
# the module's existing `rung_weight`, applied per completion block rather
# than per game, which is the unit the weight is a reliability statement
# about.
YPC_SPEC_GAME_RATIO = 'game_ratio'
YPC_SPEC_COMPLETION_BLOCKS = 'completion_blocks'
YPC_SPECS = (YPC_SPEC_GAME_RATIO, YPC_SPEC_COMPLETION_BLOCKS)


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


def primary_flags(rs):
    """Who took the most dropbacks for his team in each team-game.

    A FACT ABOUT A GAME, used only for games strictly earlier than the one
    being forecast. Ties break by attempts then gsis_id, which is the rule
    `nfl/research/v3/h1/h1_frame.py` uses, so the two agree row for row.
    Written onto every row as `_primary` and recomputed on each call, so a
    second `attach` over a frame with prospective rows appended cannot leave a
    stale label behind.
    """
    by = collections.defaultdict(list)
    for r in rs:
        by[(r['season'], r['week'], r['team'])].append(r)
    for v in by.values():
        v.sort(key=lambda r: (-r.get('db', 0), -r.get('att', 0),
                              str(r['gsis_id'])))
        for i, r in enumerate(v):
            r['_primary'] = bool(i == 0 and r.get('db', 0) > 0)
    return rs


def attach(rs):
    """Prior-only history, strict ordinal prefix cut."""
    primary_flags(rs)
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
        # THE SAME HISTORY, CONDITIONED ON THE ROLE. Only prior games, only
        # ones in which he was his team's primary passer. `prior_primary` is
        # his role in his most recent previous appearance and is None when he
        # has none; it is the only role signal in this repository that is
        # available before kickoff.
        r['h_share_primary'] = [x['db'] / x['team_db'] for x in past
                                if x['team_db'] > 0 and x['_primary']]
        r['prior_primary'] = past[-1]['_primary'] if past else None
        r['h_teamdb'] = [x['team_db'] for x in past if x['team_db'] > 0]
        r['h_ypc'] = [x['pyds'] / x['cmp'] for x in past if x['cmp'] > 0]
        # THE DENOMINATOR EACH RATIO WAS ESTIMATED ON, kept beside the
        # ratio. Written unconditionally and in the same order as `h_ypc`, so
        # the two are index-aligned by construction rather than by a later
        # zip that could silently mis-pair them. The incumbent never reads it.
        r['h_ypc_n'] = [x['cmp'] for x in past if x['cmp'] > 0]
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
    ypc_n = []
    strat = collections.defaultdict(list)
    for r in rs:
        if r['season'] >= ev or r['db'] <= 0:
            continue
        for f in ('db', 'att', 'sacks', 'scr', 'cmp', 'ptd', 'int',
                  'drush', 'rush_opp', 'rtd'):
            a[f] += r[f]
        a['pyds'] += r['pyds']; a['ryds'] += r['ryds']
        if r['team_db'] > 0:
            tdb.append(r['team_db']); shares.append(r['db'] / r['team_db'])
            # Stratified by the pool row's OWN lagged role. Absent on a frame
            # that has not been through `attach`, in which case the stratum is
            # simply not built and the starter-conditioned spec refuses by
            # name rather than falling back to the pool it is repairing.
            if 'prior_primary' in r:
                strat[r['prior_primary']].append(r['db'] / r['team_db'])
        if r['cmp'] > 0:
            ypc.append(r['pyds'] / r['cmp'])
            ypc_n.append(r['cmp'])
        if r['rush_opp'] > 0:
            ypr.append(r['ryds'] / r['rush_opp'])
    db = max(a['db'], 1)
    return {'share_by_prior_primary':
                {k: np.array(v, float) for k, v in strat.items() if v},
            'team_db': np.array(tdb, float) if tdb else np.array([32.0]),
            'share': np.array(shares, float) if shares else np.array([0.9]),
            'ypc': np.array(ypc, float) if ypc else np.array([11.0]),
            # The completion count behind each pool ratio, index-aligned with
            # 'ypc'. `ypc_w` is that count normalised: drawing a donor with
            # this probability is drawing a COMPLETION uniformly from the
            # pool's completions rather than a GAME uniformly from its games.
            'ypc_n': np.array(ypc_n, float) if ypc_n else np.array([1.0]),
            'ypc_w': ((np.array(ypc_n, float) / float(sum(ypc_n)))
                      if ypc_n else np.array([1.0])),
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


def _norm_w(n, q=None):
    """Donor probabilities proportional to completion count, optionally EWMA.

    Returns None when there is nothing to draw from, so the caller refuses
    rather than dividing by zero.
    """
    n = np.asarray(n, float)
    if n.size == 0:
        return None
    p = n if q is None else n * np.asarray(q, float)
    tot = float(p.sum())
    if not (tot > 0):
        return None
    return p / tot


def completion_block_yards(rng, own_y, own_n, pool_y, pool_p, pool_n, w, CMP,
                           own_p=None):
    """PY as a sum over COMPLETION BLOCKS. Returns (PY, ledger).

    Each block draws one donor game and takes `t = min(n_donor, completions
    still needed)` completions' worth of that donor's realised yards per
    completion. The loop ends when every draw has exactly CMP completions
    covered, so

        sum_k t_k == CMP   and   t_k <= n_k   for every block,

    which is the property the incumbent lacks: there, one donor covers ALL
    CMP completions however few produced it.

    THE SOURCE IS CHOSEN PER BLOCK, not per draw. `w` is a reliability weight
    on an estimate of a per-completion rate, so it is applied at the
    completion. The incumbent applies it at the game, which makes a whole
    game's yardage either entirely this quarterback's history or entirely the
    pool's; measured on the 2025 cohort that per-game switch is worth a factor
    of 1.8 in the rate of cells above the all-time record (9.50e-04 against
    5.24e-04) and a factor of 9 in out-of-support cells.

    THE LEDGER IS RETURNED, NOT ASSERTED AWAY. It carries the closure this
    function is supposed to hold by construction, so a caller -- and the test
    module -- reads the property from the mechanism instead of assuming it.
    An unchecked construction is an assumption.
    """
    CMP = np.asarray(CMP, np.int64)
    m = CMP.shape[0]
    acc = np.zeros(m, float)
    rem = np.maximum(CMP, 0).copy()
    covered = np.zeros(m, np.int64)
    have_own = own_p is not None and len(own_y) > 0 and w > 0
    blocks = 0
    overdraw = 0
    rounds = 0
    while True:
        live = rem > 0
        k = int(live.sum())
        if k == 0:
            break
        rounds += 1
        pk = rng.choice(len(pool_y), k, p=pool_p)
        yv = pool_y[pk]
        nv = np.asarray(pool_n, np.int64)[pk]
        if have_own:
            use = rng.random(k) < w
            if use.any():
                ok = rng.choice(len(own_y), k, p=own_p)
                yv = np.where(use, np.asarray(own_y, float)[ok], yv)
                nv = np.where(use, np.asarray(own_n, np.int64)[ok], nv)
        t = np.minimum(nv, rem[live])
        overdraw = max(overdraw, int((t - nv).max()))
        acc[live] += t * yv
        rem[live] -= t
        covered[live] += t
        blocks += k
    return acc, {'blocks_drawn': blocks, 'rounds': rounds,
                 'completions_requested': int(CMP.sum()),
                 'completions_covered': int(covered.sum()),
                 'closes': bool(np.array_equal(covered, np.maximum(CMP, 0))),
                 'max_block_completions_above_donor': overdraw}


def passing_yards_draws(r, po, rng, w, ew, m, CMP, spec=YPC_SPEC_GAME_RATIO):
    """Passing yards for one quarterback-game, as m draws.

    ONE FUNCTION, TWO SPECIFICATIONS, SO THERE IS ONE PLACE TO READ. The
    incumbent branch is the expression `simulate` used inline and consumes the
    RNG identically, so a run that does not ask for a candidate draws exactly
    what it drew before.
    """
    if spec not in YPC_SPECS:
        raise ValueError(f'unknown passing-yard specification {spec!r}; '
                         f'declared: {YPC_SPECS}')
    if spec == YPC_SPEC_GAME_RATIO:
        ypc_d = _mix(rng, r['h_ypc'], po['ypc'], w, m, ew)
        return CMP * ypc_d, None
    if 'h_ypc_n' not in r:
        raise ValueError(
            'QB_YPC_DONOR_COUNTS_ABSENT: the completion-block specification '
            "needs `h_ypc_n`, which `attach` writes beside `h_ypc`. Refusing "
            'to fall back to the game-ratio resample this specification '
            'exists to replace.')
    if len(r['h_ypc_n']) != len(r['h_ypc']):
        raise ValueError(
            f'QB_YPC_DONOR_COUNTS_MISALIGNED: {len(r["h_ypc"])} own ratios '
            f'against {len(r["h_ypc_n"])} completion counts. A ratio paired '
            f'with the wrong denominator is the defect this repairs.')
    pool_p = po.get('ypc_w')
    if pool_p is None or 'ypc_n' not in po:
        raise ValueError(
            'QB_YPC_POOL_NOT_COUNTED: `pools` built no `ypc_n`/`ypc_w`, which '
            'happens when the pool came from an older build. Refusing rather '
            'than silently drawing games uniformly.')
    own_p = _norm_w(r['h_ypc_n'], _ew(len(r['h_ypc_n'])) if ew else None)
    # THE BLOCK DRAWS RUN ON A SPAWNED CHILD STREAM, and the incumbent's own
    # `_mix` is called on the parent and its result DISCARDED. Both halves of
    # that sentence are deliberate and neither is a trick.
    #
    # A child stream, because this construction draws a VARIABLE number of
    # random numbers -- a draw needing more completions draws more donor
    # blocks. Taken from the shared stream, the RNG position of every layer
    # drawn after passing yards would depend on the completion draw, a
    # coupling the incumbent does not have and which would make two runs at
    # different draw counts non-comparable. `Generator.spawn` derives the
    # child from the parent's seed sequence, not from its stream position, so
    # the child is reproducible and independent of what the parent has drawn.
    #
    # The discarded `_mix` is STREAM ALIGNMENT and nothing else. It holds the
    # parent at exactly the position the incumbent leaves it in, so that
    # `ptd`, `int`, `drush`, `rush_opp`, `ryds` and `rtd` come out BYTE-
    # IDENTICAL in both arms and the only quantity that differs between them
    # is the one under treatment. Without it a comparison of the two arms
    # would be reading six re-randomised layers as though they were an effect.
    # Its value is never read; R2 made the opposite choice -- skip the draws
    # and accept a shifted stream -- and said so, and this says so too.
    _stream_alignment_discarded = _mix(rng, r['h_ypc'], po['ypc'], w, m, ew)
    del _stream_alignment_discarded
    PY, ledger = completion_block_yards(
        rng.spawn(1)[0], np.asarray(r['h_ypc'], float),
        np.asarray(r['h_ypc_n'], np.int64),
        po['ypc'], pool_p, po['ypc_n'], w, CMP, own_p=own_p)
    if not ledger['closes'] or ledger['max_block_completions_above_donor'] > 0:
        raise ValueError(
            f'QB_YPC_BLOCK_LEDGER_BROKEN: {ledger}. The closure holds by '
            f'construction, so a failure here is a defect in this function; '
            f'it is checked because an unchecked construction is an '
            f'assumption.')
    return PY, ledger


def share_draws(r, po, rng, w, ew, m, spec=SHARE_SPEC_UNCONDITIONAL):
    """The quarterback's share of his team's dropbacks, as m draws.

    ONE FUNCTION, TWO SPECIFICATIONS, SO THERE IS ONE PLACE TO READ. The
    incumbent branch is the expression `simulate` used inline and consumes the
    RNG identically, so a run that does not ask for a candidate draws exactly
    what it drew before.

    THE DEFECT THE CANDIDATE REPAIRS. Under SHARE_SPEC_UNCONDITIONAL the two
    mixture components answer different questions: `r['h_share']` is dominated
    by this quarterback's games as the primary passer (95.3% of the 26,044
    prior appearances behind the 2025 starting-QB frame), while `po['share']`
    is a league pool in which 20.4% of rows are backup appearances averaging a
    0.1233 share. Shrinking the first toward the second moves a starter's
    predictive distribution toward a population he is not in, which is the
    same missing normalisation `qb_allocation.py` records from the other end
    when the room is summed.

    THE CANDIDATE. Both components are conditioned on the primary-passer role:
    own history is restricted to his prior games in that role, and the pool is
    the stratum whose members carried the same `prior_primary` label he does.
    The label is his role in his own most recent previous appearance, which is
    the only pregame role signal this repository holds for 2025 -- there is no
    2025 weekly depth chart in `nfl/research/inputs/`. It is a lagged fact, so
    nothing about the game being forecast enters.

    NOT A CALIBRATED ROLE MODEL, AND SAID SO HERE. This does not forecast
    WHETHER he starts. It forecasts his share given the role his history
    points at, and the role uncertainty survives only as whatever non-primary
    mass the stratified pool carries. A quarterback whose role changes between
    his last appearance and this game is mispriced by it, and the count of
    such games in the 2025 frame is reported rather than absorbed.
    """
    if spec not in SHARE_SPECS:
        raise ValueError(f'unknown share specification {spec!r}; declared: '
                         f'{SHARE_SPECS}')
    if spec == SHARE_SPEC_UNCONDITIONAL:
        return np.clip(_mix(rng, r['h_share'], po['share'], w, m, ew), 0, 1)
    if 'h_share_primary' not in r or 'prior_primary' not in r:
        raise ValueError(
            'QB_SHARE_ROLE_FIELDS_ABSENT: the starter-conditioned share needs '
            "`h_share_primary` and `prior_primary`, which `attach` writes. "
            'Refusing to fall back to the unconditional pool this '
            'specification exists to replace.')
    strat = po.get('share_by_prior_primary') or {}
    if not strat:
        raise ValueError(
            'QB_SHARE_POOL_NOT_STRATIFIED: `pools` built no '
            '`share_by_prior_primary` strata, which happens when the frame it '
            'was given had not been through `attach`. Refusing rather than '
            'silently drawing the incumbent pool.')
    # A quarterback with no prior game in the role falls back to his whole
    # history rather than to nothing; a stratum with no rows falls back to the
    # unstratified pool. Both are named in the returned evidence by the
    # caller, not swallowed.
    own = r['h_share_primary'] or r['h_share']
    pool = strat.get(r['prior_primary'])
    if pool is None or len(pool) == 0:
        pool = po['share']
    return np.clip(_mix(rng, own, pool, w, m, ew), 0, 1)


def simulate(rs, ev, allrows, oracle=(), seed=SEED, m=M_DRAWS, rung='L1',
             db_external=None, share_spec=SHARE_SPEC_UNCONDITIONAL,
             ypc_spec=YPC_SPEC_GAME_RATIO):
    """Team-aggregate-then-allocate. Returns a dict of (n, m) draw matrices.

    `db_external` is R2: an (n_rows, m) INTEGER dropback level supplied by the
    caller, in which case this layer draws NO level at all and supplies
    conditional rates only. See
    nfl/research/r2/predeclaration_qb_level_ownership_r2.md
    (sha256 3d7beeb39f32da11623ac2be178ca4b764ecf314a5a55515b0d45c0e3d4f323c).

    `share_spec` is P2 repair 3 and defaults to the incumbent. It is INERT
    whenever `db_external` is supplied, because the share is then not drawn at
    all -- see `share_draws`.

    `ypc_spec` is the P8 repair and defaults to the incumbent. It is NOT inert
    under R2: the completion count is drawn here on every path, so the
    passing-yard construction runs whether or not the dropback level arrives
    from outside. The candidate consumes a different number of random numbers
    from the incumbent -- a variable one, because a draw needing more
    completions draws more donor blocks -- so its comparator is
    same-seed-same-slate, not draw-for-draw identity, exactly as R2's is.

    Under R2 the team dropback volume `V` and the quarterback share `S` are
    owned by D1 and QB3 respectively. Drawing them here made this layer a
    SECOND owner of both, and `football_engine` reconciled the duplicate by
    division -- which is what produced composition factors to 59.85 and a
    49.14 passing-touchdown tail off a one-dropback donor draw.

    The V and S draws are SKIPPED, not drawn-and-discarded, so the per-row RNG
    stream differs from the incumbent. That is expected and is stated rather
    than discovered: R2 is a different generator, and its comparator is
    same-seed-same-slate, not draw-for-draw identity.
    """
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
        if ypc_spec not in YPC_SPECS:
            raise ValueError(f'unknown passing-yard specification '
                             f'{ypc_spec!r}; declared: {YPC_SPECS}')
        w = rung_weight(r, rung)
        ew = rung in ('L2', 'L3')

        if db_external is not None:
            # R2: THE LEVEL IS NOT THIS LAYER'S TO DRAW. It arrives already
            # apportioned from D1 x QB3 by largest remainder, so team closure
            # is integer-exact by construction and there is no denominator for
            # the composition to divide by.
            DB = np.maximum(np.asarray(db_external[idx], np.int64), 0)
            if DB.shape[0] != m:
                raise ValueError(
                    f'R2_DB_EXTERNAL_SHAPE: row {idx} got {DB.shape[0]} '
                    f'dropback draws for m={m}')
        else:
            # V: team dropback volume
            V = (np.full(m, r['team_db'], float) if 'V' in oracle
                 else _mix(rng, r['h_team_db_series'], po['team_db'], w, m, ew))
            # S: this QB's share of it
            S = (np.full(m, (r['db'] / r['team_db']) if r['team_db'] > 0
                         else 1.0, float) if 'S' in oracle
                 else share_draws(r, po, rng, w, ew, m, share_spec))
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
            PY, _ = passing_yards_draws(r, po, rng, w, ew, m, CMP, ypc_spec)

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
