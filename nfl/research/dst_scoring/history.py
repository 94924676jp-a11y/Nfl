#!/usr/bin/env python3.12
"""Historical DraftKings DST and kicker scores, 2021-2025 regular season, from the repository's play-by-play.

    PYTHONPATH=<numpy/pandas> python3.12 nfl/research/dst_scoring/history.py [OUT.json]

RESEARCH ONLY (DST/K scoring audit, 2026-10-09). Reads nfl/research/postgame/pbp_{2021..2025}.*.csv.gz, writes one
JSON (default nfl/research/dst_scoring/DST_K_HISTORY_2021_2025.json). It fits nothing: every number is a count or a
mean of counts. Two products:

  1. The historical distribution of DK DST and DK kicker points per club-game (mean, sd, P(<=0), P(>=15), integer
     share), scored with nfl/product/dk_scoring.py -- the same adapter the postgame grader uses.
  2. The measured inputs the shadow scorer (nfl/sim/dst_k_event_scoring.py) reads: per points-allowed band, the
     ratio of each DST component's mean to its all-games mean, and each component's within-club-season
     variance-to-mean ratio (its overdispersion relative to Poisson).

DEFINITIONS (stated because each one has been derived wrongly somewhere in this repository):
  sacks             sack == 1 and defteam == club
  interceptions     interception == 1 and defteam == club
  fumble recoveries fumble_recovery_1_team == club and fumbled_1_team != club (offence AND special teams,
                    which is what DK credits; postgame's fumble_lost & defteam misses special-teams muffs)
  def/return TD     touchdown == 1 and td_team == club and (td_team == defteam or return_touchdown == 1). The
                    second clause is needed because on a kickoff nflfastR makes the RECEIVING club posteam, so a
                    kick-return TD has td_team == posteam (nfl/sim/dst.py's td_team == defteam misses it)
  safeties          safety == 1 and defteam == club
  blocked kicks     (punt_blocked == 1 or field_goal_result == 'blocked' or extra_point_result == 'blocked')
                    and defteam == club
  2-pt/XP returns   (defensive_two_point_conv == 1 or defensive_extra_point_conv == 1) and defteam == club
  points allowed    RULE A, the repository's grading rule (nfl/postgame/showdown_postgame.py dk_A): the opponent's
                    final score. RULE B (dk_B): minus 6 per opponent return/defensive TD. Both are reported.
  kicker            rule A (nfl/tools/kicker_world.MISS_RULE): FG <40 +3, 40-49 +4, 50+ +5 by kick_distance,
                    XP made +1, a miss scores 0. Per club-game (the club's kickers summed).
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import dk_scoring as DK  # noqa: E402

SEASONS = (2021, 2022, 2023, 2024, 2025)
OUT = _REPO / 'nfl/research/dst_scoring/DST_K_HISTORY_2021_2025.json'
#: The same points-allowed conditioning bands nfl/sim/dst.py measures its tuples in (CONDITIONING_BANDS), so the
#: shadow scorer conditions on the axis the incumbent already uses. Lower bound inclusive, upper exclusive, on
#: INTEGER points allowed.
BANDS = ((0, 10), (10, 17), (17, 24), (24, 31), (31, 10 ** 6))
COMPONENTS = ('sacks', 'ints', 'fumble_recoveries', 'tds', 'safeties', 'blocked_kicks', 'two_pt_returns')
COLS = ['game_id', 'season', 'season_type', 'week', 'home_team', 'away_team', 'home_score', 'away_score',
        'posteam', 'defteam', 'td_team', 'touchdown', 'return_touchdown', 'sack', 'interception', 'fumble',
        'fumble_recovery_1_team', 'fumbled_1_team', 'safety', 'punt_blocked', 'field_goal_result',
        'extra_point_result', 'field_goal_attempt', 'extra_point_attempt', 'kick_distance',
        'defensive_two_point_conv', 'defensive_extra_point_conv']


def _pbp(season):
    c = sorted((_REPO / 'nfl/research/postgame').glob(f'pbp_{season}.*.csv.gz'))
    if len(c) != 1:
        raise RuntimeError(f'HISTORY_PBP_AMBIGUOUS season {season}: {[p.name for p in c]}')
    return c[0]


def band_of(pa: int):
    for lo, hi in BANDS:
        if lo <= pa < hi:
            return f'{lo}-{hi}'
    raise ValueError(pa)


def summarise(x):
    x = [float(v) for v in x]
    n = len(x)
    m = sum(x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    return {'n': n, 'mean': round(m, 4), 'sd': round(sd, 4), 'p_le_0': round(sum(v <= 0 for v in x) / n, 4),
            'p_ge_10': round(sum(v >= 10 for v in x) / n, 4), 'p_ge_15': round(sum(v >= 15 for v in x) / n, 4),
            'p_ge_20': round(sum(v >= 20 for v in x) / n, 4),
            'integer_share': round(sum(abs(v - round(v)) < 1e-9 for v in x) / n, 4),
            'p10': sorted(x)[int(0.10 * n)], 'p50': sorted(x)[int(0.50 * n)], 'p90': sorted(x)[int(0.90 * n)]}


def measure():
    import pandas as pd
    rows, krows, files = [], [], {}
    for s in SEASONS:
        p = _pbp(s)
        files[s] = str(p.relative_to(_REPO))
        df = pd.read_csv(p, usecols=COLS, low_memory=False)
        df = df[df.season_type == 'REG']
        if df.empty:
            raise RuntimeError(f'HISTORY_PBP_EMPTY season {s}')
        for gid, g in df.groupby('game_id', sort=True):
            home, away = g.home_team.iloc[0], g.away_team.iloc[0]
            hs, as_ = g.home_score.dropna(), g.away_score.dropna()
            if hs.empty or as_.empty:
                continue
            final = {home: int(hs.iloc[-1]), away: int(as_.iloc[-1])}
            one = lambda col: (g[col] == 1)
            for club, opp in ((home, away), (away, home)):
                d = g.defteam == club
                tdm = one('touchdown') & (g.td_team == club) & ((g.td_team == g.defteam) | one('return_touchdown'))
                opp_tdm = one('touchdown') & (g.td_team == opp) & ((g.td_team == g.defteam) | one('return_touchdown'))
                c = {'sacks': int((one('sack') & d).sum()),
                     'ints': int((one('interception') & d).sum()),
                     'fumble_recoveries': int(((g.fumble_recovery_1_team == club) & g.fumbled_1_team.notna()
                                               & (g.fumbled_1_team != club)).sum()),
                     'tds': int(tdm.sum()),
                     'safeties': int((one('safety') & d).sum()),
                     'blocked_kicks': int(((one('punt_blocked') | (g.field_goal_result == 'blocked')
                                            | (g.extra_point_result == 'blocked')) & d).sum()),
                     'two_pt_returns': int(((one('defensive_two_point_conv') | one('defensive_extra_point_conv'))
                                            & d).sum())}
                pa_a = final[opp]
                pa_b = max(0, final[opp] - 6 * int(opp_tdm.sum()))
                dk_a = DK.dst_points(points_allowed=pa_a, **c)
                dk_b = DK.dst_points(points_allowed=pa_b, **c)
                rows.append({'season': s, 'game_id': gid, 'club': club, 'opp': opp, 'pa': pa_a, 'pa_b': pa_b,
                             'dk': dk_a, 'dk_b': dk_b, **c})
                k = g[(g.posteam == club)]
                fg = k[one('field_goal_attempt').loc[k.index] & (k.field_goal_result == 'made')]
                xp = k[one('extra_point_attempt').loc[k.index] & (k.extra_point_result == 'good')]
                dist = fg.kick_distance.astype(float)
                bm = {'FG30s': int((dist < 40).sum()), 'FG40s': int(((dist >= 40) & (dist < 50)).sum()),
                      'FG50+': int((dist >= 50).sum())}
                kdk = float(DK.kicker_points({b: [v] for b, v in bm.items()}, [len(xp)])[0])
                krows.append({'season': s, 'game_id': gid, 'club': club, 'pts': final[club], 'dk': kdk,
                              'fg_made': len(fg), 'xp_made': len(xp)})
    return rows, krows, files


def build(out=OUT):
    rows, krows, files = measure()
    if len(rows) < 2000 or len(krows) < 2000:
        raise RuntimeError(f'HISTORY_TOO_FEW_CLUB_GAMES dst={len(rows)} k={len(krows)}')
    allm = {c: sum(r[c] for r in rows) / len(rows) for c in COMPONENTS}
    by_band = collections.defaultdict(list)
    for r in rows:
        by_band[band_of(r['pa'])].append(r)
    bands = {}
    for lo, hi in BANDS:
        key = f'{lo}-{hi}'
        v = by_band[key]
        bm = {c: sum(r[c] for r in v) / len(v) for c in COMPONENTS}
        bands[key] = {'n': len(v), 'mean': {c: round(bm[c], 5) for c in COMPONENTS},
                      'ratio_to_all': {c: (round(bm[c] / allm[c], 5) if allm[c] > 0 else None)
                                       for c in COMPONENTS}}
    # within club-season dispersion: variance about the club-season mean over the all-games mean
    cs = collections.defaultdict(list)
    for r in rows:
        cs[(r['season'], r['club'])].append(r)
    disp = {}
    for c in COMPONENTS:
        ss = df_ = 0
        for v in cs.values():
            m = sum(r[c] for r in v) / len(v)
            ss += sum((r[c] - m) ** 2 for r in v)
            df_ += len(v) - 1
        var = ss / df_
        mu = allm[c]
        # AFTER the band: the shadow scorer multiplies a club rate by the band ratio, so the variance it still has
        # to supply is what is left once club-season AND band are conditioned on. Expected value per club-game is
        # the club-season mean times the band ratio, renormalised within the club-season so it averages to the
        # club-season mean. Using the band-blind variance would count the band's share of the spread twice.
        ss2 = 0.0
        rb = {k: v['ratio_to_all'][c] for k, v in bands.items()}
        for v in cs.values():
            m = sum(r[c] for r in v) / len(v)
            rr = [rb[band_of(r['pa'])] or 0.0 for r in v]
            norm = sum(rr) / len(rr) or 1.0
            ss2 += sum((r[c] - m * x / norm) ** 2 for r, x in zip(v, rr))
        var2 = ss2 / df_
        mu = allm[c]
        disp[c] = {'within_club_season_var': round(var, 5), 'mean': round(mu, 5),
                   'var_to_mean': round(var / mu, 4) if mu > 0 else None,
                   'within_club_season_and_band_var': round(var2, 5),
                   'var_to_mean_after_band': round(var2 / mu, 4) if mu > 0 else None,
                   'nb_k_after_band': (round(mu * mu / (var2 - mu), 4) if var2 > mu * 1.05 else None),
                   'FAMILY': 'NEGATIVE_BINOMIAL' if var2 > mu * 1.05 else 'POISSON',
                   'FAMILY_RULE': ('negative binomial only when the after-band variance exceeds the mean by more '
                                   'than 5%; otherwise Poisson. 5% is a declared materiality threshold, not a fit.')}
    doc = {
        'ARTIFACT': 'DST_K_HISTORY', 'spec_version': 'dst-k-history-1', 'seasons': list(SEASONS),
        'source_files': files, 'n_dst_club_games': len(rows), 'n_kicker_club_games': len(krows),
        'DEFINITIONS': __doc__.split('DEFINITIONS')[1].strip(),
        'dst_dk_rule_A': summarise([r['dk'] for r in rows]),
        'dst_dk_rule_B': summarise([r['dk_b'] for r in rows]),
        'dst_component_means_per_club_game': {c: round(allm[c], 5) for c in COMPONENTS},
        'points_allowed_rule_A': summarise([r['pa'] for r in rows]),
        'pa_tier_points_mean_rule_A': round(sum(DK.dst_points(points_allowed=r['pa']) for r in rows) / len(rows), 4),
        'bands_rule_A': bands, 'dispersion_within_club_season': disp,
        'kicker_dk_rule_A': summarise([r['dk'] for r in krows]),
        'kicker_fg_made_mean': round(sum(r['fg_made'] for r in krows) / len(krows), 4),
        'kicker_xp_made_mean': round(sum(r['xp_made'] for r in krows) / len(krows), 4),
        'READING': ('Unconditional league history. A single slate conditions on its own matchup, so its distribution '
                    'should be NARROWER than this, not equal to it; the comparison is about shape and support '
                    '(integers, mass at <= 0, upper tail), not a target for a mean.'),
    }
    pathlib.Path(out).write_text(json.dumps(doc, indent=1) + '\n')
    return doc


if __name__ == '__main__':
    d = build(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print(json.dumps({k: d[k] for k in ('n_dst_club_games', 'dst_dk_rule_A', 'dst_dk_rule_B',
                                        'dst_component_means_per_club_game', 'kicker_dk_rule_A')}, indent=1))
    print(json.dumps(d['dispersion_within_club_season'], indent=1))
    print(json.dumps({k: v['ratio_to_all'] for k, v in d['bands_rule_A'].items()}, indent=1))
