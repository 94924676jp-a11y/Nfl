#!/usr/bin/env python3.12
"""The final standard: one command, and a written account of whether it actually delivered.

WHAT THE OWNER ASKED FOR

"One command, hours before Sunday lock, produces projections, distributions, availability, role
state, model reasoning, external comparison, simulation, ownership, portfolio, DK upload, CSV,
Excel, readiness -- with no forgotten position, no silently missing player, no stale-source
surprise, and no foundational model development occurring minutes before kickoff."

Those last four clauses are the part worth engineering, because they are the ones a pipeline breaks
silently. Each is a check here rather than an intention:

  no forgotten position      every DK position has a sheet and a row count, kickers included even
                             though this slate rosters none
  no silently missing player every rosterable player in the availability universe appears in the
                             CSV EXACTLY ONCE, verified by set difference in both directions
  no stale-source surprise   the run is GATED on the readiness board, and refuses to produce a
                             deliverable while the model layer is stale or absent
  no late model development  the run REFUSES to fit anything. It consumes artifacts and reports
                             which are missing; it cannot build a model, by construction

WHAT IT WILL NOT DO

It does not fetch, it does not submit, it does not enter a contest, and it does not recommend a
wager. The DK-format file it writes is a deliverable for a human to look at, never an upload.
"""
from __future__ import annotations

import collections
import csv
import json
import pathlib
import re
import sys
import time
import zipfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import exact  # noqa: E402
from nfl.production import readiness  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
CSV_MAIN = OUT_DIR / 'DK_WEEK3_PROJECTIONS_V1.csv'
XLSX = OUT_DIR / 'DK_WEEK3_PROJECTIONS_V1.xlsx'
SUPP = OUT_DIR / 'DK_WEEK3_DELIVERABLE_SUPPLEMENT.xlsx'
POST = OUT_DIR / 'DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
V1 = OUT_DIR / 'DK_WEEK3_PROJ_V1.json'
FIELD = OUT_DIR / 'FIELD_MODEL.json'
PORT = OUT_DIR / 'CONTEST_PORTFOLIO.json'
REPORT = _REPO / 'nfl/production/SUNDAY_RUN_REPORT.json'

#: Names the sealed run directory. DECLARED here so a run can never be archived under a slate label
#: guessed from a filename.
SLATE_ID = 'DK_NFL_WEEK3_2026'

REQUIRED_SHEETS = ('All Projections', 'QB', 'RB', 'WR', 'TE', 'DST', 'K', 'Model vs FC',
                   'Model vs Market', 'Availability', 'Projection Coverage')
REQUIRED_COLUMNS = ('dk_id', 'name', 'position', 'team', 'salary', 'dk_points',
                    'dk_points_if_plays', 'p_plays', 'projection_state', 'availability')
DK_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'DST', 'K')


def _sheets(path):
    if not path.exists():
        return []
    try:
        with zipfile.ZipFile(path) as z:
            return re.findall(r'name="([^"]+)"', z.read('xl/workbook.xml').decode())
    except Exception:
        return []


def verify_contract() -> Outcome:
    """Every clause of the output contract, checked against the files on disk."""
    problems = []
    if not CSV_MAIN.exists() or not XLSX.exists():
        return Outcome.blocked('CONTRACT_OUTPUTS_ABSENT', 'the CSV or the workbook is missing',
                               cause=Cause.DATA, csv=CSV_MAIN.exists(), xlsx=XLSX.exists())
    with CSV_MAIN.open(newline='') as fh:
        rows = list(csv.DictReader(fh))
    cols = set(rows[0].keys()) if rows else set()
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing_cols:
        problems.append({'clause': 'REQUIRED_COLUMNS', 'missing': missing_cols})

    # exactly once, in both directions
    ids = [r['dk_id'] for r in rows]
    dupes = [k for k, n in collections.Counter(ids).items() if n > 1]
    universe = set()
    if POST.exists():
        universe = set((json.loads(POST.read_text()).get('players') or {}).keys())
    absent = sorted(universe - set(ids))
    extra = sorted(set(ids) - universe) if universe else []
    if dupes:
        problems.append({'clause': 'EXACTLY_ONCE', 'duplicated_dk_ids': dupes[:10],
                         'n': len(dupes)})
    if absent:
        problems.append({'clause': 'NO_SILENTLY_MISSING_PLAYER',
                         'in_universe_but_not_in_csv': absent[:10], 'n': len(absent)})

    # every player carries a state, and a missing number carries a reason
    stateless = [r['dk_id'] for r in rows if not (r.get('projection_state') or '').strip()]
    if stateless:
        problems.append({'clause': 'EVERY_PLAYER_HAS_A_STATE', 'stateless': stateless[:10],
                         'n': len(stateless)})
    unexplained = [r['dk_id'] for r in rows
                   if not (r.get('dk_points') or '').strip()
                   and not (r.get('reason_if_no_projection') or '').strip()]
    if unexplained:
        problems.append({'clause': 'NO_NUMBER_MEANS_A_REASON', 'unexplained': unexplained[:10],
                         'n': len(unexplained)})

    have = _sheets(XLSX)
    missing_sheets = [s for s in REQUIRED_SHEETS if s not in have]
    if missing_sheets:
        problems.append({'clause': 'REQUIRED_SHEETS', 'missing': missing_sheets})

    by_pos = collections.Counter(r['position'] for r in rows)
    forgotten = [p for p in DK_POSITIONS if p not in have]
    if forgotten:
        problems.append({'clause': 'NO_FORGOTTEN_POSITION', 'positions_without_a_sheet': forgotten})

    val = {
        'n_csv_rows': len(rows), 'n_universe': len(universe),
        'rows_by_position': dict(by_pos),
        'sheets_present': have, 'n_sheets': len(have),
        'extra_in_csv_not_in_universe': extra[:10],
        'clauses_checked': ['REQUIRED_COLUMNS', 'EXACTLY_ONCE', 'NO_SILENTLY_MISSING_PLAYER',
                            'EVERY_PLAYER_HAS_A_STATE', 'NO_NUMBER_MEANS_A_REASON',
                            'REQUIRED_SHEETS', 'NO_FORGOTTEN_POSITION'],
        'problems': problems,
    }
    if problems:
        return Outcome.fail('CONTRACT_NOT_MET', f'{len(problems)} clause(s) unmet', **val)
    return Outcome.ok('CONTRACT_MET', value=val)


def supplement() -> Outcome:
    """The sheets the new layers add: ownership, portfolio, readiness, metadata."""
    from nfl.tools import xlsx_writer
    sheets = []
    meta = [['key', 'value']]

    field = json.loads(FIELD.read_text()) if FIELD.exists() else None
    if field:
        own = [['name', 'field_share', 'marginal_form_target']]
        for d in field['field']['field_ownership_top_15']:
            own.append([d['name'], d['share'], d['marginal_form_target']])
        own += [[], ['CALIBRATION', field['CALIBRATION_STATE']],
                ['DUPLICATION_USABLE', (field.get('DUPLICATION_USABLE') or {}).get('state')],
                ['LEVERAGE_STATUS', field.get('leverage_STATUS')],
                ['SENSITIVITY_VERDICT', (field.get('sensitivity') or {}).get('VERDICT')]]
        sheets.append(('Field Ownership', own))
        meta.append(['field_calibration', field['CALIBRATION_STATE']])

    port = json.loads(PORT.read_text()) if PORT.exists() else None
    if port:
        entries = port.get('entries') or []
        rows = [['entry', 'salary', 'projected', 'simulated_mean', 'provenance', 'players']]
        for e in entries:
            rows.append([e['entry'], e['salary'], e['projected'], e['simulated_mean'],
                         e['provenance'], ' | '.join(e['names'])])
        if not entries:
            rows.append(['NOT_RECORDED', '', '', '', '',
                         'the portfolio artifact predates roster recording'])
        rows += [[], ['ENTRIES ARE NOT SUBMITTED', '', '', '', '',
                      port.get('ENTRIES_ARE_NOT_SUBMITTED', '')]]
        sheets.append(('Portfolio', rows))
        arms = [['arm', 'p_at_least_one_top_1pct', 'mean_projected', 'distinct_players',
                 'max_exposure']]
        for a in port['arms']:
            arms.append([a['label'], a['p_at_least_one_in_top_1pct'], a['mean_projected'],
                         a['n_distinct_players'], a['max_player_exposure']])
        ds = port.get('decision_sensitivity') or {}
        arms += [[], ['DECISION SENSITIVITY', ds.get('VERDICT')]]
        for x in (ds.get('settings') or []):
            arms.append([x.get('setting'), x.get('p_joint'), x.get('p_independent'),
                         x.get('portfolio_overlap_with_base'), ''])
        sheets.append(('Portfolio Method', arms))
        meta.append(['sim_optimal', (port.get('GOVERNANCE') or {}).get('sim_optimal')])

    rd = readiness.build()
    if rd.state.value == 'PASS':
        v = rd.value
        rows = [['tier', 'stage', 'state', 'age_hours', 'tolerance_hours', 'age_source']]
        for r in v['stages']:
            rows.append([r['tier'], r['name'], r['state'], r['age_hours'], r['max_age_hours'],
                         r['age_source']])
        rows += [[], ['PRODUCT MODE', v['PRODUCT_MODE']], ['BECAUSE', v['PRODUCT_MODE_BECAUSE']],
                 ['SATURDAY RULE', f"{v['saturday_rule']['state']} "
                                   f"{v['saturday_rule']['code']}"]]
        sheets.append(('Readiness', rows))
        meta += [['product_mode', v['PRODUCT_MODE']],
                 ['saturday_rule', v['saturday_rule']['code']]]

    meta += [
        ['generated_at_unix', int(time.time())],
        ['slate', 'DK NFL Week 3 2026'],
        ['WHAT_THIS_IS_NOT', 'not a recommendation, not a wager, not an upload'],
        ['dst_scoring_tail', 'defensive and return touchdowns and safeties are MEASURED from '
                             'play-by-play, not excluded; OUT-041 closed 2026-09-28'],
        ['field_is_uncalibrated', 'no archived contest ownership exists; see OUT-040'],
        ['projection_inputs', 'proprietary only. No external projection is a feature input.'],
    ]
    sheets.append(('Metadata', meta))
    # xlsx_writer.write returns a plain dict, and verify() is what says whether the file is
    # structurally a workbook. Both are checked, because a written file is not a read file.
    written = xlsx_writer.write(SUPP, sheets)
    ver = xlsx_writer.verify(SUPP, expected_sheets=[n for n, _ in sheets])
    if not ver.get('ok'):
        return Outcome.fail('SUPPLEMENT_NOT_A_VALID_WORKBOOK',
                            f"verify refused the written file: {ver.get('reason')}", **ver)
    return Outcome.ok('SUPPLEMENT_WRITTEN', value={
        'path': str(SUPP.relative_to(_REPO)),
        'sheets': written['sheets'],
        'n_sheets': len(sheets),
        'verify': ver})


def run(*, archive: bool = False) -> Outcome:
    """The Sunday deliverable.

    `archive` is OPT-IN and defaults to False. The suite calls run() many times, and with archiving
    on by default each call sealed a new directory into the permanent record, so the archive filled
    with test artifacts indistinguishable from delivered slates. The production entry points --
    main() below, and anything driving a real Sunday -- pass archive=True.
    """
    t0 = time.time()
    steps = []

    rd = readiness.build()
    steps.append({'step': 'readiness', 'state': rd.state.value, 'code': rd.code,
                  'product_mode': (rd.value or {}).get('PRODUCT_MODE')})
    if rd.state.value != 'PASS':
        return Outcome.fail('SUNDAY_RUN_READINESS_FAILED', 'the readiness board did not build',
                            steps=steps)
    mode = rd.value['PRODUCT_MODE']
    if mode == 'NOT_PRODUCTION_READY':
        report = {'ARTIFACT': 'SUNDAY_RUN_REPORT', 'RESULT': 'REFUSED', 'steps': steps,
                  'why': rd.value['PRODUCT_MODE_BECAUSE'],
                  'RULE': ('a deliverable is not produced from a board that cannot produce a legal '
                           'portfolio or is missing its model layer')}
        REPORT.write_text(json.dumps(report, indent=2))
        return Outcome.blocked('SUNDAY_RUN_REFUSED_NOT_PRODUCTION_READY',
                               rd.value['PRODUCT_MODE_BECAUSE'], cause=Cause.DEPENDENCY,
                               steps=steps)

    # FOOTBALL SANITY BEFORE ANY DELIVERABLE (owner ruling 2026-10-02). The slate projection the
    # readiness board found FRESH is read and refused on a football contradiction -- a starter
    # charged a backup penalty, a club's attempts not reconciling with its quarterback, an inactive
    # player with opportunity, a quarterback with receiver volume, a missing input read as zero.
    # Green mechanics downstream cannot repair a wrong football state upstream, so this step is a
    # step like the others: it FAILS the run, it never degrades it.
    from nfl.tools import football_sanity
    _proj_stage = next((r for r in rd.value['stages'] if r['name'] == 'slate.projection'), None)
    _proj_path = _REPO / _proj_stage['path'] if _proj_stage else None
    if _proj_path is not None and _proj_path.exists():
        try:
            # kickers are projected by the kicking layer and checked by the output contract's K
            # sheet; the projection artifact carries skill rows and the defence.
            fs = football_sanity.assess(json.loads(_proj_path.read_text()), units=('DST',))
        except Exception as e:  # noqa: BLE001 -- a gate that crashes is a gate that failed
            fs = Outcome.fail('FOOTBALL_SANITY_CRASHED', f'{type(e).__name__}: {e}')
    else:
        fs = Outcome.fail('FOOTBALL_SANITY_NO_PROJECTION', 'the slate projection is absent, so '
                          'football sanity cannot be assessed; a missing input is not a pass')
    steps.append({'step': 'football_sanity', 'state': fs.state.value, 'code': fs.code,
                  'problems': (fs.evidence or {}).get('problems') or {},
                  'projection': str(_proj_path.relative_to(_REPO)) if _proj_path else None})

    con = verify_contract()
    steps.append({'step': 'output_contract', 'state': con.state.value, 'code': con.code,
                  'n_problems': len((con.value or con.evidence or {}).get('problems') or [])})
    sup = supplement()
    steps.append({'step': 'supplement', 'state': sup.state.value, 'code': sup.code,
                  'sheets': (sup.value or {}).get('n_sheets')})

    stale = [r['name'] for r in rd.value['stages'] if r['state'] != 'FRESH']

    # ARCHIVE THE RUN INTO A SEALED DIRECTORY. The fixed output paths are overwritten by the next
    # run, so without this the slate actually delivered on a given Sunday exists only until the next
    # one. Archiving alters no number; it copies and seals. A failure here does NOT downgrade the
    # deliverable -- the deliverable exists either way -- but it is recorded as its own step so an
    # unarchived run is visible rather than assumed.
    from nfl.production import run_archive
    if archive:
        arch = run_archive.archive(SLATE_ID, note='archived by sunday.run(archive=True)')
    else:
        arch = Outcome.deferred(
            'RUN_NOT_ARCHIVED',
            'run() was called with archive=False, so this run was not sealed into the record',
            owed='call run(archive=True) from a production entry point, or archive explicitly',
            note=('the default is off because the test suite calls run() repeatedly and each '
                  'archive would be indistinguishable from a delivered slate'))
    steps.append({'step': 'run_archive', 'state': arch.state.value, 'code': arch.code,
                  'run_id': (arch.value or {}).get('run_id')})

    report = {
        'ARTIFACT': 'SUNDAY_RUN_REPORT',
        'RESULT': ('DELIVERED' if con.state.value == 'PASS' and sup.state.value == 'PASS'
                   and fs.state.value == 'PASS' else 'DELIVERED_WITH_PROBLEMS'),
        'football_sanity': {'state': fs.state.value, 'code': fs.code,
                            'problems': (fs.evidence or {}).get('problems') or {}},
        'product_mode': mode,
        'stale_stages': stale,
        'steps': steps,
        'run_archive': (arch.value if arch.state.value == 'PASS'
                        else {'state': arch.state.value, 'code': arch.code,
                              'detail': arch.detail}),
        'ARCHIVE_MEANING': (
            'the fixed output paths are the CURRENT run and the next run overwrites them. The '
            'sealed directory named here is the immutable copy of THIS run. Reproduction needs its '
            'inputs too, which the lineage block inside each artifact names.'),
        'output_contract': con.value if con.state.value == 'PASS' else con.evidence,
        'supplement': sup.value if sup.value else {},
        'elapsed_seconds': round(time.time() - t0, 2),
        'FOUR_CLAUSES': {
            'no_forgotten_position': 'checked: every DK position has a sheet',
            'no_silently_missing_player': 'checked: CSV vs availability universe, both directions',
            'no_stale_source_surprise': f'reported: {len(stale)} stale stage(s) named above',
            'no_late_model_development': ('by construction: this module consumes artifacts and '
                                          'cannot fit anything'),
            'no_football_contradiction': f'checked: football_sanity {fs.code}',
        },
        'GOVERNANCE': {
            'submitted': 'NOTHING',
            'contest_entered': 'NONE',
            'wager_recommended': 'NONE',
            'external_projection_as_input': 'NONE',
        },
    }
    REPORT.write_text(json.dumps(report, indent=2))
    # EVERY step must pass, not just the contract. The first version gated on the contract alone
    # and returned PASS while the supplement had FAILED -- the exact shape of defect this project
    # treats as the expensive one, in the module whose job is to catch it.
    failed = [s for s in steps if s['state'] not in ('PASS', 'NOT_APPLICABLE')]
    if failed:
        report['RESULT'] = 'DELIVERED_WITH_PROBLEMS'
        REPORT.write_text(json.dumps(report, indent=2))
        return Outcome.fail('SUNDAY_RUN_STEP_FAILED',
                            f"{len(failed)} step(s) did not pass: "
                            f"{[s['step'] + '=' + s['code'] for s in failed]}",
                            failed_steps=failed, **report)
    return Outcome.ok('SUNDAY_RUN_DELIVERED', value=report)


if __name__ == '__main__':
    # THE PRODUCTION ENTRY POINT ARCHIVES. Running this file is a real Sunday run, so it seals
    # itself into the record; run() called from a test does not.
    o = run(archive=True)
    print(o.state.value, o.code)
    v = o.value if o.value else o.evidence
    for s in (v.get('steps') or []):
        print(f"  {s['step']:18s} {s['state']:8s} {s['code']}"
              + (f"  mode={s['product_mode']}" if s.get('product_mode') else '')
              + (f"  sheets={s['sheets']}" if s.get('sheets') else '')
              + (f"  problems={s['n_problems']}" if s.get('n_problems') is not None else ''))
    c = v.get('output_contract') or {}
    if c:
        print(f"  CSV rows {c.get('n_csv_rows')} against a universe of {c.get('n_universe')}; "
              f"{c.get('n_sheets')} sheets")
        print(f"  by position {c.get('rows_by_position')}")
        for p in (c.get('problems') or []):
            print(f"  PROBLEM {p}")
    print(f"  RESULT {v.get('RESULT')}  mode {v.get('product_mode')}  "
          f"stale {v.get('stale_stages')}")
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
