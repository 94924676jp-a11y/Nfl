"""Recompute DET @ BUF optimal worlds with site legality enforced.

Runs the SAME universe twice -- once with the both-teams rule in the DP state
and once without -- so the effect of the correction is measured rather than
asserted. The old artifact is not touched; the corrected numbers go to a
successor.

The universe is unchanged on purpose. Kickers are still outside it, and that
is a SEPARATE defect with a separate repair; mixing the two would make it
impossible to say which change moved which number.
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
OLD = HERE / 'OPTIMAL_WORLDS.json'
NEW = HERE / 'OPTIMAL_WORLDS_v2.json'
DELTA = HERE / 'OPTIMAL_WORLDS_LEGALITY_DELTA.json'


def main() -> int:
    u = U.build()
    if u.state is not State.PASS:
        print(f'{u.state.value}[{u.code}] {u.detail}')
        return 1
    players = u.value['playable']
    print(f'{len(players)} player(s) in the optimization universe')

    print('--- unconstrained (reproduces the pre-correction answer) ---')
    un = OW.solve(players, chunk_report=4000, require_team_coverage=False)
    print(f'{un.state.value}[{un.code}] {un.detail}')
    print('--- lawful (both clubs required, in the DP state) ---')
    law = OW.solve(players, chunk_report=4000, require_team_coverage=True)
    print(f'{law.state.value}[{law.code}] {law.detail}')
    for o in (un, law):
        if o.state is not State.PASS:
            return 1

    names = law.value['names']
    tb = {p['name']: p['team'] for p in players}

    # How many worlds actually change, and how many of the OLD optima were
    # unenterable.
    changed = illegal = 0
    for a, b in zip(un.value['lineups'], law.value['lineups']):
        if a is None or b is None:
            continue
        if len({tb[names[i]] for i in [a[0]] + list(a[1])}) < 2:
            illegal += 1
        if a != b:
            changed += 1
    n = sum(1 for a, b in zip(un.value['lineups'], law.value['lineups'])
            if a is not None and b is not None)

    old_rows = {r['name']: r for r in law.value['rows']}
    un_rows = {r['name']: r for r in un.value['rows']}
    per_player = []
    for nm, r in sorted(old_rows.items()):
        o = un_rows[nm]
        per_player.append({
            'name': nm, 'team': r['team'], 'tag': r['tag'],
            'salary': r['salary'],
            'p_optimal_before': o['p_optimal'],
            'p_optimal_after': r['p_optimal'],
            'd_p_optimal': r['p_optimal'] - o['p_optimal'],
            'p_optimal_captain_before': o['p_optimal_captain'],
            'p_optimal_captain_after': r['p_optimal_captain'],
            'd_p_optimal_captain': (r['p_optimal_captain']
                                    - o['p_optimal_captain'])})
    per_player.sort(key=lambda r: -abs(r['d_p_optimal']))

    NEW.write_text(json.dumps(
        {'spec_version': OW.SPEC_VERSION,
         'supersedes': 'OPTIMAL_WORLDS.json',
         'site_legality_enforced': True,
         'detail': law.detail,
         'evidence': {k: v for k, v in law.evidence.items() if k != 'cause'},
         'rows': law.value['rows']}, indent=1, sort_keys=True))
    DELTA.write_text(json.dumps(
        {'artifact': 'DET_BUF_2026W2_OPTIMAL_WORLDS_LEGALITY_DELTA',
         'what_changed': ('the both-teams rule moved from a post-hoc field on '
                          'candidates.py into the DP state, so the optimum is '
                          'now the optimum of a lawful problem'),
         'universe_unchanged': ('kickers are still outside the optimization '
                                'universe; that is a separate defect with a '
                                'separate repair, kept separate so the effect '
                                'of THIS correction is attributable'),
         'n_worlds_compared': n,
         'n_worlds_optimum_changed': changed,
         'share_worlds_changed': changed / max(n, 1),
         'n_old_optima_that_were_unenterable': illegal,
         'share_old_optima_unenterable': illegal / max(n, 1),
         'mean_optimal_score_before': un.evidence['mean_optimal_score'],
         'mean_optimal_score_after': law.evidence['mean_optimal_score'],
         'mean_optimal_score_delta': (law.evidence['mean_optimal_score']
                                      - un.evidence['mean_optimal_score']),
         'per_player': per_player}, indent=1, sort_keys=True))
    for p in (NEW, DELTA):
        c = AC.claim(p, schema=['rows'] if p is NEW else ['per_player'],
                     label=p.name)
        if c.state is not State.PASS:
            return 1
    print(f'\nworlds compared {n}; optimum changed in {changed} '
          f'({changed / max(n, 1):.2%}); old optima unenterable {illegal} '
          f'({illegal / max(n, 1):.2%})')
    print(f'mean optimal score {un.evidence["mean_optimal_score"]:.3f} -> '
          f'{law.evidence["mean_optimal_score"]:.3f}')
    print('\nlargest moves in p_optimal:')
    for r in per_player[:8]:
        print(f"  {r['name']:22s} {r['p_optimal_before']:.4f} -> "
              f"{r['p_optimal_after']:.4f}  ({r['d_p_optimal']:+.4f})  "
              f"cpt {r['p_optimal_captain_before']:.4f} -> "
              f"{r['p_optimal_captain_after']:.4f} "
              f"({r['d_p_optimal_captain']:+.4f})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
