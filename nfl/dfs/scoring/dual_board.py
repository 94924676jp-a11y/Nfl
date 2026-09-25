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

from sportsplatform.governance import artifact_claim as AC  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.scoring import statline as SL                           # noqa: E402
from nfl.dfs import player_universe as PU
from nfl.dfs.scoring import draftkings as DK                         # noqa: E402
from nfl.dfs.scoring import fanduel as FD                            # noqa: E402
from nfl.dfs.showdown import universe as U                           # noqa: E402

SPEC_VERSION = 'nfl-dfs-dual-board-2'

#: The rules generation this board was scored under. v1 was built on a
#: FanDuel table that was later shown wrong on all three yardage bonuses, so
#: the version travels WITH the numbers rather than being inferred from a
#: filename. The v1 artifact is preserved unmodified; it is superseded, not
#: corrected in place.
RULES_VERSION = {
    'draftkings': 'nfl-dfs-scoring-draftkings-1 (VERIFIED against the engine)',
    'fanduel': 'nfl-dfs-scoring-fanduel-2 (VERIFIED against the official '
               'Rules & Scoring page, retrieved 2026-09-17)',
    'supersedes': 'DUAL_PLATFORM_BOARD.json, built under '
                  'nfl-dfs-scoring-fanduel-1, whose FanDuel bonuses were all '
                  'zero and are now all +3',
}
OUTPUT_NAME = 'DUAL_PLATFORM_BOARD_v2.json'
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
    # THE UNION, DISCOVERED. `L['dk_scoring']['row_ids']` is 30 of 32 players
    # on the sealed artifact: the two kickers carry their DK points in the
    # `kicking` layer, so a board built from one layer has no kicker row at
    # all -- and the stored-vs-recomputed identity check below never saw them.
    stored_by_id, _dk_rep = PU.dk_points_by_id(
        man, z, consumer='nfl.dfs.scoring.dual_board')
    ids = sorted(stored_by_id)
    kicker_ids = {g for g, layer in
                  PU.dk_universe(man, consumer='nfl.dfs.scoring.dual_board'
                                 )['layer_by_id'].items()
                  if layer == 'kicking'}
    n = int(next(iter(stored_by_id.values())).shape[0]) if stored_by_id else 0
    rows, worst = [], 0.0
    for g in ids:
        sl = SL.assemble(g, names.get(g, g), L, z, n)
        # A KICKER IS SCORED BY THE KICKER RULES. The offense scorer reads
        # passing, rushing and receiving, all zero for a kicker, so it would
        # return ~0 against a stored ~8.26 and blow up the identity residual
        # below -- which is how a missing position would have shown up as a
        # scoring bug. Both sites' kicker rules are identical here (3/4/5 by
        # distance, 1 per extra point), and SL.assemble already carries the
        # distance buckets off the `kicking` layer, so this is exact rather
        # than approximate.
        is_kicker = g in kicker_ids
        dk = DK.score_kicker(sl) if is_kicker else DK.score(sl)
        worst = max(worst, float(np.abs(dk - stored_by_id[g]).max()))
        fd = FD.score_kicker(sl) if is_kicker else FD.score(sl)
        rows.append({'name': names.get(g, g), 'gsis_id': g,
                     'DRAFTKINGS': _dist(dk), 'FANDUEL': _dist(fd),
                     'fd_minus_dk_mean': float(fd.mean() - dk.mean()),
                     'receptions_mean': float(sl.receptions.mean()),
                     # THE IDENTITY, CHECKED PER PLAYER. With the bonuses now
                     # agreeing, receptions are the only scored quantity that
                     # separates the sites, so this residual must be zero.
                     'identity_residual_max': float(np.abs(
                         fd - (dk - 0.5 * sl.receptions)).max())})
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
        rules_version=RULES_VERSION,
        identity_fd_equals_dk_minus_half_ppr_max_residual=max(
            r['identity_residual_max'] for r in rows),
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
    out = _REPO / 'nfl/research/dfs/DET_BUF_2026W2' / OUTPUT_NAME
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'rows': o.value}, indent=1, sort_keys=True))
    # THE ARTIFACT IS CLAIMED BY VERIFYING IT, never by
    # printing a path. `dual_board.py | head -22` once died
    # on SIGPIPE after the table printed and before the
    # write, and the run was reported as successful.
    c = AC.claim(out, schema=['rows', 'evidence'],
                 label=out.name)
    if c.state is not State.PASS:
        return 1
    print(f'FanDuel: {FD.rules_state().detail[:150]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
