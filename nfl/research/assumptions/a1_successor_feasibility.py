"""Can the A1 successor question be measured in this repository yet?

A1_APPEARANCE_CERTAINTY is FALSIFIED: the cohort it called certain appears
93.13% of the time, 117 failures in 1702, Wilson [0.9182, 0.9423]. The
successor question is not "is it 1.0" -- that is answered -- but **what
conditions the 6.87%**, and the obvious candidate is the official injury
designation, which this repository began capturing on 2026-09-07.

THIS MODULE ANSWERS THE FEASIBILITY QUESTION BEFORE THE RESEARCH QUESTION.

An underpowered test that fails to reject looks exactly like a test that found
nothing, and this project's own rule is that failure to reject a null is not
evidence of adequacy. So the cohort is sized and the conditioning variable's
CONTRAST is counted first. If every member of the cohort carries the same
designation, the effect of designation is not estimable at any sample size,
and that is a fact about the data rather than a result about football.

It reads only captured bytes and writes one artifact. It fits nothing.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'a1-successor-feasibility-1'
OUT = _REPO / 'nfl/research/assumptions/A1_SUCCESSOR_FEASIBILITY.json'

PRIOR_SEASON_BLOB = 'nfl/vintage/pbp_2025.2f135887790a013f.csv.gz'
CURRENT_SEASON_BLOB = 'nfl/vintage/pbp_2026.b69f55a172965e16.csv.gz'
INJURY_GLOB = 'nfl/vintage/injuries.*.csv.gz'

#: Opportunity, exactly as A1's estimand defines it: carries + targets > 0.
OPPORTUNITY_COLUMNS = ('rusher_player_id', 'receiver_player_id')

CODE_OK = 'A1_SUCCESSOR_FEASIBILITY_MEASURED'
CODE_NO_CONTRAST = 'A1_SUCCESSOR_CONDITIONING_VARIABLE_HAS_NO_CONTRAST'


def _opportunity(path: pathlib.Path):
    """player -> weeks with opportunity; team -> weeks played; player -> team."""
    by_player = collections.defaultdict(set)
    team_weeks = collections.defaultdict(set)
    team_count = collections.defaultdict(collections.Counter)
    with gzip.open(path, 'rt', errors='replace') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            try:
                wk = int(r['week'])
            except (KeyError, TypeError, ValueError):
                continue
            po = (r.get('posteam') or '').strip()
            if po:
                team_weeks[po].add(wk)
            for col in OPPORTUNITY_COLUMNS:
                pid = (r.get(col) or '').strip()
                if pid:
                    by_player[pid].add(wk)
                    if po:
                        team_count[pid][po] += 1
    team = {p: c.most_common(1)[0][0] for p, c in team_count.items() if c}
    return by_player, team_weeks, team


def designations(week: int) -> tuple:
    """gsis_id -> report_status, from the NEWEST captured injury vintage.

    The newest vintage is used here because this is a FEASIBILITY count, not a
    forecast: it asks whether contrast exists at all. A measurement under the
    successor specification must instead read through a declared DAG edge at a
    lawful cut, and this function is deliberately not that.
    """
    fs = sorted(glob.glob(str(_REPO / INJURY_GLOB)))
    if not fs:
        return {}, None
    newest = fs[-1]
    out = {}
    with gzip.open(newest, 'rt', errors='replace') as fh:
        for r in csv.DictReader(fh):
            if str(r.get('week')) != str(week):
                continue
            pid = (r.get('gsis_id') or '').strip()
            if pid:
                out[pid] = ((r.get('report_status') or '').strip()
                            or 'LISTED_NO_STATUS')
    return out, pathlib.Path(newest).name


def measure(forecast_week: int = 2) -> Outcome:
    prior = _REPO / PRIOR_SEASON_BLOB
    cur = _REPO / CURRENT_SEASON_BLOB
    for p in (prior, cur):
        if not p.exists():
            return Outcome.blocked('A1_SUCCESSOR_BLOB_MISSING', f'{p} absent',
                                   cause=Cause.DATA)
    p_opp, p_team_weeks, p_team = _opportunity(prior)
    c_opp, c_team_weeks, _ = _opportunity(cur)

    # A1's cohort: prior-season appearance rate 1.0, and opportunity in every
    # current-season week so far.
    prior_weeks_needed = {t: len(w) for t, w in p_team_weeks.items()}
    weeks_so_far = sorted(w for w in
                          {wk for s in c_opp.values() for wk in s}
                          if w < forecast_week)
    cohort = []
    for pid, wks in p_opp.items():
        t = p_team.get(pid)
        if not t or not prior_weeks_needed.get(t):
            continue
        if len(wks) != prior_weeks_needed[t]:
            continue
        if not weeks_so_far:
            continue
        if all(w in c_opp.get(pid, set()) for w in weeks_so_far):
            cohort.append(pid)

    desig, blob = designations(forecast_week)
    counts = collections.Counter(desig.get(p, 'NOT_LISTED') for p in cohort)
    non_trivial = {k: v for k, v in counts.items()
                   if k not in ('NOT_LISTED', 'LISTED_NO_STATUS')}
    ev = {
        'spec_version': SPEC_VERSION,
        'measured_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'forecast_week': forecast_week,
        'prior_season_blob': PRIOR_SEASON_BLOB,
        'current_season_blob': CURRENT_SEASON_BLOB,
        'injury_vintage_read': blob,
        'n_injury_vintages_on_disk': len(
            sorted(glob.glob(str(_REPO / INJURY_GLOB)))),
        'current_season_weeks_available': sorted(
            {wk for s in c_opp.values() for wk in s}),
        'weeks_required_so_far': weeks_so_far,
        'cohort_size': len(cohort),
        'designation_counts_in_cohort': dict(counts),
        'n_with_a_non_trivial_designation': sum(non_trivial.values()),
        'non_trivial_designations': non_trivial,
        'outcome_week_captured': forecast_week in sorted(
            {wk for s in c_opp.values() for wk in s}),
    }
    if not ev['n_with_a_non_trivial_designation']:
        return Outcome.blocked(
            CODE_NO_CONTRAST,
            f'the A1 cohort at week {forecast_week} is {len(cohort)} player(s) '
            f'and NONE carries an Out, Doubtful or Questionable designation: '
            f'{dict(counts)}. The conditioning variable takes one effective '
            f'value across the whole cohort, so its effect is not estimable at '
            f'any sample size. This is a fact about the data, not a result '
            f'about football.',
            cause=Cause.DATA, **ev)
    return Outcome.ok(CODE_OK, value=ev,
                      detail=f'cohort {len(cohort)}, '
                             f'{ev["n_with_a_non_trivial_designation"]} with a '
                             f'non-trivial designation', **ev)


def main() -> int:
    o = measure()
    OUT.write_text(json.dumps(
        {'artifact': 'A1_SUCCESSOR_FEASIBILITY',
         'state': o.state.value, 'code': o.code, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items()}},
        indent=1, sort_keys=True, default=str) + '\n')
    print(f'{o.state.value}[{o.code}] {o.detail}')
    print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
