"""P3 feature layer: availability quality, teammate availability, role transition.

WHAT THE HISTORICAL PRACTICE DATA ACTUALLY SUPPORTS (§4)

Measured before building anything: the nflverse injuries file holds EXACTLY ONE
row per player-week with ONE timestamp (2022: 5,450 rows / 5,450 player-weeks,
max 1 distinct timestamp; 2024: 5,954 / 5,952, max 2). It does not preserve the
Wednesday -> Thursday -> Friday practice progression. `practice_status` is a
single value, and because its timestamp is the last pregame scrape it is the
FINAL designation, not what was knowable on Wednesday.

So the intraweek sequence the directive asks about (DNP -> DNP -> LP) cannot be
reconstructed, and this module does not pretend otherwise. What IS available is
a CROSS-WEEK progression -- last week's designation into this week's -- on
13,969 player-weeks, and that is what is tested.
"""
import collections, os, sys
import numpy as np

P1 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', 'p1'))
P2 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', 'p2'))
for p in (P1, P2, '/home/user/nfl'):
    if p not in sys.path:
        sys.path.insert(0, p)
import stage_a as A                                           # noqa: E402


def short_practice(p):
    p = p or ''
    if p.startswith('Did Not'):
        return 'DNP'
    if p.startswith('Limited'):
        return 'LP'
    if p.startswith('Full'):
        return 'FP'
    return '-'


def enrich(rows, inj):
    """Add P3 features. Every one is prior-game, or same-week and
    retrospectively chronology-defensible -- see nfl/research/p2/stage_a.py and
    NFL_P3_ADDENDUM_R1.md for why that is the narrower and correct claim."""
    by_tw = collections.defaultdict(list)
    for r in rows:
        by_tw[(r['team'], r['ord'])].append(r)
    team_ords = collections.defaultdict(list)
    for (tm, o) in by_tw:
        team_ords[tm].append(o)
    for tm in team_ords:
        team_ords[tm].sort()

    # ---- cross-week practice progression ----------------------------------
    for r in rows:
        prev = inj.get((r['season'], r['week'] - 1, r['team'], r['gsis_id']))
        r['f_prev_practice'] = short_practice(prev['practice_status']) if prev else 'none'
        r['f_prev_report'] = (prev['report_status'] if prev else None)
        cur = short_practice(r.get('f_inj_practice'))
        r['f_practice_seq'] = f"{r['f_prev_practice']}>{cur}"
        r['f_practice_improving'] = 1.0 if (
            (r['f_prev_practice'], cur) in
            (('DNP', 'LP'), ('DNP', 'FP'), ('LP', 'FP'))) else 0.0
        r['f_practice_worsening'] = 1.0 if (
            (r['f_prev_practice'], cur) in
            (('FP', 'LP'), ('FP', 'DNP'), ('LP', 'DNP'))) else 0.0

    # ---- teammate availability, per opportunity class ---------------------
    # Vacated share is what a previously-appearing teammate at the same
    # position held last week and is designated Out/Doubtful for this week.
    # Deliberately NOT assumed to be fully reallocated (§7).
    for tm, ords in team_ords.items():
        for i, o in enumerate(ords):
            cur = by_tw[(tm, o)]
            prev = by_tw[(tm, ords[i - 1])] if i else []
            out_now = {x['gsis_id'] for x in cur
                       if x.get('f_inj_status') in ('Out', 'Doubtful')}
            for r in cur:
                for cls, key in (('snap_share', 'snap'), ('rpr', 'route'),
                                 ('target_share', 'target'),
                                 ('carry_share', 'carry')):
                    vac = sum((x.get(cls) or 0) for x in prev
                              if x['position'] == r['position']
                              and x['gsis_id'] != r['gsis_id']
                              and x['appeared'] and x['gsis_id'] in out_now)
                    r[f'f_vac_{key}'] = float(vac)
                r['f_n_teammates_out'] = float(len(
                    [x for x in prev if x['position'] == r['position']
                     and x['gsis_id'] != r['gsis_id'] and x['appeared']
                     and x['gsis_id'] in out_now]))

    # ---- own-absence structure and prior volatility -----------------------
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        h = hist[r['gsis_id']]
        ss = [x.get('snap_share') for x in h if x.get('snap_share') is not None]
        r['f_swing'] = (abs(ss[-1] - float(np.mean(ss[-4:-1])))
                        if len(ss) >= 4 else 0.0)
        r['f_volatility'] = float(np.std(ss[-5:])) if len(ss) >= 3 else 0.0
        # workload immediately before the current absence run
        pre = None
        for x in reversed(h):
            if x['appeared']:
                pre = x.get('snap_share')
                break
        r['f_snap_before_absence'] = pre if pre is not None else 0.0
        hist[r['gsis_id']].append(r)

    # ---- information quality (§12), structural, not tuned -----------------
    team_has_report = collections.Counter()
    for r in rows:
        if r.get('f_inj_available'):
            team_has_report[(r['season'], r['week'], r['team'])] += 1
    for r in rows:
        if r.get('f_inj_available'):
            r['info_quality'] = 'HIGH'
        elif (team_has_report[(r['season'], r['week'], r['team'])] >= 1
              and (r.get('f_n_prior') or 0) >= 4):
            r['info_quality'] = 'MEDIUM'
        else:
            r['info_quality'] = 'LOW'
    return rows


PRACTICE_SEQS = ['DNP>DNP', 'DNP>LP', 'DNP>FP', 'LP>DNP', 'LP>LP', 'LP>FP',
                 'FP>DNP', 'FP>LP', 'FP>FP', 'none>DNP', 'none>LP', 'none>FP']

FEATURE_GROUPS = {
    'p2_base': 'the P2 feature set',
    'practice_progression': 'cross-week practice transition',
    'teammate_availability': 'vacated share by opportunity class',
    'absence_history': 'workload before absence, volatility',
    'role_volatility': 'prior swing and instability',
}


def featurise_p3(r, use_injury, groups=None):
    """P3 design row. `groups` names which optional blocks to include, so the
    ablation removes a block rather than zeroing a column and leaving its
    intercept behind."""
    g = groups if groups is not None else set(FEATURE_GROUPS)
    f = list(A.featurise(r, use_injury))
    if 'practice_progression' in g:
        for s in PRACTICE_SEQS:
            f.append(1.0 if r.get('f_practice_seq') == s else 0.0)
        f.append(float(r.get('f_practice_improving') or 0.0))
        f.append(float(r.get('f_practice_worsening') or 0.0))
    if 'teammate_availability' in g:
        for k in ('snap', 'route', 'target', 'carry'):
            f.append(float(r.get(f'f_vac_{k}') or 0.0))
        f.append(min(float(r.get('f_n_teammates_out') or 0.0), 3.0) / 3.0)
    if 'absence_history' in g:
        f.append(float(r.get('f_snap_before_absence') or 0.0))
    if 'role_volatility' in g:
        f.append(float(r.get('f_swing') or 0.0))
        f.append(float(r.get('f_volatility') or 0.0))
    return f
