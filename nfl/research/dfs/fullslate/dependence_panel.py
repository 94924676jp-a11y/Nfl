"""DFS-FS1: the canonical prediction-time dependence panel.

    python3.12 nfl/research/dfs/fullslate/dependence_panel.py --write

WHAT THIS IS, AND WHAT IT IS EXPLICITLY NOT

It is a DESCRIPTIVE VALIDATION TARGET for the world generator: a statement of
what dependence looks like in football that a simulator should be able to
reproduce. It is **not** a coefficient store. No number this module produces
may be read into an optimizer, a lineup rule, or a correlation matrix pasted
into a simulator. `FS1_NOT_A_LINEUP_RULE` is carried in the artifact and
`test_dfs_fs1_panel` enforces that none of these values appears as a code
literal in production.

The distinction is not pedantic. A measured pairwise coefficient is a summary
of two seasons under one labelling scheme with real sampling error, and the
previous adjudication found published coefficients that our own reproduction
disagrees with by up to 0.16. Freezing any of them into a decision rule
imports the sampling error, the labelling choice, and the disagreement.

WHY THIS IS A SEPARATE MODULE FROM `reproduce_external_panel.py`

That module exists to answer "do the external packet's numbers reconstruct
from its stated method". Its choices are the external report's choices,
including ones this panel rejects. This module owns its own declared spec and
shares only the two pieces that are pure mechanics: the play-by-play stat-line
builder and the scoring-coefficient resolver.

THE ONE LEAKAGE RULE, STATED ONCE

A role label may be computed only from weeks strictly earlier than the week
being labelled. Week 1 has no prior and is absent from the panel rather than
back-filled. `assert_no_current_game_information` re-derives every label from
a truncated history and requires an exact match, so the guarantee is checked
rather than asserted.

HONESTY ABOUT WHAT WAS DECLARED WHEN

This is not a blind pre-registration and saying otherwise would be false. The
role-assignment rule and the pair list were chosen knowing the reproduction
results from `06bc006`, which used the same two seasons. What was fixed before
any number in THIS module was computed: the uncertainty method (cluster
bootstrap over games, 2,000 resamples, seed 20260919), the tail quantile
(0.80), the decision to report Pearson and tail dependence as separate
quantities rather than one ranking, and the decision to report seasons
separately and never pool them. `SPEC['declared_before_measurement']` lists
exactly those and no more.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
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
from nfl.dfs.scoring import fanduel as FD        # noqa: E402

SPEC_VERSION = 'dfs-fs1-dependence-panel-1'
OUT = _REPO / 'nfl/research/dfs/fullslate/DFS_FS1_DEPENDENCE_PANEL.json'

TAIL_Q = 80.0
N_BOOT = 2000
SEED = 20260919

#: MUTUALLY EXCLUSIVE ROLES, ASSIGNED IN A DECLARED ORDER.
#:
#: The external packet's method permitted one player to hold two roles, and
#: measured on 2024 that happened in 26.2% of team-games for quarterback and
#: second rusher alone. A player is correlated with himself at r = 1, so a
#: panel that allows it is partly measuring its own labelling.
#:
#: Order matters and is declared: quarterback first, then pass catchers by
#: prior targets, then rushers by prior carries, each drawn from players not
#: already taken. A quarterback who leads his team in carries is the
#: quarterback, not the rusher.
ROLE_ORDER = (('QB', 'pass_att', 1), ('PC', 'targets', 3), ('RUSH', 'carries', 2))
ROLES = ('QB', 'PC1', 'PC2', 'PC3', 'RUSH1', 'RUSH2')

#: Every pair the directive names. `('QB','QB')` under `cross` is opposing
#: quarterbacks; `same` pairs are within one team-game.
SAME_TEAM_PAIRS = (
    ('QB', 'PC1'), ('QB', 'PC2'), ('QB', 'PC3'),
    ('QB', 'RUSH1'), ('QB', 'RUSH2'),
    ('RUSH1', 'RUSH2'),
    ('PC1', 'PC2'), ('PC1', 'PC3'), ('PC2', 'PC3'),
    ('PC1', 'RUSH1'),
)
CROSS_TEAM_PAIRS = (
    ('QB', 'QB'),
    ('QB', 'PC1'), ('QB', 'PC2'), ('QB', 'PC3'),
    ('PC1', 'PC1'), ('PC1', 'PC2'), ('PC2', 'PC2'),
    ('RUSH1', 'RUSH1'),
)
#: Named, and returned NOT_MEASURABLE rather than omitted. A pair that
#: silently vanishes from a panel is indistinguishable from one that was
#: measured and found uninteresting.
DST_PAIRS = (('RUSH1', 'own_DST'), ('RUSH1', 'opp_DST'),
             ('QB', 'own_DST'), ('QB', 'opp_DST'), ('PC1', 'opp_DST'))

SPEC = {
    'spec_version': SPEC_VERSION,
    'purpose': 'a descriptive validation target for the world generator',
    'not_a_coefficient_store':
        'no value here may be read into an optimizer, a lineup rule or a '
        'simulator correlation matrix',
    'role_assignment': {
        'mutually_exclusive': True,
        'order': [r[0] for r in ROLE_ORDER],
        'ranked_by': {r[0]: r[1] for r in ROLE_ORDER},
        'rule': 'a player already assigned a role is removed from every '
                'later ranking',
    },
    'labels': {
        'window': 'weeks strictly earlier than the week being labelled, '
                  'same season',
        'week_1': 'absent from the panel; no prior history exists and it is '
                  'not back-filled',
        'current_game_information': 'NONE -- checked by '
                                    'assert_no_current_game_information',
    },
    'scoring': {'draftkings': DK.SPEC_VERSION, 'fanduel': FD.SPEC_VERSION,
                'coefficients': 'imported from the certified adapters; none '
                                'restated here'},
    'forbidden_inputs': ['sportsbook price of any kind', 'DFS ownership',
                         'realized current-game usage', 'contest results'],
    'estimators': {
        'pearson': 'linear dependence on fantasy points',
        'joint_tail_lift': f'P(both >= own {TAIL_Q:.0f}th percentile) divided '
                           f'by the product of the marginals',
        'reported_separately': 'Pearson and tail dependence are different '
                               'quantities and are never combined into one '
                               'ranking',
    },
    'uncertainty': {
        'method': 'cluster bootstrap over GAMES',
        'why': 'the two team-games of one game are not independent draws',
        'resamples': N_BOOT, 'seed': SEED, 'interval': '95 percent',
    },
    'seasons': 'reported separately and never pooled, so year-to-year '
               'instability stays visible',
    'declared_before_measurement': [
        'cluster bootstrap over games, 2000 resamples, seed 20260919',
        f'tail quantile {TAIL_Q}',
        'Pearson and tail dependence reported as separate quantities',
        'seasons reported separately, never pooled',
    ],
    'not_declared_blind':
        'the role-assignment rule and the pair list were chosen knowing the '
        'reproduction results at 06bc006, on these same two seasons',
}


# ------------------------------------------------------------- labelling

def assign_roles_prior_only(rows: dict, weeks: dict) -> dict:
    """Mutually exclusive roles from strictly prior weeks. The declared rule."""
    by_tw = collections.defaultdict(dict)
    for (gid, team, pid), stat in rows.items():
        by_tw[(team, weeks[gid])][(gid, pid)] = stat
    out = {}
    for team in sorted({t for (t, _w) in by_tw}):
        cum = collections.defaultdict(collections.Counter)
        for w in sorted(w for (t, w) in by_tw if t == team):
            cur = by_tw[(team, w)]
            if not cur:
                continue
            gid = next(iter(cur))[0]
            if cum:                      # week 1 has no prior; it is skipped
                taken, role = set(), {}
                for prefix, field, k in ROLE_ORDER:
                    ranked = sorted(cum.items(),
                                    key=lambda kv: (-kv[1][field], kv[0]))
                    picked = [p for p, s in ranked
                              if s[field] > 0 and p not in taken][:k]
                    for i, pid in enumerate(picked):
                        role[prefix if k == 1 else f'{prefix}{i + 1}'] = pid
                        taken.add(pid)
                out[(gid, team)] = role
            for (_g, pid), stat in cur.items():
                cum[pid].update(stat)
    return out


def assert_no_current_game_information(rows, weeks, roles) -> dict:
    """Re-derive every label from a history truncated before its own week.

    The leakage guarantee is CHECKED, not asserted. Each label is rebuilt from
    a history that provably cannot see the game it labels, and must match.
    """
    by_team = collections.defaultdict(list)
    for (gid, team, pid), stat in rows.items():
        by_team[team].append((weeks[gid], gid, pid, stat))
    mismatches, checked = [], 0
    for (gid, team), role in roles.items():
        wk = weeks[gid]
        cum = collections.defaultdict(collections.Counter)
        for (w, _g, pid, stat) in by_team[team]:
            if w < wk:                     # strictly earlier. nothing else.
                cum[pid].update(stat)
        taken, rebuilt = set(), {}
        for prefix, field, k in ROLE_ORDER:
            ranked = sorted(cum.items(),
                            key=lambda kv: (-kv[1][field], kv[0]))
            picked = [p for p, s in ranked
                      if s[field] > 0 and p not in taken][:k]
            for i, pid in enumerate(picked):
                rebuilt[prefix if k == 1 else f'{prefix}{i + 1}'] = pid
                taken.add(pid)
        checked += 1
        if rebuilt != role:
            mismatches.append({'game_id': gid, 'team': team,
                               'panel': role, 'rebuilt': rebuilt})
    return {'checked': checked, 'n_mismatches': len(mismatches),
            'mismatches': mismatches[:5],
            'guarantee': 'every role label re-derives from a history '
                         'truncated strictly before its own week'}


# ------------------------------------------------------------ estimation

def _pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def _tail_lift(a, b, q=TAIL_Q):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 20:
        return None
    ta, tb = np.percentile(a, q), np.percentile(b, q)
    pa, pb = (a >= ta).mean(), (b >= tb).mean()
    if pa * pb == 0:
        return None
    return float((((a >= ta) & (b >= tb)).mean()) / (pa * pb))


def _bootstrap(units, stat, n_boot=N_BOOT, seed=SEED):
    """`units` is a list of per-GAME (a_values, b_values) tuples.

    Resampling games rather than team-games is the whole point: the two sides
    of one game share its scoring environment and are not two draws.
    """
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(units), len(units))
        a = [v for i in idx for v in units[i][0]]
        b = [v for i in idx for v in units[i][1]]
        s = stat(a, b)
        if s is not None:
            out.append(s)
    if len(out) < n_boot // 4:
        return None
    return [round(float(np.percentile(out, 2.5)), 4),
            round(float(np.percentile(out, 97.5)), 4)]


def _same_units(tg, x, y):
    by_game = collections.defaultdict(list)
    for (gid, team), v in tg.items():
        by_game[gid].append((v[x], v[y]))
    return [([p[0] for p in rows], [p[1] for p in rows])
            for rows in by_game.values()]


def _cross_units(tg, x, y):
    by_game = collections.defaultdict(dict)
    for (gid, team), v in tg.items():
        by_game[gid][team] = v
    units = []
    for gid, sides in by_game.items():
        if len(sides) != 2:
            continue
        t1, t2 = sorted(sides)
        units.append(([sides[t1][x], sides[t2][x]],
                      [sides[t2][y], sides[t1][y]]))
    return units


def _measure(units):
    a = [v for u in units for v in u[0]]
    b = [v for u in units for v in u[1]]
    n_finite = int(np.isfinite(np.asarray(a, float)).sum())
    return {
        'pearson': _pearson(a, b),
        'pearson_ci95': _bootstrap(units, _pearson),
        'tail_lift': _tail_lift(a, b),
        'tail_lift_ci95': _bootstrap(units, _tail_lift),
        'n_games': len(units), 'n_observations': n_finite,
    }


# ----------------------------------------------------------------- panel

def build(season: int, site: str) -> dict:
    rows, weeks = RX.build_player_games(_REPO / RX.BLOBS[season])
    roles = assign_roles_prior_only(rows, weeks)
    leak = assert_no_current_game_information(rows, weeks, roles)
    coeff = RX.resolve_coefficients(DK if site == 'DK' else FD)
    pts = {k: RX._score(v, coeff) for k, v in rows.items()}
    tg = {}
    for (gid, team), role in roles.items():
        tg[(gid, team)] = {r: pts.get((gid, team, role[r]), 0.0)
                           if r in role else np.nan for r in ROLES}
    collisions = RX.role_collisions(roles)
    return {'team_games': tg, 'leakage_check': leak,
            'role_collisions': collisions, 'n_team_games': len(tg),
            'weeks': sorted({weeks[g] for (g, _t) in roles})}


def run() -> dict:
    res = {'artifact': 'DFS_FS1_DEPENDENCE_PANEL',
           'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'spec': SPEC,
           'FS1_NOT_A_LINEUP_RULE':
               'These are descriptive validation targets for the simulator. '
               'Converting any coefficient here into a lineup rule, an '
               'exposure cap or a simulator correlation input is forbidden.',
           'simulator_comparison': {
               'state': 'PENDING',
               'blocked_by': 'no full-slate joint-world generator exists; the '
                             'only sealed worlds are one single-game board',
               'how_it_will_be_done':
                   'score each simulated world with the same certified '
                   'adapters, form the same role panel, and compare SIGN and '
                   'ORDERING of Pearson and tail lift separately. Magnitudes '
                   'are not comparable: history is one observation per game '
                   'and carries between-matchup variation, while a sealed '
                   'board is many observations of one fixture.'},
           'dst_pairs': {
               'state': 'NOT_MEASURABLE',
               'code': 'FS1_DST_SCORING_ABSENT',
               'pairs': [f'{a}|{b}' for a, b in DST_PAIRS],
               'why': 'there is no DST scoring adapter in this repository '
                      '(statline.NOT_SIMULATED: "the engine produces no '
                      'team-defence outputs at all"), and DraftKings '
                      'points-allowed tiers cannot be verified without '
                      'network access. Named rather than omitted.',
               'unblocked_by': 'docs/AGENT_OUTBOX.md, the site-rules request'},
           'panels': {}}

    for site in ('DK', 'FD'):
        for season in (2024, 2025):
            p = build(season, site)
            tg = p['team_games']
            same = {f'{x}|{y}': _measure(_same_units(tg, x, y))
                    for x, y in SAME_TEAM_PAIRS}
            cross = {f'{x}|opp_{y}': _measure(_cross_units(tg, x, y))
                     for x, y in CROSS_TEAM_PAIRS}
            res['panels'][f'{site}_{season}'] = {
                'site': site, 'season': season,
                'n_team_games': p['n_team_games'],
                'weeks_present': p['weeks'],
                'role_collisions': p['role_collisions'],
                'leakage_check': p['leakage_check'],
                'same_team': same, 'cross_team': cross}
    # Pearson-versus-tail disagreement, which is the reason both are reported.
    dis = []
    for key, panel in res['panels'].items():
        for pair, m in panel['same_team'].items():
            if m['pearson'] is None or m['tail_lift'] is None:
                continue
            if (m['pearson'] < 0) != (m['tail_lift'] < 1.0):
                dis.append({'panel': key, 'pair': pair,
                            'pearson': m['pearson'],
                            'tail_lift': m['tail_lift']})
    res['pearson_and_tail_disagree_on'] = dis
    res['n_pearson_tail_disagreements'] = len(dis)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    r = run()
    for key, p in r['panels'].items():
        lk = p['leakage_check']
        print(f"{key}: {p['n_team_games']} team-games, "
              f"collisions {p['role_collisions'] or 'none'}, "
              f"leakage mismatches {lk['n_mismatches']}/{lk['checked']}")
    print()
    dk24 = r['panels']['DK_2024']
    for pair, m in list(dk24['same_team'].items())[:6]:
        ci = m['pearson_ci95']
        tci = m['tail_lift_ci95']
        print(f"  DK 2024 {pair:14s} r={m['pearson']:+.3f} "
              f"[{ci[0]:+.3f},{ci[1]:+.3f}]  "
              f"tail={m['tail_lift']:.3f} [{tci[0]:.3f},{tci[1]:.3f}]")
    print(f"\nPearson and tail lift disagree in sign on "
          f"{r['n_pearson_tail_disagreements']} pair-panels")
    print(f"DST pairs: {r['dst_pairs']['state']} "
          f"[{r['dst_pairs']['code']}]")
    if a.write:
        OUT.write_text(json.dumps(r, indent=1, sort_keys=True,
                                  default=str) + '\n')
        print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
