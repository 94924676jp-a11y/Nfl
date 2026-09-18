"""The prospective evaluation ledger, at slate granularity. Append-only.

WHAT THIS IS FOR. One game cannot estimate calibration, discrimination or a
hit rate. The only way those become measurable is that every slate is
REGISTERED BEFORE ITS OUTCOME IS KNOWN and then graded against that
registration, so the record accumulates and cannot be re-cut afterwards.

THE RULE THAT MAKES IT EVIDENCE. A block is written in two appends:

  AWAITING_OUTCOME  written while the result is unknown. It pins the forecast
                    identity, the sealed hashes and the scope -- what was
                    predicted, and how much of it. Nothing about the result.
  GRADED            written after an outcome artifact is verified. It may only
                    follow an AWAITING_OUTCOME block with the same block_id,
                    and it carries the hash of the grading artifacts.

Nothing on disk is ever rewritten. A correction is a further append, never an
edit, because a ledger you can edit is a ledger that tells you what you want.

THIS FILE IS NOT A PLACE TO PUT A GOOD NIGHT. A bad prospective result is
never deleted and never silently retuned after the fact.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402

SPEC_VERSION = 'nfl-prospective-evaluation-ledger-1'
LEDGER = _REPO / 'nfl/research/postgame/PROSPECTIVE_EVALUATION_LEDGER.jsonl'

AWAITING = 'AWAITING_OUTCOME'
GRADED = 'GRADED'
STATUSES = (AWAITING, GRADED)

FIELDS = ('spec_version', 'block_id', 'game_id', 'status', 'written_at_utc',
          'forecast_identity', 'sealed_inputs', 'scope', 'outcome', 'grades',
          'notes')


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load(path=None):
    p = pathlib.Path(path or LEDGER)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _append(block, path=None) -> Outcome:
    p = pathlib.Path(path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a') as fh:
        fh.write(json.dumps(block, sort_keys=True, default=str) + '\n')
    return Outcome.ok(
        'LEDGER_BLOCK_APPENDED', value=block,
        detail=f'{block["block_id"]} {block["status"]} appended to {p.name}',
        spec_version=SPEC_VERSION, path=str(p), n_blocks=len(load(p)))


def register(*, block_id, game_id, forecast_identity, sealed_inputs, scope,
             notes='', path=None) -> Outcome:
    """Write the AWAITING_OUTCOME block. Refused once an outcome is known."""
    rows = load(path)
    if any(r['block_id'] == block_id and r['status'] == AWAITING
           for r in rows):
        return Outcome.fail(
            'LEDGER_BLOCK_ALREADY_REGISTERED',
            f'{block_id} is already registered awaiting outcome. Registering '
            f'it again would let the pinned scope move after the fact.',
            cause=Cause.GOVERNANCE, block_id=block_id)
    return _append({
        'spec_version': SPEC_VERSION, 'block_id': block_id,
        'game_id': game_id, 'status': AWAITING, 'written_at_utc': _now(),
        'forecast_identity': forecast_identity,
        'sealed_inputs': sealed_inputs, 'scope': scope,
        'outcome': None, 'grades': None, 'notes': notes}, path)


def grade_block(*, block_id, outcome, grades, notes='', path=None) -> Outcome:
    """Write the GRADED block. Only ever after a registration."""
    rows = load(path)
    reg = [r for r in rows if r['block_id'] == block_id
           and r['status'] == AWAITING]
    if not reg:
        return Outcome.fail(
            'LEDGER_GRADE_WITHOUT_REGISTRATION',
            f'{block_id} was never registered awaiting outcome. A result '
            f'graded against a scope chosen after the result is not '
            f'prospective evidence.',
            cause=Cause.GOVERNANCE, block_id=block_id)
    if any(r['block_id'] == block_id and r['status'] == GRADED for r in rows):
        return Outcome.fail(
            'LEDGER_BLOCK_ALREADY_GRADED',
            f'{block_id} already carries a graded block. A correction is a '
            f'further append with its own block_id, never an edit.',
            cause=Cause.GOVERNANCE, block_id=block_id)
    r0 = reg[-1]
    return _append({
        'spec_version': SPEC_VERSION, 'block_id': block_id,
        'game_id': r0['game_id'], 'status': GRADED, 'written_at_utc': _now(),
        'forecast_identity': r0['forecast_identity'],
        'sealed_inputs': r0['sealed_inputs'], 'scope': r0['scope'],
        'outcome': outcome, 'grades': grades, 'notes': notes}, path)


def audit(path=None) -> Outcome:
    """Every block well formed; no graded block without its registration."""
    p = pathlib.Path(path or LEDGER)
    rows = load(p)
    bad = [i for i, r in enumerate(rows)
           if set(FIELDS) - set(r) or r.get('status') not in STATUSES]
    reg = {r['block_id'] for r in rows if r['status'] == AWAITING}
    orphan = sorted({r['block_id'] for r in rows if r['status'] == GRADED}
                    - reg)
    ev = {'spec_version': SPEC_VERSION, 'path': str(p), 'n_blocks': len(rows),
          'malformed_row_indexes': bad, 'graded_without_registration': orphan,
          'awaiting': sorted(reg - {r['block_id'] for r in rows
                                    if r['status'] == GRADED}),
          'append_only': True}
    if bad or orphan:
        return Outcome.fail(
            'LEDGER_MALFORMED',
            f'{len(bad)} malformed block(s), {len(orphan)} graded without a '
            f'registration', cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok('LEDGER_AUDIT_CLEAN', value=rows,
                      detail=f'{len(rows)} block(s), {len(ev["awaiting"])} '
                             f'awaiting outcome', **ev)


#: The DET @ BUF block. Registered with the result UNKNOWN to this repository:
#: on 2026-09-18 no authoritative outcome could be captured, so the scope below
#: was pinned before any number about the game reached it.
DET_BUF = dict(
    block_id='DET_BUF_2026W2',
    game_id='2026_02_DET_BUF',
    forecast_identity='c3probe_V1_CANDIDATE_R9_W1P_GSVUC/d709e67b82d5b01c',
    sealed_inputs={
        'board_dir': 'nfl/research/dfs/DET_BUF_2026W2/frozen',
        'market_board': ('nfl/research/market/DET_BUF_2026W2/'
                         'MAIN_LINE_BOARD.csv'),
        'market_snapshot_identity': ('hardrock:202609189BE34D3B@'
                                     '2026-09-17T21:45:02Z'),
        'forecast_sealed_at_utc': '2026-09-16T15:45:14Z',
        'kickoff_utc': '2026-09-18T00:15:00Z'},
    scope={
        'players_in_board': 29,
        'stats_per_player': 12,
        'supported_main_lines': 43,
        'main_lines_refused': 35,
        'portfolios': ['PORTFOLIO_CLAUDE_40.csv', 'PORTFOLIO_ALTERNATE_40.csv'],
        'graders': ['nfl/postgame/grade_projections.py',
                    'nfl/postgame/grade_props.py',
                    'nfl/postgame/grade_portfolios.py'],
        'declared_before_outcome': True},
    notes=('Registered 2026-09-18 with the outcome UNCAPTURED. nflverse still '
           'carried week 1 and every official host refused CONNECT; see '
           'POSTGAME_OUTCOME/CAPTURE_ATTEMPT.json and OUT-023. The GRADED '
           'block cannot be written until an outcome artifact verifies. One '
           'slate cannot estimate calibration -- this block exists so the '
           'record accumulates toward a sample that can.'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='prospective evaluation ledger')
    ap.add_argument('--register-det-buf', action='store_true')
    ap.add_argument('--audit', action='store_true')
    a = ap.parse_args(argv)
    rc = 0
    if a.register_det_buf:
        o = register(**DET_BUF)
        print(f'{o.state.value}[{o.code}] {o.detail}')
        rc |= 0 if o.state is State.PASS else 1
    if a.audit or a.register_det_buf:
        o = audit()
        print(f'{o.state.value}[{o.code}] {o.detail}')
        c = AC.claim(LEDGER, schema=['block_id'], label=LEDGER.name)
        print(f'{c.state.value}[{c.code}] {c.detail}')
        rc |= 0 if (o.state is State.PASS and c.state is State.PASS) else 1
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
