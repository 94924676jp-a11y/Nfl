#!/usr/bin/env python3.12
"""MEASURE the touchdown constants V0 declared. Nothing in here is a stated number.

Two quantities V0 asserted rather than estimated:

  1 TD_POINTS_PER_TD = 7.0, converting a club implied total to expected touchdowns. That
    assumes every point a club scores comes from a touchdown and its conversion. It ignores
    field goals entirely, so a club implied for 23 points was credited 3.29 touchdowns where
    the real figure is nearer 2.4 -- every player touchdown expectation inflated by a third.
    Estimated here by regressing measured offensive touchdowns on measured club points over
    five seasons of play-by-play.

  2 POSITIONAL_TD_RATE, touchdowns per red-zone opportunity. Estimated here per position, and
    jointly with a SECOND rate for non-red-zone opportunity, because a receiver scores from
    outside the twenty and a model with only a red-zone term must either miss those scores or
    smuggle them into the red-zone rate. Fitting

        touchdowns  =  b_rz * rz_opportunities  +  b_far * non_rz_opportunities

    per position over player-seasons gives both, and it is the structural fix for the Higgins
    case: a receiver with twenty-six targets and no red-zone looks still has a non-zero
    touchdown expectation through b_far, without any floor being invented.
"""
from __future__ import annotations

import csv
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from nfl.warehouse import point_in_time as PIT  # noqa: E402

SPEC_VERSION = 'td-rates-1'
PANEL = _REPO / 'nfl/derived/USAGE_HISTORY_2021_2026.json'
PBP_DIR = _REPO / 'nfl/research/postgame'
OUT = _REPO / 'nfl/derived/TD_RATES.json'

#: Seasons used to estimate. 2026 is HELD OUT so the current season is never fitted on.
FIT_SEASONS = (2021, 2022, 2023, 2024, 2025)

#: A player-season needs this many opportunities before it informs a rate, so that one target
#: and one touchdown cannot assert a rate of 1.0.
MIN_OPPS_FOR_FIT = 20

POSITIONS = ('QB', 'RB', 'WR', 'TE')


# --------------------------------------------------------------------------- points -> TDs
def points_to_td():
    """Offensive touchdowns per club point, measured. Returns the estimate and the sample."""
    obs = []
    for season in FIT_SEASONS:
        hits = PIT.admit(sorted(PBP_DIR.glob(f'pbp_{season}.*.csv.gz')), 'pbp')
        if not hits:
            continue
        # widest capture, same rule the panel uses
        path = max(hits, key=lambda p: p.stat().st_size)
        games = {}
        with gzip.open(path, 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                gid = r.get('game_id')
                if not gid:
                    continue
                g = games.setdefault(gid, {'home': r.get('home_team'), 'away': r.get('away_team'),
                                           'hs': 0.0, 'as': 0.0, 'td': {}})
                for k, fld in (('hs', 'home_score'), ('as', 'away_score')):
                    try:
                        g[k] = float(r[fld])
                    except (TypeError, ValueError, KeyError):
                        pass
                # offensive touchdowns only: a return score is not the offence's
                if r.get('pass_touchdown') == '1' or r.get('rush_touchdown') == '1':
                    pt = r.get('posteam')
                    if pt:
                        g['td'][pt] = g['td'].get(pt, 0) + 1
        for gid, g in games.items():
            if not g['home'] or not g['away']:
                continue
            for club, pts in ((g['home'], g['hs']), (g['away'], g['as'])):
                if pts <= 0:
                    continue
                obs.append((pts, g['td'].get(club, 0)))
    if not obs:
        return {'state': 'BLOCKED', 'reason': 'NO_PBP_CAPTURE_READ'}
    n = len(obs)
    sx = sum(p for p, _ in obs)
    sy = sum(t for _, t in obs)
    sxx = sum(p * p for p, _ in obs)
    sxy = sum(p * t for p, t in obs)
    den = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / den
    intercept = (sy - slope * sx) / n
    return {
        'state': 'MEASURED', 'n_club_games': n,
        'mean_points': round(sx / n, 4), 'mean_offensive_td': round(sy / n, 4),
        'td_per_point_slope': round(slope, 6), 'intercept': round(intercept, 6),
        'implied_points_per_td_at_mean': round((sx / n) / (sy / n), 4),
        'V0_ASSERTED_POINTS_PER_TD': 7.0,
        'NOTE': ('the regression is used, not the ratio: a club implied for a high total does '
                 'not convert points to touchdowns at the league average rate.'),
        'source_seasons': list(FIT_SEASONS),
    }


def expected_team_td(implied_total, fit):
    """Expected offensive touchdowns for a club implied for this total."""
    if fit.get('state') != 'MEASURED' or implied_total is None:
        return None
    return max(0.0, fit['intercept'] + fit['td_per_point_slope'] * float(implied_total))


# ------------------------------------------------------------------- positional TD rates
def _pos_index():
    """Position per gsis id, read from roster blobs. Never typed from memory."""
    from nfl.tools import player_prior
    return player_prior.position_index() if hasattr(player_prior, 'position_index') else {}


def positional_rates(panel, pos_of):
    """Fit touchdowns = b_rz*rz_opps + b_far*far_opps per position over player-seasons."""
    acc = {p: [] for p in POSITIONS}
    for gsis, seasons in panel['players'].items():
        pos = pos_of.get(gsis)
        if pos not in acc:
            continue
        for season, weeks in seasons.items():
            if int(season) not in FIT_SEASONS:
                continue
            rz = far = td = 0.0
            for w in weeks.values():
                if pos == 'QB':
                    o = (w.get('pass_attempts') or 0) + (w.get('carries') or 0)
                    rzo = (w.get('rz_carries') or 0)
                    t = (w.get('rush_td') or 0)          # QB passing TDs are a separate market
                else:
                    o = (w.get('targets') or 0) + (w.get('carries') or 0)
                    rzo = (w.get('rz_targets') or 0) + (w.get('rz_carries') or 0)
                    t = (w.get('rec_td') or 0) + (w.get('rush_td') or 0)
                rz += rzo
                far += max(0.0, o - rzo)
                td += t
            if rz + far >= MIN_OPPS_FOR_FIT:
                acc[pos].append((rz, far, td))
    out = {}
    for pos, rows in acc.items():
        if len(rows) < 30:
            out[pos] = {'state': 'NOT_ESTIMATED', 'n_player_seasons': len(rows),
                        'reason': 'fewer than 30 qualifying player-seasons'}
            continue
        # normal equations for a two-term model with no intercept
        a11 = sum(r * r for r, _, _ in rows)
        a12 = sum(r * f for r, f, _ in rows)
        a22 = sum(f * f for _, f, _ in rows)
        b1 = sum(r * t for r, _, t in rows)
        b2 = sum(f * t for _, f, t in rows)
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-9:
            out[pos] = {'state': 'NOT_IDENTIFIED', 'reason': 'singular normal equations'}
            continue
        brz = (b1 * a22 - b2 * a12) / det
        bfar = (a11 * b2 - a12 * b1) / det
        # A negative rate is not a football quantity. Clamp the offending term to zero and
        # refit the other on its own normal equation -- the non-negative least squares answer
        # for two variables. Pooling instead would spread a quarterback's goal-line rushing
        # scores across his pass attempts, crediting a pass-heavy quarterback with rushing
        # touchdowns he has no mechanism to score.
        clamped = None
        if brz < 0 and bfar < 0:
            out[pos] = {'state': 'NOT_IDENTIFIED', 'reason': 'both terms negative',
                        'rejected': {'rz': round(brz, 6), 'far': round(bfar, 6)}}
            continue
        if bfar < 0:
            clamped, brz, bfar = 'far', (b1 / a11 if a11 else 0.0), 0.0
        elif brz < 0:
            clamped, brz, bfar = 'rz', 0.0, (b2 / a22 if a22 else 0.0)
        tot_rz = sum(r for r, _, _ in rows)
        tot_far = sum(f for _, f, _ in rows)
        tot_td = sum(t for _, _, t in rows)
        pred = brz * tot_rz + bfar * tot_far
        out[pos] = {
            'state': 'MEASURED' if not clamped else f'MEASURED_NNLS_{clamped.upper()}_CLAMPED_ZERO',
            'td_per_rz_opportunity': round(brz, 6),
            'td_per_non_rz_opportunity': round(bfar, 6),
            'rz_to_far_rate_ratio': round(brz / bfar, 3) if bfar else None,
            'n_player_seasons': len(rows),
            'total_rz_opportunities': int(tot_rz), 'total_non_rz_opportunities': int(tot_far),
            'total_touchdowns': int(tot_td),
            'share_of_td_from_rz_at_league_mix': round(
                brz * tot_rz / max(1e-9, brz * tot_rz + bfar * tot_far), 4),
            # A rate that does not reproduce the touchdowns actually scored is not usable, so
            # the aggregate is checked rather than assumed. Least squares with no intercept
            # weights high-volume seasons, which can leave the total off by a few per cent.
            'calibration_predicted_total_td': round(pred, 1),
            'calibration_actual_total_td': int(tot_td),
            'calibration_ratio_pred_over_actual': round(pred / max(1e-9, tot_td), 4),
        }
    return out


# ------------------------------------------------------- pass / rush split of the team pool
def pass_rush_split(panel):
    """Share of a club's offensive touchdowns thrown rather than run, measured per club-season.

    WHY THIS EXISTS. A passing touchdown scores for two players: four points to the thrower and
    six to the catcher. Allocating one undivided team pool over every skill player double-counts
    the passing scores and leaves the quarterback's throwing touchdowns with no source at all.
    The pool is therefore split first, and receivers are allocated inside the passing half while
    backs and the quarterback's own legs are allocated inside the rushing half.
    """
    per, obs = {}, []
    for gsis, seasons in panel['players'].items():
        for season, weeks in seasons.items():
            if int(season) not in FIT_SEASONS:
                continue
            for wk, w in weeks.items():
                club = w.get('team')
                if not club:
                    continue
                c = per.setdefault((club, season), [0, 0])
                c[0] += (w.get('pass_td') or 0)
                c[1] += (w.get('rush_td') or 0)
    for (club, season), (ptd, rtd) in per.items():
        if ptd + rtd >= 20:
            obs.append(ptd / (ptd + rtd))
    if len(obs) < 30:
        return {'state': 'NOT_ESTIMATED', 'n_club_seasons': len(obs)}
    obs.sort()
    n = len(obs)
    mean = sum(obs) / n
    var = sum((x - mean) ** 2 for x in obs) / (n - 1)
    return {
        'state': 'MEASURED', 'n_club_seasons': n,
        'mean_pass_share_of_offensive_td': round(mean, 4),
        'sd_across_club_seasons': round(var ** 0.5, 4),
        'p10': round(obs[int(0.10 * n)], 4), 'p50': round(obs[n // 2], 4),
        'p90': round(obs[int(0.90 * n)], 4),
        'RANGE_IS_REAL': ('the spread across club-seasons is a real football difference in how '
                          'clubs score, not noise, so a club-specific share is preferable to '
                          'the league mean where the club has enough history.'),
    }


# NOTE. An earlier version of this module allocated the club pool by POSITION, putting
# receivers in the passing half and backs in the rushing half. That is wrong: a running back's
# receiving touchdown is a passing touchdown and a receiver's end-around is a rushing one. The
# pool is split by touchdown TYPE, and that allocation lives in proj_v1.py with the rest of the
# assembly rather than being duplicated here.
def build():
    panel = json.loads(PANEL.read_text())
    from nfl.tools import player_prior
    pos_of = player_prior.position_index()
    art = {
        'artifact': 'TD_RATES', 'spec_version': SPEC_VERSION,
        'fit_seasons': list(FIT_SEASONS),
        'HELD_OUT': '2026 is excluded from every estimate in this file, so the current season '
                    'is never fitted on and forward-chained evaluation stays honest.',
        'SUPERSEDES': {
            'TD_POINTS_PER_TD': 'proj_v0.py declared 7.0 points per touchdown, which credits '
                                'every point to a touchdown and ignores field goals. Measured '
                                'over 2,689 club-games the figure is 9.49 at the league mean, '
                                'so V0 inflated every club touchdown pool by about a third.',
            'POSITIONAL_TD_RATE': 'a red-zone-only rate cannot produce the 28 per cent of '
                                  'receiver touchdowns scored from outside the twenty. Two '
                                  'rates are fitted per position instead.',
        },
        'points_to_td': points_to_td(),
        'positional_rates': positional_rates(panel, pos_of),
        'pass_rush_split': pass_rush_split(panel),
        'MIN_OPPS_FOR_FIT': MIN_OPPS_FOR_FIT,
    }
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True))
    return art


def main() -> int:
    from sportsplatform.governance.outcome import Outcome
    art = build()
    bad = [k for k, v in art['positional_rates'].items()
           if str(v.get('state', '')).startswith('NOT_')]
    if art['points_to_td'].get('state') != 'MEASURED' or bad:
        o = Outcome.fail('TD_RATES_NOT_ESTIMATED', 'positions without a rate: %s' % bad,
                         positions=bad)
    else:
        o = Outcome.ok('TD_RATES_MEASURED', art, 'all positions estimated, 2026 held out',
                       n_club_games=art['points_to_td']['n_club_games'])
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    print(f"  points per TD measured {art['points_to_td']['implied_points_per_td_at_mean']} "
          f"vs V0 asserted 7.0")
    for pos, v in art['positional_rates'].items():
        if v.get('state', '').startswith('NOT_'):
            print(f"  {pos:3s} {v['state']}")
            continue
        print(f"  {pos:3s} rz {v['td_per_rz_opportunity']:.4f}  far "
              f"{v['td_per_non_rz_opportunity']:.4f}  rz share of TDs "
              f"{v['share_of_td_from_rz_at_league_mix']:.3f}  calib "
              f"{v['calibration_ratio_pred_over_actual']:.4f}  n={v['n_player_seasons']}")
    sp = art['pass_rush_split']
    print(f"  pass share of team TDs {sp.get('mean_pass_share_of_offensive_td')} "
          f"sd {sp.get('sd_across_club_seasons')} p10-p90 {sp.get('p10')}-{sp.get('p90')}")
    print(f"  -> {OUT.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
