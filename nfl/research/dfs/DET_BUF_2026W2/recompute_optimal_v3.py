"""v3: the lawful solve over the universe that now includes named kickers.

TWO CORRECTIONS, MEASURED SEPARATELY ON PURPOSE.

  v1 -> v2   site legality enters the DP state. Same 28-player universe.
  v2 -> v3   kickers enter the universe, resolved by gsis_id. Same lawful DP.

Running them together would have made it impossible to say which change moved
which number, and the first change turned out to move almost nothing while the
second changes the set of players the metric is even defined over.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402
from nfl.dfs.showdown import optimal_worlds as OW                      # noqa: E402
from nfl.dfs.showdown import universe as U                             # noqa: E402

HERE = _REPO / 'nfl/research/dfs/DET_BUF_2026W2'
V2 = HERE / 'OPTIMAL_WORLDS_v2.json'
V3 = HERE / 'OPTIMAL_WORLDS_v3.json'
DELTA = HERE / 'OPTIMAL_WORLDS_KICKER_DELTA.json'


def main() -> int:
    u = U.build()
    if u.state is not State.PASS:
        print(f'{u.state.value}[{u.code}] {u.detail}')
        return 1
    players = u.value['playable']
    ks = sorted(p['name'] for p in players if p['pos'] == 'K')
    print(f'{len(players)} player(s) in the optimization universe; '
          f'kickers {ks}')
    if not ks:
        print('REFUSING: no kicker reached the universe, so v3 is v2.')
        return 1
    law = OW.solve(players, chunk_report=4000, require_team_coverage=True)
    print(f'{law.state.value}[{law.code}] {law.detail}')
    if law.state is not State.PASS:
        return 1
    V3.write_text(json.dumps(
        {'spec_version': OW.SPEC_VERSION,
         'supersedes': 'OPTIMAL_WORLDS_v2.json',
         'site_legality_enforced': True,
         'kickers_in_optimization_universe': ks,
         'kickers_resolved_by': 'gsis_id, never (team, position)',
         'detail': law.detail,
         'evidence': {k: v for k, v in law.evidence.items() if k != 'cause'},
         'rows': law.value['rows']}, indent=1, sort_keys=True))

    prev = {r['name']: r for r in json.loads(V2.read_text())['rows']}
    now = {r['name']: r for r in law.value['rows']}
    per = []
    for nm, r in sorted(now.items()):
        o = prev.get(nm)
        per.append({
            'name': nm, 'team': r['team'], 'pos': r['pos'],
            'new_to_the_universe': o is None,
            'p_optimal_v2': (o['p_optimal'] if o else None),
            'p_optimal_v3': r['p_optimal'],
            'd_p_optimal': (r['p_optimal'] - o['p_optimal']) if o else None,
            'p_optimal_captain_v2': (o['p_optimal_captain'] if o else None),
            'p_optimal_captain_v3': r['p_optimal_captain'],
            'd_p_optimal_captain': ((r['p_optimal_captain']
                                     - o['p_optimal_captain'])
                                    if o else None)})
    moved = [r for r in per if r['d_p_optimal'] is not None]
    moved.sort(key=lambda r: -abs(r['d_p_optimal']))
    v2ev = json.loads(V2.read_text())['evidence']
    DELTA.write_text(json.dumps(
        {'artifact': 'DET_BUF_2026W2_OPTIMAL_WORLDS_KICKER_DELTA',
         'what_changed': ('two named kickers entered the optimization '
                          'universe, resolved by gsis_id through the governed '
                          'roster vintage'),
         'universe_size_v2': len(prev), 'universe_size_v3': len(now),
         'kickers': ks,
         'mean_optimal_score_v2': v2ev['mean_optimal_score'],
         'mean_optimal_score_v3': law.evidence['mean_optimal_score'],
         'mean_optimal_score_delta': (law.evidence['mean_optimal_score']
                                      - v2ev['mean_optimal_score']),
         'per_player': per}, indent=1, sort_keys=True))
    for p in (V3, DELTA):
        c = AC.claim(p, schema=['rows'] if p is V3 else ['per_player'],
                     label=p.name)
        if c.state is not State.PASS:
            return 1
    print(f"\nmean optimal score {v2ev['mean_optimal_score']:.3f} -> "
          f"{law.evidence['mean_optimal_score']:.3f}")
    print('kickers:')
    for r in per:
        if r['new_to_the_universe']:
            print(f"  {r['name']:22s} p_optimal {r['p_optimal_v3']:.4f}  "
                  f"cpt {r['p_optimal_captain_v3']:.4f}  (was UNDEFINED)")
    print('largest moves among players already in the universe:')
    for r in moved[:8]:
        print(f"  {r['name']:22s} {r['p_optimal_v2']:.4f} -> "
              f"{r['p_optimal_v3']:.4f}  ({r['d_p_optimal']:+.4f})  "
              f"cpt {r['d_p_optimal_captain']:+.4f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
