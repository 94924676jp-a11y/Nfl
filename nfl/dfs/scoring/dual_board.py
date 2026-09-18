"""Both platforms' distributions from the SAME draws, side by side.

The football does not change between the two columns. Every difference in this
table is arithmetic applied to one set of simulated worlds, which is the whole
claim the architecture is making, and it is checkable: a player with no
receptions has the same DK and FD score up to the bonuses.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.scoring import statline as SL                           # noqa: E402
from nfl.dfs.scoring import draftkings as DK                         # noqa: E402
from nfl.dfs.scoring import fanduel as FD                            # noqa: E402
from nfl.dfs.showdown import universe as U                           # noqa: E402

SPEC_VERSION = 'nfl-dfs-dual-board-1'
PCT = (10, 25, 50, 75, 90, 95)


def _dist(v):
    return {'mean': float(v.mean()),
            **{f'p{k}': float(np.percentile(v, k)) for k in PCT},
            'p_zero': float((v <= 0).mean())}


def build() -> Outcome:
    F = U.FROZEN
    z = np.load(F / 'sealed_player_draws.npz')
    man = json.loads((F / 'sealed_player_draws_manifest.json').read_text())
    names = json.loads((F.parent / 'frozen_board_names.json').read_text())
    L = man['layers']
    ids = L['dk_scoring']['row_ids']
    stored = np.asarray(z['dk_scoring__dk_points'])
    n = stored.shape[1]
    rows, worst = [], 0.0
    for i, g in enumerate(ids):
        sl = SL.assemble(g, names.get(g, g), L, z, n)
        dk = DK.score(sl)
        worst = max(worst, float(np.abs(dk - stored[i]).max()))
        fd = FD.score(sl)
        rows.append({'name': names.get(g, g), 'gsis_id': g,
                     'DRAFTKINGS': _dist(dk), 'FANDUEL': _dist(fd),
                     'fd_minus_dk_mean': float(fd.mean() - dk.mean()),
                     'receptions_mean': float(sl.receptions.mean())})
    if worst > 1e-9:
        return Outcome.fail(
            'DUAL_BOARD_DK_RECONCILIATION_FAILED',
            f'the DraftKings adapter no longer reproduces the engine '
            f'(max abs diff {worst}). FanDuel numbers built on the same '
            f'assembly cannot be trusted either.',
            cause=Cause.DEPENDENCY, max_abs_diff=worst)
    rows.sort(key=lambda r: -r['DRAFTKINGS']['mean'])
    fdstate = FD.rules_state()
    return Outcome.ok(
        'DUAL_PLATFORM_BOARD', value=rows,
        detail=f'{len(rows)} player(s), {n} world(s); DraftKings reconciles to '
               f'the engine at {worst:.2e}; FanDuel rules are '
               f'{fdstate.code}',
        spec_version=SPEC_VERSION, n_players=len(rows), n_draws=n,
        dk_reconciliation_max_abs_diff=worst,
        dk_provenance=DK.PROVENANCE,
        fanduel_rules_state=fdstate.code,
        fanduel_numbers_are_research_only=fdstate.state is not State.PASS,
        same_draws_both_platforms=True,
        uses_live_game_outcome_data=False)


def main() -> int:
    o = build()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    print(f"\n{'player':22s} {'DK mean':>8s} {'DK p90':>7s} {'DK P0':>6s} "
          f"{'FD mean':>8s} {'FD p90':>7s} {'FD P0':>6s} {'FD-DK':>7s} "
          f"{'rec':>5s}")
    for r in o.value:
        d, f = r['DRAFTKINGS'], r['FANDUEL']
        print(f"{r['name']:22s} {d['mean']:8.2f} {d['p90']:7.1f} "
              f"{d['p_zero']:6.3f} {f['mean']:8.2f} {f['p90']:7.1f} "
              f"{f['p_zero']:6.3f} {r['fd_minus_dk_mean']:+7.2f} "
              f"{r['receptions_mean']:5.2f}")
    out = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/DUAL_PLATFORM_BOARD.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'rows': o.value}, indent=1, sort_keys=True))
    print(f'\nwrote {out.relative_to(_REPO)}')
    print(f'FanDuel: {FD.rules_state().detail[:150]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
