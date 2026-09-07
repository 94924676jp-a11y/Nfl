"""P4B step 3a: the player panel, reusing P1-P3 unchanged, then RE-BASING the
snap share onto the derived denominator.

Only one thing is redefined and it is redefined for a stated reason:
`snap_counts.offense_pct` is rounded to a whole percent, so
offense_pct x team_off_snaps does not reproduce offense_snaps and the oracle
identity would fail by the rounding. `snap_share` here is
offense_snaps / team_off_snaps. Everything else -- the identifier-repaired
panel, the zero-extension, target/carry/rz shares, rpr, the appearance
features, the information-quality classes -- is P1-P3's, untouched.
"""
import collections, csv, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', 'p1'), os.path.join(HERE, '..', 'p2'),
          os.path.join(HERE, '..', 'p3'), '/home/user/nfl'):
    sys.path.insert(0, os.path.abspath(p))

CACHE = f'{HERE}/panel_enriched.pkl'


def denoms():
    out = {}
    for r in csv.DictReader(open(f'{HERE}/denom_panel.csv')):
        out[(r['team'], int(r['ord']))] = {
            k: int(r[k]) for k in ('team_off_snaps', 'team_dropbacks_part',
                                   'team_targets', 'team_carries',
                                   'team_rz_carries')}
    return out


def build():
    from run_p3a import load_enriched
    rows, _st = load_enriched()
    dn = denoms()
    kept, dropped = [], collections.Counter()
    for r in rows:
        d = dn.get((r['team'], r['ord']))
        if d is None:
            dropped['no_denominator_row'] += 1
            continue
        r['den'] = d
        # ---- absolute opportunity, and the share it is the product of ------
        r['y_snaps'] = int(float(r.get('offense_snaps') or 0))
        r['y_pass_snaps'] = r['pass_snaps']
        r['y_targets'] = r['targets']
        r['y_carries'] = r['carries']
        r['y_rz_carries'] = r['rz_carries']
        r['s_snaps'] = (r['y_snaps'] / d['team_off_snaps']
                        if d['team_off_snaps'] else None)
        r['s_pass_snaps'] = (r['y_pass_snaps'] / d['team_dropbacks_part']
                             if d['team_dropbacks_part'] >= 15 else None)
        r['s_targets'] = (r['y_targets'] / d['team_targets']
                          if d['team_targets'] else None)
        r['s_carries'] = (r['y_carries'] / d['team_carries']
                          if d['team_carries'] else None)
        r['s_rz_carries'] = (r['y_rz_carries'] / d['team_rz_carries']
                             if d['team_rz_carries'] else None)
        kept.append(r)
    print(f'panel rows: {len(rows)} -> {len(kept)}; dropped {dict(dropped)}')
    slim = []
    KEEP = ('season', 'week', 'team', 'ord', 'gsis_id', 'position',
            'appeared', 'info_quality', 'role_change', 'f_n_prior',
            'f_prev_appeared', 'f_weeks_since_appear', 'f_consec_missed')
    for r in kept:
        o = {k: r.get(k) for k in KEEP}
        o['den'] = r['den']
        for t in ('snaps', 'pass_snaps', 'targets', 'carries', 'rz_carries'):
            o[f'y_{t}'] = r[f'y_{t}']
            o[f's_{t}'] = r[f's_{t}']
        o['_feat'] = r          # full row kept for the Stage-A featuriser
        slim.append(o)
    return kept, slim


if __name__ == '__main__':
    kept, slim = build()
    # sanity: does the identity hold exactly on realised values?
    bad = collections.Counter()
    for r in slim:
        for t, dk in (('snaps', 'team_off_snaps'),
                      ('pass_snaps', 'team_dropbacks_part'),
                      ('targets', 'team_targets'), ('carries', 'team_carries'),
                      ('rz_carries', 'team_rz_carries')):
            s = r[f's_{t}']
            if s is None:
                continue
            if abs(s * r['den'][dk] - r[f'y_{t}']) > 1e-9:
                bad[t] += 1
    print('identity share x denominator == opportunity, violations:', dict(bad))
    print('rows:', len(slim), 'positions:',
          dict(collections.Counter(r['position'] for r in slim).most_common(8)))
    with open(CACHE, 'wb') as f:
        pickle.dump(kept, f, protocol=4)
    print('cached', CACHE)
