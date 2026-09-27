"""DK_WEEK3_TODAY_STATE -- the slate as held evidence describes it TODAY.

    python3.12 nfl/tools/today_state.py --write

It does not overwrite DK_WEEK3_SLATE_STUDY.{json,md}, which remains the
pre-Sunday historical study, so BEFORE -> AFTER stays measurable.

WHAT IT COMBINES, AND WHAT EACH LAYER MAY BE READ AS

  1. the 457-row DK universe          AUTHORITATIVE contest universe
  2. Q9 arm-A features                PRIOR_HISTORY, pre-2026, NEVER today's role
  3. observed 2026 weeks 1-2          OBSERVED_2026, snaps + play-by-play
  4. the held depth chart             its own vintage, Wednesday, PRE-Friday
  5. current availability             UNKNOWN unless authoritative evidence held
  6. FantasyCruncher                  EXTERNAL_FC_CONTEXT only, quarantined
  7. QB layer                         QB_LAYER_PRE_R2_CONTEXT, conditional

THE SIX RULES THIS FILE EXISTS TO ENFORCE

  historical role != current role. Every prior-season field is prefixed
  `historical_` and `today_expected_role` is a SEPARATE field that defaults to
  UNKNOWN_CURRENT_STATE.

  `fringe` is not a football judgement when there is no history. The 53 rows with
  a feature row and no trailing history carry
  `historical_role_class_valid_for_current_role: false`.

  no injury row != healthy. `injury_row_present` is 0/1 about a ROW.
  `current_availability` is separate and is UNKNOWN unless established.

  reported != confirmed. Statuses circulating externally are NOT ingested here.
  Nothing in this artifact records a player as OUT, DOUBTFUL or QUESTIONABLE on
  the strength of a report this repository cannot verify.

  Wednesday depth != Sunday confirmation. The depth chart is carried with its
  timestamp and its age, and never promoted to a start.

  missing != zero. Absent FC is MISSING. Absent 2026 rows are
  UNKNOWN_NO_ROW_EITHER_SOURCE. A snap row with no touch is a REAL zero and says
  so differently.

PRE_OFFICIAL_INACTIVES. No official inactive list for the 13:00 ET window was
held when this ran; the availability watch probes only pbp_participation and
snap_counts and never official_inactives. Rerun after authoritative inactives
arrive and write a SEPARATE post-inactives artifact.
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.prospective.q9shadow import live_features as LF          # noqa: E402
from nfl.tools import observed_2026 as OBS                        # noqa: E402
from sportsplatform.governance.outcome import Outcome, State      # noqa: E402

SPEC_VERSION = 'dk-today-state-1'
BASELINE = _REPO / 'nfl/dfs/salaries/DK_WEEK3_EARLY_BASELINE.json'
STUDY = _REPO / 'nfl/dfs/salaries/DK_WEEK3_SLATE_STUDY.json'
QBL = _REPO / 'nfl/dfs/salaries/DK_WEEK3_QB_LAYER.json'
FC_BLOB = _REPO / 'nfl/vintage/dk_salaries_early.35f38b43e29d0e89.csv.gz'
OUT_JSON = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE.md'
SEASON, WEEK = 2026, 3
OBSERVED_BEFORE = '2026-09-27T15:00:00Z'
KICKOFF = '2026-09-27T17:00:00Z'
GAMES = ('CAR@CLE', 'CIN@PIT', 'HOU@IND', 'KC@MIA', 'LAC@BUF',
         'NE@JAX', 'NYJ@DET', 'SEA@WAS', 'TEN@NYG')
UNKNOWN = 'UNKNOWN'
UNKNOWN_ROLE = 'UNKNOWN_CURRENT_STATE'
#: A player counts as materially active in 2026 at or above these, either week.
ACTIVE_SNAP_PCT = 0.25
ACTIVE_TOUCHES = 3


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16] \
        if pathlib.Path(p).exists() else None


def _fc_context():
    """FC rows keyed by normalised name. QUARANTINED: context display only."""
    try:
        from nfl.dfs.salaries import dk_universe as DK
        o = DK.load(FC_BLOB)
        if o.state is not State.PASS:
            return {}, f'{o.state.name}[{o.code}]'
        out = {}
        for r in o.value:
            out[(DK._norm_name(r['dk_name']), r['team'])] = {
                'fc_salary': r.get('salary'), 'fc_team': r.get('team'),
                'fc_pos': r.get('dk_pos'),
                'NOTE': ('dk_universe.load drops every third-party projection '
                         'column at parse time, so no FC projection, floor, '
                         'ceiling or ownership value is available to display '
                         'here even as context. Membership only.')}
        return out, None
    except Exception as exc:                                     # noqa: BLE001
        return {}, repr(exc)[:120]


def build():
    if not BASELINE.exists():
        return Outcome.fail('BASELINE_ABSENT', str(BASELINE))
    base = json.loads(BASELINE.read_text())
    rows = base['slate']['pool_rows']

    obs = OBS.build()
    if obs.state is not State.PASS:
        return obs
    ov = obs.value
    observed = ov['players']

    # Q9 features + the depth vintage actually consumed
    feats, depth, refused = {}, {}, {}
    clubs = sorted({r['team'] for r in rows})
    for t in clubs:
        o = LF.build_team_week(SEASON, WEEK, t,
                               observed_before=OBSERVED_BEFORE,
                               kickoff_utc=KICKOFF)
        if o.state is not State.PASS:
            refused[t] = f'{o.state.name}[{o.code}]'
            continue
        for r in o.value:
            if r.get('pid'):
                feats[r['pid']] = r
        dc = (o.evidence or {}).get('depth_chosen') or {}
        if t in dc:
            depth[t] = dc[t]

    qbl = json.loads(QBL.read_text()) if QBL.exists() else {}
    qb_by_dk = (qbl.get('quarterbacks') or {})
    fc, fc_err = _fc_context()

    players, by_game = {}, collections.OrderedDict()
    for g in GAMES:
        by_game[g] = {'away': g.split('@')[0], 'home': g.split('@')[1],
                      'clubs': {}}

    for r in rows:
        gid, dk = r.get('gsis_id'), r['dk_id']
        f = feats.get(gid) if gid else None
        ob = observed.get(gid) if gid else None
        no_hist = f is not None and f.get('trail_snap') is None
        cov = ('NO_FEATURES' if f is None
               else 'FEATURES_NO_PRIOR_HISTORY' if no_hist
               else 'FEATURES_WITH_PRIOR_HISTORY')

        # materially active in 2026, measured from observation only
        act, why = False, []
        if ob:
            for wk in ('1', '2'):
                w = (ob.get('weeks') or {}).get(wk) or {}
                if w.get('state') != 'OBSERVED':
                    continue
                if (w.get('offense_pct') or 0) >= ACTIVE_SNAP_PCT:
                    act = True
                    why.append(f"wk{wk} offense_pct {w['offense_pct']}")
                tch = (w.get('targets', 0) or 0) + (w.get('carries', 0) or 0)
                if tch >= ACTIVE_TOUCHES:
                    act = True
                    why.append(f'wk{wk} {int(tch)} touches')

        rec = {
            'dk_id': dk, 'name': r['dk_name'], 'team': r['team'],
            'opponent': r.get('opponent'), 'position': r['dk_pos'],
            'salary': r['salary'], 'gsis_id': gid,
            'identity': r.get('match_method') or 'UNMATCHED',
            'coverage_state': cov,

            'historical_role_class': (f or {}).get('role_class'),
            'historical_role_rank': (f or {}).get('role_rank'),
            'historical_role_rank_basis': (f or {}).get('role_rank_basis'),
            'historical_trail_snap': (f or {}).get('trail_snap'),
            'historical_own_share': (f or {}).get('own_share'),
            'historical_participation_ewma': (f or {}).get(
                'h_participation_ewma'),
            'historical_target_freq': (f or {}).get('h_target_freq'),
            'historical_prior_depth_bucket': (f or {}).get(
                'prior_depth_bucket'),
            'historical_provenance': 'PRIOR_HISTORY' if f else 'UNKNOWN',
            'historical_role_class_valid_for_current_role': (
                False if no_hist else (True if f else None)),
            'historical_role_class_warning': (
                'role_class is fringe ONLY because no qualifying prior-season '
                'history exists. It is a classifier artifact, not a football '
                'judgement, and must not be read as a current role.'
                if no_hist else None),

            'observed_2026': ob or {'state': 'UNKNOWN_NO_2026_ROW',
                                    'routes': OBS.UNKNOWN_SRC,
                                    'route_participation': OBS.UNKNOWN_SRC},
            'materially_active_2026': act,
            'materially_active_2026_evidence': why or None,

            'depth_source': 'HELD_DEPTH_CHART_VINTAGE',
            'depth_vintage': depth.get(r['team']),
            'depth_rank': (f or {}).get('rank'),
            'depth_source_caveat': (
                'this depth chart predates the Friday game-status deadline; it '
                'is NOT a confirmation of a Sunday start'),

            'injury_row_present': (1 if (f or {}).get('inj_available') else 0)
                                  if f else None,
            'injury_row_status': (f or {}).get('inj_status'),
            'injury_row_practice': (f or {}).get('inj_practice'),
            'current_availability': UNKNOWN,
            'current_availability_provenance': (
                'NO AUTHORITATIVE SUNDAY EVIDENCE HELD. No official inactive '
                'list for the 13:00 ET window was available when this ran, and '
                'externally reported statuses are deliberately NOT ingested. '
                'UNKNOWN is the honest state; it does not mean healthy and it '
                'does not mean out.'),

            'today_expected_role': UNKNOWN_ROLE,
            'today_role_evidence': {
                'observed_2026_snap_share': (
                    (ob.get('combined') or {}).get('mean_offense_pct')
                    if ob else None),
                'observed_2026_target_share': (
                    (ob.get('combined') or {}).get('target_share')
                    if ob else None),
                'observed_2026_rush_share': (
                    (ob.get('combined') or {}).get('rush_share')
                    if ob else None),
                'held_depth_rank': (f or {}).get('rank'),
                'dk_roster_position': r['dk_pos'],
                'historical_role_class': (f or {}).get('role_class'),
            },
            'role_confidence': 'NOT_ESTABLISHED_FROM_HELD_EVIDENCE',
            'today_expected_role_note': (
                'Held evidence describes what a player DID in weeks 1-2 and '
                'what a Wednesday depth chart listed. Neither establishes who '
                'starts today, so this stays UNKNOWN_CURRENT_STATE rather than '
                'promoting Wednesday depth into a Sunday confirmation.'),

            'external_fc_context': (
                fc.get((_norm(r['dk_name']), r['team']), 'MISSING')),
            'data_quality_warnings': [],
            'unknown_fields': [],
        }
        if cov == 'NO_FEATURES':
            rec['data_quality_warnings'].append(
                'no Q9 feature row: every QB and DST, plus the RB/WR/TE depth '
                'tail. UNKNOWN, not zero.')
        if no_hist:
            rec['data_quality_warnings'].append(
                'feature row exists but carries no trailing history')
        if not gid:
            rec['data_quality_warnings'].append(
                'UNMATCHED identity: rosterable on the DK export, not resolved '
                'to a canonical id. Our defect, not evidence he is not playing.')
        if not ob:
            rec['unknown_fields'].append('observed_2026')
        rec['unknown_fields'] += ['routes', 'route_participation',
                                  'current_availability', 'today_expected_role']
        if r['dk_pos'] == 'QB' and dk in qb_by_dk:
            q = qb_by_dk[dk]
            rec['qb_layer_pre_r2_context'] = {
                'has_row': q.get('has_qb_layer_row'),
                'why_absent': q.get('why_absent'),
                'att_mean': (q.get('att') or {}).get('mean'),
                'pyds_mean': (q.get('pyds') or {}).get('mean'),
                'ptd_mean': (q.get('ptd') or {}).get('mean'),
                'IS_NOT_A_WEEK3_PROJECTION': (
                    'pre-R2 conditional draws from a frame ending 202518 with '
                    'zero 2026 rows. Every rostered QB is drawn as though he '
                    'played, with no start-probability weighting, so team sums '
                    'overstate real opportunity and no row is an expectation. '
                    'R2 re-levels against the team dropback budget downstream; '
                    'the full week-3 board remains blocked.')}
        players[dk] = rec
        key = next((g for g in GAMES if r['team'] in g.split('@')), None)
        if key:
            by_game[key]['clubs'].setdefault(r['team'], []).append(dk)

    return Outcome.ok(
        'TODAY_STATE_BUILT',
        value={
            'artifact': 'DK_WEEK3_TODAY_STATE',
            'state_label': 'PRE_OFFICIAL_INACTIVES / CURRENT_HELD_STATE',
            'spec_version': SPEC_VERSION,
            'generated_at_utc': _dt.datetime.now(
                _dt.timezone.utc).isoformat(timespec='seconds'),
            'season': SEASON, 'week': WEEK,
            'slate': {'games': list(GAMES),
                      'kickoff_utc': KICKOFF,
                      'contest': base.get('owner_entries', {}).get(
                          'contest_name') if isinstance(
                          base.get('owner_entries'), dict) else None},
            'observed_before': OBSERVED_BEFORE,
            'upstream_artifacts': {
                'dk_baseline': {'path': str(BASELINE.relative_to(_REPO)),
                                'sha256_16': _sha(BASELINE)},
                'historical_study': {'path': str(STUDY.relative_to(_REPO)),
                                     'sha256_16': _sha(STUDY)},
                'qb_layer': {'path': str(QBL.relative_to(_REPO)),
                             'sha256_16': _sha(QBL)},
                'observed_2026_sources': ov['sources'],
                'fc_blob': {'path': str(FC_BLOB.relative_to(_REPO)),
                            'sha256_16': _sha(FC_BLOB),
                            'role': 'EXTERNAL_FC_CONTEXT_ONLY'}},
            'feature_refusals_by_club': refused,
            'fc_load_error': fc_err,
            'ROUTES_UNAVAILABLE': ov['ROUTES_UNAVAILABLE'],
            'ZERO_VS_UNKNOWN': ov['ZERO_VS_UNKNOWN'],
            'n_snap_rows_unbridged': ov['n_snap_rows_unbridged'],
            'materially_active_thresholds': {
                'offense_pct_at_or_above': ACTIVE_SNAP_PCT,
                'touches_at_or_above': ACTIVE_TOUCHES,
                'note': ('declared here so the counts are reproducible; either '
                         'week qualifying is enough')},
            'RERUN_AFTER_OFFICIAL_INACTIVES': (
                'python3.12 nfl/tools/today_state.py --write writes THIS '
                'artifact. After authoritative inactives arrive, store them via '
                'nfl/production/nonqb/inactives.py (store -> parse -> resolve '
                '-> sets), then rerun with a post-inactives output path and '
                'diff with nfl/dfs/salaries/baseline_diff.py. Do NOT overwrite '
                'this file: the whole point is a measurable before and after.'),
            'players': players,
            'games': by_game,
        },
        n_players=len(players))


def _norm(s):
    from nfl.dfs.salaries.dk_universe import _norm_name
    return _norm_name(s)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args(argv)
    o = build()
    if o.state is not State.PASS:
        print(f'{o.state.name} {o.code}: {o.detail}')
        return 1
    v = o.value
    ps = list(v['players'].values())
    cov = collections.Counter(p['coverage_state'] for p in ps)
    print(f"{len(ps)} DK players; coverage {dict(cov)}")
    print('materially active in 2026:',
          sum(1 for p in ps if p['materially_active_2026']))
    if a.write:
        v['game_findings'] = game_findings(v)
        OUT_JSON.write_text(json.dumps(v, indent=1) + '\n')
        OUT_MD.write_text(markdown(v))
        print(f'wrote {OUT_JSON.relative_to(_REPO)}')
        print(f'wrote {OUT_MD.relative_to(_REPO)}')
    return 0




def _combined(p):
    return (p.get('observed_2026') or {}).get('combined') or {}


def game_findings(v):
    """Per-club descriptive findings from OBSERVED weeks 1-2. No projections."""
    out = collections.OrderedDict()
    for g, meta in v['games'].items():
        out[g] = {}
        for tm, dks in meta['clubs'].items():
            ps = [v['players'][d] for d in dks]
            def top(pos, key, n=4):
                rs = [(p, _combined(p).get(key)) for p in ps
                      if p['position'] == pos and _combined(p).get(key)]
                return [{'name': p['name'], 'dk_id': p['dk_id'],
                         'salary': p['salary'], key: val,
                         'coverage_state': p['coverage_state'],
                         'historical_role_class': p['historical_role_class']}
                        for p, val in sorted(rs, key=lambda x: -x[1])[:n]]
            # historical label vs observed 2026 disagreement
            dis = []
            for p in ps:
                cb = _combined(p)
                sh = cb.get('mean_offense_pct')
                if p['coverage_state'] == 'FEATURES_NO_PRIOR_HISTORY' and \
                        sh and sh >= 0.5:
                    dis.append({
                        'name': p['name'], 'salary': p['salary'],
                        'historical_role_class': p['historical_role_class'],
                        'observed_2026_mean_offense_pct': sh,
                        'observed_targets': cb.get('targets'),
                        'observed_carries': cb.get('carries'),
                        'reading': ('history calls him fringe ONLY for want of '
                                    'prior-season snaps; 2026 shows a '
                                    'substantial role. The label is '
                                    'materially misleading for him.')})
                elif p['historical_role_class'] == 'starter' and sh is not None \
                        and sh < 0.35:
                    dis.append({
                        'name': p['name'], 'salary': p['salary'],
                        'historical_role_class': 'starter',
                        'observed_2026_mean_offense_pct': sh,
                        'reading': ('history calls him a starter; observed 2026 '
                                    'snap share is low. Role may have moved, or '
                                    'he may have missed time -- held evidence '
                                    'does not separate those.')})
            out[g][tm] = {
                'qb_usage_observed': top('QB', 'pass_attempts', 3),
                'backfield_observed': top('RB', 'carries', 4),
                'wr_opportunity_observed': top('WR', 'targets', 5),
                'te_opportunity_observed': top('TE', 'targets', 3),
                'red_zone_observed': top('RB', 'rz_opportunities', 3)
                                     + top('WR', 'rz_opportunities', 3),
                'goal_line_observed': top('RB', 'gl_opportunities', 2),
                'historical_vs_2026_disagreements': dis,
                'n_materially_active_2026': sum(
                    1 for p in ps if p['materially_active_2026']),
                'n_no_features_but_active': sum(
                    1 for p in ps if p['materially_active_2026']
                    and p['coverage_state'] == 'NO_FEATURES'),
                'major_current_state_unknowns': [
                    'current_availability is UNKNOWN for every player: no '
                    'official inactive list held',
                    'today_expected_role is UNKNOWN_CURRENT_STATE: Wednesday '
                    'depth is not a Sunday confirmation',
                    'routes and route_participation unavailable: '
                    'pbp_participation_2026 is 404'],
            }
    return out


def markdown(v):
    L = []
    A = L.append
    A('# Week-3 Early Only — TODAY-STATE descriptive evidence\n')
    A(f"`{v['state_label']}` · generated {v['generated_at_utc']} · "
      f"spec `{v['spec_version']}`\n")
    A('**No projection. No recommendation. No wager.** The production board '
      'remains blocked; nothing here is a Week-3 forecast.\n')
    A('## What each layer may be read as\n')
    A('| layer | provenance | may be read as |')
    A('|---|---|---|')
    A('| DK export | AUTHORITATIVE | the contest universe, 457 rows |')
    A('| Q9 arm-A features | PRIOR_HISTORY | pre-2026 usage. **never** today\'s role |')
    A('| snaps + play-by-play | OBSERVED_2026 | what actually happened in weeks 1–2 |')
    A('| depth chart | held vintage | what a list said on Wednesday |')
    A('| availability | UNKNOWN | nothing authoritative held |')
    A('| FantasyCruncher | EXTERNAL_FC_CONTEXT_ONLY | membership only |')
    A('| QB layer | PRE-R2 conditional | not an expectation |')
    A('')
    A('## Unavailable, and not estimated\n')
    A(v['ROUTES_UNAVAILABLE'] + '\n')
    A('## Zero is not unknown\n')
    A(v['ZERO_VS_UNKNOWN'] + '\n')
    ps = list(v['players'].values())
    cov = collections.Counter(p['coverage_state'] for p in ps)
    act = [p for p in ps if p['materially_active_2026']]
    A('## Coverage\n')
    A(f"457 DK rows · {dict(cov)}\n")
    A(f"**{len(act)} materially active in observed 2026** at the declared "
      f"thresholds ({v['materially_active_thresholds']}).\n")
    nh = [p for p in act if p['coverage_state'] == 'FEATURES_NO_PRIOR_HISTORY']
    A(f"**{len(nh)} of the 53 no-prior-history rows are materially active**, so "
      "their `fringe` label is materially misleading and is flagged per row "
      "with `historical_role_class_valid_for_current_role: false`.\n")
    A('| $ | pos | player | team | mean snap % | targets | carries |')
    A('|---|---|---|---|---|---|---|')
    for p in sorted(nh, key=lambda x: -x['salary']):
        cb = _combined(p)
        A(f"| {p['salary']} | {p['position']} | {p['name']} | {p['team']} | "
          f"{cb.get('mean_offense_pct','—')} | {cb.get('targets','—')} | "
          f"{cb.get('carries','—')} |")
    A('')
    for g, clubs in game_findings(v).items():
        A(f"\n---\n\n## {g}\n")
        for tm, f in clubs.items():
            A(f"### {tm} — {f['n_materially_active_2026']} materially active "
              f"in 2026 ({f['n_no_features_but_active']} of them with no Q9 "
              f"features)\n")
            for label, key in (('QB (pass attempts, wk1+2)', 'qb_usage_observed'),
                               ('Backfield (carries)', 'backfield_observed'),
                               ('WR (targets)', 'wr_opportunity_observed'),
                               ('TE (targets)', 'te_opportunity_observed')):
                rs = f[key]
                if not rs:
                    continue
                k = [x for x in rs[0] if x not in
                     ('name', 'dk_id', 'salary', 'coverage_state',
                      'historical_role_class')][0]
                inner = ', '.join(
                    f"{x['name']} {x[k]}" for x in rs)
                A(f"- **{label}:** {inner}")
            if f['historical_vs_2026_disagreements']:
                A('\n**Historical label vs observed 2026 — disagreements:**\n')
                for x in f['historical_vs_2026_disagreements']:
                    A(f"  - {x['name']} (${x['salary']}): historical "
                      f"`{x['historical_role_class']}`, observed mean snap "
                      f"share {x['observed_2026_mean_offense_pct']}. "
                      f"{x['reading']}")
            A('')
    A('\n---\n')
    A('## Rerun after official inactives\n')
    A(v['RERUN_AFTER_OFFICIAL_INACTIVES'] + '\n')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    raise SystemExit(main())
