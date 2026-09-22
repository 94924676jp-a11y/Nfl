"""Stage 6, rebuilt: the opportunity centre, from evidence that includes
the current season.

WHAT WAS WRONG

`p4c_params.class_point_forecast` computed the centre from
`p4c_build.load_panel()`, which spans ordinals 202001-202518 and contains ZERO
2026 rows. A week-2 2026 forecast therefore set every player's expected share
from 2025-and-older football. Measured on 2026_02_NYG_LA: Tyrone Tracy Jr.
carried a centre of 0.4758 -- his 2025 lead-back share, held almost unchanged
because 32 prior rows drove the shrinkage weight to 0.977 -- while Cam
Skattebo's 18 carries and 61% snap share from 2026 week 1 never entered the
computation at all.

WHY THE FIX IS NOT `panel + 2026 rows`

The old ewma weights by POSITION IN A LIST. Observation n-1 gets
`0.5 ** (1/3)` whatever the gap in time, so a week-18 row from last season and
a week-1 row from this one are adjacent in the list and treated as adjacent in
football. Concatenating 2026 onto that list would inherit exactly that: it
would make the season boundary invisible, and it would make a player's first
game at a new club look like a continuation of his last game at the old one.

So the weight is rebuilt with the two discontinuities the flat list cannot
see, and both were ESTIMATED rather than chosen -- forward-chained on
2022-2025, selection rule fixed in advance in
`nfl/research/cs2/PREREGISTRATION_STAGE2.md`, parameters in
`nfl/research/cs2/STAGE2_FIT.json`:

    recency        w *= lam ** age                   (age in observations)
    season         w *= season_decay ** seasons_back
    team change    w *= team_change_discount if the row is at another club
    opportunity    w *= opportunity ** opportunity_exponent

CURRENT-SEASON EVIDENCE NEEDS NO SPECIAL CASE, AND THAT IS THE POINT.

There is no "latest game wins" rule here and no branch that privileges 2026.
A current-season observation is simply the most recent one, so its recency
weight is `lam ** 0 = 1` and its season decay is `season_decay ** 0 = 1`. It
dominates a stale prior because it is not stale, arithmetically, under the
same formula that governs every other row. One game does not erase thirty-two:
it outweighs each of them individually and is outweighed by their sum until
the decay has done its work, which is the behaviour the formula gives for free
and a threshold rule would have had to fake.

THE GOVERNOR REACHES THE GENERATOR

`role_state` could previously refuse a role while this stage independently
built a confident workload out of the depth rank. That is closed: when the
governed role is refused or uncertain, THE DEPTH ANCHOR IS NOT AVAILABLE. The
centre falls to a measured cold-start floor and the row is marked, so the
audit and the gate both see it. A depth listing cannot manufacture a workload
that the governing module has declined to support.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import statistics
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'opportunity-centre-1'

FIT_PATH = 'nfl/research/cs2/STAGE2_FIT.json'
COLD_START_PATH = 'nfl/research/cs2/COLD_START_FLOOR.json'

# --- the evidence hierarchy, in descending authority ----------------------
E_CURRENT_SEASON = 'CURRENT_SEASON_MEASURED'
E_RECENT = 'RECENT_MEASURED'
E_CURRENT_ROLE = 'CURRENT_GAME_ROLE'
E_PRIOR_SEASON = 'PRIOR_SEASON_MEASURED'
E_CAREER = 'CAREER_HISTORY'
E_DEPTH = 'DEPTH_DERIVED_PRIOR'
E_COLD_START = 'COLD_START_PRIOR'
HIERARCHY = (E_CURRENT_SEASON, E_RECENT, E_CURRENT_ROLE, E_PRIOR_SEASON,
             E_CAREER, E_DEPTH, E_COLD_START)

# --- how a row's centre was arrived at ------------------------------------
B_EVIDENCE_SUPPORTED = 'EVIDENCE_SUPPORTED'
B_HISTORICAL_SUPPORTED = 'HISTORICAL_SUPPORTED'
B_DECLARED_STARTER_THIN = 'DECLARED_STARTER_THIN_HISTORY'
B_DEPTH_PRIOR = 'DEPTH_PRIOR'
B_GOVERNED_ROLE_REFUSED = 'GOVERNED_ROLE_REFUSED_NO_DEPTH_ANCHOR'
B_COLD_START_FLOOR = 'COLD_START_FLOOR'
BASES = (B_EVIDENCE_SUPPORTED, B_HISTORICAL_SUPPORTED,
         B_DECLARED_STARTER_THIN, B_DEPTH_PRIOR, B_GOVERNED_ROLE_REFUSED,
         B_COLD_START_FLOOR)

#: Governed role states that REFUSE workload support. Taken from role_state by
#: name rather than by value so the two cannot drift apart silently.
ROLE_REFUSED = ('ROLE_UNSUPPORTED',)
ROLE_UNCERTAIN = 'ROLE_UNCERTAIN'


@dataclass
class Observation:
    """One measured player-game, with everything the weight needs."""
    season: int
    week: Optional[int]
    team: Optional[str]
    share: float
    opportunity: float
    source: str                      # 'current_season' | 'historical_panel'
    ord: Optional[int] = None

    def tier(self, target_season: int) -> str:
        if self.source == 'current_season':
            return E_CURRENT_SEASON
        if int(self.season) == int(target_season) - 1:
            return E_PRIOR_SEASON
        return E_CAREER


@dataclass
class Attribution:
    """The machine-readable decomposition Stage 6 now emits per player."""
    gsis_id: str
    position: Optional[str]
    team: Optional[str]
    target: str                      # 'carries' | 'targets'
    centre: float = 0.0
    basis: str = B_COLD_START_FLOOR
    evidence_grade: str = E_COLD_START
    contributions: Dict[str, float] = field(default_factory=dict)
    n_observations: Dict[str, int] = field(default_factory=dict)
    n_effective: float = 0.0
    n_effective_adjusted: float = 0.0
    retention: float = 1.0
    shrinkage_weight: float = 0.0
    shrinkage_target_value: Optional[float] = None
    shrinkage_target_name: Optional[str] = None
    weighted_evidence_mean: Optional[float] = None
    governed_role: Optional[str] = None
    governed_role_support: Optional[str] = None
    depth_rank: Optional[int] = None
    depth_anchor_available: bool = True
    team_changed: bool = False
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'gsis_id': self.gsis_id, 'position': self.position,
            'team': self.team, 'target': self.target,
            'centre': self.centre, 'basis': self.basis,
            'evidence_grade': self.evidence_grade,
            'contributions': {k: round(v, 8)
                              for k, v in sorted(self.contributions.items())},
            'n_observations': dict(sorted(self.n_observations.items())),
            'n_effective': round(self.n_effective, 6),
            'n_effective_adjusted': round(self.n_effective_adjusted, 6),
            'retention': round(self.retention, 6),
            'shrinkage_weight': round(self.shrinkage_weight, 6),
            'shrinkage_target_value': self.shrinkage_target_value,
            'shrinkage_target_name': self.shrinkage_target_name,
            'weighted_evidence_mean': self.weighted_evidence_mean,
            'governed_role': self.governed_role,
            'governed_role_support': self.governed_role_support,
            'depth_rank': self.depth_rank,
            'depth_anchor_available': self.depth_anchor_available,
            'team_changed': self.team_changed,
            'notes': self.notes,
            'spec_version': SPEC_VERSION,
        }


# --------------------------------------------------------------------------
# governed parameters
# --------------------------------------------------------------------------
def load_params(target: str, *, fit_path=None, cold_path=None) -> Outcome:
    """The fitted weights and the measured cold-start floor, or a refusal.

    Nothing here has a default. A missing fit is BLOCKED, because a
    convenient default is exactly the silent constant this project logs as a
    bug.
    """
    fp = pathlib.Path(fit_path or (_REPO / FIT_PATH))
    cp = pathlib.Path(cold_path or (_REPO / COLD_START_PATH))
    if not fp.exists():
        return Outcome.blocked(
            'STAGE2_FIT_ABSENT',
            f'{fp} does not exist, so the recency, season-boundary, '
            f'team-change and opportunity weights have not been estimated. '
            f'Stage 6 refuses rather than choosing them.', cause=Cause.DATA)
    if not cp.exists():
        return Outcome.blocked(
            'COLD_START_FLOOR_ABSENT',
            f'{cp} does not exist, so there is no measured value for a player '
            f'with no observations anywhere.', cause=Cause.DATA)
    fit = json.loads(fp.read_text())
    cold = json.loads(cp.read_text())
    f = (fit.get('fits') or {}).get(target)
    if not f or not f.get('chosen'):
        return Outcome.blocked(
            'STAGE2_FIT_MISSING_TARGET',
            f'{fp} carries no chosen grid point for {target!r}; it has '
            f'{sorted((fit.get("fits") or {}))}.', cause=Cause.DATA)
    g = dict(f['chosen']['grid'])
    hl = g.get('half_life')
    g['half_life'] = float('inf') if hl in ('Infinity', 'inf', None) \
        else float(hl)
    return Outcome.ok(
        'STAGE2_PARAMS_LOADED',
        {'grid': g, 'fit_mae': f['chosen'].get('mae'),
         'fit_n_rows': f.get('n_rows'), 'fit_n_players': f.get('n_players'),
         'production_today': f.get('production_today'),
         'cold_start': cold.get('floor', cold),
         'fit_spec_version': fit.get('spec_version'),
         'preregistration': fit.get('preregistration')},
        detail=f'{target}: {g}')


# --------------------------------------------------------------------------
# the centre
# --------------------------------------------------------------------------
def _weights(obs: Sequence[Observation], *, target_season: int,
             target_team: Optional[str], grid: Dict[str, Any]
             ) -> List[float]:
    hl = grid['half_life']
    lam = 0.0 if hl == float('inf') else 0.5 ** (1.0 / hl)
    sd = float(grid.get('season_decay', 1.0))
    td = float(grid.get('team_discount', 1.0))
    oe = float(grid.get('opp_exponent', 0.0))
    ws, ws_undiscounted = [], []
    # `age` counts back from the MOST RECENT observation, which is the same
    # ordering the production ewma used. Ordering is by (season, week), not by
    # arrival, so a late-added capture cannot reorder history.
    ordered = sorted(obs, key=lambda o: (int(o.season), int(o.week or 0)))
    for age, o in enumerate(reversed(ordered)):
        base = 1.0 if hl == float('inf') else lam ** age
        if oe:
            base *= max(float(o.opportunity), 0.0) ** oe
        w = base
        if sd != 1.0:
            w *= sd ** max(0, int(target_season) - int(o.season))
        if td != 1.0 and target_team and o.team and o.team != target_team:
            w *= td
        ws.append(w)
        ws_undiscounted.append(base)
    return list(reversed(ws)), list(reversed(ws_undiscounted)), ordered


def centre(gsis_id: str, *, position: Optional[str], team: Optional[str],
           target: str, target_season: int,
           observations: Sequence[Observation],
           params: Dict[str, Any],
           governed_role: Optional[str] = None,
           governed_role_support: Optional[str] = None,
           depth_rank: Optional[int] = None,
           depth_anchor: Optional[float] = None,
           shrinkage_k: Optional[float] = None,
           shrinkage_target_name: str = 'positional_mean',
           positional_mean: Optional[float] = None,
           declared_starter: bool = False) -> Attribution:
    """One player's opportunity centre, with its full decomposition."""
    grid = params['grid']
    cold = (params['cold_start'].get(position or '') or {})
    floor_key = ('carry_share_median' if target == 'carries'
                 else 'target_share_median')
    floor = float(cold.get(floor_key, 0.0))

    a = Attribution(gsis_id=gsis_id, position=position, team=team,
                    target=target, depth_rank=depth_rank,
                    governed_role=governed_role,
                    governed_role_support=governed_role_support)

    refused = (governed_role_support in ROLE_REFUSED
               or governed_role == ROLE_UNCERTAIN)
    a.depth_anchor_available = not refused
    if refused:
        a.notes.append(
            'role_state refused or could not support this role, so the '
            'depth-derived anchor is withheld: a listing may not manufacture '
            'a workload the governor declined to support')

    obs = list(observations)
    a.team_changed = bool(team and any(o.team and o.team != team for o in obs))
    by_tier = collections.Counter(o.tier(target_season) for o in obs)
    a.n_observations = dict(by_tier)

    if not obs:
        # NOTHING MEASURED ANYWHERE. The depth anchor is the only signal there
        # is, and only if the governor left it available.
        if a.depth_anchor_available and depth_anchor is not None:
            a.centre = float(depth_anchor)
            a.basis = B_DEPTH_PRIOR
            a.evidence_grade = E_DEPTH
            a.contributions = {E_DEPTH: float(depth_anchor)}
            a.shrinkage_target_name = 'depth_tier_mean'
            a.shrinkage_target_value = float(depth_anchor)
        else:
            a.centre = floor
            a.basis = (B_GOVERNED_ROLE_REFUSED if refused
                       else B_COLD_START_FLOOR)
            a.evidence_grade = E_COLD_START
            a.contributions = {E_COLD_START: floor}
            a.notes.append(
                f'measured cold-start floor for {position}/{target}: the '
                f'MEDIAN share taken by a player in his first appeared game, '
                f'over {cold.get("n")} such players in the historical panel. '
                f'Median rather than mean because the share distribution is '
                f'right-skewed and a handful of immediate lead backs would '
                f'otherwise set the floor for everyone')
        return a

    ws, ws_raw, ordered = _weights(obs, target_season=target_season,
                                   target_team=team, grid=grid)
    tot = sum(ws)
    if tot <= 0:
        a.centre = floor
        a.basis = B_COLD_START_FLOOR
        a.evidence_grade = E_COLD_START
        a.contributions = {E_COLD_START: floor}
        a.notes.append('every observation weighted to zero')
        return a

    a.weighted_evidence_mean = sum(w * o.share
                                   for w, o in zip(ws, ordered)) / tot
    # EFFECTIVE sample size, not row count. One current-season game plus
    # thirty-two heavily decayed prior ones is not thirty-three observations
    # and is not one either; this is the quantity that says how many it is
    # worth, and it is what the shrinkage responds to.
    a.n_effective = (tot ** 2) / sum(w * w for w in ws)

    # RETENTION, and it exists because the obvious design was wrong.
    #
    # The season and team-change discounts are MULTIPLICATIVE, and n_eff and
    # the weighted mean are both SCALE-INVARIANT. So for a player whose every
    # observation is at another club -- exactly the player the team-change
    # rule is for -- a uniform discount cancels and changes nothing at all.
    # Najee Harris has 71 rows, all at PIT and LAC and none at NYG; halving
    # every one of them left his centre identical.
    #
    # Retention is the fraction of evidence weight that SURVIVES the staleness
    # and context discounts. It is 1.0 for a player whose history is current
    # and at this club, and it falls toward the discount itself for a player
    # whose history is entirely old or entirely elsewhere. Scaling n_eff by it
    # makes such a player shrink harder toward the target, which is the
    # behaviour the discounts were supposed to produce.
    #
    # DECLARED, NOT FITTED, and the distinction matters: the forward-chained
    # fit selected the WEIGHTS by predictive accuracy on the weighted mean. It
    # did not evaluate this. It is a governance rule -- evidence from another
    # context is worth less, so lean harder on the prior -- stated here with
    # its reasoning rather than estimated.
    raw_tot = sum(ws_raw)
    a.retention = (tot / raw_tot) if raw_tot > 0 else 1.0
    a.n_effective_adjusted = a.n_effective * a.retention

    # Shrinkage target, and the refused case is NOT the positional mean.
    #
    # MEASURED DEFECT: shrinking a refused role toward the positional mean
    # PROMOTED the player it was supposed to withhold support from. Patrick
    # Ricard -- a blocking fullback whose role role_state refuses -- went from
    # 0.869 to 2.382 projected carries, because the average RB takes more
    # carries than he does and the mean pulled him UP. A refusal that makes a
    # player more prominent is not a refusal.
    #
    # A refused role shrinks toward the MEASURED COLD-START FLOOR instead: the
    # median share of a player nobody has established a role for, which is
    # what a refused role means. The floor can only pull a player down toward
    # a debutant's workload, never up toward a starter's.
    if a.depth_anchor_available and depth_anchor is not None:
        tgt, tname = float(depth_anchor), 'depth_tier_mean'
    elif refused:
        tgt, tname = floor, 'cold_start_floor_refused_role'
        a.notes.append(
            'a refused role shrinks toward the measured cold-start floor, '
            'not the positional mean: shrinking toward a room average can '
            'RAISE a player the governor declined to support, which is the '
            'opposite of withholding support')
    elif positional_mean is not None:
        tgt, tname = float(positional_mean), 'positional_mean'
    else:
        tgt, tname = floor, 'cold_start_floor'
    a.shrinkage_target_name, a.shrinkage_target_value = tname, tgt

    k = float(shrinkage_k if shrinkage_k is not None else 1.0)
    n_use = a.n_effective_adjusted
    w_ev = n_use / (n_use + k) if (n_use + k) else 0.0
    a.shrinkage_weight = w_ev
    a.centre = w_ev * a.weighted_evidence_mean + (1.0 - w_ev) * tgt

    # PER-TIER CONTRIBUTION, in the units of the centre, so the parts sum to
    # it. This is what the dossier reads instead of reconstructing it.
    for tier in HIERARCHY:
        a.contributions[tier] = 0.0
    for w, o in zip(ws, ordered):
        a.contributions[o.tier(target_season)] += w_ev * (w / tot) * o.share
    a.contributions[E_DEPTH if tname == 'depth_tier_mean'
                    else (E_COLD_START if tname.startswith('cold_start_floor')
                          else E_CAREER)] += (1.0 - w_ev) * tgt
    a.contributions = {k2: v for k2, v in a.contributions.items() if v}

    has_cs = by_tier.get(E_CURRENT_SEASON, 0) > 0
    if has_cs:
        a.basis = B_EVIDENCE_SUPPORTED
        a.evidence_grade = E_CURRENT_SEASON
    elif declared_starter:
        a.basis = B_DECLARED_STARTER_THIN
        a.evidence_grade = E_PRIOR_SEASON
        a.notes.append(
            'declared a starter with no measured current-season history: the '
            'centre rests on prior-season evidence, season-decayed, and the '
            'declaration is not itself treated as measurement')
    else:
        a.basis = B_HISTORICAL_SUPPORTED
        a.evidence_grade = (E_PRIOR_SEASON if by_tier.get(E_PRIOR_SEASON)
                            else E_CAREER)
    if refused:
        a.basis = B_GOVERNED_ROLE_REFUSED
    if a.team_changed:
        a.notes.append(
            f'observations at another club are discounted by '
            f'{grid.get("team_discount")}: workload share is a property of a '
            f'player IN a depth chart, not of the player alone. Efficiency '
            f'history is a different quantity and is not touched here')
    return a


# --------------------------------------------------------------------------
# batch: one call, every player, both targets
# --------------------------------------------------------------------------
def _hist_observations(panel_hist, target_key) -> Dict[str, List[Observation]]:
    out = collections.defaultdict(list)
    for pid, rows in panel_hist.items():
        for r in rows:
            out[pid].append(Observation(
                season=int(r['season']), week=int(r.get('week') or 0),
                team=r.get('team'), share=float(r[target_key]),
                opportunity=float(r.get('opportunity') or 0.0),
                source='historical_panel', ord=r.get('ord')))
    return out


def build_centres(players, *, target: str, season: int, week: int,
                  params: Dict[str, Any],
                  historical: Dict[str, List[Observation]],
                  current_season: Optional[Dict[str, List[dict]]] = None,
                  role_by_id: Optional[Dict[str, dict]] = None,
                  depth_anchor_by_id: Optional[Dict[str, float]] = None,
                  depth_rank_by_id: Optional[Dict[str, int]] = None,
                  positional_mean: Optional[Dict[str, float]] = None,
                  shrinkage_k: Optional[Dict[str, float]] = None,
                  declared_starters=None) -> Outcome:
    """Every player's centre for one class, with attribution, in one pass."""
    share_key = 'carry_share' if target == 'carries' else 'target_share'
    opp_key = 'carries' if target == 'carries' else 'targets'
    role_by_id = role_by_id or {}
    depth_anchor_by_id = depth_anchor_by_id or {}
    depth_rank_by_id = depth_rank_by_id or {}
    positional_mean = positional_mean or {}
    shrinkage_k = shrinkage_k or {}
    declared = set(declared_starters or ())

    centres: Dict[str, float] = {}
    attribution: Dict[str, Attribution] = {}
    counts = collections.Counter()
    for q in players:
        pid = q.get('gsis_id')
        pos = q.get('position')
        team = q.get('team')
        if not pid:
            continue
        obs = list(historical.get(pid) or ())
        for r in (current_season or {}).get(pid) or ():
            v = r.get(share_key)
            if v is None:
                continue
            obs.append(Observation(
                season=int(season), week=int(r.get('week') or 0),
                team=r.get('team'), share=float(v),
                opportunity=float(r.get(opp_key) or 0.0),
                source='current_season'))
        rr = role_by_id.get(pid) or {}
        a = centre(pid, position=pos, team=team, target=target,
                   target_season=int(season), observations=obs,
                   params=params,
                   governed_role=rr.get('role'),
                   governed_role_support=rr.get('role_support'),
                   depth_rank=depth_rank_by_id.get(pid),
                   depth_anchor=depth_anchor_by_id.get(pid),
                   shrinkage_k=shrinkage_k.get(pos),
                   positional_mean=positional_mean.get(pos),
                   declared_starter=pid in declared)
        centres[pid] = a.centre
        attribution[pid] = a
        counts[a.basis] += 1

    if not centres:
        return Outcome.fail(
            'OPPORTUNITY_CENTRE_EMPTY',
            f'no {target}-class player among {len(list(players))} supplied, '
            f'so no centre was produced. An empty result read as success is '
            f'the failure mode this project pays for most.',
            value={'target': target})
    n_cs = sum(1 for a in attribution.values()
               if a.n_observations.get(E_CURRENT_SEASON))
    return Outcome.ok(
        'OPPORTUNITY_CENTRES_BUILT',
        {'centre': centres, 'attribution': attribution,
         'by_basis': dict(counts),
         'n_players': len(centres),
         'n_with_current_season_evidence': n_cs,
         'params': {k: v for k, v in params.items() if k != 'cold_start'},
         'target': target, 'season': int(season), 'week': int(week),
         'spec_version': SPEC_VERSION},
        detail=f'{len(centres)} centre(s) for {target}, {n_cs} with '
               f'current-season evidence; bases {dict(counts)}')
