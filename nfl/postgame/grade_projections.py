"""Phase 2 and Phase 10: the frozen board against what happened, stat by stat.

NOT ONE MAE. The request is explicit and it is right: a single error number
says the model was wrong and nothing about WHERE. Every supported stat is
graded on its own, and every actual is placed in the predicted distribution as
well as differenced against the mean, because a projection that is 8 yards low
on a mean but inside p25-p75 is a different object from one that is 8 yards low
and outside p90.

WHAT ONE GAME CAN AND CANNOT DO. It can show a defect and generate a
hypothesis. It cannot estimate calibration: with roughly thirty players and
twelve stats the bucket counts are small, correlated within player, and
correlated within game. The nominal shares are carried so the LEDGER
accumulates toward them across slates -- not so tonight can be scored against
them.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.postgame import outcome as OC                                 # noqa: E402
from nfl.dfs.scoring import statline as SL                             # noqa: E402
from nfl.dfs.scoring import draftkings as DK                           # noqa: E402
from nfl.dfs.scoring import fanduel as FD                              # noqa: E402
from nfl.dfs.showdown import universe as UNI                           # noqa: E402

SPEC_VERSION = 'nfl-postgame-grade-projections-1'
PCT = (10, 25, 50, 75, 90, 95)

#: model stat -> outcome key. Explicit, because an implicit mapping is how a
#: passing stat gets graded against a rushing column.
MAP = {
    'pass_att': ('qb', 'att'), 'pass_cmp': ('qb', 'cmp'),
    'pass_yards': ('qb', 'pyds'), 'pass_td': ('qb', 'ptd'),
    'interceptions': ('qb', 'int'),
    'rush_att': ('rushing', 'carries'),
    'rush_yards': ('rushing_total', 'rushing_yards'),
    'rush_td': ('rushing', 'rushing_td'),
    'targets': ('receiving', 'targets'),
    'receptions': ('receiving', 'receptions'),
    'rec_yards': ('receiving', 'receiving_yards'),
    'rec_td': ('receiving', 'receiving_td'),
}


def _q(v):
    return {f'p{k}': float(np.percentile(v, k)) for k in PCT}


def grade(outcome_path=None) -> Outcome:
    got = OC.require(outcome_path)
    if got.state is not State.PASS:
        return got
    result = got.value
    intact = OC.assert_pregame_untouched()
    if intact.state is not State.PASS:
        return intact
    F = OC.PREGAME_FROZEN
    z = np.load(F / 'sealed_player_draws.npz')
    man = json.loads((F / 'sealed_player_draws_manifest.json').read_text())
    names = json.loads((F.parent / 'frozen_board_names.json').read_text())
    L = man['layers']
    ids = L['dk_scoring']['row_ids']
    n = int(np.asarray(z['dk_scoring__dk_points']).shape[1])
    # Identity by normalised name: DraftKings and the stat feed spell the
    # same man differently ('James Cook III' / 'James Cook').
    actual = {UNI.norm(k): v for k, v in result['players'].items()}
    # Team per board player, so an absent one can be told apart from an
    # uncovered one. A board player with no outcome row whose CLUB is in the
    # outcome recorded nothing, and zero is his measurement -- dropping him
    # would grade the model only on the players it got onto the field.
    uni = UNI.build()
    # From `players`, not `playable`: the officially-inactive rows are
    # excluded from the DFS pool and still belong in the GRADE. Skyler Bell
    # was hard-zeroed before kickoff and the board projected him anyway; the
    # model's number for him is exactly the kind that must not vanish.
    teams = ({UNI.norm(p['name']): p['team'] for p in uni.value['players']}
             if uni.state is State.PASS else {})
    rows, not_in_outcome, zeroed = [], [], []
    for gid in ids:
        nm = names.get(gid, gid)
        a = actual.get(UNI.norm(nm))
        if a is None:
            line, code = OC.resolve_absent(nm, teams.get(UNI.norm(nm)),
                                           result)
            if line is None:
                not_in_outcome.append({'player': nm, 'reason': code})
                continue
            a = {'team': teams.get(UNI.norm(nm)), 'position': None,
                 **line}
            zeroed.append(nm)
        sl = SL.assemble(gid, nm, L, z, n)
        per_stat = {}
        for stat, (layer, metric) in MAP.items():
            spec = L.get(layer)
            k = f'{layer}__{metric}'
            if not spec or gid not in (spec.get('row_ids') or []) \
                    or k not in z.files:
                per_stat[stat] = {'state': 'NOT_MODELLED'}
                continue
            v = np.asarray(z[k])[spec['row_ids'].index(gid)].astype(float)
            act = a.get(stat)
            q = _q(v)
            per_stat[stat] = {
                'state': 'GRADED' if act is not None else 'NOT_IN_OUTCOME',
                'actual': act, 'mean': float(v.mean()),
                'median': float(np.median(v)), **q,
                'abs_error': (abs(act - float(v.mean()))
                              if act is not None else None),
                'signed_error': (float(v.mean()) - act
                                 if act is not None else None),
                'percentile_of_actual': (float((v < act).mean())
                                         if act is not None else None),
                'bucket': OC.percentile_bucket(act, q),
            }
        # SCORING, both sites, from the same actual stat line.
        act_sl = SL.from_line(
            1, pass_yards=a.get('pass_yards') or 0, pass_td=a.get('pass_td') or 0,
            interceptions=a.get('interceptions') or 0,
            rush_yards=a.get('rush_yards') or 0, rush_td=a.get('rush_td') or 0,
            rec_yards=a.get('rec_yards') or 0,
            receptions=a.get('receptions') or 0, rec_td=a.get('rec_td') or 0)
        for site, fn, key in (('DRAFTKINGS', DK.score, 'dk'),
                              ('FANDUEL', FD.score, 'fd')):
            pred = (np.asarray(z['dk_scoring__dk_points'])[ids.index(gid)]
                    if key == 'dk'
                    else DK.score(sl) - 0.5 * sl.receptions)
            act_pts = float(fn(act_sl)[0])
            q = _q(pred)
            per_stat[f'{key}_points'] = {
                'state': 'GRADED', 'actual': act_pts,
                'mean': float(pred.mean()), 'median': float(np.median(pred)),
                **q, 'abs_error': abs(act_pts - float(pred.mean())),
                'signed_error': float(pred.mean()) - act_pts,
                'percentile_of_actual': float((pred < act_pts).mean()),
                'bucket': OC.percentile_bucket(act_pts, q), 'site': site}
        rows.append({'player': nm, 'team': a.get('team'),
                     'position': a.get('position'), 'stats': per_stat})
    # AGGREGATE BUCKETS, per stat and overall. Descriptive only.
    buckets = {}
    for r in rows:
        for stat, d in r['stats'].items():
            if d.get('state') != 'GRADED':
                continue
            b = buckets.setdefault(stat, {k: 0 for k in OC.BUCKETS})
            b[d['bucket']] = b.get(d['bucket'], 0) + 1
    overall = {k: sum(v.get(k, 0) for v in buckets.values())
               for k in OC.BUCKETS}
    total = sum(overall.values()) or 1
    return Outcome.ok(
        'PROJECTIONS_GRADED',
        value={'rows': rows, 'buckets_by_stat': buckets,
               'buckets_overall': overall,
               'overall_share': {k: overall[k] / total for k in OC.BUCKETS}},
        detail=f'{len(rows)} player(s) graded ({len(zeroed)} of them with no '
               f'recorded production), {len(not_in_outcome)} unscorable; '
               f'{total} stat-observation(s)',
        spec_version=SPEC_VERSION, n_players=len(rows),
        players_not_in_outcome=not_in_outcome,
        players_zero_by_absence=sorted(zeroed),
        zero_by_absence_is_a_measurement=(
            'his club is in the outcome, so the game was published and he '
            'recorded no carry, target or catch. Dropping him instead would '
            'be survivorship: it grades the model only on the players it got '
            'onto the field, and those are exactly the ones it got right.'),
        n_observations=total, nominal_shares=OC.NOMINAL,
        one_game_cannot_estimate_calibration=(
            'roughly thirty players and twelve stats give small bucket counts '
            'that are correlated within player and within game. These shares '
            'are descriptive. The ledger accumulates toward the nominal '
            'column across slates; tonight is not scored against it.'),
        is_measurement_not_development=True)


def main() -> int:
    o = grade()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    out = OC.DIR / 'GRADE_PROJECTIONS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         **o.value}, indent=1, sort_keys=True))
    c = AC.claim(out, schema=['rows', 'buckets_overall'], label=out.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
