#!/usr/bin/env python3.12
"""Shadow run of the event-consistent world arm on a published Showdown scenario. READ-ONLY on its inputs.

    python3.12 nfl/research/accounting_repair/run_event_consistent_shadow.py \\
        nfl/dfs/salaries/showdown_tb_dal/OFFICIAL nfl/research/accounting_repair/TB_DAL_2026W5

1. Reads the scenario's PROJ / STATE / DRAWS (never writes there).
2. Re-runs showdown_draws.build on that projection and state with the published seed and world count, and
   re-applies the incumbent published step (classic_slate_run.efficiency_worlds + anchor_means on the DST),
   exactly as nfl/tools/showdown_slate_run.run does. REFUSES unless the reproduced incumbent DK draws equal
   the published ones for every player -- otherwise "before" and "after" would not share their inputs.
3. Builds nfl/sim/event_consistent_worlds on the same raw worlds, for both declared club-passing anchors,
   and publishes them in the incumbent format under OUT_DIR.
4. Runs nfl/tools/world_accounting_check.check and event_consistent_worlds.event_checks on the published
   scenario (before) and the repaired one (after), and measures per-player and per-club mean drift.

Writes OUT_DIR/ACCOUNTING_REPAIR_REPORT.json and OUT_DIR/ACCOUNTING_REPAIR_REPORT.md. Fits nothing, fetches
nothing, reads no sportsbook price, and is consumed by no production path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import statistics
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _mean(v):
    return statistics.fmean(v) if v else 0.0


def _rel(p):
    try:
        return str(pathlib.Path(p).resolve().relative_to(_REPO))
    except ValueError:
        return str(p)


def run(scenario_dir, out_dir):
    from nfl.sim import event_consistent_worlds as ECW, game as G
    from nfl.tools import classic_slate_run as CR, showdown_draws as SD, world_accounting_check as WAC
    sdir, out = pathlib.Path(scenario_dir), pathlib.Path(out_dir)
    dp = next(sdir.glob('SHOWDOWN_*_DRAWS.json'))
    pub = json.loads(dp.read_text())
    tag = pub['tag']
    proj_p, state_p = sdir / f'SHOWDOWN_{tag}_PROJ.json', sdir / f'SHOWDOWN_{tag}_STATE.json'
    wpath = sdir / f'SHOWDOWN_{tag}_WORLDS.npz'
    inputs = {_rel(p): _sha(p) for p in (proj_p, state_p, dp, wpath)}
    if pub.get('projection_sha256') != _sha(proj_p) or pub.get('state_sha256') != _sha(state_p):
        raise SystemExit('REFUSED: the published draws do not name this projection/state')
    proj = json.loads(proj_p.read_text())
    rows = {SD.S.player_key(r['name'], r['team']): r for r in proj['rows'].values()}
    seed, n_sims = int(pub['seed']), int(pub['n_sims'])

    # ---- the raw worlds, rebuilt from the published inputs (intermediates to a temp dir, never the scenario)
    old_out = SD.OUT
    SD.OUT = pathlib.Path(tempfile.mkdtemp(prefix='ecw_raw_')) / 'draws.json'
    try:
        o = SD.build(str(proj_p), str(state_p), n_sims=n_sims, seed=seed,
                     volume_centre=G.VOLUME_CENTRE_PROJECTION, n_calib=n_sims)
    finally:
        SD.OUT = old_out
    if o.state.value != 'PASS':
        raise SystemExit(f'REFUSED: showdown_draws.build {o.state.value}[{o.code}] {o.detail}')
    art = o.value

    # ---- the incumbent published step, exactly as showdown_slate_run.run applies it
    targets = {k: r.get('dk_points') for k, r in rows.items() if isinstance(r.get('dk_points'), (int, float))}
    kickers = {k for k, r in rows.items() if r.get('position') == 'K'}
    inc = {k: list(v) for k, v in art['draws'].items()}
    dk_new, _sw, _eff = CR.efficiency_worlds(art['stat_draws'], rows, float(proj['int_rate']), seed + 99)
    inc.update(dk_new)
    dst = {k: v for k, v in inc.items() if k not in dk_new and k not in kickers}
    dst, _acc = CR.anchor_means(dst, targets)
    inc.update(dst)
    gap = max(max(abs(a - b) for a, b in zip(inc[k], pub['draws'][k])) for k in pub['draws'])
    if set(inc) != set(pub['draws']) or gap > 1e-9:
        raise SystemExit(f'REFUSED: INCUMBENT_NOT_REPRODUCED (max |DK diff| {gap})')

    # ---- the repaired arm, both declared anchors
    arms = {}
    for anchor, sub in ((ECW.ANCHOR_QB, 'EVENT_CONSISTENT'), (ECW.ANCHOR_REC, 'EVENT_CONSISTENT_RECEIVER_ANCHOR')):
        r = ECW.build(art, rows, float(proj['int_rate']), seed, club_pass_anchor=anchor)
        if r.state.value != 'PASS':
            raise SystemExit(f'REFUSED: {anchor} {r.state.value}[{r.code}] {r.detail}')
        ECW.publish(r.value, out / sub, tag, game_id=pub['game_id'], projection_sha=_sha(proj_p),
                    state_path=state_p, extra={'inputs_sha256': inputs})
        arms[anchor] = (sub, r.value)

    before = WAC.check(sdir)
    before_x = ECW.event_checks(sdir)
    rep = {'ARTIFACT': 'ACCOUNTING_REPAIR_REPORT', 'spec_version': ECW.SPEC_VERSION, 'tag': tag,
           'scenario_dir': _rel(sdir), 'inputs_sha256': inputs, 'n_worlds': n_sims, 'seed': seed,
           'incumbent_reproduced': {'max_abs_dk_diff': gap, 'players': len(pub['draws'])},
           'incumbent_dst_multiplicative_anchor': _acc['factors'],
           'SHADOW_ONLY': 'no production module reads these worlds',
           'before': {'world_accounting_check': before['VIOLATED'], 'event_checks': before_x['VIOLATED'],
                      'event_checks_not_measurable': before_x['NOT_MEASURABLE'],
                      'detail': {k: {kk: vv for kk, vv in v.items() if kk != 'first'}
                                 for k, v in before['checks'].items()}},
           'arms': {}}
    home, away = pub['home'], pub['away']
    for anchor, (sub, res) in arms.items():
        after = WAC.check(out / sub)
        after_x = ECW.event_checks(out / sub)
        drift = []
        for k in sorted(pub['draws']):
            a, b = pub['draws'][k], res['draws'][k]
            d = [y - x for x, y in zip(a, b)]
            sd = statistics.pstdev(d) if len(d) > 1 else 0.0
            drift.append({'player': k, 'position': rows.get(k, {}).get('position'),
                          'projection_dk': targets.get(k), 'incumbent_mean': round(_mean(a), 4),
                          'repaired_mean': round(_mean(b), 4), 'drift': round(_mean(b) - _mean(a), 4),
                          'paired_se': round(sd / len(d) ** 0.5, 4),
                          'repaired_minus_projection': (round(_mean(b) - targets[k], 4) if k in targets else None)})
        drift.sort(key=lambda r: -abs(r['drift']))
        stats = {}
        for k, lines in res['stat_worlds'].items():
            inc_l = _sw[k]
            stats[k] = {f: {'incumbent': round(_mean([w[i] for w in inc_l]), 4),
                            'repaired': round(_mean([w[i] for w in lines]), 4)}
                        for i, f in enumerate(CR.WORLD_FIELDS)}
        club = {}
        for c in (home, away):
            ks = [k for k in pub['draws'] if k.endswith('|' + c)]
            pos = lambda k: rows.get(k, {}).get('position')
            def tot(dd, which):
                sel = [k for k in ks if (which == 'ALL' or (which == 'SKILL' and pos(k) in ('QB', 'RB', 'WR', 'TE'))
                                         or pos(k) == which)]
                return round(sum(_mean(dd[k]) for k in sel), 3)
            col = 0 if c == home else 1
            club[c] = {w: {'incumbent': tot(pub['draws'], w), 'repaired': tot(res['draws'], w),
                           'change': round(tot(res['draws'], w) - tot(pub['draws'], w), 3)}
                       for w in ('SKILL', 'K', 'DST', 'ALL')}
            club[c]['club_points_mean'] = {
                'incumbent_continuous': round(_mean([p[col] for p in pub['world_points']['points']]), 3),
                'repaired_event_sum': round(_mean([p[col] for p in res['world_points']['points']]), 3)}
            club[c]['club_pass_yards_mean'] = {
                'incumbent_qb': res['account']['clubs'][c]['incumbent_qb_pass_yards_mean'],
                'incumbent_receivers': res['account']['clubs'][c]['incumbent_receiver_yards_sum_mean'],
                'repaired_both_sides': res['account']['clubs'][c]['club_pass_yards_target']}
        rep['arms'][anchor] = {
            'out_dir': _rel(out / sub), 'default': anchor == ECW.ANCHOR_QB,
            'after': {'world_accounting_check': after['VIOLATED'], 'event_checks': after_x['VIOLATED'],
                      'event_checks_not_measurable': after_x['NOT_MEASURABLE'],
                      'detail': {k: {kk: vv for kk, vv in v.items() if kk != 'first'}
                                 for k, v in after['checks'].items()},
                      'event_detail': after_x['checks']},
            'account': {k: v for k, v in res['account'].items() if k != 'incumbent_efficiency'},
            'player_drift_sorted': drift, 'skill_stat_means': stats, 'club': club,
            'club_stat_totals': {c: {f: {'incumbent': round(sum(v[f]['incumbent'] for k, v in stats.items()
                                                             if k.endswith('|' + c)), 3),
                                         'repaired': round(sum(v[f]['repaired'] for k, v in stats.items()
                                                            if k.endswith('|' + c)), 3)}
                                     for f in CR.WORLD_FIELDS} for c in (home, away)}}
    rep['before']['event_detail'] = before_x['checks']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ACCOUNTING_REPAIR_REPORT.json').write_text(json.dumps(rep, indent=1, default=str) + '\n')
    (out / 'ACCOUNTING_REPAIR_REPORT.md').write_text(_markdown(rep))
    return rep


def _markdown(rep):
    from nfl.sim import event_consistent_worlds as ECW
    b = rep['before']
    L = [f"# Event-consistent Showdown worlds -- shadow repair, {rep['tag']}", '',
         'Generated by `nfl/research/accounting_repair/run_event_consistent_shadow.py` from '
         f"`{rep['scenario_dir']}` (read-only), {rep['n_worlds']} worlds, seed {rep['seed']}. SHADOW ONLY: no "
         'production path reads these worlds. The incumbent was reproduced from the same inputs first '
         f"(max |DK diff| {rep['incumbent_reproduced']['max_abs_dk_diff']} over "
         f"{rep['incumbent_reproduced']['players']} players), so before and after share their raw worlds.", '',
         '## Violations (worlds; cells where stated)', '',
         '| check | before (published OFFICIAL) | after, QB anchor (default) | after, receiver anchor |',
         '|---|---|---|---|']
    names = sorted(set(b['detail']) | set(b['event_detail'])
                   | {k for a in rep['arms'].values() for k in a['after']['detail']}
                   | {k for a in rep['arms'].values() for k in a['after']['event_detail']})
    qa, ra = rep['arms'][ECW.ANCHOR_QB]['after'], rep['arms'][ECW.ANCHOR_REC]['after']

    def cell(side, k):
        d = side['detail'].get(k) or side['event_detail'].get(k)
        if d is None:
            return 'n/a'
        if d.get('state') == 'NOT_MEASURABLE':
            return 'NOT MEASURABLE'
        s = f"{d['violations']} / {d['of']}"
        if 'player_world_cells' in d:
            s += f" ({d['player_world_cells']} cells)"
        return s
    for k in names:
        L.append(f'| {k} | {cell(b, k)} | {cell(qa, k)} | {cell(ra, k)} |')
    for anchor, a in rep['arms'].items():
        L += ['', f"## Mean drift, {anchor}{' (default)' if a['default'] else ''}", '',
              'Repaired minus incumbent mean DK on the SAME worlds; paired SE = SD of the per-world difference / '
              'sqrt(n). Top 15 by absolute drift.', '',
              '| player | pos | projection | incumbent | repaired | drift | paired SE |', '|---|---|---|---|---|---|---|']
        for r in a['player_drift_sorted'][:15]:
            pj = '' if r['projection_dk'] is None else f"{r['projection_dk']:.3f}"
            L.append(f"| {r['player']} | {r['position']} | {pj} | {r['incumbent_mean']:.3f} | {r['repaired_mean']:.3f} "
                     f"| {r['drift']:+.3f} | {r['paired_se']:.3f} |")
        L += ['', '| club | skill DK (inc -> rep) | K | DST | all players | club points mean (continuous -> event sum) '
              '| club pass yds (inc QB / inc receivers -> repaired) |', '|---|---|---|---|---|---|---|']
        for c, v in a['club'].items():
            f = lambda w: f"{v[w]['incumbent']:.2f} -> {v[w]['repaired']:.2f} ({v[w]['change']:+.2f})"
            L.append(f"| {c} | {f('SKILL')} | {f('K')} | {f('DST')} | {f('ALL')} | "
                     f"{v['club_points_mean']['incumbent_continuous']:.2f} -> {v['club_points_mean']['repaired_event_sum']:.2f} | "
                     f"{v['club_pass_yards_mean']['incumbent_qb']:.1f} / {v['club_pass_yards_mean']['incumbent_receivers']:.1f}"
                     f" -> {v['club_pass_yards_mean']['repaired_both_sides']:.1f} |")
        L += ['', 'Club totals of per-player mean stats (skill players), incumbent -> repaired:', '',
              '| club | ' + ' | '.join(ECW.WORLD_FIELDS) + ' |', '|---' * (len(ECW.WORLD_FIELDS) + 1) + '|']
        for c, v in a['club_stat_totals'].items():
            L.append(f'| {c} | ' + ' | '.join(f"{v[f]['incumbent']:.3f} -> {v[f]['repaired']:.3f}"
                                             for f in ECW.WORLD_FIELDS) + ' |')
    L += ['', 'Incumbent DST multiplicative anchor (raw simulated DST mean -> projection). The repaired arm does '
          'not apply it, because the DST score must remain the DK scoring of its own events:', '']
    for k, v in rep['incumbent_dst_multiplicative_anchor'].items():
        L.append(f"- {k}: raw mean {v['raw_mean']}, projection {v['target']}, factor {v['factor']}")
    L += ['', '## Not represented (named, not faked)', '']
    for k, v in ECW.NOT_REPRESENTED.items():
        L.append(f'- `{k}`: {v}')
    L += ['', '## Open, and what needs the owner', '',
          '- WHICH SIDE OF THE PASSING GAME IS THE ANCHOR is a value judgement the data here cannot settle: the '
          'projection itself does not close club passing yards (QB vs receiver sum above), so one side must move. '
          'Both are built and reported; the QB side is the module default, not a ruling.',
          '- The DST projection and the simulator\'s own DST events disagree (incumbent anchor factors above). The '
          'incumbent hides it with a multiplicative rescale, which makes the published DST score something other '
          'than the DK scoring of its own components. This arm reports the disagreement instead.',
          '- Nothing here is wired into production, and no gate is changed. Promotion would be a separate, '
          'declared change with its own before/after.', '']
    a = rep['arms'][ECW.ANCHOR_QB]['account']
    L += ['', '## Arm account (default anchor)', '', '```', json.dumps(a, indent=1, default=str), '```', '']
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario_dir')
    ap.add_argument('out_dir')
    a = ap.parse_args(argv)
    rep = run(a.scenario_dir, a.out_dir)
    print('BEFORE', json.dumps(rep['before']['world_accounting_check']))
    for k, v in rep['arms'].items():
        print('AFTER ', k, json.dumps(v['after']['world_accounting_check']), json.dumps(v['after']['event_checks']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
