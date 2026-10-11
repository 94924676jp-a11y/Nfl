#!/usr/bin/env python3.12
"""PM-2: PM-1 plus the player's role band, and the simulator's participation factor phi (PREREG_PM2, 69fa882b).

    python3.12 nfl/research/participation_pm1/pm2.py     -> PM2_TABLE.json, PM2_REUSED_CHECK.json

Every unit definition, the pooling rule, the prior and the bootstrap are PM-1's (pm1.py); only the strata and phi are
new. The 2024-2025 score is written as REUSED: those seasons were read once, in aggregate, for PM-1's bars, so it can
never be the evidence that passes PM-2 (its primary evaluation is prospective, 2026 weeks 6-11).
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pm1  # noqa: E402

HERE = pathlib.Path(__file__).parent
LEVELS = (('role', 'desig', 'practice', 'pos', 'inj'), ('role', 'desig', 'practice', 'pos'),
          ('role', 'desig', 'pos'), ('role', 'desig'), ('desig',))


def role_band(r0):
    if r0 is None:
        return 'NO_BASELINE'
    return 'R_GE_070' if r0 >= 0.70 else 'R_040_070' if r0 >= 0.40 else 'R_LT_040'


def with_role(units):
    for u in units:
        u['role'] = role_band(u.get('r0'))
    return units


def control_by_band(seasons):
    """r/r0 of undesignated games that played, by (position group, role band), PM-1's baseline rule."""
    pg = {s: pm1.player_games(s) for s in seasons}
    inj = {s: pm1.injury_rows(s) for s in seasons}
    hist = collections.defaultdict(list)
    for s, games in pg.items():
        for (w, c), g in games.items():
            for p, (n_on, _l) in g['on'].items():
                d = (inj[s].get((w, c, p)) or {}).get('report_status') in ('Questionable', 'Doubtful', 'Out')
                hist[p].append((s, w, c, n_on / g['n_team'] if g['n_team'] else 0.0, d))
    votes = collections.defaultdict(collections.Counter)
    for s in seasons:
        for (_w, _c, p), r in inj[s].items():
            g = pm1.SKILL.get(r.get('position'))
            if g:
                votes[p][g] += 1
    pos = {p: c.most_common(1)[0][0] for p, c in votes.items()}
    out = collections.defaultdict(list)
    for p, h in hist.items():
        h.sort()
        if p not in pos:
            continue
        for i, (s, w, c, r, d) in enumerate(h):
            if d or r <= 0:
                continue
            prior = [x for x in h[:i] if x[0] == s and x[2] == c and not x[4] and x[3] > 0][-4:]
            if len(prior) < 2:
                continue
            r0 = statistics.median(x[3] for x in prior)
            if r0 > 0:
                out[(pos[p], role_band(r0))].append(r / r0)
    return {k: pm1._quantiles(v) for k, v in out.items()}, {f'{k[0]}|{k[1]}': len(v) for k, v in out.items()}


def phi_quantiles(q_des, q_ctl):
    """phi(u) = q_des(u) / q_ctl(u), clipped to [0, 1], made non-decreasing by a running maximum (PREREG_PM2 s.1)."""
    if not q_des or not q_ctl:
        return None
    out, run = [], 0.0
    for a, b in zip(q_des, q_ctl):
        v = min(1.0, max(0.0, a / b)) if b > 0 else 1.0
        run = max(run, v)
        out.append(round(run, 5))
    return out


def main() -> int:
    saved = pm1.LEVELS
    pm1.LEVELS = LEVELS
    try:
        units_fit, cnt_fit = pm1.build_units(pm1.FIT)
        with_role(units_fit)
        table = pm1.fit_table(units_fit)
        ctl, ctl_n = control_by_band(pm1.FIT)
        for key, c in table.items():
            parts = dict(zip(c['level'].split('|'), key.split('|')))
            pos, band = parts.get('pos'), parts.get('role')
            if pos and band:
                c['phi_quantiles'] = phi_quantiles(c['r_rel_quantiles'], ctl.get((pos, band)))
                c['phi_control'] = f'{pos}|{band}'
            else:
                c['phi_quantiles'], c['phi_control'] = None, None
        sens = {str(p): {k: v['p_no_participation'] for k, v in pm1.fit_table(units_fit, prior=p).items()
                         if v['level'] == '|'.join(LEVELS[0])} for p in pm1.SENSITIVITY_PRIORS}
        (HERE / 'PM2_TABLE.json').write_text(json.dumps({
            'ARTIFACT': 'PM2_PARTICIPATION_TABLE', 'prereg': 'PREREG_PM2_PARTICIPATION.md (69fa882b)',
            'fit_seasons': list(pm1.FIT), 'levels': ['|'.join(lv) for lv in LEVELS], 'min_cell': pm1.MIN_CELL,
            'prior': pm1.PRIOR, 'grid': pm1.GRID, 'control_n': ctl_n,
            'GAME_DAY_STATUS': ('p_no_participation is BEFORE game-day status is known. A player the evidence resolves '
                                'ACTIVE is given p_no_participation = 0 and phi from the played distribution: a '
                                'declared, untestable-here assumption (PREREG_PM2 s.2).'),
            'MEANING': {'phi_quantiles': 'the per-world participation factor on a 101-point grid: the share of his '
                                         'normal role a player keeps, net of ordinary week-to-week dispersion',
                        'p_early_exit': 'P(last on-field play before 75% of club plays | played); already inside phi'},
            'cells': table, 'sensitivity_prior_p_no_participation': sens}, indent=1) + '\n')
        frozen = json.loads((HERE / 'PM2_TABLE.json').read_text())['cells']
        units_held, cnt_held = pm1.build_units(pm1.HELD)
        with_role(units_held)
        ev = pm1.evaluate(frozen, units_held)
    finally:
        pm1.LEVELS = saved
    (HERE / 'PM2_REUSED_CHECK.json').write_text(json.dumps({
        'ARTIFACT': 'PM2_REUSED_CHECK', 'LABEL': 'REUSED: 2024-2025 were read for PM-1; this cannot pass PM-2',
        'held_out_seasons': list(pm1.HELD), **ev}, indent=1) + '\n')
    print(json.dumps({k: ev[k] for k in ('n_units', 'H_a_brier_improvement', 'H_c_crps_improvement', 'passes',
                                         'verdict')}), '(REUSED)')
    print('H_b', {k: ev['H_b_calibration'][k] for k in ('intercept', 'intercept_ci95', 'slope', 'slope_ci95')})
    for k in ('R_GE_070|QUESTIONABLE|LIMITED|WR_TE|SOFT_TISSUE_LOWER', 'R_GE_070|QUESTIONABLE|LIMITED|WR_TE',
              'R_GE_070|QUESTIONABLE|WR_TE', 'R_GE_070|QUESTIONABLE|FULL|WR_TE', 'R_GE_070|QUESTIONABLE|DID_NOT_PARTICIPATE|RB'):
        c = frozen.get(k)
        if c:
            q = c.get('phi_quantiles') or []
            print(f"{k:58s} n={c['n']:4d} P(no play)={c['p_no_participation']:.3f} "
                  f"phi p10/p50/p90={q[10] if q else None},{q[50] if q else None},{q[90] if q else None} "
                  f"shrunk={c['shrunk_toward']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
