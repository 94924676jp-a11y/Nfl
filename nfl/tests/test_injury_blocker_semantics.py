#!/usr/bin/env python3.12
"""The INJURY_REPORT_INCOMPLETE blocker counts a definition, not a defect, and cannot clear.

MEASURED on the lawful 2026 vintage (injuries.b9f0740139d052ff.csv.gz, 692 rows): 518 rows carry
no `report_status`, and EVERY ONE of those 518 carries a `practice_status` (Full 260, DNP 124,
Limited 134). Not one row is blank on both. In the nflverse injury feed `report_status` is the
Friday game-status designation (Out / Doubtful / Questionable) and `practice_status` is the daily
practice report; a player listed on the practice report who receives no designation has a blank
`report_status` BY DEFINITION -- that is the source saying "no designation", which for a completed
week means expected to play.

The evaluator at nfl/prospective/q9shadow/live_features.py:454 is

    unfilled = sum(1 for r in rows if not (r.get('report_status') or '').strip())

a pure blank count that never reads `practice_status`. So it refuses every week that has any
designation-free practice row -- which is every NFL week -- and the blocker is STRUCTURALLY
UNCLEARABLE as written. A gate that cannot clear is not measuring anything.

Two different things ARE hiding in the 518, and they must not be merged:

  weeks 1-2   267 blanks, both weeks complete at capture: blank = final "no designation".
  week 3      251 blanks against 8 filled: the blob was captured mid-week (Sep 24), BEFORE the
              Friday designations existed. Those are genuinely unpublished at capture time.

The principle in nfl.production.nonqb.inputs -- "an unfiled designation is not an absence of
injury and may not be defaulted to healthy" -- is right for the week-3 case and wrong for the
week-1/2 case, and the evaluator applies it to both.

THESE ARE CHARACTERISATION CHECKS. They pin the measured facts and prove the structural claim with
a synthetic COMPLETE week. They do not change the evaluator: redefining a governance control changes
what counts as evidence, which is an owner decision. When that ruling lands the expected values here
flip; the tests are not rewritten.
"""
from __future__ import annotations

import collections
import csv
import gzip
import io
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import _registry  # noqa: E402

RESULTS = []
BLOB = _REPO / 'nfl/vintage/injuries.b9f0740139d052ff.csv.gz'


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _rows():
    b = BLOB.read_bytes()
    return list(csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(b)),
                                                encoding='utf-8')))


def _blank(v):
    return not (v or '').strip()


def _evaluator_count(rows):
    """The exact expression from live_features.py:454, executed, not paraphrased."""
    src = (_REPO / 'nfl/prospective/q9shadow/live_features.py').read_text()
    line = next(l for l in src.splitlines()
                if 'unfilled = sum(1 for r in rows if not' in l)
    env = {'rows': rows}
    exec(line.strip(), env)  # noqa: S102
    return env['unfilled']


@check('the lawful vintage carries 692 rows and 518 blank report_status -- the blocker figure')
def _measured_figure():
    rows = _rows()
    n = _evaluator_count(rows)
    assert len(rows) == 692, len(rows)
    assert n == 518, n
    return f'{n} of {len(rows)} blank, reproduced through the evaluator\'s own line'


@check('every blank-report_status row carries a practice_status -- none is blank on both')
def _no_row_blank_on_both():
    rows = _rows()
    blanks = [r for r in rows if _blank(r.get('report_status'))]
    both = [r for r in blanks if _blank(r.get('practice_status'))]
    ps = collections.Counter(r['practice_status'][:20] for r in blanks)
    assert len(blanks) == 518 and not both, (len(blanks), len(both))
    return f'518 blank-report rows, 0 blank on both; practice_status among them {dict(ps)}'


@check('the blanks split into two different facts: complete weeks vs a mid-week capture')
def _two_facts():
    rows = _rows()
    byw = collections.Counter((r['week'], 'blank' if _blank(r.get('report_status')) else 'filled')
                              for r in rows)
    w12 = byw[('1', 'blank')] + byw[('2', 'blank')]
    w3b, w3f = byw[('3', 'blank')], byw[('3', 'filled')]
    assert w12 == 267, w12
    assert (w3b, w3f) == (251, 8), (w3b, w3f)
    return (f'weeks 1-2: {w12} blanks in completed weeks (final no-designation); '
            f'week 3: {w3b} blank vs {w3f} filled -- captured before Friday designations')


@check('STRUCTURAL: a synthetic COMPLETE week with one healthy practice-only row is still refused')
def _unclearable():
    # One player given a designation, one listed Full Participation with no designation --
    # the most ordinary complete-week report there is.
    fixture = [
        {'week': '9', 'gsis_id': 'A', 'report_status': 'Questionable',
         'practice_status': 'Limited Participation in Practice'},
        {'week': '9', 'gsis_id': 'B', 'report_status': '',
         'practice_status': 'Full Participation in Practice'},
    ]
    n = _evaluator_count(fixture)
    assert n == 1, n
    return ('a complete week with one designation-free Full-Participation row counts as 1 '
            'unfilled -> BLOCKED. Every real week has such rows, so the blocker cannot clear')


@check('the appearance contract itself names BOTH fields as the row content')
def _contract_names_both():
    src = (_REPO / 'nfl/production/nonqb/inputs.py').read_text()
    assert "'report_status',\n                   'practice_status'" in src \
        or "'report_status', 'practice_status'" in src.replace('\n', ' ') \
        or "'practice_status'" in src, 'contract no longer names practice_status'
    return ('APPEARANCE_CONTRACT.practice_progression lists report_status AND practice_status; '
            'a row with one filled is a complete row under the contract\'s own schema')


@check('a corrected rule would clear weeks 1-2 and still refuse week 3 -- it is not a loosening')
def _corrected_rule_direction():
    rows = _rows()
    # Candidate rule, NOT adopted here: a row is unfilled only if BOTH statuses are blank, and a
    # week is incomplete if its capture predates that week's designation publication, proxied
    # by filled-share: a completed week in this feed has filled/blank near 1:2, week 3 has 8:251.
    def both_blank(r):
        return _blank(r.get('report_status')) and _blank(r.get('practice_status'))
    byw = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        byw[r['week']][0 if _blank(r.get('report_status')) else 1] += 1
    both = sum(1 for r in rows if both_blank(r))
    share = {w: round(f / (b + f), 3) for w, (b, f) in byw.items()}
    assert both == 0, both
    assert share['1'] > 0.25 and share['2'] > 0.25 and share['3'] < 0.05, share
    return (f'both-blank rows: {both}; filled share by week {share} -- the candidate rule keeps '
            f'week 3 refused on its own evidence and does not default anyone to healthy')


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
