#!/usr/bin/env python3.12
"""Any-slate Hard Rock player-prop comparison: DOWNSTREAM, SHADOW / NOT_VALIDATED. Never an input upstream.

    python3.12 nfl/market/showdown_prop_shadow.py seal    --scenario-dir SD --out-dir OUT --slate KC_JAX --kickoff ISO
    python3.12 nfl/market/showdown_prop_shadow.py compare --out-dir OUT --slate KC_JAX BOARD.csv
    python3.12 nfl/market/showdown_prop_shadow.py grade   --out-dir OUT --slate KC_JAX ACTUALS.json

The ATL@NO module (nfl/market/atl_no_prop_shadow.py) with its slate constants set from arguments; the logic, the
validation labels and the ordering rule (nfl/market/price_history.comparable: sealed first, price captured after the
seal and before kickoff, anything else refused by name) are that module's, unchanged.

ONE ADDITION: a seal at or after kickoff is refused (PROP_SEAL_AFTER_KICKOFF). A forecast sealed once the game has
started could have seen it.
"""
from __future__ import annotations

import argparse
import datetime as dt
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


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('seal', 'compare', 'grade'))
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
        r = A.compare(a.path) if a.cmd == 'compare' else A.grade(a.path)
        print(r if a.cmd == 'grade' else f"{r['n_compared']} compared, {r['n_refused']} refused")
