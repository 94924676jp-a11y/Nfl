"""The layer-state matrix, emitted BEFORE the simulation spend.

WHY IT RUNS FIRST

On 2026-09-24 the ATL @ GB run executed every football stage over 471 seconds
and 8,000 draws, and then refused at artifact sealing because one
current-season input was stale. Nothing was wrong with that refusal -- the
gate worked. What was wrong is that it was discovered LAST. Several blockers
that day were found the same way, one at a time, each after work that could
not have been used.

This reads the same checkers the pipeline reads and says up front which layers
are ready, which are partial, and which will refuse. It is a report, not a
gate: it never decides whether to run, because deciding that from a summary is
how a summary quietly becomes the authority.

WHAT UNKNOWN MEANS HERE, AND WHY IT IS NOT A HEDGE

A layer whose checker this module cannot call reports UNKNOWN. That is a
deliberate state and it is not the same as PASS. The whole failure mode this
project is organised against is a step that returned nothing being read as
success, and a readiness matrix that printed a comfortable colour for a layer
it never checked would be that defect wearing a dashboard.

THE TWO KINDS OF BLOCKER ARE NOT THE SAME AND ARE NOT MERGED

  EXECUTION   the simulation cannot run, or will run on evidence it should
              not be running on
  SEALING     the simulation can run and its output cannot be published

A run blocked only on SEALING is still worth executing -- that is exactly what
UNSEALED_RESEARCH_OUTPUT is for. A run blocked on EXECUTION is not. Collapsing
them into one red light would have told the operator to abandon a run whose
numbers were fine.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

SPEC_VERSION = 'pregame-readiness/1.0.0'

PASS = 'PASS'
PARTIAL = 'PARTIAL'
APPROXIMATION = 'APPROXIMATION'
BLOCKED = 'BLOCKED'
DEFERRED = 'DEFERRED'
UNKNOWN = 'UNKNOWN'

EXECUTION = 'EXECUTION'
SEALING = 'SEALING'
NONE = 'NONE'

#: Declared layer order. A layer absent from this list cannot be reported,
#: which is deliberate: the matrix must be a closed set someone chose, not
#: whatever happened to be computable on the day.
LAYERS = (
    ('schedule', EXECUTION),
    ('roster', EXECUTION),
    ('identity', EXECUTION),
    ('injury_content', EXECUTION),
    ('injury_completeness', NONE),
    ('depth_chart', EXECUTION),
    ('prior_week_pbp', EXECUTION),
    ('participation', NONE),
    ('team_volume', SEALING),
    ('official_inactives', NONE),
    ('sportsbook', NONE),
    ('dk_salary', NONE),
    ('model_execution', EXECUTION),
    ('artifact_sealing', SEALING),
)

_BLOCKING_STATES = (BLOCKED,)


class ReadinessError(RuntimeError):
    """The matrix cannot be built at all."""


def _row(layer, state, detail, *, blocks=None, evidence=None):
    declared = dict(LAYERS).get(layer)
    if declared is None:
        raise ReadinessError(
            f'{layer!r} is not a declared layer. Add it to LAYERS '
            f'deliberately rather than letting the matrix grow by accident.')
    return {
        'layer': layer,
        'state': state,
        'blocks': (blocks if blocks is not None else declared),
        'detail': detail,
        'evidence': evidence or {},
    }


def from_run_input(contract: dict, report: dict | None = None) -> list[dict]:
    """Rows derivable from a frozen run-input contract and its verify report.

    Reads the CONTRACT rather than the filesystem. This module must not do its
    own discovery: a readiness matrix that globbed for the newest file would
    be reporting on evidence the forecast is not going to use.
    """
    entries = (contract or {}).get('entries') or {}
    if not entries:
        raise ReadinessError(
            'the run-input contract carries no entries, so there is nothing '
            'to report readiness on. An empty contract is not a ready one.')
    # run_input.verify returns per_family[fam]['verdict']; older callers
    # passed a flat {family: verdict} map. Accept both rather than silently
    # finding nothing and reporting UNKNOWN for a report that was supplied.
    rep = report or {}
    family_state = {}
    for fam, v in (rep.get('per_family') or {}).items():
        family_state[fam] = v.get('verdict') if isinstance(v, dict) else v
    for fam, v in (rep.get('verdicts') or {}).items():
        family_state.setdefault(fam, v)

    def fam_row(layer, family, *, blocks=None):
        e = entries.get(family)
        if e is None:
            return _row(layer, BLOCKED,
                        f'{family} is absent from the frozen contract',
                        blocks=blocks)
        v = family_state.get(family)
        if v is None:
            return _row(layer, UNKNOWN,
                        f'{family} is pinned but this matrix was given no '
                        f'verify report for it, so its freshness is not '
                        f'established here',
                        blocks=blocks,
                        evidence={'capture_id': e.get('capture_id'),
                                  'sha256': e.get('sha256')})
        # AGE_NOT_BOUNDED is NOT a pass. Nobody declared how old is too old
        # for that family, so its age was not checked.
        if v in ('FRESH', PASS, True):
            state = PASS
        elif v == 'AGE_NOT_BOUNDED':
            state = UNKNOWN
        elif v in ('MISSING', 'HASH_MISMATCH', 'AFTER_CUTOFF'):
            state = BLOCKED
        else:
            state = PARTIAL
        return _row(layer, state, f'{family}: {v}', blocks=blocks,
                    evidence={'capture_id': e.get('capture_id'),
                              'sha256': e.get('sha256'), 'verdict': v})

    return [
        fam_row('schedule', 'schedules'),
        fam_row('roster', 'weekly_rosters'),
        fam_row('depth_chart', 'depth_charts'),
        fam_row('injury_content', 'injuries'),
    ]


def espn_completeness(truncation: dict | None) -> dict:
    """The injury feed's completeness, kept separate from its content.

    Content and completeness are different questions and the whole point of
    A2 is that they stop sharing one light. A feed can return real, correctly
    attributed, perfectly fresh content AND be truncated.
    """
    if not truncation:
        return _row('injury_completeness', UNKNOWN,
                    'no truncation report was supplied, so completeness is '
                    'not established. This is not the same as complete.')
    if truncation.get('truncated'):
        return _row(
            'injury_completeness', PARTIAL,
            f"every club returned exactly the page cap of "
            f"{truncation.get('page_cap')}, so this capture is a truncated "
            f"view: COVERAGE_NOT_ESTABLISHED / SUSPECTED_TRUNCATION. Absence "
            f"from it is doubly uninformative and is never health.",
            evidence={'page_cap': truncation.get('page_cap'),
                      'n_clubs': truncation.get('n_clubs'),
                      'n_clubs_at_cap': truncation.get('n_clubs_at_cap')})
    return _row('injury_completeness', PASS,
                'at least one club returned fewer than the cap, so the cap is '
                'not binding everywhere in this capture',
                evidence={'page_cap': truncation.get('page_cap')})


def inactives_row(contract: dict, *, now=None, kickoff=None) -> dict:
    """Official inactives, which are DEFERRED before they publish.

    Not a failure. The list publishes about ninety minutes before kickoff, so
    before that window its absence is the expected state of the world and
    saying BLOCKED would cry wolf on every pregame run.
    """
    e = ((contract or {}).get('entries') or {}).get('official_inactives')
    if e is None:
        return _row('official_inactives', DEFERRED,
                    'not pinned in this contract')
    cap = str(e.get('capture_id') or '')
    detail = f'pinned capture {cap}'
    if kickoff and now:
        mins = (kickoff - now).total_seconds() / 60.0
        if mins > 90:
            detail += (f'; {mins:.0f} min to kickoff, so the official list is '
                       f'not expected to have published yet')
        else:
            detail += (f'; {mins:.0f} min to kickoff, so the official list '
                       f'should be available and this pin should be re-checked')
    return _row('official_inactives', DEFERRED, detail,
                evidence={'capture_id': cap, 'sha256': e.get('sha256')})


def build(contract: dict, *, verify_report=None, truncation=None,
          team_volume=None, extra=None, now=None, kickoff=None) -> dict:
    """Assemble the matrix. Every declared layer gets exactly one row."""
    rows = list(from_run_input(contract, verify_report))
    rows.append(espn_completeness(truncation))
    rows.append(inactives_row(contract, now=now, kickoff=kickoff))

    if team_volume is None:
        rows.append(_row('team_volume', UNKNOWN,
                         'no current-season freshness verdict was supplied'))
    else:
        st = team_volume.get('state') or UNKNOWN
        rows.append(_row('team_volume',
                         BLOCKED if st in ('BLOCKED', 'STALE') else PASS,
                         team_volume.get('detail') or str(st),
                         evidence=team_volume))

    for layer, row in (extra or {}).items():
        rows.append(_row(layer, row.get('state', UNKNOWN),
                         row.get('detail', ''),
                         evidence=row.get('evidence')))

    seen = {r['layer'] for r in rows}
    for layer, _blocks in LAYERS:
        if layer not in seen:
            rows.append(_row(layer, UNKNOWN,
                             'no checker was supplied for this layer'))

    order = {name: i for i, (name, _) in enumerate(LAYERS)}
    rows.sort(key=lambda r: order[r['layer']])

    blocks_exec = [r['layer'] for r in rows
                   if r['state'] in _BLOCKING_STATES and r['blocks'] == EXECUTION]
    blocks_seal = [r['layer'] for r in rows
                   if r['state'] in _BLOCKING_STATES and r['blocks'] == SEALING]
    unknown = [r['layer'] for r in rows if r['state'] == UNKNOWN]

    return {
        'spec_version': SPEC_VERSION,
        'built_at_utc': (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
        'game_id': (contract or {}).get('game_id'),
        'cutoff_utc': (contract or {}).get('cutoff_utc'),
        'rows': rows,
        'blocks_execution': blocks_exec,
        'blocks_sealing': blocks_seal,
        'unknown_layers': unknown,
        'execution_verdict': 'REFUSED' if blocks_exec else 'ELIGIBLE',
        'sealing_verdict': 'REFUSED' if blocks_seal else 'NOT_REFUSED_HERE',
        'reading': (
            'ELIGIBLE means no DECLARED execution blocker was found by the '
            'checkers supplied. It does not mean the run will succeed, and a '
            'layer reported UNKNOWN was not checked at all. This is a report; '
            'it decides nothing.'),
    }


def render(matrix: dict) -> str:
    w = max(len(r['layer']) for r in matrix['rows'])
    lines = [f"pregame readiness  {matrix.get('game_id')}  "
             f"cutoff {matrix.get('cutoff_utc')}",
             f"{'layer'.ljust(w)}  {'state':<14} blocks",
             f"{'-' * w}  {'-' * 14} {'-' * 9}"]
    for r in matrix['rows']:
        lines.append(f"{r['layer'].ljust(w)}  {r['state']:<14} {r['blocks']}")
    lines.append('')
    lines.append(f"execution: {matrix['execution_verdict']}"
                 + (f"  blocked by {matrix['blocks_execution']}"
                    if matrix['blocks_execution'] else ''))
    lines.append(f"sealing:   {matrix['sealing_verdict']}"
                 + (f"  blocked by {matrix['blocks_sealing']}"
                    if matrix['blocks_sealing'] else ''))
    if matrix['unknown_layers']:
        lines.append(f"NOT CHECKED: {matrix['unknown_layers']}")
    return '\n'.join(lines)
