"""P4C step 0: WHAT IS THE CONSTRAINT? Measured before any model is chosen.

The directive is explicit that the constraint must not be assumed to be
"shares sum to 1". This module answers, per opportunity class and from the data:

  (a) what does the share of the FULL panel sum to?
  (b) what does the share of the MODELLED universe (WR/TE/RB, prior game seen)
      sum to?
  (c) how big is the residual mass, and who holds it?

Measured on TRAINING seasons 2020-2021 ONLY, so that the design of the
allocation mechanism is not conditioned on the evaluation seasons. The same
quantities are re-measured on 2022-2025 afterwards, as verification, and both
are reported.
"""
import collections, json, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
for p in (os.path.join(HERE, '..', 'p1'), os.path.join(HERE, '..', 'p2'),
          os.path.join(HERE, '..', 'p3'), P4B, '/home/user/nfl'):
    sys.path.insert(0, os.path.abspath(p))

CLASSES = {
    'snaps':      ('s_snaps',      'team_off_snaps',      ('WR', 'TE', 'RB')),
    'pass_snaps': ('s_pass_snaps', 'team_dropbacks_part', ('WR', 'TE', 'RB')),
    'targets':    ('s_targets',    'team_targets',        ('WR', 'TE', 'RB')),
    'carries':    ('s_carries',    'team_carries',        ('RB',)),
    'rz_carries': ('s_rz_carries', 'team_rz_carries',     ('RB',)),
}
TRAIN = (2020, 2021)
LATER = (2022, 2023, 2024, 2025)


def summarise(rows, seasons, cls):
    skey, dkey, pos = CLASSES[cls]
    g_all = collections.defaultdict(float)
    g_mod = collections.defaultdict(float)
    g_pos = collections.defaultdict(lambda: collections.defaultdict(float))
    g_nop = collections.defaultdict(float)       # modelled position, NO prior game
    for r in rows:
        if r['season'] not in seasons:
            continue
        s = r.get(skey)
        if s is None:
            continue
        k = (r['team'], r['ord'])
        g_all[k] += s
        g_pos[k][r['position']] += s
        if r['position'] in pos:
            if (r.get('f_n_prior') or 0) >= 1:
                g_mod[k] += s
            else:
                g_nop[k] += s
    keys = sorted(g_all)
    a = np.array([g_all[k] for k in keys])
    m = np.array([g_mod[k] for k in keys])
    z = np.array([g_nop[k] for k in keys])
    out = {
        'n_team_games': len(keys),
        'full_panel_sum': {'mean': float(a.mean()), 'sd': float(a.std(ddof=1)),
                           'p01': float(np.percentile(a, 1)),
                           'p50': float(np.median(a)),
                           'p99': float(np.percentile(a, 99)),
                           'min': float(a.min()), 'max': float(a.max())},
        'modelled_sum': {'mean': float(m.mean()), 'sd': float(m.std(ddof=1)),
                         'p01': float(np.percentile(m, 1)),
                         'p50': float(np.median(m)),
                         'p99': float(np.percentile(m, 99)),
                         'min': float(m.min()), 'max': float(m.max())},
        'modelled_position_no_prior_game': {
            'mean': float(z.mean()),
            'frac_of_full': float(z.sum() / a.sum()) if a.sum() else None},
        'residual_mass': {
            'mean': float((a - m).mean()),
            'frac_of_full': float((a - m).sum() / a.sum()) if a.sum() else None,
            'sd': float((a - m).std(ddof=1)),
            'frac_team_games_zero': float(((a - m) < 1e-9).mean())},
    }
    byp = collections.Counter()
    for k in keys:
        for p_, v in g_pos[k].items():
            byp[p_] += v
    tot = sum(byp.values())
    out['share_of_full_by_position'] = {
        p_: round(v / tot, 5) for p_, v in byp.most_common(10)} if tot else {}
    return out


def main():
    rows = pickle.load(open(f'{P4B}/panel_enriched.pkl', 'rb'))
    print(f'panel rows {len(rows)}; seasons '
          f'{sorted({r["season"] for r in rows})}')
    out = {}
    for cls in CLASSES:
        out[cls] = {'train_2020_2021': summarise(rows, TRAIN, cls),
                    'later_2022_2025': summarise(rows, LATER, cls)}
        t = out[cls]['train_2020_2021']
        l = out[cls]['later_2022_2025']
        print(f'\n=== {cls} (denominator {CLASSES[cls][1]}, '
              f'modelled positions {CLASSES[cls][2]})')
        for lbl, d in (('TRAIN 20-21', t), ('LATER 22-25', l)):
            print(f'  {lbl}: full-panel share sum '
                  f'mean {d["full_panel_sum"]["mean"]:.4f} '
                  f'sd {d["full_panel_sum"]["sd"]:.4f} '
                  f'[p01 {d["full_panel_sum"]["p01"]:.3f}, '
                  f'p99 {d["full_panel_sum"]["p99"]:.3f}]')
            print(f'{"":14s} modelled-universe sum '
                  f'mean {d["modelled_sum"]["mean"]:.4f} '
                  f'sd {d["modelled_sum"]["sd"]:.4f} '
                  f'[p01 {d["modelled_sum"]["p01"]:.3f}, '
                  f'p99 {d["modelled_sum"]["p99"]:.3f}]')
            print(f'{"":14s} residual (unmodelled) mass '
                  f'mean {d["residual_mass"]["mean"]:.4f} '
                  f'= {100*d["residual_mass"]["frac_of_full"]:.2f}% of the pie; '
                  f'zero in {100*d["residual_mass"]["frac_team_games_zero"]:.1f}% '
                  f'of team-games')
            print(f'{"":14s} of which modelled-position-but-no-prior-game: '
                  f'{100*d["modelled_position_no_prior_game"]["frac_of_full"]:.2f}%')
        print(f'  share of the full pie by position (train): '
              f'{t["share_of_full_by_position"]}')
    json.dump(out, open(f'{HERE}/accounting.json', 'w'), indent=1)
    print('\nwrote accounting.json')


if __name__ == '__main__':
    main()
