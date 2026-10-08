"""Which Showdown slate the finishing / shadow / board tools are working on.

These tools were written for ATL@NO and carried its file prefix, raw-capture directory and week as literals, so on
any other slate they would read ATL's files -- or, for the roster lookup, silently find none and treat that as "no
long snappers". The values now come from the environment, set once by nfl/tools/showdown_next_slate.sh. The
defaults ARE the ATL@NO values, so every existing ATL@NO invocation reads and writes exactly the same paths.
"""
from __future__ import annotations

import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]

TAG = os.environ.get('SHOWDOWN_TAG', 'ATL_NO_2026W4')
PREFIX = os.environ.get('SHOWDOWN_PREFIX', 'SHOWDOWN_' + TAG.split('_2026')[0])
RAW_DIR = pathlib.Path(os.environ.get('SHOWDOWN_RAW_DIR') or _REPO / 'nfl/dfs/salaries/raw' / f'showdown_{TAG.split("_2026")[0].lower()}_2026{TAG.split("_2026")[1]}')
WEEK = os.environ.get('SHOWDOWN_WEEK') or TAG.rsplit('W', 1)[-1]

# CONTESTS: id -> prize pool, entry fee, max entries per user. From SHOWDOWN_SLATE_CONFIG (the runner's slate.json,
# key "contests") when set; the default is ATL@NO's three contests as read from their DK names.
_ATL_CONTESTS = {'196285137': {'prize_pool': 100000, 'entry_fee': 0.50, 'max_entries': 150},
                 '196285160': {'prize_pool': 10000, 'entry_fee': 0.25, 'max_entries': 20},
                 '196285161': {'prize_pool': 5000, 'entry_fee': 0.10, 'max_entries': 2}}
if os.environ.get('SHOWDOWN_SLATE_CONFIG'):
    import json as _json
    CONTESTS = {str(k): v for k, v in _json.loads(pathlib.Path(os.environ['SHOWDOWN_SLATE_CONFIG']).read_text())['contests'].items()}
else:
    CONTESTS = _ATL_CONTESTS
#: the single contest with the most entries per user (the boards' "main" multi-entry view), and the 2-entry contest


def max_entries(c):
    """The declared per-user entry limit, else the declared lower bound (entries held) when DK does not state it."""
    return c['max_entries'] if c.get('max_entries') is not None else c.get('max_entries_lower_bound')


MAIN_CONTEST = max(CONTESTS, key=lambda c: (max_entries(CONTESTS[c]) or 0, c))
TWO_ENTRY = next((c for c in sorted(CONTESTS) if CONTESTS[c].get('max_entries') == 2), None)
