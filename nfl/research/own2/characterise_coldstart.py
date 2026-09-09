"""OWN-2: characterise the population QB V1 cannot forecast.

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' \
        python3.12 nfl/research/own2/characterise_coldstart.py

NO ESTIMATOR IS FITTED HERE. The owner's instruction is to characterise the
population first, and to RULE OUT DATA AND IDENTITY DEFECTS BEFORE calling
anything a cold start: a missing forecast caused by an ID join or an ingestion
gap must never be solved by a cold-start model.

The exclusion rule being characterised is `qb_v1.slate_prospective`:
    rows = [r for r in pros if r['h_games'] >= 1]
and `h_games` counts prior rows IN THE PANEL QB FRAME carrying db > 0. So a
quarterback is excluded when the FRAME shows no prior dropback -- which is not
the same statement as "he has never dropped back".

Identity matching is by gsis_id ONLY. No fuzzy name matching, ever.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(_ROOT, 'nfl', 'research', 'inputs')
ROSTER_CSV = os.path.join(_ROOT, 'nfl_vintage', 'raw',
                          'weekly_rosters.5ec59c5228198f57.csv')
PBP_SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)
PANEL_FIRST_SEASON = 2020


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def pbp_passer_history(files):
    """Dropbacks per (player, season, WEEK) straight from play-by-play.

    This is the INDEPENDENT view. If it disagrees with the frame, the frame is
    the problem and a cold-start model would be the wrong fix.

    KEYED BY WEEK, NOT BY SEASON, and the difference is not cosmetic. The first
    version of this function aggregated to the season and the historical
    classifier then tested "did he have prior dropbacks" by placing every
    season's total at week 1 of that season. A quarterback whose debut came in
    week 5 was therefore credited with prior dropbacks in weeks 2 through 4,
    and every one of the 172 rows that version called a DATA_OR_IDENTITY_DEFECT
    sat in exactly that window. A season-granular history cannot answer a
    within-season strictly-prior question.
    """
    out = collections.defaultdict(collections.Counter)
    for path in files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                if not _i(r.get('qb_dropback')):
                    continue
                o = _i(r.get('season')) * 100 + _i(r.get('week'))
                for key in ('passer_player_id', 'rusher_player_id'):
                    pid = r.get(key) or ''
                    if pid:
                        out[pid][o] += 1
                        break
    return out


def panel_qb_view():
    """What the QB frame can see: panel QB rows, and which carry a dropback."""
    rows = collections.defaultdict(collections.Counter)
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('position') != 'QB':
                continue
            pid = r.get('gsis_id') or ''
            if not pid:
                continue
            s = _i(r.get('season'))
            c = rows[pid]
            c[f'rows_{s}'] += 1
            c['rows_total'] += 1
            try:
                db = float(r.get('dropbacks_as_passer') or 0)
            except ValueError:
                db = 0.0
            if db > 0:
                c[f'db_rows_{s}'] += 1
                c['db_rows_total'] += 1
    return rows


def roster_view():
    """Career markers. entry_year / rookie_year / years_exp, by player."""
    out = {}
    if not os.path.exists(ROSTER_CSV):
        return out
    with open(ROSTER_CSV) as fh:
        for r in csv.DictReader(fh):
            pid = r.get('gsis_id') or ''
            if not pid or r.get('position') != 'QB':
                continue
            cur = out.setdefault(pid, {'seasons': set()})
            cur['seasons'].add(_i(r.get('season')))
            for k in ('entry_year', 'rookie_year', 'years_exp',
                      'draft_number', 'draft_club', 'full_name'):
                v = r.get(k)
                if v not in (None, '', 'NA') and k not in cur:
                    cur[k] = v
    for v in out.values():
        v['seasons'] = sorted(x for x in v['seasons'] if x)
    return out


def classify(pid, pbp, panel, roster, season):
    """One quarterback -> one named state. Data defects are ruled out FIRST.

    A CORRECTION TO THIS FUNCTION'S FIRST VERSION, recorded rather than quietly
    fixed. It had a branch keyed on `roster['seasons']` containing a season
    before `season`, meant to catch "on an NFL roster before, never played".
    `weekly_rosters` in this checkout holds ONLY 2026, so that branch could
    never fire and fourteen quarterbacks fell into a bucket named
    NO_PRIOR_AND_NO_CAREER_MARKER when they had a perfectly good career marker.
    A file's coverage limit read as an absent attribute -- the project's own
    worst defect class, committed inside the audit written to catch it. The
    prior-presence test now uses panel_p3, which spans 2020-2025.
    """
    p = pbp.get(pid) or collections.Counter()
    pan = panel.get(pid) or collections.Counter()
    ros = roster.get(pid) or {}
    pbp_db = int(sum(p.values()))
    pbp_seasons = sorted({o // 100 for o, n in p.items() if n > 0})
    frame_db_rows = int(pan['db_rows_total'])
    frame_rows = int(pan['rows_total'])
    entry = _i(ros.get('entry_year') or ros.get('rookie_year'), 0)
    exp = _i(ros.get('years_exp'), -1)

    ev = {'pbp_dropbacks_2020_2025': pbp_db, 'pbp_seasons': pbp_seasons,
          'panel_qb_rows': frame_rows, 'panel_rows_with_dropback': frame_db_rows,
          'entry_year': entry or None, 'years_exp': exp if exp >= 0 else None,
          'roster_file_seasons_available': ros.get('seasons') or []}

    # 1. DATA / IDENTITY DEFECT, ruled out before anything else. The
    #    independent play-by-play view says he dropped back and the frame does
    #    not. That is an ingestion or join failure and a cold-start model would
    #    be the wrong fix for it.
    if pbp_db > 0 and frame_db_rows == 0:
        return 'DATA_OR_IDENTITY_DEFECT', ev
    # 2. The frame does have dropbacks, so he should not have been excluded.
    if frame_db_rows > 0:
        return 'CONTRADICTION_FRAME_HAS_DROPBACKS', ev
    # 3. He was on the field in the participation panel and never dropped back.
    #    Distinct from never having been on an NFL field at all.
    if frame_rows > 0:
        return 'APPEARED_WITHOUT_A_DROPBACK', ev
    # 4. Career began before the panel window. Whether he has usable pre-window
    #    history is UNVERIFIED here -- this checkout holds no pre-2020 play-by-
    #    play, so the state records the boundary rather than claiming history.
    if (entry and entry < PANEL_FIRST_SEASON) or \
            (exp >= 0 and exp > (season - PANEL_FIRST_SEASON)):
        return 'PRE_WINDOW_ENTRANT_HISTORY_UNVERIFIED', ev
    # 5. Entered the league in an EARLIER season and has never appeared: a
    #    retained backup, not a debutant. One to two years of NFL exposure with
    #    no snap.
    if entry and entry < season:
        return 'PRIOR_ENTRANT_NO_NFL_APPEARANCE', ev
    # 6. True debut: entered this season, nothing anywhere before it.
    if entry and entry >= season:
        return 'TRUE_DEBUT', ev
    return 'NO_CAREER_MARKER_AVAILABLE', ev


def slate_population(season=2026, week=1, m=400, seed=20260908):
    """The quarterbacks QB V1 excluded on the live slate, with their share."""
    from nfl.production.nonqb import football_engine as FE
    from nfl.production.rehearsal import run_slate as RS
    from sportsplatform.governance.outcome import State
    _, rrows = RS.roster(season, week)
    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rrows
           if r['gsis_id'] and r['position'] == 'QB']
    qo = FE.qb_slate(season, week, qbp, m=m, seed=seed)
    if qo.state is not State.PASS:
        return None, f'{qo.state.value}[{qo.code}]'
    rows, idx = qo.value['rows'], qo.value['index_by_team']
    have = {r['gsis_id'] for r in rows}
    teams = sorted({q['team'] for q in qbp})
    qa = FE.QA.allocate(season, week, teams, qbp, m=m, seed=seed)
    if qa.state is not State.PASS:
        return None, f'{qa.state.value}[{qa.code}]'
    out = []
    for t in teams:
        a = qa.value.get(t)
        if a is None:
            continue
        for j, pid in enumerate(a['pids']):
            if pid in have:
                continue
            out.append({'gsis_id': pid, 'team': t,
                        'mean_dropback_share':
                            float(np.asarray(a['shares'][j], float).mean())})
    return out, None


DC_SEASONS = (2020, 2021, 2022, 2023, 2024)
HIST_EVAL_SEASONS = (2022, 2023, 2024)   # 2020-21 are burn-in for prior cover


def historical_incidence(pbp):
    """How often does each cold-start class occur historically, and where?

    Uses ONLY inputs that exist across seasons, because `weekly_rosters` in
    this checkout holds 2026 alone and entry_year is therefore unavailable
    historically. The prior-presence markers are the depth charts and the
    participation panel, both spanning 2020-2024/2025.

    2020 and 2021 are BURN-IN and are not scored: a player cannot be shown to
    be new when the coverage itself is new. That is the same left-boundary trap
    OWN-1's addendum had to correct for, and it is excluded by construction
    here rather than caught afterwards.

    EXPOSURE is reported as DEPTH RANK, not as a fitted allocation share. The
    QB3 shares are a 2026 artifact and there is no historical allocation to
    read; rank is the honest proxy and is labelled as one.
    """
    import bisect
    # prior panel presence, and prior panel dropbacks, per player
    rows_ord = collections.defaultdict(list)
    db_ord = collections.defaultdict(list)
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('position') != 'QB':
                continue
            pid = r.get('gsis_id') or ''
            if not pid:
                continue
            o = _i(r.get('season')) * 100 + _i(r.get('week'))
            rows_ord[pid].append(o)
            try:
                db = float(r.get('dropbacks_as_passer') or 0)
            except ValueError:
                db = 0.0
            if db > 0:
                db_ord[pid].append(o)
    for d in (rows_ord, db_ord):
        for k in d:
            d[k].sort()
    # prior play-by-play dropbacks, per player, AT WEEK GRANULARITY
    pbp_ord = {pid: sorted(o for o, n in c.items() if n > 0)
               for pid, c in pbp.items()}
    # first depth-chart ordinal per player
    dc_rows, first_dc = [], {}
    for y in DC_SEASONS:
        path = os.path.join(INPUTS, f'dc_{y}.csv.gz')
        if not os.path.exists(path):
            continue
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('position') != 'QB' or r.get('game_type') != 'REG':
                    continue
                pid = r.get('gsis_id') or ''
                if not pid:
                    continue
                try:
                    rank = int(r.get('depth_team') or 0)
                    wk = int(r['week'])
                except ValueError:
                    continue
                o = y * 100 + wk
                dc_rows.append((o, y, wk, pid, rank))
                if pid not in first_dc or o < first_dc[pid]:
                    first_dc[pid] = o
    cells = collections.defaultdict(collections.Counter)
    for o, y, wk, pid, rank in dc_rows:
        if y not in HIST_EVAL_SEASONS:
            continue
        prior_db = bisect.bisect_left(db_ord.get(pid) or [], o)
        rk = 'rank1' if rank == 1 else ('rank2' if rank == 2 else 'rank3plus')
        seg = 'week1' if wk == 1 else 'week2plus'
        cells[(seg, rk)]['n'] += 1
        if prior_db > 0:
            continue                       # forecastable; not our population
        cells[(seg, rk)]['excluded'] += 1
        prior_rows = bisect.bisect_left(rows_ord.get(pid) or [], o)
        prior_pbp = bisect.bisect_left(pbp_ord.get(pid) or [], o)
        if prior_pbp > 0:
            cls = 'DATA_OR_IDENTITY_DEFECT'
        elif prior_rows > 0:
            cls = 'APPEARED_WITHOUT_A_DROPBACK'
        elif (first_dc.get(pid) or o) < o:
            cls = 'PRIOR_ENTRANT_NO_NFL_APPEARANCE'
        else:
            cls = 'DEBUT_LIKE'
        cells[(seg, rk)][cls] += 1
    out = {'eval_seasons': list(HIST_EVAL_SEASONS),
           'burn_in_seasons': [2020, 2021],
           'exposure_proxy': 'depth rank, not a fitted allocation share',
           'by_segment': {}}
    classes = ('DATA_OR_IDENTITY_DEFECT', 'APPEARED_WITHOUT_A_DROPBACK',
               'PRIOR_ENTRANT_NO_NFL_APPEARANCE', 'DEBUT_LIKE')
    for seg in ('week1', 'week2plus'):
        for rk in ('rank1', 'rank2', 'rank3plus'):
            c = cells[(seg, rk)]
            if not c['n']:
                continue
            out['by_segment'][f'{seg}_{rk}'] = {
                'n': c['n'], 'excluded': c['excluded'],
                'excluded_rate': round(c['excluded'] / c['n'], 6),
                **{k: c[k] for k in classes}}
    tot = collections.Counter()
    for c in cells.values():
        for k in classes + ('n', 'excluded'):
            tot[k] += c[k]
    out['pooled'] = {'n': tot['n'], 'excluded': tot['excluded'],
                     'excluded_rate': round(tot['excluded'] / max(tot['n'], 1), 6),
                     **{k: tot[k] for k in classes}}
    return out


def outcome_by_class(pbp):
    """Are these states EMPIRICALLY DISTINCT, or one state wearing four names?

    For every historical depth-chart quarterback the frame could not forecast,
    what did he actually do that week? Two quantities matter downstream and
    neither is currently modelled for him:

        P(he takes a dropback at all | class, depth rank)
        the distribution of dropbacks GIVEN that he does

    This is CHARACTERISATION, not fitting. It uses realised development
    outcomes to describe the population a candidate would have to cover, and it
    scores nothing. Any estimator comparison is pre-registered separately, and
    no 2026 outcome is touched -- none exists.
    """
    import bisect
    rows_ord = collections.defaultdict(list)
    db_ord = collections.defaultdict(list)
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('position') != 'QB':
                continue
            pid = r.get('gsis_id') or ''
            if not pid:
                continue
            o = _i(r.get('season')) * 100 + _i(r.get('week'))
            rows_ord[pid].append(o)
            try:
                db = float(r.get('dropbacks_as_passer') or 0)
            except ValueError:
                db = 0.0
            if db > 0:
                db_ord[pid].append(o)
    for d in (rows_ord, db_ord):
        for k in d:
            d[k].sort()
    pbp_ord = {pid: sorted(o for o, n in c.items() if n > 0)
               for pid, c in pbp.items()}
    first_dc = {}
    dc_rows = []
    for y in DC_SEASONS:
        path = os.path.join(INPUTS, f'dc_{y}.csv.gz')
        if not os.path.exists(path):
            continue
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('position') != 'QB' or r.get('game_type') != 'REG':
                    continue
                pid = r.get('gsis_id') or ''
                if not pid:
                    continue
                try:
                    rank = int(r.get('depth_team') or 0)
                    wk = int(r['week'])
                except ValueError:
                    continue
                o = y * 100 + wk
                dc_rows.append((o, y, wk, pid, rank))
                if pid not in first_dc or o < first_dc[pid]:
                    first_dc[pid] = o
    buckets = collections.defaultdict(lambda: {'n': 0, 'played': 0, 'db': []})
    for o, y, wk, pid, rank in dc_rows:
        if y not in HIST_EVAL_SEASONS:
            continue
        if bisect.bisect_left(db_ord.get(pid) or [], o) > 0:
            continue                                   # forecastable
        prior_rows = bisect.bisect_left(rows_ord.get(pid) or [], o)
        if bisect.bisect_left(pbp_ord.get(pid) or [], o) > 0:
            cls = 'DATA_OR_IDENTITY_DEFECT'
        elif prior_rows > 0:
            cls = 'APPEARED_WITHOUT_A_DROPBACK'
        elif (first_dc.get(pid) or o) < o:
            cls = 'PRIOR_ENTRANT_NO_NFL_APPEARANCE'
        else:
            cls = 'DEBUT_LIKE'
        this_week = (pbp.get(pid) or {}).get(o, 0)
        rk = 'rank1' if rank == 1 else ('rank2' if rank == 2 else 'rank3plus')
        for key in ((cls, 'ALL'), (cls, rk), ('ALL', rk), ('ALL', 'ALL')):
            b = buckets[key]
            b['n'] += 1
            if this_week > 0:
                b['played'] += 1
                b['db'].append(int(this_week))
    out = {}
    for (cls, rk), b in sorted(buckets.items()):
        d = sorted(b['db'])
        out[f'{cls}|{rk}'] = {
            'n_player_weeks': b['n'], 'n_with_a_dropback': b['played'],
            'p_takes_a_dropback': round(b['played'] / b['n'], 6) if b['n'] else None,
            'dropbacks_given_played': ({
                'mean': round(sum(d) / len(d), 4),
                'p10': d[int(0.10 * (len(d) - 1))],
                'p50': d[int(0.50 * (len(d) - 1))],
                'p90': d[int(0.90 * (len(d) - 1))],
                'max': d[-1]} if d else None)}
    out['_reading'] = (
        'a candidate must cover BOTH margins: whether an unforecastable '
        'quarterback takes a dropback at all, and how many if he does. The '
        'first is close to zero for a backup and is the mass that currently '
        'disappears; the second is what a point estimate would destroy.')
    return out


def main():
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB. The identity '
                         'check needs the independent view and is refused '
                         'without it -- assuming a cold start because the '
                         'evidence is missing is the error being guarded.')
    pbp = pbp_passer_history(files)
    panel = panel_qb_view()
    roster = roster_view()
    pop, err = slate_population()
    if pop is None:
        raise SystemExit(f'slate population unavailable: {err}')
    rows, by_class = [], collections.defaultdict(
        lambda: {'n': 0, 'share': 0.0, 'players': []})
    for q in pop:
        cls, ev = classify(q['gsis_id'], pbp, panel, roster, 2026)
        rec = {**q, 'state': cls, **ev,
               'full_name': (roster.get(q['gsis_id']) or {}).get('full_name')}
        rows.append(rec)
        b = by_class[cls]
        b['n'] += 1
        b['share'] += q['mean_dropback_share']
        if len(b['players']) < 8:
            b['players'].append(
                {'gsis_id': q['gsis_id'], 'team': q['team'],
                 'share': round(q['mean_dropback_share'], 4),
                 'pbp_db': ev['pbp_dropbacks_2020_2025'],
                 'entry_year': ev['entry_year']})
    total_share = sum(q['mean_dropback_share'] for q in pop)
    hist = historical_incidence(pbp)
    outcomes = outcome_by_class(pbp)
    out = {
        'artifact': 'OWN2_COLDSTART_CHARACTERISATION',
        'historical_incidence': hist,
        'outcome_by_class': outcomes,
        'no_estimator_fitted': True,
        'season': 2026, 'week': 1,
        'exclusion_rule': "qb_v1.slate_prospective keeps rows with "
                          "h_games >= 1; h_games counts prior PANEL rows with "
                          "db > 0",
        'identity_matching': 'gsis_id only; no fuzzy name matching',
        'n_excluded_quarterbacks': len(pop),
        'total_dropback_share_excluded': round(total_share, 6),
        'total_share_mass': 32.0,
        'fraction_of_league_dropbacks': round(total_share / 32.0, 6),
        'by_state': {k: {'n': v['n'], 'share': round(v['share'], 6),
                         'share_pct_of_league': round(v['share'] / 32.0, 6),
                         'examples': v['players']}
                     for k, v in sorted(by_class.items(),
                                        key=lambda kv: -kv[1]['share'])},
        'players': sorted(rows, key=lambda r: -r['mean_dropback_share']),
    }
    dest = os.path.join(HERE, 'own2_population.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=str)
    show = {k: v for k, v in out.items() if k != 'players'}
    print(json.dumps(show, indent=2, sort_keys=True, default=str))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
