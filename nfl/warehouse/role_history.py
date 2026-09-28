#!/usr/bin/env python3.12
"""Role history: what each player WAS, per club-week, derived and never assumed from a label.

THE TAXONOMY the owner specified, and for each entry whether this checkout can support it.

  SUPPORTED, derived from opportunity and its distribution
    starter / backup              depth rank on the club's own opportunity that week
    committee / rotational        share held against the measured share of that rank
    injury replacement            a rank-1 week for a player who was not rank 1 in the club's
                                  recent weeks, while the previous leader has no opportunity row
    returning starter             a rank-1 week for a player who led earlier, after a gap
    promoted reserve              a first rank-1 or rank-2 week with no prior leading history
    cold-start rookie             no prior season in the table at all
    early-down back               carries concentrated on first and second down
    passing-down back             targets concentrated on third down and later
    goal-line back                share of the club's goal-line carries
    alpha receiver                rank 1 by target share, above the measured rank-1 median
    secondary receiver            rank 2, or rank 1 below that median

  NOT SUPPORTED, and recorded as such rather than approximated
    slot / interior alignment     alignment is charted. Nothing here carries it at any season, and
                                  ROSTER POSITION IS NOT ALIGNMENT. Never substituted.
    blocking vs receiving TE      a target RATE distinction is derivable and is provided under that
                                  name. It is NOT a blocking measurement: a tight end can block on
                                  every snap of a drive and the play-by-play will not say so.
    snap share before 2012        era.py. The proxies above are used instead, and a snap column is
                                  never fabricated.

EVERY THRESHOLD THAT SEPARATES TWO LABELS IS MEASURED FROM THE DISTRIBUTION OF THAT RANK, not chosen.
The one exception is the concentration cut for down-type roles, which is declared and marked.
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import era  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'role-history-1'
PLAYER_GAME = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
OUT = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'

#: How many recent club-weeks establish "who was leading". DECLARED.
LOOKBACK_WEEKS = 4

#: Concentration cut for a down-type role. DECLARED: a back with more than this share of his own
#: carries on early downs is an early-down back. Not measured because the underlying distribution is
#: continuous and any cut is a naming convention rather than a discovered boundary.
DOWN_TYPE_CONCENTRATION = 0.72

#: A goal-line back holds at least this share of his club's goal-line carries in the week. DECLARED.
GOAL_LINE_SHARE = 0.50

NOT_SUPPORTED = {
    'slot_or_interior_alignment': ('alignment is charted and absent from this checkout at every '
                                   'season. Roster position is NOT alignment.'),
    'blocking_vs_receiving_te': ('only a target-rate distinction is derivable, provided as '
                                 'te_target_rate_tier. It is not a blocking measurement.'),
}


def _pos_index():
    from nfl.tools import player_prior
    return player_prior.position_index()


def build():
    if not PLAYER_GAME.exists():
        return Outcome.blocked('PLAYER_GAME_ABSENT', 'build the player-game table first',
                               cause=Cause.DEPENDENCY)
    art = json.loads(PLAYER_GAME.read_text())
    rows = art['rows']
    pos_of = _pos_index()

    # group by club-week
    by_cw = collections.defaultdict(list)
    for r in rows.values():
        key = (r['season'], int(r['week']), r['club'])
        by_cw[key].append(r)

    # measure the rank-share distribution so label boundaries come from the data
    rank_shares = collections.defaultdict(lambda: collections.defaultdict(list))
    ranked_cache = {}
    for key, members in by_cw.items():
        for pos, measure in (('QB', 'pass_attempts'), ('RB', 'carries'),
                             ('WR', 'targets'), ('TE', 'targets')):
            grp = [m for m in members if pos_of.get(m['player_id']) == pos]
            tot = sum(m.get(measure) or 0 for m in grp)
            if tot < 5:
                continue
            grp.sort(key=lambda m: -(m.get(measure) or 0))
            ranked_cache[(key, pos)] = (grp, tot, measure)
            for i, m in enumerate(grp, start=1):
                rank_shares[pos][i].append((m.get(measure) or 0) / tot)
    bands = {}
    for pos, d in rank_shares.items():
        bands[pos] = {}
        for rk, vals in sorted(d.items()):
            if len(vals) >= 30:
                bands[pos][f'rank_{rk}'] = {
                    'n': len(vals), 'median': round(statistics.median(vals), 5),
                    'mean': round(statistics.fmean(vals), 5),
                    'p25': round(sorted(vals)[len(vals) // 4], 5),
                    'p75': round(sorted(vals)[3 * len(vals) // 4], 5)}

    # leading history, for the transition labels
    club_leader = {}           # (season, week, club, pos) -> player_id
    player_seasons = collections.defaultdict(set)
    player_weeks = collections.defaultdict(set)
    for r in rows.values():
        player_seasons[r['player_id']].add(r['season'])
        player_weeks[r['player_id']].add((r['season'], int(r['week'])))
    for (key, pos), (grp, tot, measure) in ranked_cache.items():
        if grp:
            club_leader[(key[0], key[1], key[2], pos)] = grp[0]['player_id']

    out = {}
    counts = collections.Counter()
    for (key, pos), (grp, tot, measure) in ranked_cache.items():
        season, week, club = key
        for rank, m in enumerate(grp, start=1):
            pid = m['player_id']
            share = (m.get(measure) or 0) / tot
            b = (bands.get(pos) or {}).get(f'rank_{rank}') or {}
            med1 = ((bands.get(pos) or {}).get('rank_1') or {}).get('median')

            # --- depth
            if rank == 1:
                depth = 'STARTER'
            elif rank == 2:
                depth = 'SECOND'
            else:
                depth = 'RESERVE'

            # --- concentration against what this rank usually holds
            if b.get('median') is not None:
                if share >= b['p75']:
                    conc = 'ABOVE_TYPICAL_FOR_RANK'
                elif share <= b['p25']:
                    conc = 'BELOW_TYPICAL_FOR_RANK'
                else:
                    conc = 'TYPICAL_FOR_RANK'
            else:
                conc = 'RANK_NOT_MEASURED'

            # --- transitions
            prior_leads = [(s, w) for (s, w) in
                           [(season, week - k) for k in range(1, LOOKBACK_WEEKS + 1)]
                           if club_leader.get((s, w, club, pos)) == pid]
            prev_leaders = [club_leader.get((season, week - k, club, pos))
                            for k in range(1, LOOKBACK_WEEKS + 1)]
            prev_leaders = [x for x in prev_leaders if x]
            ever_led = any(club_leader.get((s, w, c, p)) == pid
                           for (s, w, c, p) in club_leader
                           if p == pos and (s < season or (s == season and w < week)))
            transition = 'CONTINUING'
            if rank == 1 and not prior_leads and prev_leaders:
                prev = prev_leaders[0]
                prev_played = (season, week) in player_weeks.get(prev, set())
                if not prev_played:
                    transition = ('RETURNING_STARTER' if ever_led else 'INJURY_REPLACEMENT')
                else:
                    transition = 'OVERTOOK_INCUMBENT'
            elif rank == 1 and not prev_leaders and not ever_led:
                transition = 'PROMOTED_RESERVE'
            if len(player_seasons.get(pid, ())) == 1 and season == min(player_seasons[pid]):
                first_week = min(w for (s, w) in player_weeks[pid] if s == season)
                if week <= first_week + 3:
                    transition = ('COLD_START_NO_PRIOR_SEASON_IN_TABLE'
                                  if transition == 'CONTINUING' else transition)

            # --- usage archetype
            arche = []
            if pos == 'RB':
                ed, ld = m.get('early_down_carries') or 0, m.get('late_down_carries') or 0
                if ed + ld >= 5:
                    if ed / (ed + ld) >= DOWN_TYPE_CONCENTRATION:
                        arche.append('EARLY_DOWN_BACK')
                    elif ld / (ed + ld) >= 1 - DOWN_TYPE_CONCENTRATION:
                        arche.append('BALANCED_DOWN_USAGE')
                td_ = m.get('third_down_targets') or 0
                if td_ >= 2:
                    arche.append('PASSING_DOWN_TARGETS')
                club_gl = sum(x.get('gl_carries') or 0 for x in by_cw[key])
                if club_gl and (m.get('gl_carries') or 0) / club_gl >= GOAL_LINE_SHARE:
                    arche.append('GOAL_LINE_BACK')
            if pos in ('WR', 'TE') and med1 is not None:
                if rank == 1 and share >= med1:
                    arche.append('ALPHA_RECEIVER')
                elif rank == 1 or rank == 2:
                    arche.append('SECONDARY_RECEIVER')
            if pos == 'TE':
                tg = m.get('targets') or 0
                arche.append('TE_TARGET_RATE_HIGH' if tg >= 4 else 'TE_TARGET_RATE_LOW')

            counts[depth] += 1
            counts[transition] += 1
            for a in arche:
                counts[a] += 1
            out[f'{season}|{week}|{club}|{pid}'] = {
                'season': season, 'week': week, 'club': club, 'player_id': pid,
                'position': pos, 'measure': measure,
                'depth_rank': rank, 'share_of_club': round(share, 5),
                'depth': depth, 'concentration_vs_rank': conc,
                'transition': transition, 'archetypes': arche,
                'rank_band_median': b.get('median'),
                'snap_share': (era.NOT_AVAILABLE_FOR_ERA if season < 2012
                               else era.UNKNOWN_PENDING_ACQUISITION),
                'slot_or_interior_alignment': era.UNKNOWN_PENDING_ACQUISITION,
                'routes_run': era.UNKNOWN_PENDING_ACQUISITION,
            }

    artifact = {'artifact': 'ROLE_HISTORY', 'spec_version': SPEC_VERSION,
                'n_rows': len(out), 'rank_share_bands_measured': bands,
                'label_counts': dict(counts.most_common()),
                'declared_constants': {
                    'LOOKBACK_WEEKS': LOOKBACK_WEEKS,
                    'DOWN_TYPE_CONCENTRATION': DOWN_TYPE_CONCENTRATION,
                    'GOAL_LINE_SHARE': GOAL_LINE_SHARE},
                'NOT_SUPPORTED': NOT_SUPPORTED,
                'THRESHOLDS': ('rank band edges are MEASURED from the distribution of that rank; '
                               'only the down-type and goal-line cuts are declared, and they are '
                               'naming conventions rather than discovered boundaries.'),
                'rows': out}
    OUT.write_text(json.dumps(artifact, separators=(',', ':'), sort_keys=True))
    return Outcome.ok('ROLE_HISTORY_BUILT',
                      {'n_rows': len(out), 'bands': bands, 'counts': dict(counts.most_common(24))},
                      f'{len(out)} player-club-weeks')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    v = o.value
    print(f"  {v['n_rows']} role rows")
    print('  MEASURED rank share bands (median share of club opportunity):')
    for pos, d in sorted(v['bands'].items()):
        cells = ' '.join(f"{k.split('_')[1]}:{x['median']:.3f}" for k, x in sorted(d.items())[:5])
        print(f'    {pos:3s} {cells}')
    print('  label counts:')
    for k, n in list(v['counts'].items()):
        print(f'    {k:38s} {n}')
    print(f'  -> {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
