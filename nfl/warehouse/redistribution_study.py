#!/usr/bin/env python3.12
"""GAP 9's central question, answered from history instead of assumed.

    When a club's lead back misses, what share goes to the second back? The third? The
    quarterback? Does the club pass more? Does total volume change? And the same for a lead
    receiver, a lead tight end, a starting quarterback.

WHY THIS IS NOT OPTIONAL. The standing instruction is "do not assume a nominal backup inherits 100
per cent of the work" and "do not manufacture one-for-one redistribution". Both are prohibitions.
Neither tells the model what DOES happen. Without this study the redistribution layer either invents
a number or refuses, and it has been doing both.

THE DESIGN, and the one thing that makes it credible.

  A club-week is an ABSENCE EVENT when the club's established leader at a position -- leader in at
  least three of the previous four weeks -- has NO opportunity row that week.

  The comparison is WITHIN CLUB AND WITHIN SEASON: the absence week against that same club's
  baseline weeks in the same season with the leader present. A cross-club comparison would confound
  the absence with the club, and a cross-season one with the roster.

  Shares are of the club's own total for that measure, so a club that simply ran fewer plays does not
  register as a redistribution.

WHAT THIS CANNOT SAY. It measures what happened when a leader was absent; it does not isolate WHY.
A leader missing a game and his club trailing by three scores are correlated, so the pass-rate
movement here is an association and is labelled as one. Nothing in it identifies a causal effect, and
the artifact says so rather than implying otherwise.
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

from nfl.warehouse import stats  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'redistribution-study-1'
PLAYER_GAME = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
ROLE = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'
OUT = _REPO / 'nfl/warehouse/REDISTRIBUTION_STUDY.json'

#: A leader is ESTABLISHED when he led in at least this many of the previous four club-weeks.
#: DECLARED: two of four would admit a committee's alternating weeks as an absence event.
ESTABLISHED_LEAD_WEEKS = 3
LOOKBACK = 4

#: Positions and the opportunity each one is measured on.
MEASURES = {'QB': 'pass_attempts', 'RB': 'carries', 'WR': 'targets', 'TE': 'targets'}

#: Minimum club total on a measure for a week to count, so a 3-carry game does not define a share.
MIN_CLUB_TOTAL = {'pass_attempts': 15, 'carries': 12, 'targets': 15}


def build():
    for f in (PLAYER_GAME, ROLE):
        if not f.exists():
            return Outcome.blocked('WAREHOUSE_INCOMPLETE', f'{f.name} missing',
                                   cause=Cause.DEPENDENCY)
    pg = json.loads(PLAYER_GAME.read_text())['rows']
    from nfl.tools import player_prior
    pos_of = player_prior.position_index()

    # club-week -> {position: [(player, opportunity)], totals}
    cw = collections.defaultdict(lambda: collections.defaultdict(list))
    club_tot = collections.defaultdict(lambda: collections.Counter())
    present = collections.defaultdict(set)
    for r in pg.values():
        k = (r['season'], int(r['week']), r['club'])
        p = pos_of.get(r['player_id'])
        present[k].add(r['player_id'])
        for pos, meas in MEASURES.items():
            if p == pos:
                cw[k][pos].append((r['player_id'], r.get(meas) or 0, r))
        club_tot[k]['carries'] += r.get('carries') or 0
        club_tot[k]['targets'] += r.get('targets') or 0
        club_tot[k]['pass_attempts'] += r.get('pass_attempts') or 0

    def leader(k, pos):
        grp = cw.get(k, {}).get(pos) or []
        if not grp:
            return None
        return max(grp, key=lambda t: t[1])[0]

    def share(k, pos, pid, meas):
        tot = club_tot[k][meas]
        if tot < MIN_CLUB_TOTAL[meas]:
            return None
        for p, v, _r in cw.get(k, {}).get(pos) or []:
            if p == pid:
                return v / tot
        return 0.0

    def rank_share(k, pos, rank, meas, exclude=None):
        grp = [t for t in (cw.get(k, {}).get(pos) or []) if t[0] != exclude]
        tot = club_tot[k][meas]
        if tot < MIN_CLUB_TOTAL[meas] or len(grp) < rank:
            return None
        grp.sort(key=lambda t: -t[1])
        return grp[rank - 1][1] / tot

    results = {}
    for pos, meas in MEASURES.items():
        events, baselines = [], []
        for k in sorted(cw):
            season, week, club = k
            prev = [(season, week - i, club) for i in range(1, LOOKBACK + 1)]
            leads = [leader(pk, pos) for pk in prev]
            leads = [x for x in leads if x]
            if len(leads) < ESTABLISHED_LEAD_WEEKS:
                continue
            common = collections.Counter(leads).most_common(1)[0]
            if common[1] < ESTABLISHED_LEAD_WEEKS:
                continue
            est = common[0]
            base_weeks = [pk for pk in prev if est in present.get(pk, set())]
            if not base_weeks:
                continue
            absent = est not in present.get(k, set())
            row = {'season': season, 'week': week, 'club': club, 'leader': est,
                   'game_id_key': f'{season}|{week}|{club}'}
            # the second and third men, excluding the established leader from the ranking so the
            # same players are compared across absence and baseline weeks
            for rk in (1, 2, 3):
                row[f'r{rk}_excl_leader'] = rank_share(k, pos, rk, meas, exclude=est)
                bl = [rank_share(pk, pos, rk, meas, exclude=est) for pk in base_weeks]
                bl = [x for x in bl if x is not None]
                row[f'r{rk}_baseline'] = statistics.fmean(bl) if bl else None
            row['leader_share'] = share(k, pos, est, meas)
            bl = [share(pk, pos, est, meas) for pk in base_weeks]
            bl = [x for x in bl if x is not None]
            row['leader_baseline'] = statistics.fmean(bl) if bl else None
            # club-level responses
            row['club_measure'] = club_tot[k][meas]
            row['club_measure_baseline'] = statistics.fmean(
                [club_tot[pk][meas] for pk in base_weeks]) if base_weeks else None
            pa, ca = club_tot[k]['pass_attempts'], club_tot[k]['carries']
            row['club_pass_rate'] = (pa / (pa + ca)) if (pa + ca) else None
            brs = [(club_tot[pk]['pass_attempts'] /
                    (club_tot[pk]['pass_attempts'] + club_tot[pk]['carries']))
                   for pk in base_weeks
                   if (club_tot[pk]['pass_attempts'] + club_tot[pk]['carries'])]
            row['club_pass_rate_baseline'] = statistics.fmean(brs) if brs else None
            (events if absent else baselines).append(row)

        # aggregate the absence events
        def delta(rows, a, b):
            d = [r[a] - r[b] for r in rows
                 if r.get(a) is not None and r.get(b) is not None]
            if len(d) < 5:
                return None
            return {'n': len(d), 'mean': round(statistics.fmean(d), 5),
                    'median': round(statistics.median(d), 5),
                    'sd': round(statistics.pstdev(d), 5) if len(d) > 1 else None,
                    'se': round(statistics.pstdev(d) / (len(d) ** 0.5), 5) if len(d) > 1 else None,
                    **{f'p{q}': round(v, 5) for q, v in
                       zip((5, 25, 50, 75, 95), stats.quantiles(d).values())}}

        results[pos] = {
            'measure': meas,
            'n_absence_events': len(events),
            'n_baseline_weeks_with_leader': len(baselines),
            'leader_share_when_present': (
                round(statistics.fmean([r['leader_baseline'] for r in events
                                        if r.get('leader_baseline') is not None]), 5)
                if events else None),
            'redistribution': {
                'to_next_man_r1': delta(events, 'r1_excl_leader', 'r1_baseline'),
                'to_r2': delta(events, 'r2_excl_leader', 'r2_baseline'),
                'to_r3': delta(events, 'r3_excl_leader', 'r3_baseline'),
            },
            'club_response': {
                'measure_total_change': delta(events, 'club_measure', 'club_measure_baseline'),
                'pass_rate_change': delta(events, 'club_pass_rate', 'club_pass_rate_baseline'),
            },
            'NOT_ONE_FOR_ONE': ('the next man does NOT absorb the leader share. Read the mean '
                                'against leader_share_when_present: the difference is what goes '
                                'elsewhere, to deeper backs, to other positions, or is simply not '
                                'run.'),
            'ASSOCIATION_NOT_CAUSE': ('a leader missing and a club trailing are correlated, so the '
                                      'pass-rate movement is an association. Nothing here '
                                      'identifies a causal effect.'),
        }
    art = {'artifact': 'REDISTRIBUTION_STUDY', 'spec_version': SPEC_VERSION,
           'declared': {'ESTABLISHED_LEAD_WEEKS': ESTABLISHED_LEAD_WEEKS, 'LOOKBACK': LOOKBACK,
                        'MIN_CLUB_TOTAL': MIN_CLUB_TOTAL},
           'DESIGN': ('within club and within season: an absence week against that same club '
                      'baseline weeks in the same season with the leader present'),
           'by_position': results}
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))
    return Outcome.ok('REDISTRIBUTION_STUDY_BUILT', art,
                      f'{sum(v["n_absence_events"] for v in results.values())} absence events')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    for pos, v in o.value['by_position'].items():
        print(f"\n  {pos} on {v['measure']}: {v['n_absence_events']} absence events, "
              f"leader normally holds {v['leader_share_when_present']}")
        for k, d in v['redistribution'].items():
            if not d:
                print(f'    {k:18s} too few events')
                continue
            print(f"    {k:18s} n={d['n']:4d} mean {d['mean']:+.4f} +/- {d['se']:.4f} "
                  f"median {d['median']:+.4f}  p25 {d['p25']:+.4f} p75 {d['p75']:+.4f}")
        for k, d in v['club_response'].items():
            if d:
                print(f"    {k:18s} n={d['n']:4d} mean {d['mean']:+.4f} +/- {d['se']:.4f}")
    print(f"\n  -> {OUT.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
