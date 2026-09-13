"""QB participation causal audit: is QB3 estimating the wrong quantity?

THE QUESTION. `qb3_lib` fits `p_primary` and a share pool on an UNCONDITIONAL
historical frame: every team-game in which a charted quarterback appeared,
whatever the reason he appeared. A pregame product needs two separable things
instead -- what the coaching staff PLANNED, and the CONTINGENT risk that plan
breaks during the game. If the layer is estimating the mixture of those two as
though it were one quantity, then the backup's share is being charged to the
starter's pregame projection.

Measured consequence to check it against: cell (1, yes) -- the depth chart's
QB1 who was also last game's primary, the cleanest case the model has -- is
given P(share = 1) of 0.7765 and P(share = 0) of 0.0736, with a pool mean of
0.8919. If, conditional on an established starter and no planned rotation, the
real world finishes the game with that starter far more often than 77.65% of
the time, the layer is spending roughly a fifth of his projection on events
that a pregame forecast should carry as a separate contingent risk.

CLASSIFICATION IS PREDECLARED AND DETERMINISTIC. The rules below are fixed
before any rate is computed, and each is a rule about GAME CONTEXT, never about
whether the resulting number looks right.

WHAT PLAY-BY-PLAY CANNOT DO. It cannot separate an injury from a benching. Both
look identical in the bytes: the starter stops taking snaps and does not come
back. They are therefore reported together as REPLACEMENT_NO_RETURN rather than
split on a guess, and the limitation is stated wherever the number appears.

HARD ROCK BACKUP-QB MARKET AVAILABILITY IS NOT USED HERE AT ALL -- not as a
feature, not as a rule, not as a filter. If it is ever recorded it is an
external diagnostic only.

DIAGNOSIS ONLY. No predictive value is changed by this module.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.research import postgame as PG                             # noqa: E402

SPEC_VERSION = 'qb-participation-causal-audit/1.0.0'

# Predeclared thresholds. Fixed before any rate was computed.
BLOWOUT_MARGIN = 17          # a three-score game
LATE_SECONDS = 900           # final 15 minutes of game clock
ROTATION_MAX_SHARE = 0.35    # a package, not a takeover
CLASSES = ('PLANNED_ROTATION_OR_PACKAGE', 'REPLACEMENT_NO_RETURN',
           'BLOWOUT_RELIEF', 'KNEEL_OR_SPECIAL', 'SPLIT_FROM_THE_START',
           'UNCLASSIFIED')


def _f(v, d=None):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return d


def team_qb_sequence(rows, team):
    """Every dropback by this team, in play order, with context."""
    seq = []
    for r in rows:
        if r.get('posteam') != team:
            continue
        pid = r.get('passer_player_id') or ''
        is_db = (_f(r.get('pass_attempt'), 0) == 1 or _f(r.get('sack'), 0) == 1
                 or _f(r.get('qb_scramble'), 0) == 1)
        if not pid or not is_db:
            continue
        if _f(r.get('two_point_attempt'), 0) == 1:
            continue
        seq.append({
            'pid': pid,
            'qtr': _f(r.get('qtr'), 0),
            'secs': _f(r.get('game_seconds_remaining'), 0),
            'posteam_score': _f(r.get('posteam_score'), 0),
            'defteam_score': _f(r.get('defteam_score'), 0),
            'kneel': _f(r.get('qb_kneel'), 0) == 1,
            'spike': _f(r.get('qb_spike'), 0) == 1,
        })
    return seq


def classify_team_game(seq):
    """One team-game: starter, backups, and WHY each backup appeared."""
    if not seq:
        return None
    counts = collections.Counter(p['pid'] for p in seq)
    starter = seq[0]['pid']
    total = sum(counts.values())
    order = [p['pid'] for p in seq]
    out = {'starter': starter, 'total_dropbacks': total,
           'starter_dropbacks': counts[starter],
           'starter_share': counts[starter] / total if total else None,
           'n_qb_with_dropback': len(counts), 'backups': []}
    for pid, n in counts.items():
        if pid == starter:
            continue
        mine = [p for p in seq if p['pid'] == pid]
        first = mine[0]
        idx = order.index(pid)
        after = order[idx:]
        starter_returns = starter in after[1:]
        # how many times possession of the QB job changed hands
        alternations = sum(1 for a, b in zip(order, order[1:]) if a != b)
        margin = abs(first['posteam_score'] - first['defteam_score'])
        share = n / total
        all_kneel_spike = all(p['kneel'] or p['spike'] for p in mine)
        if all_kneel_spike:
            cls = 'KNEEL_OR_SPECIAL'
        elif idx == 0:
            cls = 'SPLIT_FROM_THE_START'
        elif margin >= BLOWOUT_MARGIN and first['secs'] <= LATE_SECONDS:
            cls = 'BLOWOUT_RELIEF'
        elif starter_returns and share <= ROTATION_MAX_SHARE and alternations >= 2:
            cls = 'PLANNED_ROTATION_OR_PACKAGE'
        elif not starter_returns:
            cls = 'REPLACEMENT_NO_RETURN'
        else:
            cls = 'UNCLASSIFIED'
        out['backups'].append({
            'pid': pid, 'dropbacks': n, 'share': round(share, 4),
            'classification': cls,
            'entry_qtr': first['qtr'], 'entry_secs_remaining': first['secs'],
            'margin_at_entry': margin, 'starter_returned': starter_returns,
            'alternations': alternations,
        })
    return out


def build(seasons):
    """One record per team-game, across seasons, with provenance."""
    recs, prov = [], {}
    for y in seasons:
        o = PG.fetch_outcomes(y)
        if o.state is not State.PASS:
            raise SystemExit(f'OUTCOME_FETCH_REFUSED {y}: {o.code}')
        prov[y] = {'sha256': o.evidence['sha256'],
                   'n_games': o.evidence['n_games'],
                   'blob': str(o.evidence['blob'])}
        rows = PG._rows(o.evidence['blob'])
        by_game = collections.defaultdict(list)
        for r in rows:
            by_game[r.get('game_id')].append(r)
        for gid, grows in by_game.items():
            for team in sorted({r.get('posteam') for r in grows if r.get('posteam')}):
                c = classify_team_game(team_qb_sequence(grows, team))
                if c:
                    c.update({'season': y, 'game_id': gid, 'team': team})
                    recs.append(c)
    # ESTABLISHED INCUMBENT, defined from the team's OWN PRIOR GAME only.
    # No injury report, no depth chart, no market. A starter who also started
    # the club's previous game is "established"; the first game of a season
    # has no prior and is excluded rather than assumed.
    recs.sort(key=lambda r: (r['team'], r['season'], r['game_id']))
    prev = {}
    for r in recs:
        k = (r['team'], r['season'])
        r['prev_starter'] = prev.get(k)
        r['established_incumbent'] = (r['prev_starter'] is not None
                                      and r['prev_starter'] == r['starter'])
        prev[k] = r['starter']
    return recs, prov


def conditional_rates(recs):
    """The quantity a PREGAME product actually needs.

    Conditioning set: an established incumbent started, and the game shows no
    planned rotation. That is the population a pregame forecast faces when the
    depth chart's QB1 is also the incumbent -- QB3's cell (1, yes).
    """
    pool = [r for r in recs if r['established_incumbent']
            and not any(b['classification'] == 'PLANNED_ROTATION_OR_PACKAGE'
                        for b in r['backups'])]
    if not pool:
        return None
    share = np.array([r['starter_share'] for r in pool], float)
    def bu_share(r):
        return sum(b['share'] for b in r['backups']
                   if b['classification'] != 'KNEEL_OR_SPECIAL')
    bs = np.array([bu_share(r) for r in pool], float)
    any_db = np.array([bu_share(r) > 0 for r in pool], bool)
    # "finished the game" = no backup appeared for a non-kneel reason
    finished = [r for r in pool if bu_share(r) == 0]
    fs = np.array([r['starter_share'] for r in finished], float)
    repl = [r for r in pool
            if any(b['classification'] == 'REPLACEMENT_NO_RETURN'
                   for b in r['backups'])]
    blow = [r for r in pool
            if any(b['classification'] == 'BLOWOUT_RELIEF' for b in r['backups'])]
    return {
        'n_team_games': len(pool),
        'p_qb2_any_dropback': round(float(any_db.mean()), 4),
        'p_qb2_share_ge_10pct': round(float((bs >= 0.10).mean()), 4),
        'p_qb2_share_ge_25pct': round(float((bs >= 0.25).mean()), 4),
        'p_qb2_share_ge_50pct': round(float((bs >= 0.50).mean()), 4),
        'starter_share_mean': round(float(share.mean()), 4),
        'starter_share_median': round(float(np.median(share)), 4),
        'p_starter_share_eq_1': round(float((share >= 0.999).mean()), 4),
        'p_starter_share_eq_0': round(float((share <= 0.001).mean()), 4),
        'n_starter_finished': len(finished),
        'p_starter_finished': round(len(finished) / len(pool), 4),
        'starter_share_given_finished_mean': (round(float(fs.mean()), 4)
                                              if len(fs) else None),
        'p_replacement_no_return': round(len(repl) / len(pool), 4),
        'p_blowout_relief': round(len(blow) / len(pool), 4),
    }


def qb3_cell_1_1():
    """What QB3 currently assigns the same population."""
    sys.path.insert(0, str(_REPO / 'nfl' / 'research' / 'qb3'))
    import qb3_lib as Q
    frame = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    par = Q.fit(frame, 2026)
    pool = par['share_pool'][(1, 1)]
    return {
        'cell': '(rank 1, was_prev_primary yes)',
        'n': int(par['n'][(1, 1)]),
        'p_primary': round(par['p_primary'][(1, 1)], 4),
        'pool_mean': round(float(pool.mean()), 4),
        'pool_median': round(float(np.median(pool)), 4),
        'P_share_eq_1': round(float((pool >= 0.999).mean()), 4),
        'P_share_eq_0': round(float((pool <= 0.001).mean()), 4),
        'P_share_le_0.5': round(float((pool <= 0.5).mean()), 4),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='QB participation causal audit')
    ap.add_argument('--seasons', default='2021,2022,2023,2024')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    seasons = [int(x) for x in a.seasons.split(',')]
    recs, prov = build(seasons)
    rows = []
    for r in recs:
        for b in r['backups']:
            rows.append({'season': r['season'], 'game_id': r['game_id'],
                         'team': r['team'], 'starter': r['starter'],
                         'established_incumbent': r['established_incumbent'],
                         'team_dropbacks': r['total_dropbacks'],
                         'starter_share': round(r['starter_share'], 4),
                         **{k: b[k] for k in ('pid', 'dropbacks', 'share',
                                              'classification', 'entry_qtr',
                                              'entry_secs_remaining',
                                              'margin_at_entry',
                                              'starter_returned')}})
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            for x in rows:
                w.writerow(x)
    cond = conditional_rates(recs)
    cell = qb3_cell_1_1()
    summary = {
        'artifact': 'QB_PARTICIPATION_CAUSAL_AUDIT',
        'spec_version': SPEC_VERSION,
        'governance': 'DIAGNOSIS ONLY. No predictive value is changed.',
        'seasons': seasons, 'outcome_provenance': prov,
        'n_team_games': len(recs),
        'n_backup_appearances': len(rows),
        'predeclared_thresholds': {
            'blowout_margin': BLOWOUT_MARGIN,
            'late_seconds_remaining': LATE_SECONDS,
            'rotation_max_share': ROTATION_MAX_SHARE},
        'classification_counts': dict(collections.Counter(
            x['classification'] for x in rows)),
        'what_play_by_play_cannot_do': (
            'an injury and a benching are identical in these bytes: the '
            'starter stops taking snaps and does not return. They are reported '
            'together as REPLACEMENT_NO_RETURN and are NOT split on a guess.'),
        'conditional_on_established_incumbent_no_rotation': cond,
        'qb3_current_allocation_same_population': cell,
        'hard_rock_backup_qb_markets': (
            'NOT USED. Not a feature, not a rule, not a filter, not a '
            'conditioning variable anywhere in this module.'),
    }
    if cond and cell:
        summary['the_comparison'] = {
            'p_starter_takes_every_dropback_REALITY': cond['p_starter_share_eq_1'],
            'p_starter_takes_every_dropback_QB3': cell['P_share_eq_1'],
            'p_starter_takes_zero_REALITY': cond['p_starter_share_eq_0'],
            'p_starter_takes_zero_QB3': cell['P_share_eq_0'],
            'starter_share_mean_REALITY': cond['starter_share_mean'],
            'starter_share_mean_QB3': cell['pool_mean'],
        }
    sp = out.with_suffix('.summary.json')
    sp.write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f'{len(recs)} team-game(s), {len(rows)} backup appearance(s) -> {out}')
    print(f'summary -> {sp}')
    print('classes:', summary['classification_counts'])
    if cond:
        print(f"\nCONDITIONAL (established incumbent, no planned rotation), "
              f"n={cond['n_team_games']}:")
        for k in ('p_qb2_any_dropback', 'p_qb2_share_ge_10pct',
                  'p_qb2_share_ge_25pct', 'p_qb2_share_ge_50pct',
                  'starter_share_mean', 'starter_share_median',
                  'p_starter_share_eq_1', 'p_starter_share_eq_0',
                  'p_starter_finished', 'p_replacement_no_return',
                  'p_blowout_relief'):
            print(f'   {k:32} {cond[k]}')
        print(f"\nQB3 cell (1, yes), n={cell['n']}:")
        for k in ('p_primary', 'pool_mean', 'P_share_eq_1', 'P_share_eq_0'):
            print(f'   {k:32} {cell[k]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
