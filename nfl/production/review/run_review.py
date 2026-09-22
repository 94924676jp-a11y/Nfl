"""Run the mandatory player review over one slate and write the artifact.

    python3.12 -m nfl.production.review.run_review \
        --game 2026_02_NYG_LA --season 2026 --week 2 \
        --cut 2026-09-21T23:05:00Z \
        --draws nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e \
        --inactives nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json

Every input is a path or a declared string. Nothing is fetched, nothing is
inferred from cwd, and a missing input refuses rather than defaults.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import slate_report as SR               # noqa: E402
from nfl.production.universe import player_universe as PU          # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from nfl.production.universe import usage_vintage as UV            # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--cut', required=True,
                    help='information cut, ISO-8601 with an explicit zone')
    ap.add_argument('--draws', default=None)
    ap.add_argument('--inactives', default=None,
                    help='INACTIVE_IDENTITY_RESOLUTION-shaped JSON')
    ap.add_argument('--slate-key', default=None)
    ap.add_argument('--deep-capacity', type=int, default=12)
    ap.add_argument('--root', default=None)
    a = ap.parse_args(argv)

    inactive_ids = set()
    if a.inactives:
        j = json.loads(pathlib.Path(a.inactives).read_text())
        inactive_ids = set(j.get('resolved', {}))

    emitted = set()
    if a.draws:
        po = SR.DOS.read_projection(a.draws)
        if po.state.name != 'PASS':
            print(f'{po.state.name} {po.code}: {po.detail}')
            return 2
        emitted = set(po.value['per_player'])

    uo = PU.build(a.season, a.week, a.game, a.cut,
                  emitted_ids=emitted, inactive_ids=inactive_ids)
    if uo.state.name != 'PASS':
        print(f'universe {uo.state.name} {uo.code}: {uo.detail}')
        return 2
    universe = uo.value['rows'] if isinstance(uo.value, dict) else uo.value

    us = UV.usage_season(a.season, a.cut, before_week=a.week)
    usage = us.value if us.state.name == 'PASS' else {}
    if us.state.name != 'PASS':
        print(f'NOTE usage panel {us.state.name} {us.code}: {us.detail}')

    ro = RS.assign(universe, season=a.season, week=a.week,
                   usage_rows=usage, inactive_ids=inactive_ids)
    roles = []
    if ro.state.name == 'PASS':
        roles = ro.value['rows'] if isinstance(ro.value, dict) else ro.value
    else:
        print(f'NOTE role_state {ro.state.name} {ro.code}: {ro.detail}')

    so = RS.load_snaps(a.season, a.week)
    snaps = so.value if so.state.name == 'PASS' else []

    out = SR.review_slate(
        slate_key=a.slate_key or a.game,
        universe_rows=universe, role_rows=roles, snap_rows=snaps,
        usage_rows=usage, draws_dir=a.draws, inactive_ids=inactive_ids,
        publishable_ids=emitted, information_cut=a.cut,
        deep_research_capacity=a.deep_capacity, root=a.root,
        notes=[f'usage panel: {us.state.name}/{us.code}',
               f'role_state: {ro.state.name}/{ro.code}',
               f'snap file: {so.state.name}/{so.code}'])
    print(f'{out.state.name} {out.code}: {out.detail}')
    if out.state.name == 'PASS':
        v = out.value
        print(json.dumps({'written': v['written'],
                          'coverage': v['report']['coverage'],
                          'uncertainty': v['report']['uncertainty'],
                          'audit': {k: v['report']['audit'].get(k) for k in
                                    ('n_conflicts', 'by_severity', 'by_code')},
                          'escalation': v['report']['escalation']['by_tier'],
                          'gate': [v['gate_state'], v['gate_code']]},
                         indent=1, default=str))
        return 0
    print(json.dumps(out.evidence, indent=1, default=str)[:3000])
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
