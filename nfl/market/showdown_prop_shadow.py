#!/usr/bin/env python3.12
"""Any-slate Hard Rock player-prop comparison: DOWNSTREAM, SHADOW / NOT_VALIDATED. Never an input upstream.

    python3.12 nfl/market/showdown_prop_shadow.py seal    --scenario-dir SD --out-dir OUT --slate KC_JAX --kickoff ISO
    python3.12 nfl/market/showdown_prop_shadow.py compare --out-dir OUT --slate KC_JAX BOARD.csv
    python3.12 nfl/market/showdown_prop_shadow.py grade   --out-dir OUT --slate KC_JAX ACTUALS.json

The ATL@NO module (nfl/market/atl_no_prop_shadow.py) with its slate constants set from arguments; the logic, the
validation labels and the ordering rule (nfl/market/price_history.comparable: sealed first, price captured after the
seal and before kickoff, anything else refused by name) are that module's, unchanged.

ADDITIONS over the ATL@NO module (2026-10-07):
  * a seal at or after kickoff is refused (PROP_SEAL_AFTER_KICKOFF): a forecast sealed once the game has started could
    have seen it;
  * CAPTURE CONTRACT. A board is compared only with a sidecar BOARD.csv.CAPTURE.json naming book (Hard Rock Bet only),
    jurisdiction, product, the settlement-rules version or source it was captured under, capture time, who captured it,
    and the board's sha256. Missing or mismatched -> CAPTURE_CONTRACT_INCOMPLETE / BOARD_HASH_MISMATCH. A board that
    is not Hard Rock is refused (BOOK_NOT_HARD_ROCK). The settlement rules are recorded, never assumed;
  * FOUR SETTLEMENT STATES. `settle` grades every ledger row as WIN_OVER / WIN_UNDER / PUSH (actual exactly on an
    integer line) / VOID_NO_ACTION (the player did not participate, as the captured settlement rules define it) or
    UNRESOLVED (no official actual yet). A missing actual is never a loss and never a win.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.market import atl_no_prop_shadow as A  # noqa: E402


def configure(out_dir, slate, scenario_dir=None, kickoff=None):
    A.OUT = pathlib.Path(out_dir).resolve()
    A.SLATE_NAME = slate
    if scenario_dir:
        A.SD = pathlib.Path(scenario_dir).resolve()
    if kickoff:
        A.KICKOFF_UTC = dt.datetime.fromisoformat(kickoff.replace('Z', '+00:00')).isoformat()


def seal(scenario_dir, out_dir, slate, kickoff, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    ko = dt.datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
    if now >= ko:
        raise SystemExit(f'PROP_SEAL_AFTER_KICKOFF now {now.isoformat()} kickoff {ko.isoformat()}')
    if not any(pathlib.Path(scenario_dir).glob('SHOWDOWN_*_WORLDS.npz')):
        raise SystemExit(f'PROP_SEAL_NO_WORLDS {scenario_dir}')
    configure(out_dir, slate, scenario_dir, kickoff)
    return A.seal()


CONTRACT_FIELDS = ('book', 'jurisdiction', 'product', 'settlement_rules', 'captured_at_utc', 'captured_by',
                   'board_sha256')


def capture_contract(board_csv):
    """The capture sidecar, verified against the board bytes. Refuses by name; never fills a field."""
    b = pathlib.Path(board_csv)
    side = b.with_name(b.name + '.CAPTURE.json')
    if not side.exists():
        raise SystemExit(f'CAPTURE_CONTRACT_INCOMPLETE no sidecar {side.name}')
    c = json.loads(side.read_text())
    miss = [k for k in CONTRACT_FIELDS if not c.get(k)]
    if miss:
        raise SystemExit(f'CAPTURE_CONTRACT_INCOMPLETE missing {miss}')
    if 'hard rock' not in str(c['book']).lower():
        raise SystemExit(f'BOOK_NOT_HARD_ROCK {c["book"]!r} (Hard Rock Bet only)')
    if c['board_sha256'] != hashlib.sha256(b.read_bytes()).hexdigest():
        raise SystemExit('BOARD_HASH_MISMATCH the sidecar describes different bytes')
    return c


def settle_row(row, actual):
    """One ledger row -> settlement state. `actual` is {value, participated} from the official box score, or None."""
    if actual is None or actual.get('value') is None and actual.get('participated') is not False:
        return 'UNRESOLVED'
    if actual.get('participated') is False:
        return 'VOID_NO_ACTION'
    y, line = float(actual['value']), float(row['line'])
    if y == line:
        return 'PUSH'
    return 'WIN_OVER' if y > line else 'WIN_UNDER'


def settle(out_dir, actuals_json):
    """Settle every ledger row into the four states (plus UNRESOLVED). Appends; never overwrites."""
    out = pathlib.Path(out_dir)
    act = json.loads(pathlib.Path(actuals_json).read_text())
    led = [json.loads(l) for l in (out / 'PROP_GRADING_LEDGER.jsonl').read_text().splitlines() if l.strip()]
    if not led:
        raise SystemExit('LEDGER_EMPTY')
    rows, counts = [], {}
    for r in led:
        a = (act.get(f"{r['player']}|{r['team']}") or {})
        a = None if not a else {'value': a.get(r['our_variable']), 'participated': a.get('participated')}
        st = settle_row(r, a)
        counts[st] = counts.get(st, 0) + 1
        rows.append({**r, 'settlement': st, 'actual': None if a is None else a.get('value')})
    with (out / 'PROP_SETTLEMENT_LEDGER.jsonl').open('a') as fh:
        for x in rows:
            fh.write(json.dumps(x) + '\n')
    return {'settled': counts, 'NOTE': 'PUSH and VOID_NO_ACTION are not graded as hits or misses'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('seal', 'compare', 'grade', 'settle'))
    ap.add_argument('path', nargs='?')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--slate', required=True)
    ap.add_argument('--scenario-dir')
    ap.add_argument('--kickoff')
    a = ap.parse_args()
    if a.cmd == 'seal':
        if not (a.scenario_dir and a.kickoff):
            raise SystemExit('seal needs --scenario-dir and --kickoff')
        p, b = seal(a.scenario_dir, a.out_dir, a.slate, a.kickoff)
        print(p, b['seal_sha256'], b['written_at'], len(b['players']), 'players')
    else:
        if not a.path:
            raise SystemExit(f'{a.cmd} needs a file')
        configure(a.out_dir, a.slate)
        if a.cmd == 'settle':
            print(settle(a.out_dir, a.path))
            sys.exit(0)
        if a.cmd == 'compare':
            capture_contract(a.path)
        r = A.compare(a.path) if a.cmd == 'compare' else A.grade(a.path)
        print(r if a.cmd == 'grade' else f"{r['n_compared']} compared, {r['n_refused']} refused")
