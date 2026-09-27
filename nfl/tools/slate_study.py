"""A game-by-game, player-by-player study of the frozen slate, from held evidence.

    python3.12 nfl/tools/slate_study.py --write

WHAT THIS IS, AND WHAT IT REFUSES TO BE

It joins three things this repository already holds, for the nine 1 PM ET games:

  1. the frozen DK contest universe  -- 457 rows, salary/position/team, from
     DK's own entries export (DK_WEEK3_EARLY_BASELINE.json);
  2. the Q9 live pregame features    -- role class, role rank, trailing snap
     share, trailing target share, participation EWMA, prior depth bucket;
  3. the depth-chart vintage actually consumed, with its age at the clock.

IT CONTAINS NO PROJECTION AND NO RECOMMENDATION. The production feature builder
is unimplemented and the board pipeline refuses (see
2026-09-27_FEATURE_BUILD_BLOCKER.md), so there is no lawful projection to show.
Every number here is an OBSERVED HISTORICAL QUANTITY or a DK fact, never a
forecast, and nothing here ranks players for selection.

THREE CAVEATS THAT CHANGE HOW EVERY ROW READS

*The features contain NO 2026 information.* The builder runs arm A, whose stated
reason is that "history is restricted to seasons strictly before the forecast
season". So `trail_snap`, `own_share` and every `h_*` value is measured through
2025 and earlier. A player whose role changed this September looks like last
year's player, and a rookie has no history at all. This is a deliberate
anti-leakage property, not a defect -- but it means these are PRIOR-SEASON
descriptors, and they are labelled as such in every column heading.

*`inj_available` does not mean the player is available.* In the builder it is
`1 if d is not None else 0` -- it records whether an INJURY ROW EXISTS. Most
players have none. An absent injury row is UNKNOWN and is printed as UNKNOWN,
never as healthy. Separately, 518 of 692 injury rows carry no `report_status`.

*Feature coverage is partial by position.* Q9 covers receiving and rushing
roles. There are no features for any QB and none for any DST, and 111 RB/WR/TE
in the $2,500-$4,000 band have none either. Those rows are listed as
NO_FEATURES rather than omitted, because omitting them is how a depth player who
becomes relevant after inactives disappears from the study.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.prospective.q9shadow import live_features as LF        # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

SPEC_VERSION = 'slate-study-1'
BASELINE = _REPO / 'nfl/dfs/salaries/DK_WEEK3_EARLY_BASELINE.json'
OUT_JSON = _REPO / 'nfl/dfs/salaries/DK_WEEK3_SLATE_STUDY.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/DK_WEEK3_SLATE_STUDY.md'
SEASON, WEEK = 2026, 3
OBSERVED_BEFORE = '2026-09-27T04:00:00Z'
KICKOFF = '2026-09-27T17:00:00Z'
POS_ORDER = ('QB', 'RB', 'WR', 'TE', 'DST')


def _baseline():
    if not BASELINE.exists():
        return Outcome.fail('SLATE_BASELINE_ABSENT',
                            f'{BASELINE} does not exist, so there is no frozen '
                            f'universe to study. This is not an empty study.')
    d = json.loads(BASELINE.read_text())
    rows = (d.get('slate') or {}).get('pool_rows')
    if not rows:
        return Outcome.fail('SLATE_BASELINE_CARRIES_NO_ROWS',
                            'the baseline exists but holds no pool_rows')
    return Outcome.ok('SLATE_BASELINE_LOADED', value=(d, rows))


def features(clubs):
    """Q9 live features per club, and the refusals, kept apart."""
    got, refused, depth = {}, {}, {}
    for t in sorted(clubs):
        o = LF.build_team_week(SEASON, WEEK, t,
                               observed_before=OBSERVED_BEFORE,
                               kickoff_utc=KICKOFF)
        if o.state is not State.PASS:
            refused[t] = {'state': o.state.name, 'code': o.code,
                           'detail': (o.detail or '')[:200]}
            continue
        for r in o.value:
            pid = r.get('pid')
            if pid:
                got[pid] = r
        dc = (o.evidence or {}).get('depth_chosen') or {}
        if t in dc:
            depth[t] = dc[t]
    return got, refused, depth


def _inj(r):
    """Injury state as three distinguishable answers, never two."""
    if not r:
        return 'NO_FEATURE_ROW'
    if not r.get('inj_available'):
        return 'UNKNOWN_NO_INJURY_ROW'
    st = r.get('inj_status')
    pr = r.get('inj_practice')
    if not st and pr:
        return f'ROW_NO_STATUS: {pr}'
    return f'{st or "NO_STATUS"}' + (f' / {pr}' if pr else '')


def study():
    b = _baseline()
    if b.state is not State.PASS:
        return b
    doc, rows = b.value
    slate = doc['slate']
    clubs = sorted({r['team'] for r in rows})
    feats, refused, depth = features(clubs)

    by_game = collections.OrderedDict()
    for key in slate['games']:
        # The baseline stores each game as the string 'AWAY@HOME'. Read, not
        # assumed: a first version unpacked it as a 2-tuple and raised.
        away, home = key.split('@')
        by_game[key] = {'away': away, 'home': home, 'clubs': {}}
        for t in (away, home):
            club_rows = [r for r in rows if r['team'] == t]
            players = []
            for r in sorted(club_rows,
                            key=lambda x: (POS_ORDER.index(x['dk_pos'])
                                           if x['dk_pos'] in POS_ORDER else 9,
                                           -x['salary'])):
                f = feats.get(r.get('gsis_id')) if r.get('gsis_id') else None
                players.append({
                    'dk_id': r['dk_id'], 'name': r['dk_name'],
                    'pos': r['dk_pos'], 'salary': r['salary'],
                    'gsis_id': r.get('gsis_id'),
                    'identity': r.get('match_method') or 'UNMATCHED',
                    'has_features': f is not None,
                    # THREE STATES, NOT TWO. A feature row with no trailing
                    # history is neither covered nor uncovered: the player is
                    # known to the depth chart and unknown to the model.
                    'coverage': (
                        'NO_FEATURES' if f is None
                        else ('FEATURES_NO_PRIOR_HISTORY'
                              if f.get('trail_snap') is None
                              else 'FEATURES_WITH_PRIOR_HISTORY')),
                    'role_class': (f or {}).get('role_class'),
                    'role_rank': (f or {}).get('role_rank'),
                    'role_rank_basis': (f or {}).get('role_rank_basis'),
                    'depth_rank': (f or {}).get('rank'),
                    'prior_depth_bucket': (f or {}).get('prior_depth_bucket'),
                    'trail_snap_prior_seasons': (f or {}).get('trail_snap'),
                    'own_share_prior_seasons': (f or {}).get('own_share'),
                    'own_n_games': (f or {}).get('own_n'),
                    'participation_ewma_prior': (f or {}).get(
                        'h_participation_ewma'),
                    'target_freq_prior': (f or {}).get('h_target_freq'),
                    'appeared_games_prior': (f or {}).get('h_appeared_games'),
                    'injury': _inj(f),
                })
            by_game[key]['clubs'][t] = {
                'n_rows': len(club_rows),
                'by_position': dict(collections.Counter(
                    r['dk_pos'] for r in club_rows)),
                'salary_min': min((r['salary'] for r in club_rows), default=None),
                'salary_max': max((r['salary'] for r in club_rows), default=None),
                'n_with_features': sum(1 for p in players if p['has_features']),
                'n_without_features': sum(1 for p in players
                                          if not p['has_features']),
                'n_features_no_prior_history': sum(
                    1 for p in players
                    if p['coverage'] == 'FEATURES_NO_PRIOR_HISTORY'),
                'depth_chart_vintage': depth.get(t),
                'players': players,
            }

    allp = [p for g in by_game.values() for c in g['clubs'].values()
            for p in c['players']]
    covered = sum(1 for p in allp if p['has_features'])
    states = collections.Counter(p['coverage'] for p in allp)
    return Outcome.ok(
        'SLATE_STUDY_BUILT',
        value={
            'artifact': 'DK_WEEK3_SLATE_STUDY', 'spec_version': SPEC_VERSION,
            'season': SEASON, 'week': WEEK,
            'observed_before': OBSERVED_BEFORE, 'kickoff_utc': KICKOFF,
            'n_games': len(by_game), 'n_pool_rows': len(rows),
            'n_rows_with_features': covered,
            'n_rows_without_features': len(rows) - covered,
            'coverage_states': dict(states),
            'feature_refusals_by_club': refused,
            'CONTAINS_NO_PROJECTION': (
                'Every number is an observed historical quantity or a DK fact. '
                'The production feature builder is unimplemented and the board '
                'pipeline refuses, so no lawful projection exists to show. '
                'Nothing here ranks players for selection.'),
            'FEATURES_CARRY_NO_2026_INFORMATION': (
                'The builder runs arm A: history is restricted to seasons '
                'strictly before the forecast season. trail_snap, own_share '
                'and every h_* value is measured through 2025 and earlier, so '
                'a role change this September does not appear and a rookie has '
                'no history at all.'),
            'INJURY_FIELD_MEANING': (
                'inj_available is 1 if an injury ROW exists, not if the player '
                'is available. An absent row is UNKNOWN_NO_INJURY_ROW and is '
                'never healthy. 518 of 692 injury rows carry no report_status.'),
            'ROLE_RANK_IS_SNAP_SHARE_NOT_TARGET_SHARE': (
                'role_rank_basis is TRAILING_SNAP_SHARE, so the ranking is by '
                'time on the field and NOT by receiving volume. Concretely, in '
                'CIN: Drew Sample ranks TE1 on 0.573 trailing snap share with '
                '0.038 target share, while Mike Gesicki is TE2 on 0.349 snaps '
                'with 0.092 target share -- the blocking tight end outranks the '
                'receiving one, which is correct for what the column measures '
                'and wrong for anyone reading it as a depth chart of who gets '
                'the ball. Read role_rank beside the target-share column, '
                'never instead of it.'),
            'FRINGE_IS_AN_ARTIFACT_FOR_PLAYERS_WITH_NO_HISTORY': (
                'Every one of the rows with a feature row but no trailing '
                'history is classed role_class=fringe, and that is a property '
                'of the classifier rather than a judgement about the player: '
                'with no prior-season snap share there is nothing to rank him '
                'on, so he cannot come out anywhere else. Because arm A '
                'excludes the forecast season, a rookie whose only NFL snaps '
                'are in 2026 is indistinguishable here from a practice-squad '
                'body. DK prices several of them between $4,300 and $5,300, '
                'which is not depth-tail pricing. This is the largest blind '
                'spot in the study and it compounds after inactives, because '
                'the replacement for an inactive starter is frequently one of '
                'these players.'),
            'games': by_game,
        },
        n_games=len(by_game), n_rows=len(rows), n_covered=covered)


def _fmt(v, nd=3):
    return '—' if v is None else (f'{v:.{nd}f}' if isinstance(v, float)
                                  else str(v))


def markdown(val):
    L = []
    A = L.append
    A('# Week-3 Early Only — game-by-game, player-by-player study\n')
    A(f"Built from held evidence at `observed_before = {val['observed_before']}`, "
      f"kickoff `{val['kickoff_utc']}`. Spec `{val['spec_version']}`.\n")
    A('**This document contains no projection and no recommendation.** '
      + val['CONTAINS_NO_PROJECTION'] + '\n')
    A('## Three caveats that change how every row reads\n')
    A('**No 2026 information.** ' + val['FEATURES_CARRY_NO_2026_INFORMATION']
      + ' Columns below say `prior` for exactly this reason.\n')
    A('**Injury blanks are UNKNOWN.** ' + val['INJURY_FIELD_MEANING'] + '\n')
    A('**`role_rank` is snap share, not target share.** '
      + val['ROLE_RANK_IS_SNAP_SHARE_NOT_TARGET_SHARE'] + '\n')
    A('**`fringe` is an artifact for anyone with no prior history.** '
      + val['FRINGE_IS_AN_ARTIFACT_FOR_PLAYERS_WITH_NO_HISTORY'] + '\n')
    A('**Coverage is partial by position.** '
      f"{val['n_rows_with_features']} of {val['n_pool_rows']} DK rows carry "
      f"features; {val['n_rows_without_features']} do not — every QB, every "
      f'DST, and the RB/WR/TE depth tail. Uncovered rows are listed as '
      '`NO_FEATURES` rather than dropped, because dropping them is how a '
      'depth player who becomes relevant after inactives disappears.\n')
    if val['feature_refusals_by_club']:
        A(f"**Feature refusals:** {val['feature_refusals_by_club']}\n")
    for key, g in val['games'].items():
        A(f"\n---\n\n## {g['away']} @ {g['home']}\n")
        for t, c in g['clubs'].items():
            v = c['depth_chart_vintage'] or {}
            A(f"### {t} — {c['n_rows']} DK rows, "
              f"${c['salary_min']}–${c['salary_max']}")
            A(f"\n{c['n_with_features'] - c['n_features_no_prior_history']} "
              f"with prior history · "
              f"{c['n_features_no_prior_history']} rostered but no history · "
              f"{c['n_without_features']} no features")
            if v:
                A(f"\nDepth chart consumed: `{v.get('dt')}`, "
                  f"{v.get('hours_before_clock')}h before the clock, "
                  f"{v.get('n_listed')} listed.\n")
            A('\n| pos | player | $ | role | rank | trail snap (prior) | '
              'tgt share (prior, n) | part. EWMA (prior) | injury |')
            A('|---|---|---|---|---|---|---|---|---|')
            for p in c['players']:
                if p['has_features']:
                    role = p['role_class'] or '—'
                    rank = (f"{p['role_rank']}"
                            if p['role_rank'] is not None else '—')
                    ts = _fmt(p['trail_snap_prior_seasons'])
                    os_ = (f"{_fmt(p['own_share_prior_seasons'])} "
                           f"({p['own_n_games']})"
                           if p['own_share_prior_seasons'] is not None else '—')
                    pe = _fmt(p['participation_ewma_prior'])
                else:
                    role = rank = ts = os_ = pe = '**NO_FEATURES**'
                if p['coverage'] == 'FEATURES_NO_PRIOR_HISTORY':
                    role = f'{role} *(no history)*'
                A(f"| {p['pos']} | {p['name']} | {p['salary']} | {role} | "
                  f"{rank} | {ts} | {os_} | {pe} | {p['injury']} |")
            A('')
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args(argv)
    o = study()
    if o.state is not State.PASS:
        print(f'{o.state.name} {o.code}: {o.detail}')
        return 1
    v = o.value
    print(f"{v['n_games']} game(s), {v['n_pool_rows']} pool row(s), "
          f"{v['n_rows_with_features']} with features, "
          f"{v['n_rows_without_features']} without")
    if a.write:
        OUT_JSON.write_text(json.dumps(v, indent=1) + '\n')
        OUT_MD.write_text(markdown(v))
        print(f'wrote {OUT_JSON.relative_to(_REPO)}')
        print(f'wrote {OUT_MD.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
