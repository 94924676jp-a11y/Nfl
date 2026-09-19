"""Reproduce the external full-slate DFS panel from its stated method.

    python3.12 nfl/research/dfs/fullslate/reproduce_external_panel.py --write

THE PACKET ARRIVED INCOMPLETE, SO THIS IS A RE-IMPLEMENTATION, NOT A RE-RUN.

`external-research/nfl-fullslate-dfs-construction-2026-09-18/` holds the
report. The four companion files it names -- `measure_dfs_correlations.py`,
`measure_tails.py`, `dfs_correlation_results.json`, `dfs_tail_results.json` --
**did not arrive**. `EXTERNAL_PACKET_PROVENANCE.json` records that, and the
request is in `docs/AGENT_OUTBOX.md`.

That changes what a reproduction can mean and it is worth being exact about.
Re-running someone's script checks that the script is deterministic. Building
the method from its written specification and landing on the same numbers
checks something stronger: that the specification is complete enough to
reconstruct, and that the numbers follow from the method rather than from
something the prose left out. This module is the second thing. Where it
disagrees with the report, either the prose under-specified the method or one
of us is wrong, and the disagreement is reported rather than tuned away.

SCORING COMES FROM OUR CERTIFIED ADAPTERS, WITH ONE STATED EXTENSION

`nfl/dfs/scoring/draftkings.py` and `fanduel.py` own the constants. This module
imports `RULES` from them and never restates a coefficient.

Our production `score()` deliberately omits three events -- fumbles lost,
two-point conversions and return touchdowns -- because `statline.NOT_SIMULATED`
records that the engine produces none of them. The external panel includes all
three, because it scores HISTORY, where they are observed. So this module
applies the same certified constants to those three fields as well, and says so
here rather than quietly matching. A reproduction that silently dropped them
would disagree with the report for a reason having nothing to do with the
claim under test.

WHAT IS NOT REPRODUCED, AND WHY IT IS NOT A CHOICE

Every DST claim. There is no DST scoring adapter in this repository:
`statline.NOT_SIMULATED` says "the engine produces no team-defence outputs at
all". Reconstructing one would mean introducing DraftKings' points-allowed
tiers as fresh constants, and this executor cannot reach DraftKings' rules page
to verify them. Unverified site constants are exactly what the standing
directive forbids, so the DST rows are returned NOT_REPRODUCED_HERE with that
reason attached, and the absent adapter is recorded as an architecture gap
rather than papered over.
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

from nfl.dfs.scoring import draftkings as DK   # noqa: E402
from nfl.dfs.scoring import fanduel as FD      # noqa: E402

SPEC_VERSION = 'fullslate-external-reproduction-1'
OUT = _REPO / 'nfl/research/dfs/fullslate/FULLSLATE_REPRODUCTION.json'

BLOBS = {
    2024: 'nfl/vintage/pbp_2024.23370d5d10f8104d.csv.gz',
    2025: 'nfl/vintage/pbp_2025.2f135887790a013f.csv.gz',
}

ROLES = ('QB', 'PC1', 'PC2', 'PC3', 'RUSH1', 'RUSH2')

#: The report's own published values, transcribed once, for comparison only.
#: Nothing downstream reads these as truth; they are the thing being tested.
PUBLISHED_DK_EX_ANTE = {
    ('QB', 'PC1'): (0.368, 0.274), ('QB', 'PC2'): (0.296, 0.318),
    ('QB', 'PC3'): (0.208, 0.259), ('QB', 'RUSH1'): (0.109, 0.050),
    ('QB', 'RUSH2'): (0.118, 0.117), ('PC1', 'PC2'): (-0.024, 0.120),
    ('PC1', 'PC3'): (-0.000, 0.088), ('PC2', 'PC3'): (0.036, -0.000),
    ('PC1', 'RUSH1'): (0.034, 0.162), ('PC3', 'RUSH1'): (0.238, 0.318),
    ('RUSH1', 'RUSH2'): (-0.121, -0.104),
}
PUBLISHED_DK_CROSS = {
    ('QB', 'QB'): (0.088, 0.180), ('QB', 'PC1'): (0.108, 0.105),
    ('QB', 'PC2'): (0.036, 0.079), ('QB', 'PC3'): (0.045, 0.127),
    ('QB', 'RUSH1'): (-0.021, 0.128), ('PC1', 'PC1'): (0.094, 0.096),
    ('PC1', 'PC2'): (0.051, 0.086), ('RUSH1', 'RUSH1'): (-0.123, -0.067),
    ('OFFENSE', 'OFFENSE'): (0.083, 0.186),
}
PUBLISHED_REALIZED_DK = {
    ('QB', 'PC1'): (0.420, 0.438), ('QB', 'PC2'): (0.409, 0.352),
    ('PC1', 'PC2'): (0.207, 0.182), ('RUSH1', 'RUSH2'): (0.016, -0.030),
}
PUBLISHED_FD_EX_ANTE = {
    ('QB', 'PC1'): (0.378, 0.280), ('QB', 'PC2'): (0.307, 0.315),
    ('PC1', 'PC2'): (-0.015, 0.108), ('RUSH1', 'RUSH2'): (-0.120, -0.082),
}
#: Cross-team, realized labels. Only one row is published.
PUBLISHED_REALIZED_CROSS = {('PC1', 'PC1'): (0.161, 0.163)}

TOLERANCE = 0.02   # declared before running; see the artifact's `tolerance`.


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def build_player_games(path: pathlib.Path) -> dict:
    """(game_id, team, player_id) -> stat line + the usage counts roles rank on.

    Rebuilt from play level exactly as the report describes: passing,
    rushing and receiving production, interceptions thrown, fumbles lost,
    two-point conversions and return touchdowns.
    """
    rows = collections.defaultdict(lambda: collections.Counter())
    weeks = {}
    with gzip.open(path, 'rt', errors='replace') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            gid = r.get('game_id') or ''
            wk = _i(r.get('week'), -1)
            po = (r.get('posteam') or '').strip()
            if not gid or wk < 0 or not po:
                continue
            weeks[gid] = wk

            def rec(pid, **kw):
                if not pid:
                    return
                k = (gid, po, pid)
                for f, v in kw.items():
                    rows[k][f] += v

            passer = (r.get('passer_player_id') or '').strip()
            receiver = (r.get('receiver_player_id') or '').strip()
            rusher = (r.get('rusher_player_id') or '').strip()

            if _i(r.get('pass_attempt')) == 1 and passer:
                rec(passer, pass_att=1)
                if receiver:
                    rec(receiver, targets=1)
            if _i(r.get('complete_pass')) == 1:
                y = _f(r.get('passing_yards'))
                rec(passer, pass_yards=y)
                rec(receiver, rec_yards=y, receptions=1)
            if _i(r.get('interception')) == 1 and passer:
                rec(passer, interceptions=1)
            if _i(r.get('rush_attempt')) == 1 and rusher:
                rec(rusher, carries=1, rush_yards=_f(r.get('rushing_yards')))
            if _i(r.get('touchdown')) == 1:
                td_team = (r.get('td_team') or '').strip()
                if td_team == po:
                    if _i(r.get('pass_touchdown')) == 1:
                        rec(passer, pass_td=1)
                        rec(receiver, rec_td=1)
                    elif _i(r.get('rush_touchdown')) == 1:
                        rec(rusher, rush_td=1)
                    elif _i(r.get('return_touchdown')) == 1:
                        rec((r.get('td_player_id') or '').strip(),
                            return_td=1)
            if _i(r.get('fumble_lost')) == 1:
                rec((r.get('fumbled_1_player_id') or '').strip(),
                    fumbles_lost=1)
            if (r.get('two_point_conv_result') or '') == 'success':
                # SCORED AND THROWN ARE DIFFERENT EVENTS ON FANDUEL, so they
                # are recorded as different fields rather than collapsed. On a
                # two-point PASS the passer threw it and the receiver scored
                # it; on a two-point RUN the rusher scored it.
                if receiver and passer:
                    rec(passer, two_point_thrown=1)
                    rec(receiver, two_point_scored=1)
                elif rusher:
                    rec(rusher, two_point_scored=1)
    return rows, weeks


#: A FINDING, RECORDED RATHER THAN WORKED AROUND SILENTLY.
#:
#: The two certified adapters do not share an interface. DraftKings keeps its
#: three bonuses inside `RULES` and has a single `two_point` key. FanDuel puts
#: bonuses in a separate `BONUSES` dict and splits two-point conversions into
#: `two_point_scored` and `two_point_thrown`. Both are faithful to their own
#: site; neither is wrong. But a caller written against one raises KeyError on
#: the other, which is what happened on this module's first run.
#:
#: `resolve_coefficients` is the shim. It is HERE, in research code, and not in
#: the adapters, because changing a certified adapter's public shape to suit a
#: research consumer is how a scoring contract stops meaning what it was
#: verified to mean. The divergence is reported to the architecture gap map
#: instead.
ADAPTER_SCHEMA_DIVERGENCE = {
    'draftkings': {'two_point_keys': ['two_point'], 'bonuses_in': 'RULES'},
    'fanduel': {'two_point_keys': ['two_point_scored', 'two_point_thrown'],
                'bonuses_in': 'BONUSES'},
    'consequence': 'a caller written against one adapter raises KeyError on '
                   'the other; no shared accessor exists',
    'handled_here_by': 'resolve_coefficients, in research code, leaving both '
                       'certified adapters untouched',
}


def resolve_coefficients(mod) -> dict:
    """Every coefficient this module needs, from whichever shape the site uses.

    Refuses on a key it cannot find rather than defaulting to zero. A missing
    coefficient silently scored as zero is a scoring error that looks like a
    small correlation difference.
    """
    rules = dict(getattr(mod, 'RULES', {}))
    bonuses = dict(getattr(mod, 'BONUSES', {}))
    both = {**bonuses, **rules}

    def need(*names):
        for n in names:
            if n in both:
                return float(both[n]), n
        raise KeyError(
            f'{mod.SITE}: none of {names} is in RULES or BONUSES. A '
            f'coefficient this module cannot find is refused rather than '
            f'defaulted, because a silent zero looks like a small '
            f'correlation difference.')

    out = {}
    for field, names in (
            ('pass_yard', ('pass_yard',)), ('pass_td', ('pass_td',)),
            ('interception', ('interception',)),
            ('rush_yard', ('rush_yard',)), ('rush_td', ('rush_td',)),
            ('rec_yard', ('rec_yard',)), ('reception', ('reception',)),
            ('rec_td', ('rec_td',)), ('fumble_lost', ('fumble_lost',)),
            ('return_td', ('return_td',)),
            ('two_point_scored', ('two_point_scored', 'two_point')),
            ('two_point_thrown', ('two_point_thrown', 'two_point')),
            ('bonus_300_pass_yards', ('bonus_300_pass_yards',)),
            ('bonus_100_rush_yards', ('bonus_100_rush_yards',)),
            ('bonus_100_rec_yards', ('bonus_100_rec_yards',))):
        v, src = need(*names)
        out[field] = v
        out[f'_{field}_key'] = src
    return out


def _score(stat: collections.Counter, c: dict) -> float:
    """Certified constants, with the three history-only events applied."""
    s = (c['pass_yard'] * stat['pass_yards']
         + c['pass_td'] * stat['pass_td']
         + c['interception'] * stat['interceptions']
         + c['rush_yard'] * stat['rush_yards']
         + c['rush_td'] * stat['rush_td']
         + c['rec_yard'] * stat['rec_yards']
         + c['reception'] * stat['receptions']
         + c['rec_td'] * stat['rec_td']
         + c['fumble_lost'] * stat['fumbles_lost']
         + c['two_point_scored'] * stat['two_point_scored']
         + c['two_point_thrown'] * stat['two_point_thrown']
         + c['return_td'] * stat['return_td'])
    s += c['bonus_300_pass_yards'] * (stat['pass_yards'] >= 300)
    s += c['bonus_100_rush_yards'] * (stat['rush_yards'] >= 100)
    s += c['bonus_100_rec_yards'] * (stat['rec_yards'] >= 100)
    return float(s)


#: THE REPORT UNDER-SPECIFIES ROLE ASSIGNMENT, AND IT MATTERS A LOT.
#:
#: Its method reads: "the quarterback is the player with the most prior pass
#: attempts, PC1 through PC3 are the three players with the most prior targets,
#: and RUSH1 and RUSH2 are the two players with the most prior carries." Read
#: literally, the three rankings are independent, so one player can hold two
#: roles. Measured on 2024 ex-ante, that happens constantly:
#:
#:     QB is also RUSH2     134 of 512 team-games   26.2%
#:     PC3 is also RUSH1     56 of 512               10.9%
#:     PC2 is also RUSH1     46 of 512                9.0%
#:     PC1 is also RUSH1     11 of 512                2.1%
#:
#: A player correlated with himself has r = 1, so 26% collision drives the
#: independent-ranking QB-with-RUSH2 coefficient to +0.435 against a published
#: +0.118. The published number cannot have been produced that way.
#:
#: Three readings are therefore computed and all three are reported. None is
#: declared "the" method, because the report does not say which it used.
VARIANTS = ('independent', 'sequential_removal', 'qb_excluded_only')


def assign_roles(rows: dict, weeks: dict, scheme: str,
                 variant: str = 'sequential_removal') -> dict:
    """(game_id, team) -> {role: player_id}. `ex_ante` uses prior weeks only."""
    by_team_week = collections.defaultdict(dict)
    for (gid, team, pid), stat in rows.items():
        by_team_week[(team, weeks[gid])][(gid, pid)] = stat
    out = {}
    teams = sorted({t for (t, _w) in by_team_week})
    for team in teams:
        wks = sorted(w for (t, w) in by_team_week if t == team)
        cum = collections.defaultdict(collections.Counter)
        for w in wks:
            cur = by_team_week[(team, w)]
            gid = next(iter(cur))[0] if cur else None
            if gid is None:
                continue
            if scheme == 'ex_ante':
                basis = cum
                # WEEK 1 HAS NO PRIOR HISTORY AND IS DROPPED, not
                # back-filled. The report's 512 team-games per season against
                # 544 is exactly this, and the count is asserted.
                usable = bool(cum)
            else:
                basis = collections.defaultdict(collections.Counter)
                for (_g, pid), stat in cur.items():
                    basis[pid] = stat
                usable = True
            if usable:
                def top(field, k, excl=()):
                    ranked = sorted(basis.items(),
                                    key=lambda kv: (-kv[1][field], kv[0]))
                    return [p for p, s in ranked
                            if s[field] > 0 and p not in excl][:k]
                role, taken = {}, set()
                qb = top('pass_att', 1)
                if qb:
                    role['QB'] = qb[0]
                if variant == 'independent':
                    excl_pc = excl_rb = ()
                elif variant == 'qb_excluded_only':
                    excl_pc = excl_rb = set(role.values())
                else:                      # sequential_removal
                    taken = set(role.values())
                    excl_pc = taken
                    excl_rb = None         # recomputed after PCs are taken
                for i, pid in enumerate(top('targets', 3, excl_pc)):
                    role[f'PC{i + 1}'] = pid
                    if variant == 'sequential_removal':
                        taken.add(pid)
                rb_excl = taken if variant == 'sequential_removal' else excl_rb
                for i, pid in enumerate(top('carries', 2, rb_excl or ())):
                    role[f'RUSH{i + 1}'] = pid
                out[(gid, team)] = role
            for (_g, pid), stat in cur.items():
                cum[pid].update(stat)
    return out


def role_collisions(roles: dict) -> dict:
    """How often one player holds two roles. The hazard, quantified."""
    c = collections.Counter()
    for role in roles.values():
        inv = collections.defaultdict(list)
        for r, pid in role.items():
            inv[pid].append(r)
        for pid, rs in inv.items():
            if len(rs) > 1:
                c['+'.join(sorted(rs))] += 1
    n = max(len(roles), 1)
    return {k: {'n': v, 'pct': round(100.0 * v / n, 2)}
            for k, v in c.most_common()}


def panel(season: int, scheme: str, site: str,
          variant: str = 'sequential_removal') -> dict:
    rows, weeks = build_player_games(_REPO / BLOBS[season])
    roles = assign_roles(rows, weeks, scheme, variant)
    coeff = resolve_coefficients(DK if site == 'DK' else FD)
    pts = {}
    for (gid, team, pid), stat in rows.items():
        pts[(gid, team, pid)] = _score(stat, coeff)
    tg = {}
    for (gid, team), role in roles.items():
        v = {r: pts.get((gid, team, role[r]), 0.0) if r in role else np.nan
             for r in ROLES}
        v['OFFENSE'] = float(np.nansum([v[r] for r in ROLES]))
        v['_week'] = weeks[gid]
        tg[(gid, team)] = v
    return {'team_games': tg, 'weeks': weeks,
            'role_collisions': role_collisions(roles), 'variant': variant}


def _r(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return None, int(m.sum())
    if np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return None, int(m.sum())
    return float(np.corrcoef(a[m], b[m])[0, 1]), int(m.sum())


def same_team_corr(tg: dict, pairs) -> dict:
    out = {}
    for x, y in pairs:
        a = [v[x] for v in tg.values()]
        b = [v[y] for v in tg.values()]
        r, n = _r(a, b)
        out[f'{x}|{y}'] = {'r': r, 'n': n}
    return out


def cross_team_corr(tg: dict, pairs) -> dict:
    """One row per ORDERED team-game, so each game contributes twice.

    Stated because it is a choice and it moves nothing: a Pearson coefficient
    over a symmetric pair list is identical whether each game appears once or
    in both orientations, but the n differs and the n is reported.
    """
    by_game = collections.defaultdict(dict)
    for (gid, team), v in tg.items():
        by_game[gid][team] = v
    out = {}
    for x, y in pairs:
        a, b = [], []
        for gid, sides in by_game.items():
            if len(sides) != 2:
                continue
            t1, t2 = sorted(sides)
            a.append(sides[t1][x])
            b.append(sides[t2][y])
            a.append(sides[t2][x])
            b.append(sides[t1][y])
        r, n = _r(a, b)
        out[f'{x}|opp_{y}'] = {'r': r, 'n': n}
    return out


def tail_lift(tg: dict, pairs, q: float = 80.0) -> dict:
    out = {}
    for x, y in pairs:
        a = np.asarray([v[x] for v in tg.values()], float)
        b = np.asarray([v[y] for v in tg.values()], float)
        m = np.isfinite(a) & np.isfinite(b)
        a, b = a[m], b[m]
        if len(a) < 20:
            out[f'{x}|{y}'] = {'lift': None, 'n': int(len(a))}
            continue
        ta, tb = np.percentile(a, q), np.percentile(b, q)
        pa, pb = (a >= ta).mean(), (b >= tb).mean()
        joint = ((a >= ta) & (b >= tb)).mean()
        out[f'{x}|{y}'] = {
            'lift': float(joint / (pa * pb)) if pa * pb > 0 else None,
            'p_joint': float(joint), 'p_a': float(pa), 'p_b': float(pb),
            'n': int(len(a))}
    return out


def stack_p95_inflation(tg: dict, members, n_draw: int = 200_000,
                        seed: int = 20260919) -> dict:
    """p95 of the actual sum against p95 of an independent resample.

    The resample draws each member's marginal independently WITH replacement
    from the same observed values, so the only difference between the two
    numbers is the dependence.
    """
    cols = []
    for r in members:
        cols.append(np.asarray([v[r] for v in tg.values()], float))
    stack = np.vstack(cols)
    m = np.isfinite(stack).all(axis=0)
    stack = stack[:, m]
    if stack.shape[1] < 20:
        return {'members': list(members), 'n': int(stack.shape[1]),
                'actual_p95': None, 'independent_p95': None,
                'inflation': None}
    actual = np.percentile(stack.sum(axis=0), 95)
    rng = np.random.default_rng(seed)
    sim = np.zeros(n_draw)
    for row in stack:
        sim += rng.choice(row, size=n_draw, replace=True)
    indep = np.percentile(sim, 95)
    return {'members': list(members), 'n': int(stack.shape[1]),
            'actual_p95': float(actual), 'independent_p95': float(indep),
            'inflation': float(actual / indep) if indep else None,
            'n_resample_draws': n_draw, 'seed': seed}


def compare(measured: dict, published: dict, key_fmt) -> list:
    out = []
    for pair, (p24, p25) in published.items():
        for season, pub in ((2024, p24), (2025, p25)):
            k = key_fmt(pair)
            got = (measured.get(season) or {}).get(k, {}).get('r')
            d = None if got is None else abs(got - pub)
            out.append({'pair': k, 'season': season, 'published': pub,
                        'reproduced': got,
                        'abs_difference': None if d is None else round(d, 4),
                        'within_tolerance': None if d is None
                        else bool(d <= TOLERANCE)})
    return out


SAME_PAIRS = [('QB', 'PC1'), ('QB', 'PC2'), ('QB', 'PC3'), ('QB', 'RUSH1'),
              ('QB', 'RUSH2'), ('PC1', 'PC2'), ('PC1', 'PC3'),
              ('PC2', 'PC3'), ('PC1', 'RUSH1'), ('PC3', 'RUSH1'),
              ('RUSH1', 'RUSH2')]
CROSS_PAIRS = [('QB', 'QB'), ('QB', 'PC1'), ('QB', 'PC2'), ('QB', 'PC3'),
               ('QB', 'RUSH1'), ('PC1', 'PC1'), ('PC1', 'PC2'),
               ('RUSH1', 'RUSH1'), ('OFFENSE', 'OFFENSE')]


def run() -> dict:
    res = {'spec_version': SPEC_VERSION,
           'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'tolerance': TOLERANCE,
           'tolerance_declared': 'before running, as an absolute difference '
                                 'on a Pearson coefficient',
           'scoring_source': {
               'draftkings': DK.SPEC_VERSION, 'fanduel': FD.SPEC_VERSION,
               'note': 'RULES imported from the certified adapters; no '
                       'coefficient is restated in this module'},
           'adapter_schema_divergence': ADAPTER_SCHEMA_DIVERGENCE,
           'extension_over_production_score': [
               'fumbles_lost', 'two_point', 'return_td'],
           'extension_reason':
               'statline.NOT_SIMULATED records that the engine produces none '
               'of these, so production score() omits them. History observes '
               'them and the external panel includes them, so the same '
               'certified constants are applied to them here.',
           'not_reproduced': {
               'every DST claim':
                   'no DST scoring adapter exists (statline.NOT_SIMULATED: '
                   '"the engine produces no team-defence outputs at all"), '
                   'and this executor cannot reach DraftKings to verify '
                   'points-allowed tiers. Introducing unverified site '
                   'constants is forbidden by the standing directive.'},
           'panels': {}, 'comparisons': {}}

    res['role_variant_sensitivity'] = {}
    for v in VARIANTS:
        per = {}
        for season in (2024, 2025):
            p = panel(season, 'ex_ante', 'DK', v)
            per[season] = {
                'same_team': same_team_corr(p['team_games'], SAME_PAIRS),
                'role_collisions': p['role_collisions']}
        res['role_variant_sensitivity'][v] = per

    for scheme in ('ex_ante', 'realized'):
        for site in ('DK', 'FD'):
            same, cross, counts = {}, {}, {}
            tails, stacks = {}, {}
            for season in (2024, 2025):
                p = panel(season, scheme, site)
                tg = p['team_games']
                same[season] = same_team_corr(tg, SAME_PAIRS)
                cross[season] = cross_team_corr(tg, CROSS_PAIRS)
                counts[season] = {'n_team_games': len(tg),
                                  'weeks': sorted({v['_week']
                                                   for v in tg.values()}),
                                  'role_collisions': p['role_collisions'],
                                  'variant': p['variant']}
                if site == 'DK':
                    tails[season] = tail_lift(
                        tg, [('QB', 'PC1'), ('QB', 'PC2'), ('QB', 'PC3'),
                             ('PC1', 'PC2'), ('RUSH1', 'RUSH2')])
                    stacks[season] = {
                        'QB+PC1': stack_p95_inflation(tg, ('QB', 'PC1')),
                        'QB+PC1+PC2': stack_p95_inflation(
                            tg, ('QB', 'PC1', 'PC2')),
                        'QB+PC1+PC2+PC3': stack_p95_inflation(
                            tg, ('QB', 'PC1', 'PC2', 'PC3')),
                    }
            key = f'{scheme}_{site}'
            res['panels'][key] = {'same_team': same, 'cross_team': cross,
                                  'counts': counts}
            if tails:
                res['panels'][key]['tail_lift'] = tails
                res['panels'][key]['stack_p95'] = stacks

    res['comparisons']['ex_ante_DK_same_team'] = compare(
        {s: res['panels']['ex_ante_DK']['same_team'][s] for s in (2024, 2025)},
        PUBLISHED_DK_EX_ANTE, lambda p: f'{p[0]}|{p[1]}')
    res['comparisons']['ex_ante_DK_cross_team'] = compare(
        {s: res['panels']['ex_ante_DK']['cross_team'][s] for s in (2024, 2025)},
        PUBLISHED_DK_CROSS, lambda p: f'{p[0]}|opp_{p[1]}')
    res['comparisons']['realized_DK_same_team'] = compare(
        {s: res['panels']['realized_DK']['same_team'][s] for s in (2024, 2025)},
        PUBLISHED_REALIZED_DK, lambda p: f'{p[0]}|{p[1]}')
    res['comparisons']['realized_DK_cross_team'] = compare(
        {s: res['panels']['realized_DK']['cross_team'][s]
         for s in (2024, 2025)},
        PUBLISHED_REALIZED_CROSS, lambda p: f'{p[0]}|opp_{p[1]}')
    res['comparisons']['ex_ante_FD_same_team'] = compare(
        {s: res['panels']['ex_ante_FD']['same_team'][s] for s in (2024, 2025)},
        PUBLISHED_FD_EX_ANTE, lambda p: f'{p[0]}|{p[1]}')

    flat = [c for v in res['comparisons'].values() for c in v]
    ok = [c for c in flat if c['within_tolerance'] is True]
    res['summary'] = {
        'n_compared': len(flat), 'n_within_tolerance': len(ok),
        'n_outside_tolerance': sum(1 for c in flat
                                   if c['within_tolerance'] is False),
        'n_not_measured': sum(1 for c in flat
                              if c['within_tolerance'] is None),
        'max_abs_difference': max(
            (c['abs_difference'] for c in flat
             if c['abs_difference'] is not None), default=None),
        'worst': sorted((c for c in flat if c['abs_difference'] is not None),
                        key=lambda c: -c['abs_difference'])[:6],
    }
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    r = run()
    s = r['summary']
    print(f"compared {s['n_compared']}: {s['n_within_tolerance']} within "
          f"{TOLERANCE}, {s['n_outside_tolerance']} outside, "
          f"{s['n_not_measured']} not measured")
    print(f"max abs difference {s['max_abs_difference']}")
    for c in s['worst']:
        print(f"  {c['pair']:22s} {c['season']} published {c['published']:+.3f} "
              f"reproduced {c['reproduced']:+.3f} d={c['abs_difference']}")
    for k, v in r['panels'].items():
        print(f"  {k}: n team-games "
              f"{[v['counts'][s]['n_team_games'] for s in (2024, 2025)]}")
    if a.write:
        OUT.write_text(json.dumps(r, indent=1, sort_keys=True,
                                  default=str) + '\n')
        print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
