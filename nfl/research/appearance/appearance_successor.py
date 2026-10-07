#!/usr/bin/env python3.12
"""Appearance-propagation SUCCESSOR: SC-APPEAR-1 rates + a strict HURDLE gate with FIELD-SPECIFIC pi. SHADOW_ONLY.

This is the core library. It edits no production file, assigns no production attribute, and writes nothing.
Consumers: nfl/prospective/appearance/seal_appearance_w5.py (the week-5 prospective seal),
nfl/research/appearance/appearance_successor_dev.py (2025 DEVELOPMENT scoring),
nfl/research/appearance/grade_appearance_seal.py (postgame grader), nfl/tests/test_appearance_successor.py.

WHAT IS FIXED RELATIVE TO THE SC-APPEAR-1 PROPAGATION PROTOTYPE (sc_appear_1_propagation.py)
  The prototype gate gave P(N = 0) = (1 - pi) + pi x P(M = 0 | open): an open player could still draw zero from the
  Dirichlet-multinomial, so the zero mass overshot 1 - pi. Here the positive part is ZERO-TRUNCATED:

  1. GATE (per club-world, separate random stream _grng = Random(seed + GATE_SEED_OFFSET)). One uniform u per gated
     player; field f is OPEN iff u < pi_f. One uniform for all of a player's fields, so an RB's carry and target gates
     are comonotone (declared: P(both closed) = 1 - max(pi_carries, pi_targets)).
  2. CLOSED  -> weight 0 in that field's allocation and 0 in the matching TD share: exactly 0 in every world.
  3. OPEN    -> the field's Dirichlet-multinomial draw (the production alloc() closure, production concentration) is
     CONDITIONED on every open gated player receiving >= 1: the draw is repeated (rejection) until it does, at most
     HURDLE_MAX_REDRAWS times, then the RESERVATION fallback (1 unit reserved per open gated player, the remainder
     drawn by the same alloc()) is used and counted. Either way an open player gets >= 1. Hence
         P(N_f = 0) = 1 - pi_f   EXACTLY, per field, for every gated player,
     except in a world whose club total is smaller than the number of open gated players (HURDLE_INFEASIBLE, counted;
     then the units go one each to a uniformly chosen subset of them).
  4. MEAN OF THE POSITIVE PART (POSITIVE_PART below). The projection stays the expected-value centre (owner ruling
     2026-10-02): an open player's conditional target mean is his production unconditional share / pi, renormalised
     over the open set exactly as the prototype did; the Dirichlet-multinomial weight that delivers that mean AFTER
     truncation is solved from the beta-binomial marginal (explicit derivation, no fitted constant); a target mean
     <= 1 (the floor of a zero-truncated count) is met by reserving exactly one unit (MEAN_FLOOR_BINDING, counted).
     The choice between the candidate positive-part constructions was made on a NON-OUTCOME structural criterion
     (mean drift against the production unconditional means on the frozen ATL@NO projection), recorded in
     POSITIVE_PART_SELECTION and in the pre-registration, before any new score.
  5. CLUB TOTALS: every allocation is a multinomial over the drawn club total, so player counts + the unallocated
     (ghost) bucket equal the club total in every world. The ghost WEIGHT is kept at the production value (pool
     weights are renormalised to the production pool sum), so the ghost is never used to absorb the gate.

  FIELDS GATED (field-specific pi exists only for these): RB carries, RB targets, WR targets, TE targets.
  NOT gated (production allocation, untouched): QB pass attempts and carries, WR/TE carries. No pi exists for them.

FIELD-SPECIFIC pi. pi(pos, field, h) = P(>= 1 opportunity in `field` | dressed, pos, h), where h = the number of the
club's previous 3 games PRESENT IN THE PANEL in which the player recorded >= 1 of `field`. Fitted on 2024 only, on
exactly the player-game rows sc_appear_1_forward.rows_for builds (dressed = snap-count present, pregame-ranked). The
h = 3 cell IS the SC-APPEAR-1 rate (identical rows; checked by FIT_H3_EQUALS_SC_APPEAR_1). h = 0, 1, 2 extend the same
estimator to the non-qualifiers, for whom production's only rate (the depth any-stat appearance rate) is not
field-specific.

THE CANDIDATE ALLOCATION (the means) is SC-APPEAR-1's: the production allocator with the SC-APPEAR-1 rate hooked at
proj_v1 line 879 for qualifiers (sc_appear_1_production_path.allocate_with_hook). The gate (the zero mass) uses pi.

ELIGIBILITY IS SEPARATE. A player whose eligibility is in availability.ABSENT_STATUSES (or 'INACTIVE') is removed
before shares are built, exactly as production removes NOT_PLAYING rows: no share, no draws, no gate.
UNKNOWN_ACTIVE_STATE (DECLARED): treated as eligible -- he stays in the pool and is gated with pi, which is a
probability CONDITIONAL ON BEING ACTIVE. His forecast is therefore conditional on activity, and a grader scores him
only if he is found dressed; an undressed sealed player is excluded from scoring and counted, never scored as zero.

IDENTITY (both tested):
  * successor DISABLED (no 'hurdle' key on any player) -> the gated module returns production's own objects and
    consumes no extra main-stream randomness: draws, stat lines and club worlds are BYTE-IDENTICAL to production.
  * every pi = 1 -> NOT byte-identical, by design: a gated field with pi = 1 is a zero-truncated draw (P(0) = 0
    exactly), while production's Dirichlet-multinomial can draw 0. Byte identity at pi = 1 is NOT claimed.
"""
from __future__ import annotations

import collections
import copy
import functools
import hashlib
import importlib.util
import json
import math
import pathlib
import random
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import game as SIM  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import classic_slate_run as CR  # noqa: E402
from nfl.tools import showdown_draws as SD  # noqa: E402
from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from nfl.tools import proj_v1 as V  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

_HERE = pathlib.Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P2 = _load('sc_appear_1_production_path', _HERE / 'sc_appear_1_production_path.py')
F1 = P2.F1
SIM_FILE = _REPO / 'nfl/sim/game.py'
PRODUCTION_FILES = ('nfl/sim/game.py', 'nfl/tools/showdown_draws.py', 'nfl/tools/proj_v1.py',
                    'nfl/tools/classic_slate_run.py', 'nfl/tools/showdown_slate_run.py',
                    'nfl/tools/showdown_slate_state.py', 'nfl/tools/role_state.py', 'nfl/tools/availability.py',
                    'nfl/tools/forward_chain.py', 'nfl/sim/football_points.py')

FIT_SEASON = 2024
N_PRIOR = 3
#: (position, field) cells that carry a field-specific pi. Exactly SC-APPEAR-1's cells.
GATED_CELLS = (('RB', 'carries'), ('RB', 'targets'), ('WR', 'targets'), ('TE', 'targets'))
HISTORY_CLASSES = (0, 1, 2, 3)
#: Refuse a fitted cell with fewer rows. DERIVATION, not a tuning: the binomial SE of a rate is <= 0.5/sqrt(n), so
#: n >= 100 bounds it at 0.05; the 2024 cells hold 170-1038 rows, so this never binds on the declared fit.
MIN_CELL_N = 100
#: Separate gate stream; NOT a coefficient (any integer gives an independent stream). Same value as the prototype.
GATE_SEED_OFFSET = 7919
#: Compute bound on the rejection step, NOT a model constant: past it the reservation fallback (also >= 1 per open
#: player, so P(0) = 1 - pi still holds exactly) is used and counted.
HURDLE_MAX_REDRAWS = 200
#: Gated field -> (simulator share key of the count, simulator share key of the matching TD share).
GATE_KEYS = {'targets': ('target_share', 'pass_td_share'), 'carries': ('carry_share', 'rush_td_share')}
SIM_IX = {f: i for i, f in enumerate(SIM.STAT_FIELDS)}
FIELD_TO_STAT = {'targets': 'targets', 'carries': 'carries', 'pass_attempts': 'pass_att'}

POSITIVE_PART_OPTIONS = ('PROTOTYPE_WEIGHTS', 'TRUNCATION_MATCHED_RENORMALISED')
#: Set from the structural selection recorded in POSITIVE_PART_SELECTION (see select_positive_part()).
POSITIVE_PART = 'TRUNCATION_MATCHED_RENORMALISED'


class SuccessorError(RuntimeError):
    """Named refusal. `code` is the machine-readable reason."""

    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


def sha_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def production_hashes():
    return {f: sha_file(_REPO / f) for f in PRODUCTION_FILES}


# ===================================================================================== field-specific pi (<= 2024)
def history_class(panel, season, club, week, gsis, field, team_weeks):
    """h = games among the club's last N_PRIOR games PRESENT IN THE PANEL (weeks < week) with >= 1 of `field`.

    Returns (h, prev_weeks). h is None when the club has fewer than N_PRIOR games in the panel before `week`.
    A week absent from the panel (e.g. 2026 week 4, MISSING_FROM_REPO) is simply not a present game: it is never read
    as zero opportunity, and the window is the last N_PRIOR games that ARE present (declared in the prereg)."""
    prev = sorted(w for w in team_weeks.get(club, ()) if w < week)[-N_PRIOR:]
    if len(prev) < N_PRIOR:
        return None, prev
    ss = (panel['players'].get(gsis) or {}).get(str(season)) or {}
    return sum(1 for w in prev if ((ss.get(str(w)) or {}).get(field) or 0) > 0), prev


def club_team_weeks(panel, season):
    """sc_appear_1_forward's definition of a club game week: any player row carrying the club in that week."""
    tw = collections.defaultdict(set)
    for g, ss in panel['players'].items():
        for w, d in (ss.get(str(season)) or {}).items():
            if d.get('team'):
                tw[d['team']].add(int(w))
    return tw


def dressed_rows(panel, pos_of, season, dressed):
    """sc_appear_1_forward.rows_for WITHOUT its pregame-rank filter: every dressed RB/WR/TE player-game of `season`,
    weeks >= 4, club with >= 3 earlier games, one row per gated field, with h. The rank filter cannot be kept for
    h < 3: pregame_depth ranks only players with usage in the table field, so rows_for has no h = 0 carries/targets
    row at all, while the pools the gate is applied to contain such players."""
    P = panel['players']
    tw = club_team_weeks(panel, season)
    out = []
    for (team, wk), ids in dressed.items():
        if wk < 4:
            continue
        for g in ids:
            pos = pos_of.get(g)
            ss = (P.get(g) or {}).get(str(season)) or {}
            now = ss.get(str(wk)) or {}
            for p_, f in GATED_CELLS:
                if p_ != pos:
                    continue
                h, prev = history_class(panel, season, team, wk, g, f, tw)
                if h is None:
                    continue
                out.append({'season': season, 'week': wk, 'team': team, 'gsis': g, 'pos': pos, 'field': f, 'h': h,
                            'y': int((now.get(f) or 0) > 0)})
    return out


def fit_field_rates(panel, pos_of, dressed_fit, through=FIT_SEASON):
    """pi(pos, field, h), season `through` (<= 2024 only).

    h = 3: the SC-APPEAR-1 rate itself, on sc_appear_1_forward.rows_for's rows (prior3_all). h = 0, 1, 2: the same
    estimator on dressed_rows (no rank filter; see there). Both are 2024 snap-count-dressed player-games."""
    if through >= 2025:
        raise SuccessorError('FIT_SEASON_NOT_HELD_OUT', f'through={through}')
    if not panel or not panel.get('players'):
        raise SuccessorError('EMPTY_PANEL')
    if not dressed_fit:
        raise SuccessorError('EMPTY_DRESSED_FIT')
    try:
        tr = F1.rows_for(panel, pos_of, through, dressed_fit)
    except F1.AppearError as e:
        raise SuccessorError('NO_FIT_ROWS', str(e)) from e
    if not len(tr) or int(tr.season.max()) > through:
        raise SuccessorError('FIT_ROWS_AFTER_CUTOFF' if len(tr) else 'NO_FIT_ROWS')
    dr = dressed_rows(panel, pos_of, through, dressed_fit)
    if not dr or max(r['season'] for r in dr) > through:
        raise SuccessorError('NO_FIT_ROWS' if not dr else 'FIT_ROWS_AFTER_CUTOFF')
    rates, n = {}, {}
    for pos, f in GATED_CELLS:
        d = tr[(tr.pos == pos) & (tr.field == f) & tr.prior3_all]
        if len(d) < MIN_CELL_N:
            raise SuccessorError('FIT_CELL_TOO_SMALL', f'{pos} {f} h=3: n={len(d)} < {MIN_CELL_N}')
        rates[(pos, f, N_PRIOR)] = float(d.y.mean())
        n[(pos, f, N_PRIOR)] = int(len(d))
        for h in HISTORY_CLASSES[:-1]:
            ys = [r['y'] for r in dr if r['pos'] == pos and r['field'] == f and r['h'] == h]
            if len(ys) < MIN_CELL_N:
                raise SuccessorError('FIT_CELL_TOO_SMALL', f'{pos} {f} h={h}: n={len(ys)} < {MIN_CELL_N}')
            rates[(pos, f, h)] = float(sum(ys)) / len(ys)
            n[(pos, f, h)] = len(ys)
    return {'rates': rates, 'n': n, 'through': through, 'n_rows_h3': int(tr.prior3_all.sum()), 'n_rows_h012': len(dr),
            'SOURCE': {'h3': 'sc_appear_1_forward.rows_for prior3_all (the SC-APPEAR-1 rate)',
                       'h0_h1_h2': 'dressed_rows (rows_for without the pregame-rank filter)'}}


def rates_json(fr):
    return {f'{p}|{f}|h{h}': {'pi': round(v, 6), 'n': fr['n'][(p, f, h)]} for (p, f, h), v in sorted(fr['rates'].items())}


def pi_for(fr, pos, field, h):
    """Field-specific pi for one player-field, or None when the cell is not gated (production allocation)."""
    if (pos, field) not in GATED_CELLS:
        return None
    if h is None:
        raise SuccessorError('HISTORY_UNDEFINED', f'{pos} {field}: club has < {N_PRIOR} games in the panel')
    return fr['rates'][(pos, field, int(h))]


# ===================================================================================== the hurdle (in memory only)
COUNTS: collections.Counter = collections.Counter()
#: When a list, every gated allocation appends (field, total, player_sum, ghost, n_open_required). Tests only.
ALLOC_LOG = None


def _p0_betabinom(w, T, conc):
    """P(M = 0) for the production Dirichlet-multinomial marginal: M ~ BetaBinomial(T, conc*w, conc*(1-w))."""
    if w <= 0:
        return 1.0
    if w >= 1:
        return 0.0
    a, b = conc * w, conc * (1.0 - w)
    return math.exp(math.lgamma(conc) + math.lgamma(b + T) - math.lgamma(b) - math.lgamma(conc + T))


@functools.lru_cache(maxsize=200_000)
def truncated_weight(m, T, conc):
    """The weight w whose zero-truncated beta-binomial mean w*T / (1 - P0(w)) equals m (1 < m < T). Bisection.

    E[M | M > 0] rises monotonically from 1 (w -> 0) to T (w -> 1), so the root is unique."""
    if T <= 0:
        return 0.0
    if m >= T:
        return 1.0
    lo, hi = 1e-12, 1.0 - 1e-12
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        p0 = _p0_betabinom(mid, T, conc)
        val = mid * T / (1.0 - p0) if p0 < 1.0 else 1.0
        if val < m:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _pi(p, field):
    g = p.get('hurdle') or {}
    v = g.get(field)
    if v is None:
        return None
    v = float(v)
    if math.isnan(v) or not (0.0 <= v <= 1.0):
        raise SuccessorError('GATE_PROBABILITY_OUT_OF_RANGE', f'{p.get("id")} {field}: {v}')
    return v


def hurdle_open(players, grng):
    """Draw the per-world gate. Returns (players, None) untouched when nothing is gated (production identity)."""
    if not any(p.get('hurdle') for p in players):
        return players, None
    out = [dict(p) for p in players]
    hz = {}
    u = {i: grng.random() for i, p in enumerate(players) if p.get('hurdle')}
    for field, (share_key, td_key) in GATE_KEYS.items():
        g = {}
        for i, p in enumerate(players):
            pi = _pi(p, field) if i in u else None
            if pi is None:
                continue
            g[i] = (u[i] < pi, pi, max(0.0, float(p.get(share_key, 0.0) or 0.0)))
        if not g:
            continue
        hz[field] = g
        COUNTS[f'{field}_gated_player_worlds'] += len(g)
        COUNTS[f'{field}_closed_player_worlds'] += sum(1 for v in g.values() if not v[0])
        # TD shares follow the field's gate: closed -> 0; open -> share / pi; renormalised to the production sum.
        base = [max(0.0, float(p.get(td_key, 0.0) or 0.0)) for p in players]
        tot = sum(base)
        cond = []
        for i in range(len(players)):
            if i in g:
                op, pi, _b = g[i]
                cond.append(base[i] / pi if (op and pi > 0) else 0.0)
            else:
                cond.append(base[i])
        ctot = sum(cond)
        for i in range(len(players)):
            out[i][td_key] = (tot * cond[i] / ctot) if ctot > 0 else 0.0
    return out, (hz or None)


def _positive_weights(g, idx, weights, T, conc, mode):
    """Per-world weights for one gated field. Returns (w, required_positions, reserve_positions)."""
    S = sum(weights)
    proto = list(weights)
    open_pos = []
    for k, i in enumerate(idx):
        if i in g:
            op, pi, b = g[i]
            if op and pi > 0:
                proto[k] = b / pi
                open_pos.append(k)
            else:
                proto[k] = 0.0
    ptot = sum(proto)
    if ptot <= 0:
        return [0.0] * len(weights), [], []
    r = S / ptot
    w = [x * r for x in proto]
    reserve, required = [], []
    for k in open_pos:
        m = w[k] * T                      # the open player's target conditional mean
        if m <= 1.0:
            reserve.append(k)             # a zero-truncated count cannot have mean below 1: exactly one unit
            w[k] = 0.0
            COUNTS['MEAN_FLOOR_BINDING'] += 1
            continue
        required.append(k)
        if mode == 'TRUNCATION_MATCHED_RENORMALISED':
            w[k] = truncated_weight(round(m, 9), int(T), round(float(conc), 9))
    if mode == 'TRUNCATION_MATCHED_RENORMALISED':
        tot = sum(w)
        if tot > 0:
            w = [x * S / tot for x in w]  # ghost weight held at the production value
    elif mode != 'PROTOTYPE_WEIGHTS':
        raise SuccessorError('UNKNOWN_POSITIVE_PART', mode)
    return w, required, reserve


def make_hurdle_alloc(mode=None):
    def hurdle_alloc(hz, field, ix, alloc_fn, rng, total, weights, conc=None, shock=None, slots=None):
        g = (hz or {}).get(field)
        if not g:
            return alloc_fn(total, weights, conc, shock, slots)
        if shock is not None or not conc:
            raise SuccessorError('HURDLE_REQUIRES_DIRICHLET', 'the hurdle is defined on the Dirichlet-multinomial only')
        idx = list(ix) if ix is not None else list(range(len(weights)))
        w, req, res = _positive_weights(g, idx, weights, total, conc, mode or POSITIVE_PART)
        need = len(req) + len(res)
        if total < need:
            COUNTS['HURDLE_INFEASIBLE'] += 1
            pick = set(rng.sample(req + res, total)) if total > 0 else set()
            got = [1 if k in pick else 0 for k in range(len(weights))]
            ghost = 0
        else:
            rem = total - len(res)
            got = ghost = None
            for attempt in range(HURDLE_MAX_REDRAWS):
                gg, gh = alloc_fn(rem, w, conc, shock, slots)
                if all(gg[k] >= 1 for k in req):
                    got, ghost = list(gg), gh
                    COUNTS['REDRAWS'] += attempt
                    break
            if got is None:
                COUNTS['RESERVATION_FALLBACK'] += 1
                gg, gh = alloc_fn(rem - len(req), w, conc, shock, slots)
                got, ghost = list(gg), gh
                for k in req:
                    got[k] += 1
            for k in res:
                got[k] += 1
        COUNTS[f'{field}_gated_allocations'] += 1
        if ALLOC_LOG is not None:
            ALLOC_LOG.append((field, int(total), int(sum(got)), int(ghost), need))
        return got, ghost
    return hurdle_alloc


SUBSTITUTIONS = (
    ("    rng = random.Random(seed)\n",
     "    rng = random.Random(seed)\n    _grng = random.Random(seed + GATE_SEED_OFFSET)\n"),
    ("            ps = c['players']\n",
     "            ps, _hz = hurdle_open(c['players'], _grng)\n"),
    ("            tgt_r, tgt_ghost = alloc(tg_total, ",
     "            tgt_r, tgt_ghost = hurdle_alloc(_hz, 'targets', rec_ix, alloc, rng, tg_total, "),
    ("            car_all, car_ghost = alloc(ra, ",
     "            car_all, car_ghost = hurdle_alloc(_hz, 'carries', None, alloc, rng, ra, "),
)


def hurdle_simulator(src=None, mode=None):
    """The production nfl/sim/game.py source with exactly the four SUBSTITUTIONS, compiled as a separate module."""
    src = src if src is not None else SIM_FILE.read_text()
    new = src
    for old, rep in SUBSTITUTIONS:
        if new.count(old) != 1:
            raise SuccessorError('HURDLE_ANCHOR_NOT_FOUND', f'{old.strip()!r} occurs {new.count(old)} times')
        new = new.replace(old, rep)
    mod = types.ModuleType('nfl_sim_game_hurdle_research')
    mod.__file__ = str(SIM_FILE)
    mod.__dict__.update({'hurdle_open': hurdle_open, 'hurdle_alloc': make_hurdle_alloc(mode),
                         'GATE_SEED_OFFSET': GATE_SEED_OFFSET})
    exec(compile(new, f'<hurdle:{SIM_FILE.relative_to(_REPO)}>', 'exec'), mod.__dict__)
    mod.SOURCE_SHA256 = hashlib.sha256(src.encode()).hexdigest()
    mod.N_LINES_ADDED = len(new.splitlines()) - len(src.splitlines())
    mod.N_SUBSTITUTIONS = len(SUBSTITUTIONS)
    return mod


_HURDLE = {}


def hurdle(mode=None):
    m = mode or POSITIVE_PART
    if m not in _HURDLE:
        _HURDLE[m] = hurdle_simulator(mode=m)
    return _HURDLE[m]


def with_hurdle(spec, gates):
    """Copy of a simulator spec with p['hurdle'] = gates[p['id']] ({field: pi}) for gated players."""
    out = copy.deepcopy(spec)
    for c in out['clubs']:
        for p in c['players']:
            g = gates.get(p['id'])
            if g:
                gg = {f: float(v) for f, v in g.items() if f in GATE_KEYS and isinstance(v, (int, float))}
                if gg:
                    p['hurdle'] = gg
    return out


# ============================================================================ the end-to-end production path
def remove_ineligible(rows):
    """Eligibility is separate from the gate: absent rows lose dk_points, so showdown_draws._shares never admits them."""
    out = []
    for r in rows:
        r = dict(r)
        el = r.get('eligibility')
        if el is not None and (el == 'INACTIVE' or el in AV.ABSENT_STATUSES):
            r['dk_points'] = None
            r['projection_state'] = 'NOT_PLAYING'
        out.append(r)
    return out


def build_spec(rows, home, away, centre_fc, dst=False):
    """showdown_draws.build's FOOTBALL_ONLY spec (its lines 224-250) from projection rows, without writing a file."""
    if not rows:
        raise SuccessorError('EMPTY_ROWS')
    rows = remove_ineligible(rows)
    spec = {'total_line': centre_fc['total'], 'home_spread': centre_fc['home_margin'], 'clubs': []}
    for club in (home, away):
        players = SD._shares(rows, club)
        if not players:
            raise SuccessorError('EMPTY_CLUB_POOL', club)
        if not any(p['position'] == 'QB' for p in players):
            raise SuccessorError('SHOWDOWN_CLUB_HAS_NO_QUARTERBACK', club)
        spec['clubs'].append({'club': club, 'players': players, 'dst_id': (f'DST|{club}' if dst else None)})
    return spec


def end_to_end(model, spec, centre, rows_by_key, int_rate, n_sims, seed, gates=None, dst_targets=None, mode=None):
    """showdown_draws spec -> simulate_game_centred (production, or the hurdle module when `gates`) ->
    classic_slate_run.efficiency_worlds -> showdown_slate_run's DST anchor step -> DK points.

    Returns {'sim': simulator value, 'stages': {...}, 'counts': hurdle counters}. Raises on a refused simulation."""
    if not spec.get('clubs') or any(not c.get('players') for c in spec['clubs']):
        raise SuccessorError('EMPTY_GAME')
    sp = with_hurdle(spec, gates) if gates else spec
    mod = hurdle(mode) if gates else SIM
    COUNTS.clear()
    o = mod.simulate_game_centred(model, sp, centre, n_sims=n_sims, seed=seed, n_calib=n_sims)
    if o.state is not State.PASS:
        raise SuccessorError('SIMULATION_REFUSED', o.code)
    v = o.value
    counts = dict(COUNTS)
    # showdown_slate_run lines 85-93, in order
    dk_skill, stat_worlds, eff = CR.efficiency_worlds(v['stat_draws'], rows_by_key, float(int_rate), seed + 99)
    draws = {k: list(x) for k, x in v['draws'].items()}
    skill = set(dk_skill)
    draws.update(dk_skill)
    dst = {k: x for k, x in draws.items() if k not in skill}
    dst_acc = None
    if dst:
        dst, dst_acc = CR.anchor_means(dst, dst_targets or {})
        draws.update(dst)
    if {len(x) for x in draws.values()} != {n_sims}:
        raise SuccessorError('RAGGED_DRAWS')
    return {'sim': v, 'stat_draws': v['stat_draws'], 'stat_worlds_after_efficiency': stat_worlds,
            'dk_after_efficiency': dk_skill, 'draws_final': draws, 'efficiency': eff, 'dst_anchor': dst_acc,
            'counts': counts, 'spec': sp}


def field_counts(stat_rows, field):
    return [w[SIM_IX[FIELD_TO_STAT[field]]] for w in stat_rows]


# ===================================================================================== harness (pregame only)
def pregame_panel(panel, season, week):
    """The panel as it stood before (season, week): later seasons and season rows with week >= `week` are dropped."""
    out = {k: v for k, v in panel.items() if k not in ('players', 'teams')}
    pl = {}
    for g, ss in panel['players'].items():
        keep = {}
        for s, wk in ss.items():
            if int(s) > season:
                continue
            keep[s] = {w: d for w, d in wk.items() if int(s) < season or int(w) < week}
        pl[g] = keep
    tm = {}
    for c, ss in panel['teams'].items():
        tm[c] = {s: ({w: d for w, d in wk.items() if int(s) < season or int(w) < week})
                 for s, wk in ss.items() if int(s) <= season}
    out['players'], out['teams'] = pl, tm
    return out


def harness_rows(rows):
    """Projection rows in the shape showdown_draws._shares reads (sc_appear_1_propagation._sim_rows, plus eligibility).
    dk_points is a MEMBERSHIP flag (0.0, never scored); TD expectations are the rows' own opportunity volumes."""
    out = []
    for r in rows:
        x = V.finalize(dict(r))
        out.append({'name': r['_dk'], 'team': r['team'], 'position': r['position'], 'dk_points': 0.0,
                    'eligibility': r.get('eligibility', AV.UNKNOWN_ACTIVE_STATE),
                    'targets': x.get('targets') or 0.0, 'carries': x.get('carries') or 0.0,
                    'pass_attempts': x.get('pass_attempts') or 0.0, 'receptions': x.get('receptions') or 0.0,
                    'td': {'rec_td': x.get('targets') or 0.0, 'rush_td': x.get('carries') or 0.0},
                    'conditional_volume': r.get('conditional_volume') or {}})
    return out


def club_arms(ctx, depth, groups, sc_rates, club, week, starter, pool, team_weeks, qual_requires_dressed):
    """CURRENT (production allocator) and CANDIDATE (SC-APPEAR-1 hook) rows for one club-week, with h per field."""
    tv, crows = P2.club_rows(ctx, club, week, pool, starter, depth)
    if not crows or any((tv or {}).get(k) is None for k in ('proj_pass_attempts', 'proj_rush_attempts', 'proj_targets')):
        return None
    dressed_now = ctx.get('dressed', {}).get((club, week), set())
    hist, qual = {}, {}
    for r in crows:
        for f, _ in P2.ALLOC:
            h, _prev = history_class(ctx['panel'], ctx['season'], club, week, r['_dk'], f, team_weeks)
            hist[(r['_dk'], f)] = h
            ok = (r['position'], f) in sc_rates and h == N_PRIOR
            if qual_requires_dressed:
                ok = ok and r['_dk'] in dressed_now
            qual[(r['_dk'], f)] = bool(ok)
    cur = copy.deepcopy(crows)
    V.allocate_opportunity(cur, tv, depth, groups)
    cand = copy.deepcopy(crows)
    P2.allocate_with_hook(cand, tv, depth, groups, rate_fn=P2.candidate_rate_fn(sc_rates, qual))
    for r in cur + cand:
        r['team'] = club
    return {'tv': tv, 'cur': cur, 'cand': cand, 'qual': qual, 'hist': hist}


def gates_for(rows, hist, fr, club):
    """{player key: {field: pi}} for the gated cells; non-gated fields carry no key (production allocation)."""
    out = {}
    for r in rows:
        g = {}
        for pos, f in GATED_CELLS:
            if r['position'] == pos:
                g[f] = pi_for(fr, pos, f, hist[(r['_dk'], f)])
        if g:
            out[S.player_key(r['_dk'], club)] = g
    return out


def centre_from_tv(arms):
    return {c: {'pass_attempts': float(a['tv']['proj_pass_attempts']),
                'rush_attempts': float(a['tv']['proj_rush_attempts']),
                'targets': min(float(a['tv']['proj_targets']), float(a['tv']['proj_pass_attempts']))}
            for c, a in arms.items()}


def load_model(football_only=True):
    from nfl.sim import football_points as FP
    mo = SIM.Model.load()
    if mo.state is not State.PASS:
        raise SuccessorError('SIM_MODEL_NOT_LOADED', mo.code)
    m = mo.value
    if football_only:   # showdown_draws.build lines 225-236: the FOOTBALL_ONLY arm swaps the residual sets
        fp = FP.load()
        if not fp:
            raise SuccessorError('FOOTBALL_POINTS_ABSENT')
        m.total_res = fp['empirical_residuals']['total']
        m.margin_res = fp['empirical_residuals']['margin']
    return m


def histogram(xs):
    c = collections.Counter(int(round(x)) for x in xs)
    return {str(k): int(v) for k, v in sorted(c.items())}


def crps_hist(hist, y):
    """CRPS of an integer-support predictive distribution given as {count: n}, at outcome y."""
    if not hist:
        return float('nan')
    ks = sorted(int(k) for k in hist)
    n = float(sum(hist.values()))
    out, cum = 0.0, 0.0
    for k in range(min(ks[0], int(y)), max(ks[-1], int(y)) + 1):
        cum += hist.get(str(k), 0) / n
        out += (cum - (1.0 if y <= k else 0.0)) ** 2
    return out


def conditional_hist(hist):
    return {k: v for k, v in hist.items() if int(k) > 0}
