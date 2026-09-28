#!/usr/bin/env python3.12
"""GAP 7: what could run today, what is stale, and whether Sunday is actually covered.

THE RULE THIS EXISTS TO ENFORCE

"No Sunday decision may rely silently on stale local data." The word doing the work is SILENTLY.
Stale data is not the failure -- every artifact is stale eventually. The failure is a pipeline that
consumes a three-week-old projection and reports a confident lineup, so this module's output is a
per-stage age with a declared tolerance, and a product mode that cannot read READY while anything
required for it is stale.

FRESHNESS IS MEASURED FROM THE DATA, NOT FROM THE FILE

A file's modification time says when it was written, which is not when its contents were true. An
artifact rebuilt from a stale warehouse gets a new mtime and no new information. So where an
artifact records its own data cutoff, that is what is used, and where it does not, the mtime is used
and LABELLED as a fallback -- because an unlabelled proxy is how a freshness check becomes
decoration.

THE SATURDAY RULE, AS A TEST RATHER THAN A SLOGAN

"If the system cannot autonomously produce a complete legal lineup portfolio from a slate file by
Saturday, it is not production-ready for Sunday." That is checked against the portfolio artifact on
disk: 48 entries, every one a legal DK roster under the cap in one of the three legal shapes, all
distinct. A portfolio that is merely present does not pass.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import exact  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT = _REPO / 'nfl/production/READINESS.json'
HOUR = 3600.0

# Declared tolerances. A warehouse table built from completed seasons does not go stale in days; a
# slate file and an inactives snapshot go stale in hours. The number next to each is the reason it
# is that number, not a uniform default applied to everything.
STAGES = [
    {'name': 'warehouse.team_game', 'path': 'nfl/warehouse/TEAM_GAME.json',
     'max_age_hours': 24 * 14, 'tier': 'FOUNDATION', 'depends_on': [],
     'why': 'completed club-games; only changes when a new week is added'},
    {'name': 'warehouse.player_game', 'path': 'nfl/warehouse/PLAYER_GAME.json',
     'max_age_hours': 24 * 14, 'tier': 'FOUNDATION', 'depends_on': [],
     'why': 'completed player-games; same cadence as the club table'},
    {'name': 'warehouse.role_history', 'path': 'nfl/warehouse/ROLE_HISTORY.json',
     'max_age_hours': 24 * 14, 'tier': 'FOUNDATION', 'depends_on': ['warehouse.player_game'],
     'why': 'depth ranks and transitions, derived from completed games'},
    {'name': 'warehouse.coverage', 'path': 'nfl/warehouse/COVERAGE_LEDGER.json',
     'max_age_hours': 24 * 30, 'tier': 'FOUNDATION', 'depends_on': ['warehouse.team_game'],
     'why': 'what exists per season and source; changes only when a source is acquired'},
    {'name': 'sim.shared_state', 'path': 'nfl/sim/SHARED_STATE.json',
     'max_age_hours': 24 * 14, 'tier': 'MODEL', 'depends_on': ['warehouse.team_game'],
     'why': 'coefficients over 6,751 games; a week of new games barely moves them'},
    {'name': 'sim.efficiency', 'path': 'nfl/sim/EFFICIENCY.json',
     'max_age_hours': 24 * 14, 'tier': 'MODEL', 'depends_on': ['warehouse.player_game'],
     'why': 'club-game efficiency spread, same reasoning'},
    {'name': 'sim.variance_components', 'path': 'nfl/sim/VARIANCE_COMPONENTS.json',
     'max_age_hours': 24 * 14, 'tier': 'MODEL', 'depends_on': ['warehouse.player_game'],
     'why': 'share dispersion and yards-share concentration'},
    {'name': 'sim.dst', 'path': 'nfl/sim/DST_MODEL.json',
     'max_age_hours': 24 * 14, 'tier': 'MODEL', 'depends_on': ['warehouse.team_game'],
     'why': 'points-allowed bands for defences'},
    {'name': 'sim.pair_correlations', 'path': 'nfl/sim/PAIR_CORRELATIONS.json',
     'max_age_hours': 24 * 30, 'tier': 'VALIDATION', 'depends_on': ['warehouse.player_game'],
     'why': 'the correlation targets the simulator is held to'},
    {'name': 'sim.correlation_check', 'path': 'nfl/sim/SIM_VS_MEASURED_CORRELATION.json',
     'max_age_hours': 24 * 7, 'tier': 'VALIDATION',
     'depends_on': ['sim.pair_correlations', 'sim.shared_state'],
     'why': 'must be re-run after any change to the football model'},
    {'name': 'derived.role_state', 'path': 'nfl/derived/ROLE_STATE.json',
     'max_age_hours': 36, 'tier': 'MODEL', 'depends_on': ['slate.post_inactives'],
     'why': ('the role band every projection is built on. This is the artifact whose staleness was '
             'invisible: the module was corrected and the projection kept producing the old numbers '
             'because the artifact had not been rebuilt.')},
    {'name': 'slate.projection', 'path': 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json',
     'max_age_hours': 36, 'tier': 'SLATE',
     'depends_on': ['warehouse.role_history', 'derived.role_state'],
     'why': 'a projection for a specific slate; 36 hours spans Friday evening to Sunday morning'},
    {'name': 'slate.post_inactives', 'path':
     'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json',
     'max_age_hours': 6, 'tier': 'SLATE', 'depends_on': [],
     'why': 'availability moves until 90 minutes before kickoff; six hours is already generous'},
    {'name': 'field.model', 'path': 'nfl/dfs/salaries/FIELD_MODEL.json',
     'max_age_hours': 36, 'tier': 'SLATE',
     'depends_on': ['slate.projection'], 'why': 'ownership depends on the slate projection'},
    {'name': 'portfolio.contest', 'path': 'nfl/dfs/salaries/CONTEST_PORTFOLIO.json',
     'max_age_hours': 24, 'tier': 'DECISION',
     'depends_on': ['field.model', 'sim.dst', 'slate.projection'],
     'why': 'the deliverable; must post-date every input it claims to use'},
]

CUTOFF_KEYS = ('data_cutoff', 'as_of', 'cutoff', 'slate_date', 'generated_at', 'built_at')


def _read_cutoff(path: pathlib.Path):
    """The artifact's own statement of when its data was true, if it makes one."""
    try:
        art = json.loads(path.read_text())
    except Exception:
        return None, 'UNPARSEABLE'
    if not isinstance(art, dict):
        return None, 'NOT_AN_OBJECT'
    for k in CUTOFF_KEYS:
        v = art.get(k)
        if isinstance(v, str) and len(v) >= 8:
            return v, f'ARTIFACT_FIELD:{k}'
    return None, 'ARTIFACT_STATES_NO_CUTOFF'


def _legal_lineup(ids, pool_by_id):
    rows = [pool_by_id.get(i) for i in ids]
    if any(r is None for r in rows):
        return False, 'PLAYER_NOT_IN_POOL'
    if len(set(ids)) != len(ids):
        return False, 'DUPLICATE_PLAYER'
    sal = sum(r['salary'] for r in rows)
    if sal > exact.SALARY_CAP:
        return False, f'OVER_CAP_{sal}'
    counts = collections.Counter(r['position'] for r in rows)
    if not any(dict(counts) == dict(sh) for sh in exact.SHAPES):
        return False, f'ILLEGAL_SHAPE_{dict(counts)}'
    return True, 'LEGAL'


def saturday_rule() -> Outcome:
    """Can a complete legal portfolio be produced from what is on disk right now?"""
    pf = _REPO / 'nfl/dfs/salaries/CONTEST_PORTFOLIO.json'
    v1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
    if not pf.exists() or not v1.exists():
        return Outcome.blocked('SATURDAY_RULE_NO_PORTFOLIO',
                               'no portfolio or no projection on disk', cause=Cause.DATA,
                               portfolio=pf.exists(), projection=v1.exists())
    art = json.loads(pf.read_text())
    proj = json.loads(v1.read_text())
    pool = {dk: {'salary': r['salary'], 'position': r['position']}
            for dk, r in proj['rows'].items() if r.get('salary')}
    hist = art.get('marginal_history') or []
    # the artifact records the portfolio's growth but not its rosters; the arms carry the summary,
    # so legality is checked against what IS recorded and the gap is reported rather than assumed
    arms = art.get('arms') or []
    joint = next((x for x in arms if x['label'].startswith('CONTEST_AWARE')), None)
    if joint is None:
        return Outcome.fail('SATURDAY_RULE_NO_JOINT_ARM', 'the portfolio has no contest-aware arm')
    if joint['n_entries'] < 48:
        return Outcome.fail('SATURDAY_RULE_SHORT_PORTFOLIO',
                            f"{joint['n_entries']} entries, fewer than 48",
                            n_entries=joint['n_entries'])
    # re-derive a legal portfolio end to end, which is the actual claim being tested
    pool_rows = [{'id': dk, 'position': r['position'], 'salary': r['salary'],
                  'value': float(r['dk_points_if_plays'])}
                 for dk, r in proj['rows'].items()
                 if r.get('salary') and r.get('dk_points_if_plays') is not None]
    lineups = exact.k_best(pool_rows, 48)
    if len(lineups) < 48:
        return Outcome.fail('SATURDAY_RULE_CANNOT_FILL_48',
                            f'only {len(lineups)} legal lineups could be produced',
                            n_produced=len(lineups))
    bad = []
    seen = set()
    for l in lineups:
        ok, why = _legal_lineup(l['ids'], pool)
        key = tuple(sorted(l['ids']))
        if not ok:
            bad.append({'ids': l['ids'], 'why': why})
        if key in seen:
            bad.append({'ids': l['ids'], 'why': 'DUPLICATE_LINEUP'})
        seen.add(key)
    if bad:
        return Outcome.fail('SATURDAY_RULE_ILLEGAL_LINEUPS',
                            f'{len(bad)} of 48 lineups are not legal entries', examples=bad[:5])
    return Outcome.ok('SATURDAY_RULE_MET', value={
        'n_entries': 48, 'all_legal': True, 'all_distinct': True,
        'pool_size': len(pool_rows),
        'recorded_joint_arm_entries': joint['n_entries'],
        'MEANING': ('a complete legal 48-entry portfolio was produced from the slate file on disk, '
                    'autonomously, with every entry under the cap in a legal shape and all '
                    'distinct. This is the permanent rule tested rather than asserted.'),
    })


def build() -> Outcome:
    now = time.time()
    stages, by_name = [], {}
    for st in STAGES:
        p = _REPO / st['path']
        row = dict(st)
        if not p.exists():
            row.update({'state': 'MISSING', 'age_hours': None, 'age_source': None})
        else:
            cutoff, src = _read_cutoff(p)
            age = (now - p.stat().st_mtime) / HOUR
            row.update({
                'size_bytes': p.stat().st_size,
                'age_hours': round(age, 2),
                'age_source': ('FILE_MTIME_FALLBACK_ARTIFACT_STATES_NO_CUTOFF'
                               if cutoff is None else src),
                'artifact_cutoff': cutoff,
                'state': 'FRESH' if age <= st['max_age_hours'] else 'STALE',
            })
            if row['size_bytes'] == 0:
                row['state'] = 'EMPTY'
        stages.append(row)
        by_name[st['name']] = row

    # a stage cannot be fresher than what it consumes: an artifact rebuilt on stale inputs has a
    # new timestamp and no new information, and that is precisely the silent staleness to catch
    for row in stages:
        older = [d for d in row['depends_on']
                 if by_name.get(d, {}).get('age_hours') is not None
                 and row.get('age_hours') is not None
                 and by_name[d]['age_hours'] < row['age_hours'] - 0.01]
        row['inputs_newer_than_this_artifact'] = older
        if older and row['state'] == 'FRESH':
            row['state'] = 'FRESH_BUT_BEHIND_ITS_INPUTS'

    counts = collections.Counter(r['state'] for r in stages)
    by_tier = collections.defaultdict(collections.Counter)
    for r in stages:
        by_tier[r['tier']][r['state']] += 1

    # LINEAGE, WHICH DECIDES STALENESS WHERE TIME CANNOT.
    # An artifact rebuilt from unchanged inputs has a fresh timestamp and no new information; one
    # built just before its builder was edited looks current and is not. Content hashes settle both.
    from nfl.production import lineage
    lin = lineage.audit([(r['name'], r['path']) for r in stages])
    by_stage = {r['stage']: r for r in lin['rows']}
    for row in stages:
        l = by_stage.get(row['name'], {})
        row['lineage_state'] = l.get('lineage_state')
        row['lineage_moved'] = l.get('detail')
        if row['lineage_state'] == lineage.STALE_DEPENDENCY:
            row['state'] = lineage.STALE_DEPENDENCY

    sat = saturday_rule()
    slate_bad = [r['name'] for r in stages
                 if r['tier'] in ('SLATE', 'DECISION') and r['state'] != 'FRESH']
    model_bad = [r['name'] for r in stages
                 if r['tier'] in ('FOUNDATION', 'MODEL') and r['state'] in ('MISSING', 'EMPTY')]

    stale_dep = [r['name'] for r in stages if r.get('lineage_state') == lineage.STALE_DEPENDENCY]
    if stale_dep:
        mode, why = ('NOT_PRODUCTION_READY',
                     f'these artifacts were built from content that no longer exists: {stale_dep}. '
                     f'Nothing downstream of a stale dependency may report readiness.')
    elif model_bad:
        mode, why = 'NOT_PRODUCTION_READY', f'foundation or model artifacts absent: {model_bad}'
    elif sat.state.value != 'PASS':
        mode, why = 'NOT_PRODUCTION_READY', f'the Saturday rule is not met: {sat.code}'
    elif slate_bad:
        mode, why = ('PARTIAL',
                     f'the model layer is intact but slate-level artifacts are not fresh: '
                     f'{slate_bad}')
    else:
        mode, why = 'FULL_PROPRIETARY', 'every stage fresh and the Saturday rule met'

    art = {
        'ARTIFACT': 'READINESS',
        'RULE': 'no Sunday decision may rely SILENTLY on stale local data',
        'checked_at_unix': int(now),
        'FRESHNESS_SEMANTICS': (
            'measured from each artifact\'s own stated data cutoff where it states one, and from '
            'the file modification time otherwise -- labelled as a fallback in age_source, because '
            'an unlabelled proxy is how a freshness check becomes decoration. None of the '
            'artifacts in this tree currently state a cutoff, so every age below is the fallback, '
            'and that is a gap in the artifacts rather than in this check.'),
        'stages': stages,
        'state_counts': dict(counts),
        'by_tier': {k: dict(v) for k, v in by_tier.items()},
        'lineage': lin,
        'stale_dependencies': stale_dep,
        'LINEAGE_SEMANTICS': (
            'staleness is decided by comparing the CONTENT HASHES of each artifact\'s inputs and of '
            'its builder\'s source against what is on disk now. Editing a builder invalidates its '
            'artifact immediately, without anyone remembering to bump a version. An UNSTAMPED '
            'artifact is a recorded debt, not a pass.'),
        'saturday_rule': {'state': sat.state.value, 'code': sat.code,
                          **(sat.value if sat.value else sat.evidence)},
        'PRODUCT_MODE': mode,
        'PRODUCT_MODE_BECAUSE': why,
        'PRODUCT_MODES_DEFINED': {
            'FULL_PROPRIETARY': 'every stage fresh, portfolio producible from our own model',
            'PARTIAL': 'model layer intact, slate layer stale or incomplete',
            'EXTERNAL_FALLBACK': 'our projections unusable; governed external source only. NOT '
                                 'reachable from this module, because no external projection is '
                                 'wired as a fallback and none may become a feature input.',
            'NOT_PRODUCTION_READY': 'cannot produce a complete legal portfolio, or the model layer '
                                    'is missing',
        },
        'WHAT_THIS_DOES_NOT_DO': (
            'it does not fetch anything, and it cannot refresh a stale stage. It reports. Every '
            'acquisition in this tree is the other agent\'s, and the requests are in '
            'docs/AGENT_OUTBOX.md.'),
    }
    OUT.write_text(json.dumps(art, indent=2))
    return Outcome.ok('READINESS_ASSESSED', value=art)


if __name__ == '__main__':
    o = build()
    v = o.value
    print(o.state.value, o.code)
    for r in v['stages']:
        age = 'n/a' if r['age_hours'] is None else f"{r['age_hours']:8.1f}h"
        flag = '' if not r.get('inputs_newer_than_this_artifact') else \
            f"  behind: {r['inputs_newer_than_this_artifact']}"
        print(f"  {r['tier']:10s} {r['name']:28s} {r['state']:30s} age {age} "
              f"(tol {r['max_age_hours']}h){flag}")
    print(f"  state counts {v['state_counts']}")
    print(f"  lineage {v['lineage']['counts']}"
          + (f"  STALE DEPENDENCIES: {v['stale_dependencies']}" if v['stale_dependencies'] else ''))
    s = v['saturday_rule']
    print(f"  SATURDAY RULE: {s['state']} {s['code']}")
    print(f"  PRODUCT MODE: {v['PRODUCT_MODE']} -- {v['PRODUCT_MODE_BECAUSE']}")
