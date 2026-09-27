#!/usr/bin/env python3.12
"""Hierarchical, role-aware player prior. Six tiers, each used only when the one above fails.

WHAT THIS REPLACES. V0 shrank every receiver toward the mean target share of all receivers on
the slate -- 0.105, in a population where 40 of 96 held under 5%. The mean among actual
role-holders was 0.211. Established starters therefore took a 24-40% haircut and Ja'Marr Chase
came out at 7.82 against FantasyCruncher's 27.08.

THE FIX IS NOT JUST "USE HISTORY". Owner correction, and it is the important one: recency
weighting must be ROLE-AWARE, not merely season-aware. A 2023 season played as the primary
receiver is more relevant to a player's current primary role than a 2025 season spent injured
or buried, and treating both as "one season back" throws that away. So every historical
observation carries three multiplicative weights:

    recency        exponential decay in seasons back, declared half-life
    role_similarity how close that week's role was to the CURRENT role, by measured share tier
    sample         how much football that week actually contained

A five-year-old season at the same role can outweigh last year at a different one. That is
the intended behaviour, not a bug.

THE SIX TIERS, and the tier used is recorded per player so a star and a reserve can never be
shown to have come from the same pool:

    1 PLAYER_OWN_ROLE      enough weighted history AT A COMPARABLE ROLE
    2 PLAYER_OWN_OFF_ROLE  has history, but not at this role -- widened, and flagged
    3 ROLE_GROUP           same club, same position, same current role tier
    4 ARCHETYPE            league-wide cohort of the same usage SHAPE, not position label
    5 TEAM_CONTEXT         what this club historically gives to this role slot
    6 POSITIONAL_BROAD     last resort. Tagged, because this is the V0 failure mode

WHAT THIS DELIBERATELY DOES NOT DO. It does not use 2026 weeks 1-2 when fitting the prior for
a forward-chained test. The `through_season` argument exists so the prior can be built from
strictly earlier information and checked on weeks it never saw -- otherwise fixing Chase and
Lock on the one slate where the answers are already known proves nothing.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'player-prior-1'
PANEL = _REPO / 'nfl/derived/USAGE_HISTORY_2021_2026.json'
ROSTERS = 'nfl/vintage/weekly_rosters.*raw.csv.gz'
OUT = _REPO / 'nfl/derived/PLAYER_PRIOR.json'

# --- declared constants ------------------------------------------------------
RECENCY_HALFLIFE_SEASONS = 2.0
MIN_EFFECTIVE_OBS_TIER1 = 6.0
MIN_EFFECTIVE_OBS_TIER2 = 3.0
ROLE_SIMILARITY_FLOOR = 0.15
MIN_TEAM_OPP_FOR_SHARE = 8

CONSTANTS = {
    'RECENCY_HALFLIFE_SEASONS': (
        2.0, 'DECLARED. A season two years back carries half the weight of the current one. '
             'Not estimated -- a stated prior about how fast NFL roles go stale.'),
    'MIN_EFFECTIVE_OBS_TIER1': (
        6.0, 'DECLARED. Six effective player-weeks at a comparable role before the player '
             'anchors himself. Below that his own history is too thin to lead.'),
    'MIN_EFFECTIVE_OBS_TIER2': (
        3.0, 'DECLARED. Three effective weeks of ANY role before off-role history is used.'),
    'ROLE_SIMILARITY_FLOOR': (
        0.15, 'DECLARED. A week two or more role tiers away still contributes something, '
              'because a player who has been an alpha retains information even from a '
              'fringe season. It does not contribute much.'),
    'MIN_TEAM_OPP_FOR_SHARE': (
        8, 'DECLARED. A team-week with fewer than eight opportunities of a type yields a '
           'share too noisy to use, so the observation is dropped rather than trusted.'),
}

#: Role tiers by measured share of team opportunity. Declared bands, not fitted.
ROLE_BANDS = {
    'WR': ((0.22, 'ALPHA'), (0.15, 'PRIMARY'), (0.08, 'SECONDARY'),
           (0.03, 'ROTATIONAL'), (0.0, 'FRINGE')),
    'TE': ((0.18, 'ALPHA'), (0.12, 'PRIMARY'), (0.06, 'SECONDARY'),
           (0.02, 'ROTATIONAL'), (0.0, 'FRINGE')),
    'RB': ((0.55, 'ALPHA'), (0.35, 'PRIMARY'), (0.18, 'SECONDARY'),
           (0.06, 'ROTATIONAL'), (0.0, 'FRINGE')),
    'QB': ((0.70, 'ALPHA'), (0.40, 'PRIMARY'), (0.15, 'SECONDARY'),
           (0.02, 'ROTATIONAL'), (0.0, 'FRINGE')),
}
TIER_ORDER = ('FRINGE', 'ROTATIONAL', 'SECONDARY', 'PRIMARY', 'ALPHA')

TIERS = ('PLAYER_OWN_ROLE', 'PLAYER_OWN_OFF_ROLE', 'ROLE_GROUP', 'ARCHETYPE',
         'TEAM_CONTEXT', 'POSITIONAL_BROAD')

#: The quantities the prior estimates. Shares, not counts -- counts belong to team volume.
MEASURES = ('target_share', 'carry_share', 'rz_target_share', 'rz_carry_share',
            'gl_carry_share', 'yards_per_target', 'yards_per_carry', 'catch_rate',
            'td_per_rz_opp', 'pass_attempt_share', 'yards_per_attempt', 'completion_rate')


def _band(pos, share):
    for cut, name in ROLE_BANDS.get(pos, ROLE_BANDS['WR']):
        if share >= cut:
            return name
    return 'FRINGE'


def _role_similarity(a, b):
    """1.0 for the same tier, decaying with tier distance, never below the floor."""
    try:
        d = abs(TIER_ORDER.index(a) - TIER_ORDER.index(b))
    except ValueError:
        return ROLE_SIMILARITY_FLOOR
    return max(ROLE_SIMILARITY_FLOOR, 1.0 - 0.32 * d)


def _recency(seasons_back):
    return 0.5 ** (seasons_back / RECENCY_HALFLIFE_SEASONS)


def _observations(panel, gsis, pos, forecast_season, through_season):
    """Every usable historical player-week, with its measures and weights.

    The denominator is THAT PLAYER'S OWN CLUB for THAT WEEK, read from the team recorded on
    the player-week row. An earlier build had no team on the row and divided by a
    league-median team-week, which produced a pass-attempt share of 1.0259 -- impossible, not
    approximate. A share divided by the wrong denominator is not a rounding problem.
    """
    out = []
    seasons = (panel['players'].get(gsis) or {})
    for s_str, weeks in seasons.items():
        s = int(s_str)
        if s > through_season:
            continue
        for w_str, d in weeks.items():
            club = d.get('team')
            if not club:
                continue
            t = ((panel['teams'].get(club) or {}).get(s_str) or {}).get(w_str)
            if not t:
                continue
            tt, tc = t.get('targets') or 0, t.get('rush_attempts') or 0
            tpa, trz = t.get('pass_attempts') or 0, t.get('rz_plays') or 0
            tgl = t.get('gl_plays') or 0
            m = {}
            if tt >= MIN_TEAM_OPP_FOR_SHARE:
                m['target_share'] = (d['targets'] or 0) / tt
                if trz:
                    m['rz_target_share'] = (d['rz_targets'] or 0) / trz
            if tc >= MIN_TEAM_OPP_FOR_SHARE:
                m['carry_share'] = (d['carries'] or 0) / tc
                if trz:
                    m['rz_carry_share'] = (d['rz_carries'] or 0) / trz
                if tgl:
                    m['gl_carry_share'] = (d['gl_carries'] or 0) / tgl
            if tpa >= MIN_TEAM_OPP_FOR_SHARE:
                m['pass_attempt_share'] = (d['pass_attempts'] or 0) / tpa
            if (d['targets'] or 0) >= 2:
                m['yards_per_target'] = (d['rec_yards'] or 0.0) / d['targets']
                m['catch_rate'] = (d['receptions'] or 0) / d['targets']
            if (d['carries'] or 0) >= 3:
                m['yards_per_carry'] = (d['rush_yards'] or 0.0) / d['carries']
            if (d['pass_attempts'] or 0) >= 5:
                m['yards_per_attempt'] = (d['pass_yards'] or 0.0) / d['pass_attempts']
                m['completion_rate'] = (d['completions'] or 0) / d['pass_attempts']
            rz_opp = (d['rz_targets'] or 0) + (d['rz_carries'] or 0)
            if rz_opp >= 1:
                m['td_per_rz_opp'] = ((d['rec_td'] or 0) + (d['rush_td'] or 0)) / rz_opp
            if not m:
                continue
            if pos == 'RB':
                denom = tc + tt
                share = ((d['carries'] or 0) + (d['targets'] or 0)) / denom if denom else 0.0
            elif pos == 'QB':
                share = (d['pass_attempts'] or 0) / tpa if tpa else 0.0
            else:
                share = (d['targets'] or 0) / tt if tt else 0.0
            touches = ((d['targets'] or 0) + (d['carries'] or 0) + (d['pass_attempts'] or 0))
            out.append({'season': s, 'week': int(w_str), 'club': club,
                        'role_band': _band(pos, share), 'role_share': round(share, 4),
                        'touches': touches, 'measures': m,
                        'seasons_back': forecast_season - s})
    return out


def resolve_identity(name_wanted):
    """gsis_id from the roster blobs, never typed from memory.

    FOURTH INSTANCE OF THE SAME MISTAKE PROMPTED THIS. A demo case in an earlier version used
    00-0036442 as Tee Higgins. It is Joe Burrow, so a quarterback was scored as a wide
    receiver at alpha role and returned a 0.0 target share. Two defects filed earlier the
    same day were about exactly this habit. Identifiers are now looked up.
    """
    import csv
    import glob
    import gzip
    hits = {}
    for f in sorted(glob.glob(str(_REPO / ROSTERS))):
        with gzip.open(f, 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                nm = (r.get('full_name') or r.get('player_name') or '').strip()
                g = (r.get('gsis_id') or '').strip()
                if nm and g and nm == name_wanted:
                    hits[g] = (nm, (r.get('position') or '').strip(),
                               (r.get('team') or '').strip())
        if hits:
            break
    if len(hits) == 1:
        g, (nm, pos, team) = next(iter(hits.items()))
        return {'gsis_id': g, 'name': nm, 'position': pos, 'team': team,
                'state': 'RESOLVED'}
    return {'gsis_id': None, 'name': name_wanted, 'state': (
        'AMBIGUOUS' if hits else 'NOT_FOUND'), 'candidates': list(hits)[:5]}


def estimate(panel, gsis, pos, current_role_band, forecast_season, through_season):
    obs = _observations(panel, gsis, pos, forecast_season, through_season)
    weighted = []
    for o in obs:
        w = (_recency(o['seasons_back'])
             * _role_similarity(o['role_band'], current_role_band)
             * min(1.0, o['touches'] / 8.0))
        if w > 0:
            weighted.append((w, o))
    eff_role = sum(w for w, o in weighted
                   if _role_similarity(o['role_band'], current_role_band) >= 0.65)
    eff_all = sum(w for w, _o in weighted)

    def wmean(measure, rows):
        num = den = 0.0
        for w, o in rows:
            v = o['measures'].get(measure)
            if v is None:
                continue
            num += w * v
            den += w
        return (num / den) if den > 0 else None

    if eff_role >= MIN_EFFECTIVE_OBS_TIER1:
        tier = 'PLAYER_OWN_ROLE'
        rows = [(w, o) for w, o in weighted
                if _role_similarity(o['role_band'], current_role_band) >= 0.65]
    elif eff_all >= MIN_EFFECTIVE_OBS_TIER2:
        tier = 'PLAYER_OWN_OFF_ROLE'
        rows = weighted
    else:
        return {'tier': None, 'effective_obs_at_role': round(eff_role, 2),
                'effective_obs_any_role': round(eff_all, 2), 'n_raw_obs': len(obs),
                'measures': {}}
    return {
        'tier': tier,
        'effective_obs_at_role': round(eff_role, 2),
        'effective_obs_any_role': round(eff_all, 2),
        'n_raw_obs': len(obs),
        'n_seasons': len({o['season'] for _w, o in rows}),
        'seasons_used': sorted({o['season'] for _w, o in rows}),
        'season_weight': {str(s): round(sum(w for w, o in rows if o['season'] == s), 3)
                          for s in sorted({o['season'] for _w, o in rows})},
        'role_bands_seen': dict(collections.Counter(o['role_band'] for _w, o in rows)),
        'current_role_band': current_role_band,
        'mean_role_similarity': round(statistics.fmean(
            [_role_similarity(o['role_band'], current_role_band) for _w, o in rows]), 3),
        'measures': {m: (round(v, 5) if (v := wmean(m, rows)) is not None else None)
                     for m in MEASURES},
        'confidence': ('HIGH' if eff_role >= 2 * MIN_EFFECTIVE_OBS_TIER1 else
                       'MEDIUM' if tier == 'PLAYER_OWN_ROLE' else 'LOW'),
    }


def _cohort(panel, pos, role_band, forecast_season, through_season,
            club=None, exclude=None):
    """Weighted observations pooled across players, for tiers 3 to 6.

    The pooling rule is what separates these tiers from V0's failure. V0 averaged EVERY
    player at a position, a population where 40 of 96 receivers held under a 5% target share,
    so the mean described a reserve. Here a cohort is always restricted to observations AT THE
    ROLE BEING ASKED ABOUT, so a starter is compared with starters.
    """
    rows = []
    for gsis, seasons in panel['players'].items():
        if exclude and gsis == exclude:
            continue
        for o in _observations(panel, gsis, pos, forecast_season, through_season):
            if club and o['club'] != club:
                continue
            sim = _role_similarity(o['role_band'], role_band)
            if sim < 0.65:
                continue
            w = _recency(o['seasons_back']) * sim * min(1.0, o['touches'] / 8.0)
            if w > 0:
                rows.append((w, o))
    return rows


def _wmean(measure, rows):
    num = den = 0.0
    for w, o in rows:
        v = o['measures'].get(measure)
        if v is None:
            continue
        num += w * v
        den += w
    return (num / den) if den > 0 else None


_COHORT_CACHE: dict = {}


def cohort_estimate(panel, pos, role_band, forecast_season, through_season,
                    club=None, exclude=None, tier='ROLE_GROUP'):
    key = (pos, role_band, forecast_season, through_season, club)
    if key not in _COHORT_CACHE:
        _COHORT_CACHE[key] = _cohort(panel, pos, role_band, forecast_season,
                                     through_season, club=club)
    rows = [(w, o) for w, o in _COHORT_CACHE[key]
            if not (exclude and o.get('_g') == exclude)]
    eff = sum(w for w, _o in rows)
    if eff < MIN_EFFECTIVE_OBS_TIER2:
        return None
    return {
        'tier': tier, 'effective_obs_at_role': round(eff, 2),
        'n_raw_obs': len(rows), 'current_role_band': role_band,
        'cohort_club': club,
        'n_players_pooled': len({(o['club'], o['season'], o['week']) for _w, o in rows}),
        'seasons_used': sorted({o['season'] for _w, o in rows}),
        'mean_role_similarity': round(statistics.fmean(
            [_role_similarity(o['role_band'], role_band) for _w, o in rows]), 3),
        'measures': {m: (round(v, 5) if (v := _wmean(m, rows)) is not None else None)
                     for m in MEASURES},
        'confidence': 'LOW',
        'POOLED_NOT_PLAYER': (
            'this is a cohort of other players at the same role, not this player. It is used '
            'because his own history is too thin, and it is restricted to the role asked '
            'about so a starter is never averaged with reserves.'),
    }


def hierarchical(panel, gsis, pos, role_band, forecast_season, through_season,
                 club=None):
    """The full ladder. Returns the first tier with support, and what it skipped."""
    tried = []
    own = estimate(panel, gsis, pos, role_band, forecast_season, through_season)
    tried.append({'tier': 'PLAYER_OWN_ROLE/OFF_ROLE',
                  'supported': bool(own['tier']),
                  'effective_obs_at_role': own['effective_obs_at_role'],
                  'effective_obs_any_role': own.get('effective_obs_any_role')})
    if own['tier']:
        own['ladder'] = tried
        return own
    for tier, kwargs in (('ROLE_GROUP', {'club': club}),
                         ('ARCHETYPE', {}),
                         ('TEAM_CONTEXT', {'club': club}),
                         ('POSITIONAL_BROAD', {})):
        band = role_band if tier != 'POSITIONAL_BROAD' else role_band
        e = cohort_estimate(panel, pos, band, forecast_season, through_season,
                            tier=tier, **kwargs)
        tried.append({'tier': tier, 'supported': bool(e),
                      'effective_obs_at_role': (e or {}).get('effective_obs_at_role', 0.0)})
        if e:
            e['ladder'] = tried
            e['fallback_reason'] = (
                f'player own history gave only {own["effective_obs_at_role"]} effective '
                f'observations at {role_band}, below the {MIN_EFFECTIVE_OBS_TIER1} required')
            return e
    return {'tier': 'PRIOR_UNAVAILABLE', 'ladder': tried, 'measures': {},
            'why': ('no tier had support, including the broad positional cohort. This is a '
                    'state, not a zero, and the player must be projected as UNAVAILABLE '
                    'rather than given a number.')}


def load_panel():
    if not PANEL.exists():
        return Outcome.blocked('USAGE_PANEL_ABSENT', f'{PANEL.name} not built',
                               cause=Cause.DATA)
    return Outcome.ok('PANEL_LOADED', json.loads(PANEL.read_text()), 'panel read')


def main() -> int:
    r = load_panel()
    print(r)
    if r.state.value != 'PASS':
        return 1
    panel = r.value
    print(f"  {panel['n_players']} players, {panel['n_teams']} teams, "
          f"seasons {panel['seasons']}")
    # every identity resolved by lookup, none typed
    wanted = [("Ja'Marr Chase", 'WR', 'ALPHA', 'established star'),
              ('Tee Higgins', 'WR', 'ALPHA', 'established star'),
              ('Rashee Rice', 'WR', 'PRIMARY', 'established star'),
              ("De'Von Achane", 'RB', 'ALPHA', 'committee back'),
              ('Aaron Rodgers', 'QB', 'ALPHA', 'declining veteran'),
              ('Drew Lock', 'QB', 'ALPHA', 'backup asked about a starter role'),
              ('Drew Lock', 'QB', 'FRINGE', 'backup asked about a backup role'),
              ('Brycen Tremayne', 'WR', 'SECONDARY', 'thin-history receiver'),
              ('Jaylen Warren', 'RB', 'PRIMARY', 'promoted back')]
    print(f"\n{'player':20s} {'pos':4s} {'askedRole':10s} {'tier':22s} {'effR':>6s} "
          f"{'simil':>6s} {'share':>8s} {'conf':8s} note")
    for name, pos, band, note in wanted:
        ident = resolve_identity(name)
        if ident['state'] != 'RESOLVED':
            print(f"{name:20s} {pos:4s} {band:10s} IDENTITY_{ident['state']}")
            continue
        e = hierarchical(panel, ident['gsis_id'], pos, band, 2026, 2025,
                         club=ident.get('team'))
        if e['tier'] in (None, 'PRIOR_UNAVAILABLE'):
            print(f"{name:20s} {pos:4s} {band:10s} {'PRIOR_UNAVAILABLE':22s} "
                  f"{'':>6s} {'':>6s} {'':>8s} {'':8s} {note}")
            continue
        m = e['measures']
        key = (m.get('carry_share') if pos == 'RB' else
               m.get('pass_attempt_share') if pos == 'QB' else m.get('target_share'))
        ks = f'{key:.4f}' if key is not None else 'None'
        flag = '  <-- IMPOSSIBLE' if (key or 0) > 1.0 else ''
        print(f"{name:20s} {pos:4s} {band:10s} {e['tier']:22s} "
              f"{e['effective_obs_at_role']:6.1f} {e['mean_role_similarity']:6.2f} "
              f"{ks:>8s} {e['confidence']:8s} {note}{flag}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
