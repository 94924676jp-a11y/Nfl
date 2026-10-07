#!/usr/bin/env python3.12
"""Does the projection's zero mass (1 - p_plays) reach the simulated worlds? Trace, measure, prototype. SHADOW_ONLY.

    python3.12 nfl/research/appearance/sc_appear_1_propagation.py            # full run (held-out replay ~20 min)
    python3.12 nfl/research/appearance/sc_appear_1_propagation.py --quick    # trace + ATL@NO + 2 weeks of replay

QUESTION. SC-APPEAR-1 was scored at the PROJECTION layer: proj_v1.allocate_opportunity emits p_plays[field] (line
942) and an unconditional expected volume r[field] = club total x normalised(claim x p_plays) (lines 912-943). The
DFS and prop products consume SIMULATED WORLDS, not that layer. If no stage between the projection and the worlds
reads p_plays, the projection's zero mass never becomes a world in which the player has zero opportunity; appearance
only scales his mean share, every world still hands him a Dirichlet-multinomial slice, and SC-APPEAR-1's gain stops at
the projection.

WHAT THIS MODULE DOES (read-only to production; it writes only into nfl/research/appearance/):
  1. TRACE  the five states (eligibility, offensive appearance, special-teams-only appearance, positive opportunity,
            positive count) from slate state to final draws, with every file:line located by an anchor regex at run
            time (TRACE_ANCHOR_MISSING if production moved), plus the exact p_plays grep over the draw path.
  2. ATL@NO the frozen v2 production worlds (RW_INACTIVES_CHARTFIX): p_plays per field against the share of worlds
            with 0 targets / 0 carries / 0 pass attempts / 0 DK points, by role. The run also REPRODUCES the frozen
            per-world opportunity counts from the frozen projection through the production simulator (a check that
            the spec below is the production spec), then re-draws the same game through the gated prototype.
  3. REPLAY held-out 2025 (sc_appear_1_production_path machinery: fit <= 2024, dressed universe, production
            allocator with the candidate hooked at line 879). Each game is pushed through the production
            simulate_game_centred (volume_centre = PROJECTION, CLUB_TOTAL_IMPOSED, DIRICHLET -- the live Showdown
            configuration) for CURRENT and CANDIDATE, and through the gated prototype for both. Scored: the
            draw-implied P(0 opportunities), Brier and log score, week-blocked; and positive-count calibration
            conditional on > 0.
  4. GATE   the minimal propagation, RESEARCH ONLY. The production simulator source is read from disk and exactly two
            lines are substituted at run time (no file is edited, no production attribute is assigned):
                rng = random.Random(seed)   ->  + a SEPARATE gate stream  _grng = random.Random(seed + GATE_SEED_OFFSET)
                ps = c['players']           ->  ps = gate_players(c['players'], _grng)
            gate_players draws one uniform per player per club-world and opens field f when u < pi_f (pi_f = the
            arm's p_plays[f]; one uniform for all of a player's fields, so the gates are comonotone). Closed players
            get weight 0; open players get their CONDITIONAL weight u_i / pi_i (the unique scaling whose expectation
            before renormalising is the production unconditional share u_i); the open weights are renormalised to
            the production sum, so the club total, the unallocated ghost fraction and every simulator identity are
            unchanged. TD shares follow the same gate (receiving TD with targets, rushing TD with carries). With no
            gate keys, or every pi = 1, the main random stream is untouched and the draws are byte-identical to
            production. P(N = 0) = (1 - pi) + pi x P(M = 0 | open), where M is the existing Dirichlet-multinomial
            allocation among the open players; the second term is measured, not assumed away.
            pi here is P(positive opportunity) as the projection states it, NOT P(active): eligibility stays where
            production puts it (absent players are never in the pool; see the trace).
  5. ACTIVE ZERO-SNAP players: official 2024-2025 active lists are not in the repository; that cohort is reported
            NOT_IDENTIFIABLE_FROM_CURRENT_DATA and realised snaps are never substituted for eligibility.

THE PRIMARY COMPARISON IS DECLARED IN THE JSON BEFORE ANY SCORE IS COMPUTED (DECLARATION block, declared_at, sha).
"""
from __future__ import annotations

import argparse
import collections
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import pathlib
import random
import re
import sys
import time
import types

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import game as SIM  # noqa: E402
from nfl.sim import football_points as FP  # noqa: E402
from nfl.tools import classic_slate_run as CR  # noqa: E402
from nfl.tools import showdown_draws as SD  # noqa: E402
from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from nfl.tools import proj_v1 as V  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

_P2_PATH = pathlib.Path(__file__).resolve().parent / 'sc_appear_1_production_path.py'
_spec = importlib.util.spec_from_file_location('sc_appear_1_production_path', _P2_PATH)
P2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P2)
F1 = P2.F1

OUT = _REPO / 'nfl/research/appearance/SC_APPEAR_1_PROPAGATION.json'
SIM_FILE = _REPO / 'nfl/sim/game.py'
ATL_DIR = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
ATL_TAG = 'ATL_NO_2026W4'
ATL_SEED = 20261005           # nfl/tools/showdown_slate_run.SEED, the seed the frozen worlds were drawn with
ATL_N_SIMS = 2000             # the frozen run's n_sims (and n_calib, as showdown_slate_run passes)
PRODUCTION_FILES = ('nfl/sim/game.py', 'nfl/tools/showdown_draws.py', 'nfl/tools/proj_v1.py',
                    'nfl/tools/classic_slate_run.py', 'nfl/tools/showdown_slate_run.py',
                    'nfl/tools/showdown_slate_state.py', 'nfl/tools/role_state.py', 'nfl/tools/availability.py')

#: Separates the gate's random stream from the simulator's. NOT a coefficient: any integer gives a valid, independent
#: stream; it is fixed only so the gated draws are reproducible. The main stream is never read by the gate.
GATE_SEED_OFFSET = 7919
#: Held-out replay draws per game per arm, and the centring calibration size (production passes n_calib = n_sims).
#: Monte Carlo SE of a per-unit P(0) is <= 0.5/sqrt(1000) = 0.016; it inflates every arm's Brier by the same order
#: (<= p(1-p)/n <= 0.00025) and the paired differences use common random numbers on the main stream.
REPLAY_N_SIMS = 1000
REPLAY_SEED = 20261007
#: Probability floor for log scores of a draw-implied P(0): half a draw out of n (continuity correction). Derived from
#: the draw count, applied to every arm and to the projection layer alike so the arms are scored on one scale.
P_FLOOR = 0.5 / REPLAY_N_SIMS
SIM_IX = {f: i for i, f in enumerate(SIM.STAT_FIELDS)}
FIELD_TO_STAT = {'targets': 'targets', 'carries': 'carries', 'pass_attempts': 'pass_att'}
GATE_FIELDS = (('targets', ('target_share', 'pass_td_share')),
               ('carries', ('carry_share', 'rush_td_share')),
               ('pass_attempts', ('pass_att_share',)))
ARMS = ('CURRENT', 'CANDIDATE', 'CURRENT_GATED', 'CANDIDATE_GATED')


class PropagationError(RuntimeError):
    """Named refusal. `code` is the machine-readable reason."""

    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def production_hashes():
    return {f: _sha(_REPO / f) for f in PRODUCTION_FILES}


# ============================================================================================== 1. the trace
#: (state, stage, file, anchor regex, what the line does). Line numbers are located at run time.
TRACE_ANCHORS = [
    ('ELIGIBILITY', 'slate state', 'nfl/tools/showdown_slate_state.py',
     r"status, tier = AV\.REPORTED_INACTIVE_HIGH_CONFIDENCE, AV\.TIER_AGGREGATOR_REPORTED",
     'a name on the relayed inactive list -> REPORTED_INACTIVE_HIGH_CONFIDENCE (in ABSENT_STATUSES)'),
    ('ELIGIBILITY', 'slate state', 'nfl/tools/showdown_slate_state.py',
     r"status = DESIGNATION_MAP\[desig\[nm\]\]", 'a team-release designation (OUT etc.) -> status'),
    ('ELIGIBILITY', 'slate state', 'nfl/tools/showdown_slate_state.py',
     r"status, tier = AV\.UNKNOWN_ACTIVE_STATE, AV\.TIER_NONE",
     'everybody else -> UNKNOWN_ACTIVE_STATE. There is no ACTIVE state on this path: unknown players stay in the pool'),
    ('ELIGIBILITY', 'availability', 'nfl/tools/availability.py', r"^ABSENT_STATUSES = ",
     'the statuses treated as not playing (incl. NO_OFFENSIVE_ROLE); UNKNOWN is NOT_A_CLAIM_OF_ABSENCE'),
    ('ELIGIBILITY', 'role state', 'nfl/tools/role_state.py', r"if av in AV\.ABSENT_STATUSES:",
     'absent -> state NOT_PLAYING, no role band'),
    ('ELIGIBILITY', 'projection', 'nfl/tools/proj_v1.py', r"if state == 'NOT_PLAYING':",
     'NOT_PLAYING -> dk_points None, no allocation row; he is outside the club allocation entirely'),
    ('ELIGIBILITY', 'draw spec', 'nfl/tools/showdown_draws.py', r"and isinstance\(r\.get\('dk_points'\), \(int, float\)\)",
     '_shares admits only rows with numeric dk_points: an absent player is in no share denominator and gets no draws'),
    ('SPECIAL_TEAMS_ONLY_APPEARANCE', 'slate state', 'nfl/tools/showdown_slate_state.py',
     r"status, tier = AV\.NO_OFFENSIVE_ROLE, AV\.TIER_ROSTER_POSITION",
     'long snapper / punter by roster or chart -> NO_OFFENSIVE_ROLE, which is IN ABSENT_STATUSES: collapsed into '
     'ineligible-for-opportunity'),
    ('SPECIAL_TEAMS_ONLY_APPEARANCE', 'slate state', 'nfl/tools/showdown_slate_state.py',
     r"returner_review\[nm\] = ",
     'chart lists him only as a returner -> RETURNER_ONLY_REVIEW: listed, NOT excluded, no variable downstream'),
    ('OFFENSIVE_APPEARANCE', 'depth table', 'nfl/tools/proj_v1.py', r"appear = n / n_club_weeks if n_club_weeks else None",
     'appearance_rate = share of club-weeks with >= r position players holding ANY panel row (play-by-play stat). '
     'No snap variable exists on the live path: offensive appearance without a recorded stat is unobservable here'),
    ('POSITIVE_OPPORTUNITY', 'projection', 'nfl/tools/proj_v1.py', r"appear\[i\] = row\.get\('appearance_rate'\)",
     'P(plays) read from the depth table at the player\'s allocator rank (one table per position, so in practice the '
     'same rate for every field)'),
    ('POSITIVE_OPPORTUNITY', 'projection', 'nfl/tools/proj_v1.py', r"claims = \[c \* \(1\.0 if \(force_appearance_for",
     'COLLAPSE: P(plays) multiplied into the claim, so appearance becomes a scale on the expected share'),
    ('POSITIVE_OPPORTUNITY', 'projection', 'nfl/tools/proj_v1.py', r"r\.setdefault\('p_plays', \{\}\)\[field\] = appear\[i\]",
     'p_plays[field] emitted beside the unconditional volume r[field] = team_total * w_i / sum w'),
    ('POSITIVE_OPPORTUNITY', 'projection', 'nfl/tools/proj_v1.py', r"r\['p_plays_by_field'\] = ",
     'p_plays_by_field written to the projection artifact (consumed by workbooks / audits, not by the draw path)'),
    ('POSITIVE_OPPORTUNITY', 'draw spec', 'nfl/tools/showdown_draws.py',
     r"'target_share': share\(r\.get\('targets'\), 'targets'\)",
     'DROPPED: the simulator share is the UNCONDITIONAL volume over the club sum; p_plays is not carried into the spec'),
    ('POSITIVE_OPPORTUNITY', 'simulator', 'nfl/sim/game.py', r"g = \[rng\.gammavariate\(max\(1e-6, conc \* x\), 1\.0\) if x > 0 else 0\.0",
     'per-world shares: Dirichlet(conc x unconditional share). This is the ONLY source of a zero-opportunity world: '
     'small mean share -> small alpha -> mass near zero. Driven by the mean and the concentration, never by p_plays'),
    ('POSITIVE_OPPORTUNITY', 'simulator', 'nfl/sim/game.py', r"got = _multinomial\(total, w, rng\)",
     'multinomial over the drawn club total; zero count when the drawn share is small'),
    ('POSITIVE_COUNT', 'projection', 'nfl/tools/proj_v1.py', r"r\['conditional_volume'\] = \{k: w\.get\(k\) for k in",
     'conditional (if-plays) volume from build()\'s second pass'),
    ('POSITIVE_COUNT', 'simulator', 'nfl/sim/game.py', r"tgt_r, tgt_ghost = alloc\(tg_total, \[max\(0\.0, ps\[i\]\['target_share'\]\)",
     'COLLAPSE: positive counts are the same Dirichlet-multinomial draw as the zeros; there is no separate positive '
     'part, so a backup\'s count given > 0 is centred on his unconditional (shrunk) share, not his conditional volume'),
    ('POSITIVE_COUNT', 'post-step', 'nfl/tools/classic_slate_run.py', r"cv = r\.get\('conditional_volume'\) or \{\}",
     'conditional_volume consumed ONLY as yards per opportunity in efficiency_worlds; counts untouched'),
    ('POSITIVE_COUNT', 'post-step', 'nfl/tools/classic_slate_run.py',
     r"pyd, ryd, recyd = pyd \* f\['pass_yards'\], ryd \* f\['rush_yards'\], recyd \* f\['rec_yards'\]",
     'yards rescaled per world; volumes, catches and touchdowns left exactly as simulated -> zero worlds stay zero'),
    ('ELIGIBILITY', 'post-step', 'nfl/tools/showdown_slate_run.py', r"dst, dst_acc = CR\.anchor_means\(dst, targets\)",
     'the only multiplicative anchor on the Showdown path is applied to DST, not to skill players'),
]


def find_line(relpath, regex, src=None):
    src = src if src is not None else (_REPO / relpath).read_text()
    for i, line in enumerate(src.splitlines(), start=1):
        if re.search(regex, line):
            return i
    raise PropagationError('TRACE_ANCHOR_MISSING', f'{relpath}: /{regex}/')


def trace():
    rows = []
    for state, stage, f, rx, what in TRACE_ANCHORS:
        rows.append({'state': state, 'stage': stage, 'at': f'{f}:{find_line(f, rx)}', 'what': what})
    return rows


def p_plays_grep():
    """The exact grep: every occurrence of p_plays / appearance on the draw path, and what reads p_plays at all."""
    draw_path = ['nfl/sim/game.py', 'nfl/sim/share_model.py', 'nfl/sim/dst.py', 'nfl/sim/football_points.py',
                 'nfl/tools/showdown_draws.py', 'nfl/tools/classic_slate_run.py', 'nfl/tools/showdown_slate_run.py']
    sim_all = sorted(str(p.relative_to(_REPO)) for p in (_REPO / 'nfl/sim').glob('*.py'))
    hits = {}
    for f in sorted(set(draw_path) | set(sim_all)):
        src = (_REPO / f).read_text().splitlines()
        hits[f] = [f'{i}: {ln.strip()[:100]}' for i, ln in enumerate(src, 1) if re.search(r'p_plays|appearance_rate', ln)]
    readers = []
    for p in sorted((_REPO / 'nfl').rglob('*.py')):
        rel = str(p.relative_to(_REPO))
        if rel.startswith(('nfl/research/', 'nfl/tests/')):
            continue
        try:
            if 'p_plays' in p.read_text():
                readers.append(rel)
        except (UnicodeDecodeError, OSError):
            continue
    return {'command': "grep -nE 'p_plays|appearance_rate' nfl/sim/*.py nfl/tools/showdown_draws.py "
                       "nfl/tools/classic_slate_run.py nfl/tools/showdown_slate_run.py",
            'hits_on_draw_path': {k: v for k, v in hits.items() if v},
            'n_hits_on_draw_path': sum(len(v) for v in hits.values()),
            'files_searched': sorted(hits),
            'non_research_modules_that_mention_p_plays': readers,
            'VERDICT': ('CONFIRMED: no line in nfl/sim or in the three draw-path tools reads p_plays or an appearance rate'
                        if not any(hits.values()) else 'REFUTED: see hits_on_draw_path')}


# ============================================================================================ 4. the gate
_GATE_COUNTS: collections.Counter = collections.Counter()
GATE_SUBSTITUTIONS = (
    ("    rng = random.Random(seed)\n",
     "    rng = random.Random(seed)\n    _grng = random.Random(seed + GATE_SEED_OFFSET)\n"),
    ("            ps = c['players']\n",
     "            ps = gate_players(c['players'], _grng)\n"),
)


def _pi(p, field):
    g = p.get('gate')
    if not g:
        return 1.0
    v = g.get(field, 1.0)
    if v is None:
        return 1.0
    v = float(v)
    if not (0.0 <= v <= 1.0) or math.isnan(v):
        raise PropagationError('GATE_PROBABILITY_OUT_OF_RANGE', f'{p.get("id")} {field}: {v}')
    return v


def gate_players(players, grng):
    """Per-world appearance gate. Returns `players` itself when nothing is gated (production identity)."""
    if not any(p.get('gate') for p in players):
        return players
    u = [grng.random() for _ in players]
    out = [dict(p) for p in players]
    for field, keys in GATE_FIELDS:
        pis = [_pi(p, field) for p in players]
        if all(x >= 1.0 for x in pis):
            continue
        open_ = [u[i] < pis[i] for i in range(len(players))]
        for key in keys:
            base = [max(0.0, float(p.get(key, 0.0) or 0.0)) for p in players]
            tot = sum(base)
            cond = [(base[i] / pis[i]) if (open_[i] and pis[i] > 0) else 0.0 for i in range(len(players))]
            ctot = sum(cond)
            if ctot <= 0:
                if tot > 0:
                    _GATE_COUNTS[f'EMPTY_OPEN_SET_FALLBACK_{key}'] += 1
                continue
            for i in range(len(players)):
                out[i][key] = tot * cond[i] / ctot
        _GATE_COUNTS[f'{field}_closed_player_worlds'] += sum(1 for i in range(len(players))
                                                            if not open_[i] and pis[i] < 1.0)
        _GATE_COUNTS[f'{field}_gated_player_worlds'] += sum(1 for x in pis if x < 1.0)
    return out


def gated_simulator(src=None):
    """The production simulator source with exactly the two GATE_SUBSTITUTIONS, as a separate module."""
    src = src if src is not None else SIM_FILE.read_text()
    new = src
    for old, rep in GATE_SUBSTITUTIONS:
        if new.count(old) != 1:
            raise PropagationError('GATE_ANCHOR_NOT_FOUND', f'{old.strip()!r} occurs {new.count(old)} times')
        new = new.replace(old, rep)
    mod = types.ModuleType('nfl_sim_game_gated_research')
    mod.__file__ = str(SIM_FILE)
    mod.__dict__['gate_players'] = gate_players
    mod.__dict__['GATE_SEED_OFFSET'] = GATE_SEED_OFFSET
    exec(compile(new, f'<gated:{SIM_FILE.relative_to(_REPO)}>', 'exec'), mod.__dict__)
    diff = [(a, b) for a, b in zip(src.splitlines(), new.splitlines()) if a != b]
    mod.SOURCE_SHA256 = hashlib.sha256(src.encode()).hexdigest()
    mod.N_LINES_ADDED = len(new.splitlines()) - len(src.splitlines())
    mod.FIRST_DIFF = diff[:1]
    return mod


_GATED = None


def gated():
    global _GATED
    if _GATED is None:
        _GATED = gated_simulator()
    return _GATED


def with_gates(spec, gates):
    """Copy of a simulator spec with p['gate'] = gates[p['id']] (a {field: pi} dict) attached."""
    out = copy.deepcopy(spec)
    for c in out['clubs']:
        for p in c['players']:
            g = gates.get(p['id'])
            if g:
                p['gate'] = {f: float(v) for f, v in g.items() if isinstance(v, (int, float))}
    return out


def run_sim(model, spec, centre, n_sims, seed, gated_arm):
    if not spec.get('clubs') or any(not c.get('players') for c in spec['clubs']):
        raise PropagationError('EMPTY_GAME', 'a club with no players cannot be simulated')
    mod = gated() if gated_arm else SIM
    _GATE_COUNTS.clear()
    o = mod.simulate_game_centred(model, spec, centre, n_sims=n_sims, seed=seed, n_calib=n_sims)
    return o, dict(_GATE_COUNTS)


def load_model(football_only=True):
    mo = SIM.Model.load()
    if mo.state is not State.PASS:
        raise PropagationError('SIM_MODEL_NOT_LOADED', mo.code)
    m = mo.value
    if football_only:   # showdown_draws.build lines 225-236: the FOOTBALL_ONLY arm swaps the residual sets
        fp = FP.load()
        if not fp:
            raise PropagationError('FOOTBALL_POINTS_ABSENT')
        m.total_res = fp['empirical_residuals']['total']
        m.margin_res = fp['empirical_residuals']['margin']
    return m


# =========================================================================================== 2. ATL@NO frozen
def _role(r):
    pos = r.get('position')
    tf = V.DEPTH_TABLE_FIELD.get(pos)
    rk = ((r.get('allocation') or {}).get(tf) or {}).get('depth_rank_in_group')
    return f'{pos}{rk}' if rk else f'{pos}?'


def atl_spec(proj, state):
    """showdown_draws.build's spec for the FOOTBALL_ONLY arm (its lines 224-250), rebuilt from frozen files."""
    rows = list(proj['rows'].values())
    away, home = state['away'], state['home']
    c = (proj.get('football_centre') or {}).get(f'{away}@{home}')
    if proj.get('market_arm') != 'FOOTBALL_ONLY' or not c:
        raise PropagationError('ATL_NOT_FOOTBALL_ONLY')
    spec = {'total_line': c['total'], 'home_spread': c['home_margin'], 'clubs': []}
    for club in (home, away):
        players = SD._shares(rows, club)
        if not players:
            raise PropagationError('EMPTY_CLUB_POOL', club)
        dst = next((r for r in rows if r.get('team') == club and r.get('position') == 'DST'
                    and isinstance(r.get('dk_points'), (int, float))), None)
        spec['clubs'].append({'club': club, 'players': players,
                              'dst_id': (S.player_key(dst['name'], club) if dst else None)})
    tv = proj['team_volume']
    centre = {club: {'pass_attempts': float(tv[club]['proj_pass_attempts']),
                     'rush_attempts': float(tv[club]['proj_rush_attempts']),
                     'targets': float(tv[club]['proj_targets'])} for club in (home, away)}
    return spec, centre


def atl_gates(proj):
    out = {}
    for r in proj['rows'].values():
        pp = r.get('p_plays_by_field')
        if r.get('position') in ('QB', 'RB', 'WR', 'TE') and pp:
            out[S.player_key(r['name'], r['team'])] = {f: pp.get(f) for f in ('targets', 'carries', 'pass_attempts')}
    return out


def _zero_shares(stat_rows):
    a = np.asarray(stat_rows, dtype=float)
    return {f: round(float((a[:, SIM_IX[s]] == 0).mean()), 4) for f, s in FIELD_TO_STAT.items()}, \
           {f: round(float(a[:, SIM_IX[s]].mean()), 3) for f, s in FIELD_TO_STAT.items()}


def atl_no(model=None, resimulate=True):
    files = {k: ATL_DIR / f'SHOWDOWN_{ATL_TAG}_{k}.{"npz" if k == "WORLDS" else "json"}'
             for k in ('PROJ', 'DRAWS', 'WORLDS', 'STATE')}
    for k, p in files.items():
        if not p.exists():
            raise PropagationError('FROZEN_WORLDS_ABSENT', str(p.relative_to(_REPO)))
    hashes_before = {k: _sha(p) for k, p in files.items()}
    proj = json.loads(files['PROJ'].read_text())
    draws = json.loads(files['DRAWS'].read_text())
    state = json.loads(files['STATE'].read_text())
    stats, _pts, meta = CR.load_worlds(files['WORLDS'])
    if meta.get('projection_sha256') != hashes_before['PROJ'] or draws.get('projection_sha256') != hashes_before['PROJ']:
        raise PropagationError('WORLDS_PROJECTION_HASH_MISMATCH')
    if stats.size == 0 or not meta.get('keys'):
        raise PropagationError('FROZEN_WORLDS_EMPTY')
    fx = {f: i for i, f in enumerate(meta['fields'])}
    rows_by_key = {S.player_key(r['name'], r['team']): r for r in proj['rows'].values()}
    inactive = sorted(k for k, r in rows_by_key.items() if str(r.get('projection_state', '')).startswith('NOT_PLAYING'))
    leaked = sorted(set(inactive) & (set(meta['keys']) | set(draws['draws'])))
    table = []
    for i, k in enumerate(meta['keys']):
        r = rows_by_key[k]
        pp = r.get('p_plays_by_field') or {}
        dk = np.asarray(draws['draws'][k], dtype=float)
        row = {'player': k, 'role': _role(r), 'availability': r.get('availability'),
               'dk_points_projection': r.get('dk_points'), 'dk_points_if_plays': r.get('dk_points_if_plays'),
               'zero_dk_share_worlds': round(float((dk == 0).mean()), 4)}
        for f, s in FIELD_TO_STAT.items():
            p = pp.get(f)
            z = float((stats[i, :, fx[s]] == 0).mean())
            row[f] = {'p_plays': p, 'proj_P0': (None if p is None else round(1 - p, 4)),
                      'worlds_zero_share': round(z, 4),
                      'gap_worlds_minus_proj_P0': (None if p is None else round(z - (1 - p), 4)),
                      'mean_worlds': round(float(stats[i, :, fx[s]].mean()), 3),
                      'proj_unconditional': round(float(r.get(f) or 0.0), 3),
                      'proj_conditional': round(float((r.get('conditional_volume') or {}).get(f) or 0.0), 3)}
        table.append(row)
    out = {'files': {k: str(p.relative_to(_REPO)) for k, p in files.items()}, 'sha256': hashes_before,
           'n_worlds': int(stats.shape[1]), 'n_skill_players_in_worlds': len(meta['keys']),
           'inactive_rows_in_projection': len(inactive), 'inactive_rows_with_draws_or_worlds': leaked,
           'table': table}
    if resimulate:
        out['resimulation'] = atl_resimulate(proj, state, stats, meta, model or load_model(), rows_by_key, table)
    if {k: _sha(p) for k, p in files.items()} != hashes_before:
        raise PropagationError('FROZEN_FILES_CHANGED_DURING_READ')
    out['by_role'] = atl_by_role(out)
    return out


def atl_resimulate(proj, state, stats, meta, model, rows_by_key, table):
    spec, centre = atl_spec(proj, state)
    t0 = time.time()
    o, _ = run_sim(model, spec, centre, ATL_N_SIMS, ATL_SEED, gated_arm=False)
    if o.state is not State.PASS:
        raise PropagationError('ATL_RESIM_REFUSED', o.code)
    fx = {f: i for i, f in enumerate(meta['fields'])}
    mism = []
    for i, k in enumerate(meta['keys']):
        a = np.asarray(o.value['stat_draws'][k], dtype=float)
        for s in ('pass_att', 'carries', 'targets', 'receptions', 'pass_td', 'rush_td', 'rec_td'):
            if not np.array_equal(a[:, SIM_IX[s]], stats[i, :, fx[s]].astype(float)):
                mism.append(f'{k}:{s}')
    gspec = with_gates(spec, atl_gates(proj))
    og, gcounts = run_sim(model, gspec, centre, ATL_N_SIMS, ATL_SEED, gated_arm=True)
    if og.state is not State.PASS:
        raise PropagationError('ATL_GATED_REFUSED', og.code)
    # showdown_slate_run line 90: efficiency_worlds(stat_draws, rows, int_rate, seed + 99) -> the frozen DK draws
    dk_u, _w, _eff = CR.efficiency_worlds(o.value['stat_draws'], rows_by_key, float(proj['int_rate']), ATL_SEED + 99)
    frozen = json.loads((ATL_DIR / f'SHOWDOWN_{ATL_TAG}_DRAWS.json').read_text())['draws']
    dk_mism = sorted(k for k in dk_u if list(map(float, dk_u[k])) != list(map(float, frozen[k])))
    dk_g, _w, _eff = CR.efficiency_worlds(og.value['stat_draws'], rows_by_key, float(proj['int_rate']), ATL_SEED + 99)
    for row in table:
        k = row['player']
        z, m = _zero_shares(og.value['stat_draws'][k])
        d = np.asarray(dk_g[k], dtype=float)
        row['gated'] = {'zero_share': z, 'mean': m, 'zero_dk_share': round(float((d == 0).mean()), 4),
                        'mean_dk': round(float(d.mean()), 3)}
        row['ungated_mean_dk_worlds'] = round(float(np.mean(dk_u[k])), 3)
    cw_g = og.value['club_worlds']
    cons = {}
    for c in cw_g:
        keys = [p['id'] for cl in gspec['clubs'] if cl['club'] == c for p in cl['players']]
        tg = np.asarray([[w[SIM_IX['targets']] for w in og.value['stat_draws'][k]] for k in keys]).sum(0)
        car = np.asarray([[w[SIM_IX['carries']] for w in og.value['stat_draws'][k]] for k in keys]).sum(0)
        pa = np.asarray([[w[SIM_IX['pass_att']] for w in og.value['stat_draws'][k]] for k in keys]).sum(0)
        club = np.asarray(cw_g[c])
        cons[c] = {'max_abs_targets_minus_club': float(np.abs(tg - club[:, 2]).max()),
                   'max_abs_carries_minus_club': float(np.abs(car - club[:, 1]).max()),
                   'max_abs_pass_att_minus_club': float(np.abs(pa - club[:, 0]).max()),
                   'NOTE': 'differences of a unit are the ghost bucket (pool shares sum below 1); see unallocated'}
    return {'reproduced_frozen_counts': not mism, 'mismatched_series': mism[:20],
            'reproduced_frozen_dk_draws': not dk_mism, 'mismatched_dk_players': dk_mism[:20],
            'REPRODUCTION_MEANING': ('the frozen projection pushed through the production simulate_game_centred with the '
                                     'frozen seed and n_sims reproduces every per-world count in the frozen WORLDS.npz '
                                     '(pass attempts, carries, targets, receptions, TDs) exactly; the spec is the '
                                     'production spec'),
            'gated_seed': ATL_SEED, 'gate_counts': gcounts,
            'gated_unallocated_fraction': og.value.get('unallocated_fraction'),
            'ungated_unallocated_fraction': o.value.get('unallocated_fraction'),
            'gated_volume_centre_all_within_tol': og.value['volume_centre']['all_within_tol'],
            'gated_conservation_per_world': cons, 'seconds': round(time.time() - t0, 1),
            'WRITTEN_TO_NFL_DFS': False}


def atl_by_role(atl):
    out = collections.defaultdict(list)
    for r in atl['table']:
        pos = r['role'][:2]
        f = V.DEPTH_TABLE_FIELD.get(pos)
        x = r[f]
        e = {'player': r['player'], 'field': f, 'p_plays': x['p_plays'], 'proj_P0': x['proj_P0'],
             'worlds_P0': x['worlds_zero_share'], 'gap': x['gap_worlds_minus_proj_P0'],
             'worlds_P0_dk': r['zero_dk_share_worlds'], 'mean_worlds': x['mean_worlds'],
             'proj_conditional': x['proj_conditional']}
        if pos == 'RB':
            e['targets'] = {'p_plays': r['targets']['p_plays'], 'worlds_P0': r['targets']['worlds_zero_share']}
        if 'gated' in r:
            e['gated_P0'] = r['gated']['zero_share'][f]
            e['gated_P0_dk'] = r['gated']['zero_dk_share']
            e['mean_dk_ungated_vs_gated'] = [r.get('ungated_mean_dk_worlds'), r['gated']['mean_dk']]
        out[r['role']].append(e)
    return dict(sorted(out.items()))


# ======================================================================================= 3. held-out replay
def _snaps(season):
    prov = json.loads((F1.HIST / 'PROVENANCE.json').read_text())
    f = {x['kind']: _REPO / x['file'] for x in prov['files']}
    cw = pd.read_csv(f['players_crosswalk'])
    s = pd.read_csv(f[f'snap_counts_{season}'])
    s = s[s.game_type == 'REG'].merge(cw[['pfr_id', 'gsis_id']], left_on='pfr_player_id', right_on='pfr_id')
    snaps = {(r.team, int(r.week), r.gsis_id): (float(r.offense_snaps or 0), float(r.st_snaps or 0))
             for r in s.itertuples()}
    games = {}
    for gid in s.game_id.unique():
        parts = gid.split('_')
        games[gid] = {'week': int(parts[1]), 'away': parts[2], 'home': parts[3]}
    if not snaps or not games:
        raise PropagationError('NO_SNAPS', str(season))
    return snaps, games


def _sim_rows(rows, club):
    """Projection rows in the shape showdown_draws._shares reads. dk_points is a MEMBERSHIP flag only (never scored);
    TD expectations are the rows' own opportunity volumes (validate_correlations' declared proxy): TD shares move the
    TD draw, not any opportunity count, which is all this replay scores."""
    out = []
    for r in rows:
        x = V.finalize(dict(r))
        out.append({'name': r['_dk'], 'team': club, 'position': r['position'], 'dk_points': 0.0,
                    'targets': x.get('targets') or 0.0, 'carries': x.get('carries') or 0.0,
                    'pass_attempts': x.get('pass_attempts') or 0.0, 'receptions': x.get('receptions') or 0.0,
                    'td': {'rec_td': x.get('targets') or 0.0, 'rush_td': x.get('carries') or 0.0}})
    return out


def club_arms(ctx, fitted, club, week, starter):
    depth, groups, rates = fitted['depth'], fitted['groups'], fitted['rates']
    prev = sorted(w for w in ctx['team_weeks'].get(club, ()) if w < week)
    if len(prev) < P2.N_PRIOR:
        return None
    pool = P2.pool_for(ctx, club, week, 'DRESSED')
    if not pool:
        return None
    tv, crows = P2.club_rows(ctx, club, week, pool, starter, depth)
    if not crows or any(tv.get(k) is None for k in ('proj_pass_attempts', 'proj_rush_attempts', 'proj_targets')):
        return None
    dressed_now = ctx['dressed'].get((club, week), set())
    qual, p3 = {}, {}
    for r in crows:
        for f, _ in P2.ALLOC:
            c = P2.prior3(ctx, r['_dk'], club, week, f)
            p3[(r['_dk'], f)] = c
            qual[(r['_dk'], f)] = bool((r['position'], f) in rates and r['_dk'] in dressed_now and c == P2.N_PRIOR)
    cur = copy.deepcopy(crows)
    V.allocate_opportunity(cur, tv, depth, groups)
    cand = copy.deepcopy(crows)
    P2.allocate_with_hook(cand, tv, depth, groups, rate_fn=P2.candidate_rate_fn(rates, qual))
    return {'tv': tv, 'cur': cur, 'cand': cand, 'qual': qual, 'p3': p3}


def _crps(x, y):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    if not n:
        return float('nan')
    i = np.arange(1, n + 1)
    return float(np.abs(x - y).mean() - (2.0 * ((2 * i - n - 1) * x).sum() / (n * n)) / 2.0)


def replay(ctx, fitted, model, weeks=None, n_sims=REPLAY_N_SIMS, max_games=None, progress=None):
    snaps, games = ctx['snaps'], ctx['games']
    season = ctx['season']
    all_weeks = sorted({g['week'] for g in games.values()})
    weeks = [w for w in (weeks or all_weeks) if w >= P2.MIN_WEEK]
    fp_table = FP.club_points_table(FP._rows())
    units, refused, gate_tot, n_games = [], collections.Counter(), collections.Counter(), 0
    for week in weeks:
        starter = P2.starter_proxy(ctx, week)
        for gi, (gid, g) in enumerate(sorted((k, v) for k, v in games.items() if v['week'] == week)):
            if max_games is not None and n_games >= max_games:
                break
            arms = {c: club_arms(ctx, fitted, c, week, starter) for c in (g['home'], g['away'])}
            if any(a is None for a in arms.values()):
                refused['CLUB_NOT_PROJECTABLE'] += 1
                continue
            fc = FP.centre_for_game(g['home'], g['away'], season, week, table=fp_table)
            if fc is None:
                refused['NO_FOOTBALL_CENTRE'] += 1
                continue
            centre = {c: {'pass_attempts': float(a['tv']['proj_pass_attempts']),
                          'rush_attempts': float(a['tv']['proj_rush_attempts']),
                          'targets': min(float(a['tv']['proj_targets']), float(a['tv']['proj_pass_attempts']))}
                      for c, a in arms.items()}
            specs, gates = {}, {}
            for arm, key in (('CURRENT', 'cur'), ('CANDIDATE', 'cand')):
                sp = {'total_line': fc['total'], 'home_spread': fc['home_margin'], 'clubs': []}
                gt = {}
                for c in (g['home'], g['away']):
                    rows = arms[c][key]
                    players = SD._shares(_sim_rows(rows, c), c)
                    if not any(p['position'] == 'QB' for p in players):
                        sp = None
                        break
                    sp['clubs'].append({'club': c, 'players': players, 'dst_id': None})
                    for r in rows:
                        gt[S.player_key(r['_dk'], c)] = {f: (r.get('p_plays') or {}).get(f, 1.0)
                                                         for f in ('targets', 'carries', 'pass_attempts')}
                if sp is None:
                    break
                specs[arm], gates[arm] = sp, gt
            if len(specs) != 2:
                refused['CLUB_HAS_NO_QB_IN_POOL'] += 1
                continue
            seed = REPLAY_SEED + week * 1000 + gi
            outs = {}
            for arm in ARMS:
                base = arm.replace('_GATED', '')
                sp = with_gates(specs[base], gates[base]) if arm.endswith('_GATED') else specs[base]
                o, gc = run_sim(model, sp, centre, n_sims, seed, gated_arm=arm.endswith('_GATED'))
                if o.state is not State.PASS:
                    outs = None
                    refused[f'{arm}:{o.code}'] += 1
                    break
                outs[arm] = o.value['stat_draws']
                if arm.endswith('_GATED'):
                    gate_tot.update({f'{arm}:{k}': v for k, v in gc.items()})
            if outs is None:
                continue
            n_games += 1
            for c in (g['home'], g['away']):
                a = arms[c]
                dressed_now = ctx['dressed'].get((c, week), set())
                for rc, rn in zip(a['cur'], a['cand']):
                    gs, pos = rc['_dk'], rc['position']
                    if ctx['pos_src'].get(gs) == 'USAGE_INFERRED' or gs not in dressed_now:
                        continue
                    key = S.player_key(gs, c)
                    now = ((ctx['panel']['players'].get(gs) or {}).get(str(season)) or {}).get(str(week)) or {}
                    off, st = snaps.get((c, week, gs), (float('nan'), float('nan')))
                    tf = P2.TABLE_FIELD[pos]
                    for f in P2.SCORE_FIELDS[pos]:
                        y = float(now.get(f) or 0.0)
                        u = {'season': season, 'week': week, 'club': c, 'game_id': gid, 'gsis': gs, 'pos': pos,
                             'field': f, 'rank_table': ((rc.get('allocation') or {}).get(tf) or {}).get('depth_rank_in_group'),
                             'qualifies': a['qual'][(gs, f)], 'offense_snaps': off, 'st_snaps': st,
                             'p_cur': float((rc.get('p_plays') or {}).get(f, 1.0)),
                             'p_cand': float((rn.get('p_plays') or {}).get(f, 1.0)),
                             'e_cur': float(rc.get(f) or 0.0), 'e_cand': float(rn.get(f) or 0.0), 'actual': y}
                        for arm in ARMS:
                            x = np.asarray([w[SIM_IX[FIELD_TO_STAT[f]]] for w in outs[arm][key]], float)
                            pos_x = x[x > 0]
                            u[f'p0_{arm}'] = float((x == 0).mean())
                            u[f'mean_{arm}'] = float(x.mean())
                            u[f'crps_{arm}'] = _crps(x, y)
                            u[f'cmean_{arm}'] = float(pos_x.mean()) if len(pos_x) else float('nan')
                            u[f'ccrps_{arm}'] = _crps(pos_x, y) if (len(pos_x) and y > 0) else float('nan')
                        units.append(u)
            if progress:
                progress(week, n_games, len(units))
        if max_games is not None and n_games >= max_games:
            break
    if not units:
        raise PropagationError('NO_SCORED_UNITS', f'weeks={weeks}')
    return pd.DataFrame(units), dict(refused), dict(gate_tot), n_games


# ------------------------------------------------------------------------------------------- statistics
def _clip(p):
    return np.clip(np.asarray(p, float), P_FLOOR, 1 - P_FLOOR)


def _brier(p0, y0):
    return (_clip(p0) - y0) ** 2


def _logs(p0, y0):
    p = _clip(p0)
    return -(y0 * np.log(p) + (1 - y0) * np.log(1 - p))


def _blk(v, blocks):
    return P2._blocked(v, blocks)


def p0_columns():
    return {'PROJ_CURRENT': lambda d: 1 - d.p_cur.values, 'PROJ_CANDIDATE': lambda d: 1 - d.p_cand.values,
            **{f'DRAW_{a}': (lambda a: lambda d: d[f'p0_{a}'].values)(a) for a in ARMS}}


def cohort_scores(d):
    if not len(d):
        return {'n_units': 0, 'state': 'EMPTY_COHORT'}
    y0 = (d.actual.values == 0).astype(float)
    out = {'n_units': int(len(d)), 'n_players': int(d.gsis.nunique()), 'n_weeks': int(d.week.nunique()),
           'n_club_weeks': int(d.groupby(['week', 'club']).ngroups),
           'observed_P0': round(float(y0.mean()), 4), 'arms': {}}
    for name, fn in p0_columns().items():
        p0 = fn(d)
        out['arms'][name] = {'mean_P0': round(float(np.mean(p0)), 4),
                             'P0_minus_observed': {'pooled': round(float(np.mean(p0) - y0.mean()), 4),
                                                   **_blk(p0 - y0, d.week.values)},
                             'brier': round(float(_brier(p0, y0).mean()), 5),
                             'log_score': round(float(_logs(p0, y0).mean()), 5)}
    pos = d[d.actual > 0]
    for a in ARMS:
        x = out['arms'][f'DRAW_{a}']
        x['unconditional_crps'] = round(float(d[f'crps_{a}'].mean()), 4)
        x['mean_draw_minus_actual'] = round(float((d[f'mean_{a}'] - d.actual).mean()), 4)
        if len(pos):
            cm = pos[f'cmean_{a}']
            x['positive_count'] = {
                'n_units_actual_gt0': int(len(pos)),
                'n_units_no_positive_draw': int(cm.isna().sum()),
                'conditional_mean_minus_actual': round(float((cm - pos.actual).mean()), 4),
                'conditional_abs_error': round(float((cm - pos.actual).abs().mean()), 4),
                'conditional_crps': round(float(pos[f'ccrps_{a}'].mean()), 4)}
    return out


def paired(d, loss_a, loss_b):
    """Improvement of B over A (loss A - loss B, positive = B better), week- and club-blocked."""
    diff = np.asarray(loss_a, float) - np.asarray(loss_b, float)
    m = ~np.isnan(diff)
    dd = d[m]
    return {'n_units': int(m.sum()), 'pooled': round(float(diff[m].mean()), 6),
            'week_blocked': _blk(diff[m], dd.week.values), 'club_blocked': _blk(diff[m], dd.club.values)}


COMPARISONS = {
    'PRIMARY__GATE_ALONE__CURRENT_GATED_vs_CURRENT': ('DRAW_CURRENT', 'DRAW_CURRENT_GATED'),
    'S1__CANDIDATE_UNGATED_vs_CURRENT__does_the_candidate_reach_the_draws_today': ('DRAW_CURRENT', 'DRAW_CANDIDATE'),
    'S2__CANDIDATE_GATED_vs_CURRENT_GATED__candidate_effect_once_propagated': ('DRAW_CURRENT_GATED', 'DRAW_CANDIDATE_GATED'),
    'S3__CANDIDATE_GATED_vs_CURRENT__both_changes': ('DRAW_CURRENT', 'DRAW_CANDIDATE_GATED'),
    'S4__CANDIDATE_GATED_vs_CANDIDATE_UNGATED__gate_under_candidate_rates': ('DRAW_CANDIDATE', 'DRAW_CANDIDATE_GATED'),
    'REF__PROJECTION_CANDIDATE_vs_PROJECTION_CURRENT__the_layer_SC_APPEAR_1_was_scored_on': ('PROJ_CURRENT', 'PROJ_CANDIDATE'),
}


def compare(d):
    y0 = (d.actual.values == 0).astype(float)
    cols = p0_columns()
    out = {}
    for name, (a, b) in COMPARISONS.items():
        pa, pb = cols[a](d), cols[b](d)
        out[name] = {'A': a, 'B': b, 'brier_improvement_B_over_A': paired(d, _brier(pa, y0), _brier(pb, y0)),
                     'log_score_improvement_B_over_A': paired(d, _logs(pa, y0), _logs(pb, y0))}
        if a.startswith('DRAW_') and b.startswith('DRAW_'):
            aa, bb = a[5:], b[5:]
            out[name]['unconditional_crps_improvement_B_over_A'] = paired(d, d[f'crps_{aa}'], d[f'crps_{bb}'])
            pos = d[d.actual > 0]
            out[name]['positive_count_crps_improvement_B_over_A'] = paired(pos, pos[f'ccrps_{aa}'], pos[f'ccrps_{bb}'])
    return out


def propagation_ratio(d):
    """Change in draw-implied P(0) per unit change in the projection's P(0), candidate minus current."""
    q = d[d.qualifies]
    dp = (1 - q.p_cand) - (1 - q.p_cur)
    out = {}
    for lab, a, b in (('UNGATED', 'p0_CURRENT', 'p0_CANDIDATE'), ('GATED', 'p0_CURRENT_GATED', 'p0_CANDIDATE_GATED')):
        dd = q[b] - q[a]
        out[lab] = {'mean_change_projection_P0': round(float(dp.mean()), 4),
                    'mean_change_draw_P0': round(float(dd.mean()), 4),
                    'ratio_draw_over_projection': (round(float(dd.mean() / dp.mean()), 3) if abs(dp.mean()) > 1e-9 else None),
                    'n_qualifying_units': int(len(q))}
    out['MEANING'] = ('1.0 = the projection layer\'s change in zero mass arrives in the worlds in full; 0 = none of it '
                      'does. Measured on qualifying units, the only units whose P(plays) the candidate changes')
    return out


def state_decomposition(d):
    """Observed five-state frequencies among DRESSED (snap-present) RB/WR/TE units, 2025."""
    x = d[d.pos.isin(['RB', 'WR', 'TE'])]
    off = x.offense_snaps.values > 0
    st_only = (x.offense_snaps.values == 0) & (x.st_snaps.values > 0)
    pos_opp = x.actual.values > 0
    out = {'n_units': int(len(x)),
           'ELIGIBILITY': ('dressed = present in snap counts (>= 1 offensive or special-teams snap). Active players with '
                           'zero snaps are NOT in the data: NOT_IDENTIFIABLE_FROM_CURRENT_DATA'),
           'share_offensive_appearance': round(float(off.mean()), 4),
           'share_special_teams_only': round(float(st_only.mean()), 4),
           'share_positive_opportunity_in_field': round(float(pos_opp.mean()), 4),
           'P_positive_given_offensive_appearance': round(float(pos_opp[off].mean()), 4) if off.any() else None,
           'P_positive_given_special_teams_only': round(float(pos_opp[st_only].mean()), 4) if st_only.any() else None,
           'P0_decomposition': {
               'special_teams_only': round(float(st_only.mean()), 4),
               'offensive_snap_but_zero_in_field': round(float((off & ~pos_opp).mean()), 4),
               'total_observed_P0': round(float((~pos_opp).mean()), 4)}}
    by = {}
    for (pos, rk, fld), g in x.groupby(['pos', 'rank_table', 'field']):
        if len(g) < 30:
            continue
        o = g.offense_snaps.values > 0
        by[f'{pos}{int(rk)}_{fld}'] = {
            'n': int(len(g)), 'st_only': round(float(((g.offense_snaps == 0) & (g.st_snaps > 0)).mean()), 4),
            'offensive': round(float(o.mean()), 4), 'positive_in_field': round(float((g.actual > 0).mean()), 4)}
    out['by_role'] = by
    return out


def summarise(df):
    rbwrte = df.pos.isin(['RB', 'WR', 'TE'])
    cohorts = {'ALL_RB_WR_TE': rbwrte, 'QUALIFYING_RB_WR_TE': rbwrte & df.qualifies,
               'NON_QUALIFYING_RB_WR_TE': rbwrte & ~df.qualifies, 'RANK1_RB_WR_TE': rbwrte & (df.rank_table == 1),
               'RANK2PLUS_RB_WR_TE': rbwrte & (df.rank_table >= 2),
               'QB_RANK1_pass_attempts': (df.pos == 'QB') & (df.rank_table == 1),
               'QB_RANK2PLUS_pass_attempts': (df.pos == 'QB') & (df.rank_table >= 2)}
    for pos, ranks in (('RB', (1, 2, 3)), ('WR', (1, 2, 3, 4, 5)), ('TE', (1, 2, 3))):
        for rk in ranks:
            for f in P2.SCORE_FIELDS[pos]:
                cohorts[f'{pos}{rk}_{f}'] = (df.pos == pos) & (df.rank_table == rk) & (df.field == f)
    res = {k: cohort_scores(df[m]) for k, m in cohorts.items()}
    cmp_all = compare(df[rbwrte])
    cmp_q = compare(df[rbwrte & df.qualifies])
    cmp_r1 = compare(df[rbwrte & (df.rank_table == 1)])
    return {'n_units': int(len(df)), 'n_weeks': int(df.week.nunique()), 'weeks': sorted(int(w) for w in df.week.unique()),
            'n_club_weeks': int(df.groupby(['week', 'club']).ngroups), 'cohorts': res,
            'comparisons_ALL_RB_WR_TE': cmp_all, 'comparisons_QUALIFYING_RB_WR_TE': cmp_q,
            'comparisons_RANK1_RB_WR_TE': cmp_r1, 'propagation_ratio': propagation_ratio(df[rbwrte]),
            'observed_state_decomposition_2025': state_decomposition(df)}


# ------------------------------------------------------------------------------------------- declaration
DECLARATION = {
    'written_before_any_score': True,
    'PRIMARY': {
        'comparison': 'PRIMARY__GATE_ALONE__CURRENT_GATED_vs_CURRENT',
        'why_this_one': ('one change at a time (governing rule 2): the gate alone, at the CURRENT production p_plays, '
                         'against the production draws. The candidate\'s effect under the gate is the secondary S2'),
        'cohort': 'ALL_RB_WR_TE dressed units, held-out 2025 REG weeks >= 4',
        'metric': 'Brier score of the draw-implied P(0 opportunities in the field), paired per unit',
        'bar': ('improvement (CURRENT loss - GATED loss) has week-blocked z > 2 AND the club-blocked mean is positive; '
                'AND positive-count calibration is not worse: conditional CRPS (actual > 0 units) of the gated arm is '
                'not worse than current by more than 2 week-blocked SE'),
        'what_a_pass_would_mean': ('the gate moves the worlds\' zero mass toward the observed zero share on held-out '
                                   'games. It would NOT establish that the gate is adequate, that DFS lineups improve, '
                                   'or that the shape conditional on > 0 is calibrated -- those are separate questions'),
    },
    'SECONDARY': ['S1 (is draw P(0) under the candidate different from current without a gate)', 'S2', 'S3', 'S4',
                  'REF (the projection-layer comparison SC-APPEAR-1 already passed, recomputed on these units)',
                  'propagation_ratio', 'positive-count calibration by arm', 'cohorts by role'],
    'NOT_A_BAR': 'secondaries are descriptive; no secondary result promotes anything',
    'evidence_class': ('RETROSPECTIVE OUT-OF-SAMPLE. 2025 has been read twice before this (forward test and the '
                       'production-path replay); this is the third read. Not a sealed holdout for any variant chosen '
                       'after reading it'),
}


def _declaration_sha(decl):
    return hashlib.sha256(json.dumps(decl, sort_keys=True).encode()).hexdigest()


def declare():
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    doc = {'ARTIFACT': 'SC_APPEAR_1_PROPAGATION', 'STATUS': 'SHADOW_ONLY', 'PHASE': 'DECLARED_NOT_SCORED',
           'DECLARATION': DECLARATION, 'declared_at': stamp, 'declaration_sha256': _declaration_sha(DECLARATION)}
    OUT.write_text(json.dumps(doc, indent=1))
    return stamp


def primary_verdict(summary):
    c = summary['comparisons_ALL_RB_WR_TE']['PRIMARY__GATE_ALONE__CURRENT_GATED_vs_CURRENT']
    b = c['brier_improvement_B_over_A']
    pc = c['positive_count_crps_improvement_B_over_A']['week_blocked']
    checks = {'brier_week_blocked_z_gt_2': bool(b['week_blocked']['z'] is not None and b['week_blocked']['z'] > 2),
              'brier_club_blocked_mean_positive': bool(b['club_blocked']['mean_of_block_means'] > 0),
              'positive_count_crps_not_worse_by_2se': bool(pc['mean_of_block_means'] >= -2 * pc['se'])}
    return {'checks': checks, 'RESULT': 'PASS' if all(checks.values()) else 'FAIL',
            'brier': b, 'positive_count_crps': c['positive_count_crps_improvement_B_over_A']}


SMOKE_RUN_NOTE = (
    'DISCLOSED: after the DECLARATION text above was written into this module and before run() stamped it into the '
    'JSON, the scoring code was exercised once on 6 games of 2025 week 7 at 300 draws to check it did not crash '
    '(that subset pointed the primary toward FAIL: gated Brier worse than current). The declaration was not edited '
    'after that run; declaration_sha256 is the hash of the text as first written.')


LIMITATIONS = [
    'ACTIVE ZERO-SNAP PLAYERS: NOT_IDENTIFIABLE_FROM_CURRENT_DATA. Official 2024-2025 game-day active lists are not in '
    'the repository (outbox request filed). The dressed universe is snap-count presence, so an active player who took '
    'no snap is in neither the pool nor the scored set; observed zero shares are understated for every arm alike. '
    'Realised snaps are used only to DESCRIBE observed states, never as an eligibility input.',
    'SIMULATOR CONSTANTS ARE NOT HELD OUT: the share concentrations (VARIANCE_COMPONENTS, USAGE_MODEL), efficiency and '
    'the football-points residuals are fitted on data that include 2025 (PLAYER_GAME 2021-2026; FOOTBALL_POINTS '
    '2001-2025). They are identical in every arm, so the paired comparisons are not driven by them, but the absolute '
    'calibration of any arm is partly in-sample. Refitting them would need a production change and is not done here.',
    'p_plays IS NOT FIELD-SPECIFIC IN PRODUCTION: the depth appearance rate is P(>= r position players hold ANY panel '
    'row), one table per position. Used as the gate for a specific field it overstates P(>= 1 in that field) for a '
    'player who appears without e.g. a target; the gated P(0) then adds P(M = 0 | open) on top of 1 - pi.',
    'THE GATE IS NOT A STRICT HURDLE: P(N = 0) = (1 - pi) + pi x P(M = 0 | open). A zero-truncated positive part would '
    'make P(N = 0) = 1 - pi exactly but cannot be byte-identical to production at pi = 1, which the identity test '
    'requires. Both readings are reported (gate_counts, positive-count calibration).',
    'GATED MEANS DRIFT: renormalising over open players preserves club totals exactly and each player\'s expected '
    'weight before renormalising, not his expected count after it. The ATL@NO table reports ungated vs gated means.',
    'HARNESS IS NOT LIVE PRODUCTION: no role state, no captured chart rank, QB starter proxy from prior pass attempts, '
    'TD shares proxied by opportunity shares (they move TD draws only, never an opportunity count), no DST/kicker. '
    'The allocator, the share builder (showdown_draws._shares), the football-only centre and the centred simulator '
    'are production code.',
    'MONTE CARLO: 1,000 worlds per game per arm; per-unit P(0) carries SE <= 0.016. Common random numbers on the main '
    'stream within a game; the gate draws from its own stream.',
    'WEEK-BLOCKED SEs rest on 15 blocks; club-blocked SEs are reported alongside.',
    '2025 HAS NOW BEEN READ THREE TIMES. Any variant chosen after this read needs a new holdout.',
]


def production_change_note():
    return {
        'STATUS': 'DESCRIPTION ONLY -- NO PRODUCTION FILE EDITED',
        'steps': [
            'nfl/tools/showdown_draws._shares: carry each player\'s p_plays_by_field into the spec (as `gate`), beside '
            'the unconditional share it already carries',
            'nfl/sim/game.simulate_game: a DECLARED ARM (keyword, default off -> byte-identical) that draws the gate from '
            'a separate random stream and reweights open players by u/pi before alloc(); simulate_game_centred passes '
            'it through. Club totals, the ghost bucket and all seven identities are unchanged by construction',
            'decide, as a declared choice, whether the positive part is zero-truncated (strict hurdle, P(0) = 1 - pi, '
            'loses byte identity at pi = 1) or left as the existing allocation (this prototype)',
            'decide whether pi should be field-specific (P(>= 1 target) etc.) rather than the any-stat depth rate',
            'keep eligibility separate: an UNKNOWN_ACTIVE_STATE player is currently a pool member whose eligibility '
            'uncertainty is silently folded into p_plays; an official-actives gate would be a second, separate factor',
            're-run the ATL@NO baseline and a classic slate with the arm off (identity) and on; the optimiser and '
            'candidate scorer then see more zero worlds for backups, which changes p_optimal and exposures',
            'its own commit, with its own baseline, never in the same commit as a validation change (rule 2)'],
    }


def run(quick=False, log=print):
    hashes_before = production_hashes()
    declared_at = declare()
    t0 = time.time()
    tr = trace()
    grep = p_plays_grep()
    gm = gated()
    log(f'trace {len(tr)} anchors; grep {grep["n_hits_on_draw_path"]} hits; gated sim +{gm.N_LINES_ADDED} line(s)')
    model = load_model()
    atl = atl_no(model)
    log(f'ATL@NO reproduced={atl["resimulation"]["reproduced_frozen_counts"]} ({time.time() - t0:.0f}s)')
    po = P2.PP.load_panel()
    if po.state.value != 'PASS':
        raise PropagationError('PANEL', str(po.state))
    panel, pos_of = po.value, P2.PP.position_index()
    fitted = P2.fit(panel, pos_of, F1._dressed(P2.FIT_SEASON))
    ctx = P2.context(panel, pos_of, P2.TEST_SEASON, F1._dressed(P2.TEST_SEASON),
                     snap_pos=P2._snap_positions(P2.TEST_SEASON))
    ctx['snaps'], ctx['games'] = _snaps(P2.TEST_SEASON)
    weeks = [6, 12] if quick else None
    df, refused, gate_tot, n_games = replay(ctx, fitted, model, weeks=weeks,
                                            progress=lambda w, g, u: log(f'  week {w}: {g} games, {u} units, '
                                                                         f'{time.time() - t0:.0f}s'))
    summary = summarise(df)
    hashes_after = production_hashes()
    doc = json.loads(OUT.read_text())
    if doc.get('declaration_sha256') != _declaration_sha(DECLARATION) or doc.get('declared_at') != declared_at:
        raise PropagationError('DECLARATION_CHANGED_AFTER_SCORING_BEGAN')
    doc.update({
        'PHASE': 'SCORED' + ('_QUICK_SUBSET' if quick else ''),
        'scored_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'production_files': {'sha256_before': hashes_before, 'sha256_after': hashes_after,
                             'any_production_file_changed': hashes_before != hashes_after},
        'FIVE_STATE_TRACE': tr,
        'FIVE_STATE_SUMMARY': FIVE_STATE_SUMMARY,
        'P_PLAYS_GREP': grep,
        'GATED_SIMULATOR': {'source': 'nfl/sim/game.py read at run time; two substitutions, nothing written',
                            'source_sha256': gm.SOURCE_SHA256, 'lines_added': gm.N_LINES_ADDED,
                            'substitutions': [{'production': a.strip(), 'research': b.strip()} for a, b in GATE_SUBSTITUTIONS],
                            'gate_seed_offset': GATE_SEED_OFFSET},
        'ATL_NO_FROZEN_V2': atl,
        'HELD_OUT_2025': {'n_games_simulated': n_games, 'n_sims_per_game_per_arm': REPLAY_N_SIMS,
                          'refused': refused, 'gate_counts': gate_tot,
                          'gate_counts_MEANING': ('player-worlds, summed over the 3 centring calibration passes and the '
                                                  'final pass of every game'),
                          'configuration': {
                              'simulator': 'simulate_game_centred (volume_centre=PROJECTION, n_calib=n_sims), '
                                           'CLUB_TOTAL_IMPOSED, DIRICHLET -- showdown_slate_run\'s configuration',
                              'scoring_centre': 'nfl/sim/football_points.centre_for_game (FOOTBALL_ONLY arm residuals)',
                              'shares': 'nfl/tools/showdown_draws._shares on the allocator\'s unconditional volumes',
                              'fit': 'depth table, group split, priors and SC-APPEAR-1 rates through 2024'},
                          **summary},
        'PRIMARY_RESULT': primary_verdict(summary),
        'PRE_DECLARATION_SMOKE_RUN': SMOKE_RUN_NOTE,
        'ACTIVE_ZERO_SNAP_COHORT': 'NOT_IDENTIFIABLE_FROM_CURRENT_DATA',
        'LIMITATIONS': LIMITATIONS,
        'PRODUCTION_CHANGE_WOULD_INVOLVE': production_change_note(),
        'AUDIT_LADDER': {
            'reached': 'ADVERSARIAL_TESTED (research prototype); production: NOT_ON_EXECUTION_PATH',
            'IMPLEMENTED': 'yes -- research module; the gated simulator is the production source plus two lines, in memory',
            'ON_EXECUTION_PATH': 'NO -- nothing on the live Showdown or classic path calls it; no production file edited',
            'SUCCESS_TESTED': ('yes -- nfl/tests/test_sc_appear_1_propagation.py: all-pi=1 and no-gate draws byte-'
                               'identical to production; frozen ATL@NO counts reproduced'),
            'REFUSAL_TESTED': 'yes -- empty game, empty pool, missing gate anchor, pi out of range, no scored units',
            'ADVERSARIAL_TESTED': ('yes -- inactive rows with volume never drawn; pi = 0 never receives volume; club totals '
                                   'conserved per world; fit identical with 2025 removed; week-W draws identical after '
                                   'perturbing week >= W outcomes'),
            'PROSPECTIVELY_VALIDATED': 'NO'},
        'seconds': round(time.time() - t0, 1),
    })
    OUT.write_text(json.dumps(doc, indent=1, default=float))
    return OUT, doc


FIVE_STATE_SUMMARY = {
    'ELIGIBILITY': {'distinct_variable': 'YES, as current_availability.status (slate state); collapsed to a pool '
                                         'membership boolean at proj_v1 NOT_PLAYING / showdown_draws._shares',
                    'produced_by': 'showdown_slate_state.build', 'consumed_by': 'role_state.assign -> proj_v1.build -> '
                                                                              'showdown_draws._shares',
                    'collapsed_or_dropped': ('ABSENT -> outside the pool (exact zero, no draws). UNKNOWN_ACTIVE_STATE -> '
                                             'inside the pool as if eligible; its eligibility uncertainty has no variable '
                                             'and is only implicitly inside the depth appearance rate')},
    'OFFENSIVE_APPEARANCE': {'distinct_variable': 'NO', 'produced_by': 'nothing on the live path (no snap input)',
                             'consumed_by': 'nothing', 'collapsed_or_dropped': (
                                 'merged with positive opportunity: appearance_rate counts a player as appearing only '
                                 'if he holds a play-by-play row')},
    'SPECIAL_TEAMS_ONLY_APPEARANCE': {'distinct_variable': 'NO (only a roster/chart specialist label)',
                                      'produced_by': 'showdown_slate_state.specialist_class',
                                      'consumed_by': 'availability.ABSENT_STATUSES via NO_OFFENSIVE_ROLE',
                                      'collapsed_or_dropped': (
                                          'specialists collapsed into ABSENT; returner-only flagged for review and '
                                          'otherwise identical to any pool member; a skill player who plays only '
                                          'special teams has no representation')},
    'POSITIVE_OPPORTUNITY': {'distinct_variable': 'YES in the projection (p_plays[field]); NO in the simulator',
                             'produced_by': 'proj_v1.allocate_opportunity', 'consumed_by': (
                                 'its own claim product (mean scaling) and output tables; NOT showdown_draws, NOT '
                                 'nfl/sim, NOT the post-steps'),
                             'collapsed_or_dropped': (
                                 'collapsed into the unconditional mean share at the claim product, then DROPPED at '
                                 'showdown_draws._shares. Per-world zero opportunity in the draws comes only from the '
                                 'Dirichlet-multinomial on the mean share')},
    'POSITIVE_COUNT': {'distinct_variable': 'YES in the projection (conditional_volume); NO in the simulator',
                       'produced_by': 'proj_v1.build second pass', 'consumed_by': (
                           'classic_slate_run.efficiency_worlds as yards per opportunity only'),
                       'collapsed_or_dropped': ('the simulator draws zeros and positive counts from one Dirichlet-'
                                                'multinomial centred on the unconditional share; there is no positive '
                                                'part of a hurdle')},
}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    p, doc = run(quick=a.quick)
    print(p)
    print(json.dumps({'primary': doc['PRIMARY_RESULT']['RESULT'], 'checks': doc['PRIMARY_RESULT']['checks'],
                      'grep': doc['P_PLAYS_GREP']['VERDICT'],
                      'atl_reproduced': doc['ATL_NO_FROZEN_V2']['resimulation']['reproduced_frozen_counts'],
                      'n_units': doc['HELD_OUT_2025']['n_units'],
                      'propagation_ratio': doc['HELD_OUT_2025']['propagation_ratio']}, indent=1))
