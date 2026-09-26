#!/usr/bin/env python3.12
"""Classify a board-refresh pass, and give each state its own exit code.

WHY THIS MODULE EXISTS. `nfl-product-board.yml` computed three genuinely
different outcomes in shell -- an unhandled exception, a governed refusal, and a
pass that never reached its summary -- printed a distinct message for each, and
then exited 1 for all three. The distinction was computed and discarded at the
exit code, so the Actions history cannot tell a system that is correctly
declining from one that is broken. Measured 2026-09-26: 1,116 runs, the most
recent 8 all red, every one of them a correct refusal of all 15 Week 3 games
with `feature_build: STAGE_DECLARED_UNIMPLEMENTED`.

That is this repository's own invariant broken one level up. "Missing is a state,
zero is an outcome" at the CI layer reads: A REFUSAL IS A RESULT. A CRASH IS A
DEFECT. They must not share an exit code.

The neutral code is 78, which is the convention `nfl-production-forecast.yml`
already uses for its authorization gate -- so this is consistency with existing
in-repo precedent, not a new idea.

FAIL CLOSED, and this is the whole design. Neutral is granted only when EVERY
refusal code in the log is declared debt AND the declaration is still present in
SYSTEM_STATE.json AND nothing raised AND the pass reached its summary line. One
unrecognised refusal code, one unparseable refusal line, or a missing
declaration and the pass is a FAILURE. Turning a red pass green is not the
purpose here and would hide the blocker; separating two states that were sharing
one code is.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

RAISED = 'BOARD_REFRESH_RAISED'
REFUSED_UNDECLARED = 'BOARD_REFRESH_REFUSED_UNDECLARED'
REFUSED_DECLARED_DEBT = 'BOARD_REFRESH_REFUSED_DECLARED_DEBT'
NO_SUMMARY = 'BOARD_REFRESH_WROTE_NO_SUMMARY'
CLEAN = 'BOARD_REFRESH_CLEAN'

FAILURE, NEUTRAL, OK = 1, 78, 0
EXIT = {RAISED: FAILURE, REFUSED_UNDECLARED: FAILURE, NO_SUMMARY: FAILURE,
        REFUSED_DECLARED_DEBT: NEUTRAL, CLEAN: OK}

# A refusal code may be treated as declared debt only while the repository still
# declares it. The value is the substring that must appear in SYSTEM_STATE.json;
# if the declaration is edited away, the code silently stops qualifying and the
# pass goes back to being a failure. That direction of failure is deliberate.
DECLARED_DEBT = {
    'STAGE_DECLARED_UNIMPLEMENTED': 'STAGE_DECLARED_UNIMPLEMENTED',
}

_TRACEBACK = 'Traceback (most recent call last)'
_REFUSAL = re.compile(r'^(\S+) +(?:REFUSED|ERROR) +(.*)$', re.M)
_SUMMARY = re.compile(r'^-- [0-9]+ board\(s\) written', re.M)
# `feature_build: STAGE_DECLARED_UNIMPLEMENTED` -> the code is the last token.
_CODE = re.compile(r'([A-Z][A-Z0-9_]{3,})\s*$')


def declared(state_path=None) -> set:
    """Which debt codes the repository currently declares."""
    p = pathlib.Path(state_path) if state_path else ROOT / 'SYSTEM_STATE.json'
    try:
        blob = p.read_text(errors='replace')
    except OSError:
        return set()
    return {code for code, needle in DECLARED_DEBT.items() if needle in blob}


def classify(log: str, *, state_path=None) -> dict:
    """The pass's state, the refusal codes seen, and why."""
    refusals = _REFUSAL.findall(log or '')
    codes, unparseable = [], []
    for game, detail in refusals:
        m = _CODE.search(detail.strip())
        (codes.append(m.group(1)) if m else unparseable.append(game))
    ok = declared(state_path)
    undeclared = sorted({c for c in codes if c not in ok})

    if _TRACEBACK in (log or ''):
        state, why = RAISED, 'an unhandled exception reached the top level'
    elif unparseable:
        state = REFUSED_UNDECLARED
        why = ('a refusal line carried no recognisable code, so it cannot be '
               f'matched against declared debt: {sorted(unparseable)}')
    elif undeclared:
        state = REFUSED_UNDECLARED
        why = f'refusal codes not declared as debt: {undeclared}'
    elif not _SUMMARY.search(log or ''):
        state = NO_SUMMARY
        why = 'the pass never printed its summary line, so it did not complete'
    elif codes:
        state = REFUSED_DECLARED_DEBT
        why = ('every refusal is declared debt, so the pass declined rather '
               'than guessing; this is the intended behaviour and not a '
               'failure')
    else:
        state, why = CLEAN, 'the pass completed with no refusal'
    return {'state': state, 'exit_code': EXIT[state], 'why': why,
            'n_refused': len(refusals), 'codes': sorted(set(codes)),
            'undeclared_codes': undeclared,
            'declared_debt_recognised': sorted(ok)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('usage: judge_board_pass.py <board.log>', file=sys.stderr)
        return FAILURE
    p = pathlib.Path(argv[0])
    # A missing or empty log is not a clean pass. Zeros and empties are errors.
    log = p.read_text(errors='replace') if p.exists() else ''
    out = classify(log)
    print(f"{out['state']}: {out['why']}")
    if out['codes']:
        print(f"  {out['n_refused']} refused, codes {out['codes']}")
    for line in _REFUSAL.findall(log)[:20]:
        print(f'  {line[0]} {line[1]}')
    if out['state'] == REFUSED_DECLARED_DEBT:
        print('::notice::Every refusal in this pass is declared debt. The job '
              'stops here by design. This is not a failure.')
    return out['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
