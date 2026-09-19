"""Why the external coupling number and P5's disagree. One axis at a time.

    python3.12 nfl/research/dfs/fullslate/coupling_reconciliation.py --write

THE CONFLICT, STATED WITHOUT PICKING A WINNER

The external report says the repository's world generator has a sign error:
"archived play-by-play gives +0.1201 for 2024 and +0.2034 for 2025 across 272
games each" for club-versus-opponent offence, against a simulated -0.128. Its
own new panel measures the same idea as +0.083 and +0.186.

`nfl/research/coupling/game_offense_coupling.py` -- this project's canonical
P5 measurement -- found 2024 approximately -0.086 and 2025 approximately
+0.018, with intervals containing zero, against a simulation near -0.131.

Two measurements, opposite signs in 2024, both from the same two blobs. At
most one of them is measuring what the other is measuring. This module does
not adjudicate by authority; it computes every variant on a common footing and
isolates which methodological axis moves the number.

THE AXES, AND WHY EACH COULD PLAUSIBLY DO IT

1. **Units.** P5 measures OFFENSIVE YARDS, defined in its docstring as passing
   plus rushing and explicitly NOT including receiving, because receiving
   yards are the same yards seen from the other end. The external measures
   FANTASY POINTS. Fantasy points are dominated by touchdowns -- six apiece,
   four for a passing touchdown -- and touchdowns are the part of offence most
   tightly bound to game scoring environment. This is the leading candidate.
2. **Coverage.** P5 sums a club's yards. The external sums six ROLE PLAYERS.
   A six-player subset omits the rest of the roster.
3. **Population.** P5 uses all 272 games. The ex-ante panel drops week 1,
   leaving 256.
4. **Orientation.** Both sides of a game contribute, so the pairing must be
   symmetric; an accidental home-always-first ordering would change nothing
   for Pearson but is checked anyway.

NOTHING HERE AUTHORIZES A SIMULATOR CHANGE. The directive is explicit and it
is right: a disagreement between two historical estimands says nothing about
whether the world generator is wrong until the estimands agree.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

sys.path.insert(0, str(_REPO / 'nfl/research/dfs/fullslate'))
import reproduce_external_panel as RX            # noqa: E402
from nfl.dfs.scoring import draftkings as DK     # noqa: E402

SPEC_VERSION = 'fullslate-coupling-reconciliation-1'
OUT = _REPO / 'nfl/research/dfs/fullslate/FULLSLATE_COUPLING_RECONCILIATION.json'

#: Published values being reconciled. Transcribed once, tested never trusted.
EXTERNAL_CLAIM = {2024: 0.1201, 2025: 0.2034}
EXTERNAL_PANEL = {2024: 0.083, 2025: 0.186}
P5_CANONICAL = {2024: -0.086, 2025: 0.018}
P5_SIMULATION = -0.131


def club_game_totals(path: pathlib.Path) -> dict:
    """(game_id, team) -> club totals, several units, all from one pass.

    `offense_yards` is P5's definition exactly: passing plus rushing, with
    receiving deliberately excluded because it double-counts a completion.
    """
    t = collections.defaultdict(collections.Counter)
    weeks = {}
    with gzip.open(path, 'rt', errors='replace') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            gid = r.get('game_id') or ''
            po = (r.get('posteam') or '').strip()
            if not gid or not po:
                continue
            weeks[gid] = RX._i(r.get('week'), -1)
            k = (gid, po)
            if RX._i(r.get('complete_pass')) == 1:
                t[k]['pass_yards'] += RX._f(r.get('passing_yards'))
            if RX._i(r.get('rush_attempt')) == 1:
                t[k]['rush_yards'] += RX._f(r.get('rushing_yards'))
            if RX._i(r.get('touchdown')) == 1 and \
                    (r.get('td_team') or '').strip() == po:
                t[k]['offensive_td'] += (
                    1 if (RX._i(r.get('pass_touchdown')) == 1
                          or RX._i(r.get('rush_touchdown')) == 1) else 0)
    for k in t:
        t[k]['offense_yards'] = t[k]['pass_yards'] + t[k]['rush_yards']
    return t, weeks


def _pair(values: dict, keep_games=None):
    """Symmetric club-versus-opponent pairing. Each game contributes twice."""
    by_game = collections.defaultdict(dict)
    for (gid, team), v in values.items():
        if keep_games is not None and gid not in keep_games:
            continue
        by_game[gid][team] = v
    a, b = [], []
    for gid, sides in by_game.items():
        if len(sides) != 2:
            continue
        t1, t2 = sorted(sides)
        a.append(sides[t1]); b.append(sides[t2])
        a.append(sides[t2]); b.append(sides[t1])
    return np.asarray(a, float), np.asarray(b, float), len(by_game)


def _r(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def _ci(a, b, n_boot=2000, seed=20260919):
    """Bootstrap over GAMES, not team-games: the two sides are one draw."""
    rng = np.random.default_rng(seed)
    pairs = list(zip(a[::2], b[::2]))
    if len(pairs) < 10:
        return None
    out = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(pairs), len(pairs))
        xa = np.array([pairs[i][0] for i in idx] + [pairs[i][1] for i in idx])
        xb = np.array([pairs[i][1] for i in idx] + [pairs[i][0] for i in idx])
        v = _r(xa, xb)
        if v is not None:
            out.append(v)
    if not out:
        return None
    return [round(float(np.percentile(out, 2.5)), 4),
            round(float(np.percentile(out, 97.5)), 4)]


def run() -> dict:
    res = {'spec_version': SPEC_VERSION,
           'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'external_claim_272_games': EXTERNAL_CLAIM,
           'external_new_panel': EXTERNAL_PANEL,
           'p5_canonical_offense_yards': P5_CANONICAL,
           'p5_simulation': P5_SIMULATION,
           'authorizes_no_simulator_change':
               'a disagreement between two historical estimands says nothing '
               'about the world generator until the estimands agree',
           'variants': {}}

    coeff = RX.resolve_coefficients(DK)
    for season in (2024, 2025):
        blob = _REPO / RX.BLOBS[season]
        totals, weeks = club_game_totals(blob)
        rows, wk2 = RX.build_player_games(blob)
        roles = RX.assign_roles(rows, wk2, 'ex_ante', 'sequential_removal')
        pts = {k: RX._score(v, coeff) for k, v in rows.items()}

        # Club fantasy points over EVERY player, not only the six roles.
        club_fp = collections.Counter()
        for (gid, team, pid), p in pts.items():
            club_fp[(gid, team)] += p
        # Club fantasy points over the six ex-ante role players only.
        role_fp = {}
        for (gid, team), role in roles.items():
            role_fp[(gid, team)] = sum(
                pts.get((gid, team, role[r]), 0.0) for r in RX.ROLES
                if r in role)

        all_games = set(weeks)
        wk1 = {g for g, w in weeks.items() if w == 1}
        ex_ante_games = {g for (g, _t) in roles}

        variants = {
            'offense_yards_all_272 (P5 estimand)':
                (totals, 'offense_yards', all_games),
            'offense_yards_ex_ante_games':
                (totals, 'offense_yards', ex_ante_games),
            'offensive_touchdowns_all_272':
                (totals, 'offensive_td', all_games),
            'club_fantasy_points_all_players_all_272':
                (club_fp, None, all_games),
            'club_fantasy_points_all_players_ex_ante_games':
                (club_fp, None, ex_ante_games),
            'role_six_fantasy_points_ex_ante (external panel estimand)':
                (role_fp, None, ex_ante_games),
        }
        per = {}
        for name, (src, field, keep) in variants.items():
            if field is None:
                vals = {k: float(v) for k, v in src.items()}
            else:
                vals = {k: float(v[field]) for k, v in src.items()}
            a, b, n_games = _pair(vals, keep)
            per[name] = {'r': _r(a, b), 'n_games': n_games,
                         'n_ordered_rows': int(len(a)),
                         'ci95_game_bootstrap': _ci(a, b)}
        res['variants'][season] = per
        res.setdefault('week1_games_dropped', {})[season] = len(wk1)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    r = run()
    for season in (2024, 2025):
        print(f'--- {season} '
              f'(external claim {EXTERNAL_CLAIM[season]:+.4f}, '
              f'external panel {EXTERNAL_PANEL[season]:+.3f}, '
              f'P5 {P5_CANONICAL[season]:+.3f})')
        for name, v in r['variants'][season].items():
            ci = v['ci95_game_bootstrap']
            cis = f'[{ci[0]:+.3f}, {ci[1]:+.3f}]' if ci else 'n/a'
            print(f'   {name:56s} r={v["r"]:+.4f}  n_games={v["n_games"]:3d}'
                  f'  ci95 {cis}')
    if a.write:
        OUT.write_text(json.dumps(r, indent=1, sort_keys=True,
                                  default=str) + '\n')
        print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
