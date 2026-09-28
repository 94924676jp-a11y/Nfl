#!/usr/bin/env python3.12
"""The owner-facing deliverable: every slate row, with the provenance of its number.

REQUESTED AS: "once V1 passes, the projection run should automatically generate the full CSV +
Excel workbook for the entire slate, with all 457 players and explicit projection provenance."

WHAT "PROVENANCE" MEANS HERE, and it is the point of the file rather than a decoration. For each
row a reader can answer, without opening any code:

  * what the number is, and which of the four projection modes produced it
  * which tier of the hierarchical prior was used, on how many effective observations, over which
    seasons, and at what confidence
  * for every single measure, whether it came from the prior, the current season, or both, and with
    what weight
  * what role band the player was asked about, what ceiling current evidence permitted, and whether
    he was capped by it
  * his depth rank inside his own position room, the measured appearance rate at that rank, and the
    share of his club's volume he was finally allocated
  * how his identity was resolved -- exact name, declared alias, or suffix normalisation
  * and where there is NO number, the named reason, never a zero

A ROW WITHOUT A NUMBER IS A ROW WITH A REASON. Thirty-one of the 457 carry no projection: reported
inactive, an open identity conflict, or a position with no pathway. They are all present in the
workbook with their state, because a player silently missing from a deliverable reads as a player
with nothing to say about him.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'projection-workbook-1'
V1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
ACC = _REPO / 'nfl/dfs/salaries/DK_WEEK3_V1_ACCEPTANCE.json'
CHAIN = _REPO / 'nfl/derived/FORWARD_CHAIN.json'
OUT_DIR = _REPO / 'nfl/dfs/salaries'
CSV_MAIN = OUT_DIR / 'DK_WEEK3_PROJECTIONS_V1.csv'
CSV_PROV = OUT_DIR / 'DK_WEEK3_PROJECTIONS_V1_PROVENANCE.csv'
XLSX = OUT_DIR / 'DK_WEEK3_PROJECTIONS_V1.xlsx'

MAIN_COLS = [
    ('dk_id', 'DraftKings player id'),
    ('name', 'player'),
    ('position', 'DK position'),
    ('team', 'club'),
    ('salary', 'DK salary'),
    ('dk_points', 'projected DK points, or BLANK where there is no projection'),
    ('projection_state', 'PROJECTED / PROJECTED_COLD_START / PROJECTED_DST / a named refusal'),
    ('role_band', 'the band the prior was asked about'),
    ('askable_ceiling', 'the strongest band current evidence permitted'),
    ('capped', 'True where the ceiling bound the band down'),
    ('is_predicted_starter', 'in the club predicted starting group'),
    ('availability', 'availability state from the post-inactives reconciliation'),
    ('pass_attempts', 'projected'), ('pass_yards', 'projected'),
    ('carries', 'projected'), ('rush_yards', 'projected'),
    ('targets', 'projected'), ('receptions', 'projected'), ('rec_yards', 'projected'),
    ('pass_td', 'projected'), ('rush_td', 'projected'), ('rec_td', 'projected'),
    ('reason_if_no_projection', 'why this row carries no number'),
]

PROV_COLS = [
    ('dk_id', ''), ('name', ''), ('position', ''), ('team', ''),
    ('projection_state', ''),
    ('gsis_id', 'resolved identity, never typed from memory'),
    ('identity_matched_by', 'EXACT_NAME / DECLARED_ALIAS / SUFFIX_NORMALISED / unresolved'),
    ('prior_tier', 'which tier of the hierarchical ladder supplied the measures'),
    ('prior_confidence', ''),
    ('prior_effective_obs', 'effective observations at the band asked about'),
    ('prior_seasons_used', ''),
    ('current_season_weeks', 'weeks of 2026 evidence available'),
    ('depth_rank_in_group', 'rank inside his own club and position room'),
    ('appearance_rate_measured', 'measured P(a player at this rank appears)'),
    ('rank_beyond_measured_table', 'True where his rank is deeper than the measured curve'),
    ('final_share_of_club_targets', ''), ('final_share_of_club_carries', ''),
    ('final_share_of_club_attempts', ''),
    ('basis_target_share', 'PRIOR_ONLY / CURRENT_SEASON_ONLY / PRIOR_AND_CURRENT / no evidence'),
    ('basis_carry_share', ''), ('basis_pass_attempt_share', ''),
    ('basis_rz_target_share', ''), ('basis_yards_per_target', ''),
    ('basis_catch_rate', ''), ('basis_yards_per_carry', ''), ('basis_yards_per_attempt', ''),
    ('prior_weight_fraction_targets', 'share of the target claim that came from the prior'),
    ('appearance_adjustment', 'applied where a non-starting quarterback was decomposed'),
    ('team_pool_scale_rec', ''), ('team_pool_scale_rush', ''),
    ('dst_league_rate_substituted', 'defensive measures replaced after an implausible zero'),
]


def _g(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def main_rows(v1):
    rows = [[c for c, _d in MAIN_COLS]]
    for dk_id, r in sorted(v1['rows'].items(),
                           key=lambda kv: -(kv[1].get('dk_points') or -1)):
        td = r.get('td') or {}
        rows.append([
            dk_id, r.get('name'), r.get('position'), r.get('team'), r.get('salary'),
            r.get('dk_points'), r.get('projection_state'), r.get('role_band'),
            r.get('askable_ceiling'), r.get('capped'), r.get('is_predicted_starter'),
            r.get('availability'),
            _r(r.get('pass_attempts')), _r(r.get('pass_yards')),
            _r(r.get('carries')), _r(r.get('rush_yards')),
            _r(r.get('targets')), _r(r.get('receptions')), _r(r.get('rec_yards')),
            _r(td.get('pass_td')), _r(td.get('rush_td')), _r(td.get('rec_td')),
            r.get('NOT_ZERO') or r.get('IDENTITY_NOT_GUESSED') or '',
        ])
    return rows


def _r(v, nd=3):
    return round(v, nd) if isinstance(v, (int, float)) else v


def prov_rows(v1):
    ident = {}
    rows = [[c for c, _d in PROV_COLS]]
    for dk_id, r in sorted(v1['rows'].items(),
                           key=lambda kv: -(kv[1].get('dk_points') or -1)):
        b = r.get('basis') or {}
        al = r.get('allocation') or {}
        dst = r.get('dst') or {}
        rows.append([
            dk_id, r.get('name'), r.get('position'), r.get('team'), r.get('projection_state'),
            r.get('gsis_id') or '', (r.get('identity_matched_by') or ''),
            r.get('prior_tier'), r.get('prior_confidence'), _r(r.get('prior_effective_obs')),
            ','.join(str(x) for x in (r.get('prior_seasons_used') or [])),
            r.get('current_season_weeks'),
            _g(al, 'targets', 'depth_rank_in_group') or _g(al, 'carries', 'depth_rank_in_group')
            or _g(al, 'pass_attempts', 'depth_rank_in_group'),
            _g(al, 'targets', 'appearance_rate_measured'),
            _g(al, 'targets', 'rank_beyond_measured_table'),
            _g(al, 'targets', 'final_share'), _g(al, 'carries', 'final_share'),
            _g(al, 'pass_attempts', 'final_share'),
            _g(b, 'target_share', 'basis'), _g(b, 'carry_share', 'basis'),
            _g(b, 'pass_attempt_share', 'basis'), _g(b, 'rz_target_share', 'basis'),
            _g(b, 'yards_per_target', 'basis'), _g(b, 'catch_rate', 'basis'),
            _g(b, 'yards_per_carry', 'basis'), _g(b, 'yards_per_attempt', 'basis'),
            _g(b, 'target_share', 'prior_weight_fraction'),
            'YES' if r.get('appearance_adjustment') else '',
            _g(r, 'td', 'rec_pool_scale'), _g(r, 'td', 'rush_pool_scale'),
            ','.join(sorted(dst.get('implausible_zeros_substituted') or {})),
        ])
    return rows


def readme_rows(v1, acc, chain):
    """A sheet that says what the numbers are and, more importantly, what they are not."""
    s = v1.get('summary') or {}
    g = (acc or {}).get('guards') or {}
    passing = sum(1 for v in g.values() if v.get('state') == 'PASS')
    R = [['field', 'value']]

    def add(k, v):
        R.append([k, v])
    add('artifact', 'DK_WEEK3_PROJECTIONS_V1')
    add('spec_version', SPEC_VERSION)
    add('projection label', v1.get('label'))
    add('universe', f"{s.get('n_universe')} DraftKings-eligible rows")
    add('projected', s.get('n_projected'))
    add('carrying no projection', s.get('n_unavailable'))
    add('rows at exactly 0.00', s.get('n_exactly_zero'))
    add('guards passing', f'{passing} of {len(g)}')
    add('club identities checked', len(v1.get('identities') or ()))
    add('club identities violated', v1.get('identity_failures'))
    R.append(['', ''])
    R.append(['WHAT THESE NUMBERS ARE', ''])
    add('holdout', v1.get('HOLDOUT'))
    add('market input',
        'the market enters ONCE, in the club touchdown pool, from a regression of offensive '
        'touchdowns on club points over 2,689 club-games. It is NOT applied to play volume; V0 '
        'applied it to both and double-counted the same signal.')
    add('external projections',
        'FantasyCruncher is a COMPARISON baseline for a level tripwire only. It is not an input '
        'to any projection and no constant was selected by looking at it.')
    R.append(['', ''])
    R.append(['WHAT THESE NUMBERS ARE NOT -- read this before using them', ''])
    add('discrimination not established',
        'forward-chained over 42 weeks and confirmed on 28 untouched weeks, a '
        'CURRENT-SEASON-ONLY baseline still edges this model on rank correlation '
        '(0.4671 against 0.4296 unconditional), with top-30 realised points tied. The '
        'multi-season prior demonstrably improves absolute error and level calibration. It is '
        'NOT demonstrated to improve ranking, and ranking is the objective.')
    add('availability dominates',
        '42 per cent of candidates in a club pool score ZERO in a given week, and rank '
        'correlation falls from about 0.52 conditional on playing to about 0.43 unconditional. '
        'Availability, not allocation, is the largest remaining error source.')
    add('no wager implication',
        'these are projections, not recommendations. Nothing here has been priced against a '
        'book, and no bet or contest entry follows from it.')
    add('not modelled',
        'offensive fumbles lost (absent from the usage panel, which makes every skill '
        'projection slightly HIGH), opponent-specific matchup, the two-point-return score.')
    add('known data defects',
        'OUT-036 no historical closing lines; OUT-037 the 2025 capture credits the Jets defence '
        'with zero interceptions; OUT-038 no historical rosters, which caused survivorship bias '
        'in the evaluation harness until it was worked around.')
    return R


def constants_rows(v1):
    R = [['constant', 'value', 'provenance']]
    for k, v in sorted((v1.get('CONSTANTS_PROVENANCE') or {}).items()):
        val, why = (v if isinstance(v, (list, tuple)) and len(v) == 2 else (v, ''))
        R.append([k, json.dumps(val) if isinstance(val, (dict, list)) else val, why])
    return R


def guards_rows(acc):
    R = [['guard', 'state', 'code', 'detail']]
    for k, v in sorted(((acc or {}).get('guards') or {}).items()):
        R.append([k, v.get('state'), v.get('code'), str(v.get('detail') or '')[:600]])
    lv = ((acc or {}).get('guards') or {}).get('level_within_band') or {}
    if lv.get('slices'):
        R.append(['', '', '', ''])
        R.append(['LEVEL SLICES vs the external comparison board', 'ratio', 'ours', 'external'])
        for sl in lv['slices']:
            R.append([sl['slice'], sl['ratio'], sl['ours_mean'], sl['external_mean']])
        R.append(['NOTE', 'the two top_N_by_external slices CONDITION ON THE EXTERNAL BOARD, '
                          'which biases any other predictor downward on that subset. The salary '
                          'slices are independent of both boards and are the clean comparison.',
                  '', ''])
    return R


def team_rows(v1):
    R = [['club', 'implied_total', 'weeks_2026', 'weeks_prior_season', 'plays_pg',
          'pass_attempts_pg', 'rush_attempts_pg', 'targets_pg', 'rz_plays_pg',
          'volume_scale_applied', 'scale_V0_would_have_applied', 'expected_offensive_td',
          'V0_would_have_said_td']]
    td = v1.get('td_account') or {}
    for club, t in sorted((v1.get('team_volume') or {}).items()):
        if t.get('state') != 'OK':
            R.append([club, '', '', '', t.get('state')] + [''] * 8)
            continue
        a = td.get(club) or {}
        R.append([club, t.get('implied_total'), t.get('weeks_observed_2026'),
                  t.get('weeks_observed_prior_season'), t.get('plays_pg'),
                  t.get('pass_attempts_pg'), t.get('rush_attempts_pg'), t.get('targets_pg'),
                  t.get('rz_plays_pg'), t.get('volume_scale_applied'),
                  t.get('volume_scale_V0_WOULD_HAVE_APPLIED'),
                  a.get('team_expected_td'), a.get('V0_WOULD_HAVE_SAID')])
    return R


def chain_rows(chain):
    R = [['arm', 'weeks', 'MAE', 'RMSE', 'pearson', 'spearman', 'level',
          'dfs_MAE', 'dfs_spearman', 'dfs_level', 'dfs_top30_mean_actual']]
    if not chain:
        R.append(['NOT BUILT'] + [''] * 10)
        return R
    for arm in chain.get('arms') or []:
        v = (chain.get('summary') or {}).get(arm)
        if not v:
            continue
        d = v.get('dfs') or {}
        R.append([arm, v.get('n_weeks'), v.get('mae'), v.get('rmse'), v.get('pearson'),
                  v.get('spearman'), v.get('level_ratio'), d.get('mae'), d.get('spearman'),
                  d.get('level_ratio'), d.get('top30_mean_actual')])
    R.append(['', '', '', '', '', '', '', '', '', '', ''])
    for k in ('CONDITIONAL_ON_PLAYING', 'NO_MARKET_INPUT', 'ROLE_STATE_NOT_RECONSTRUCTIBLE'):
        if chain.get(k):
            R.append([k, chain[k]] + [''] * 9)
    return R


def no_projection_rows(v1):
    R = [['name', 'position', 'team', 'salary', 'state', 'reason']]
    for dk_id, r in sorted(v1['rows'].items(), key=lambda kv: (kv[1].get('position') or '',
                                                               kv[1].get('name') or '')):
        if r.get('dk_points') is not None:
            continue
        R.append([r.get('name'), r.get('position'), r.get('team'), r.get('salary'),
                  r.get('projection_state'),
                  r.get('NOT_ZERO') or r.get('IDENTITY_NOT_GUESSED') or ''])
    return R


def build():
    from nfl.tools import xlsx_writer
    if not V1.exists():
        return Outcome.blocked('V1_ARTIFACT_ABSENT', f'{V1.name} not built', cause=Cause.DATA)
    v1 = json.loads(V1.read_text())
    acc = json.loads(ACC.read_text()) if ACC.exists() else None
    chain = json.loads(CHAIN.read_text()) if CHAIN.exists() else None

    # THE GATE. A deliverable is not produced from a board that has not passed its guards.
    guards = (acc or {}).get('guards') or {}
    failing = [k for k, v in guards.items() if v.get('state') == 'FAIL']
    if not guards:
        return Outcome.blocked('ACCEPTANCE_NOT_RUN',
                               'no acceptance artifact; the workbook is gated on the guards',
                               cause=Cause.DEPENDENCY)
    if failing:
        return Outcome.fail(
            'WORKBOOK_REFUSED_GUARDS_FAILING',
            f'{len(failing)} guard(s) failing: {failing}. The owner asked for this workbook '
            f'"once V1 passes"; producing it while a guard is red would hand over a number the '
            f'system itself rejects.',
            failing=failing)

    main = main_rows(v1)
    prov = prov_rows(v1)
    sheets = [
        ('READ THIS FIRST', readme_rows(v1, acc, chain)),
        ('Projections', main),
        ('Provenance', prov),
        ('No projection', no_projection_rows(v1)),
        ('Club volume and TD pools', team_rows(v1)),
        ('Constants', constants_rows(v1)),
        ('Guards', guards_rows(acc)),
        ('Forward chain', chain_rows(chain)),
        ('Column notes', [['sheet', 'column', 'meaning']]
         + [['Projections', c, d] for c, d in MAIN_COLS]
         + [['Provenance', c, d] for c, d in PROV_COLS]),
    ]
    wrote = xlsx_writer.write(XLSX, sheets)
    ver = xlsx_writer.verify(XLSX, expected_sheets=len(sheets))

    for path, rows in ((CSV_MAIN, main), (CSV_PROV, prov)):
        with path.open('w', newline='', encoding='utf-8') as fh:
            csv.writer(fh).writerows(rows)

    # read the CSV back and confirm the row count, because a written file is not a verified one
    with CSV_MAIN.open(newline='', encoding='utf-8') as fh:
        back = list(csv.reader(fh))
    checks = {
        'csv_rows_written': len(main) - 1,
        'csv_rows_read_back': len(back) - 1,
        'csv_roundtrip_ok': len(back) == len(main),
        'universe_expected': (v1.get('summary') or {}).get('n_universe'),
        'universe_in_csv': len(main) - 1,
        'every_row_present': (len(main) - 1) == (v1.get('summary') or {}).get('n_universe'),
        'xlsx': ver,
    }
    if not checks['csv_roundtrip_ok'] or not checks['every_row_present'] or not ver.get('ok'):
        return Outcome.fail('WORKBOOK_VERIFICATION_FAILED',
                            'the workbook was written but did not verify', checks=checks)
    return Outcome.ok('WORKBOOK_BUILT', {'wrote': wrote, 'checks': checks},
                      f'{len(main) - 1} rows across {len(sheets)} sheets',
                      xlsx=str(XLSX.relative_to(_REPO)),
                      csv=str(CSV_MAIN.relative_to(_REPO)))


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}] {o.detail}')
    if o.state.name != 'PASS':
        return 1
    v = o.value
    print(f"  rows {v['checks']['csv_rows_written']} (universe "
          f"{v['checks']['universe_expected']}), every row present "
          f"{v['checks']['every_row_present']}")
    print(f"  xlsx {v['wrote']['bytes']} bytes, {v['checks']['xlsx']['n_sheets']} sheets, "
          f"{v['checks']['xlsx']['n_rows']} rows, {v['checks']['xlsx']['n_cells']} cells, "
          f"verified {v['checks']['xlsx']['ok']}")
    for s, n in v['wrote']['rows_per_sheet'].items():
        print(f"    {s:28s} {n:5d} rows")
    print(f"  -> {XLSX.relative_to(_REPO)}")
    print(f"  -> {CSV_MAIN.relative_to(_REPO)}")
    print(f"  -> {CSV_PROV.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
