"""What the QB layer actually produces for the nine 1 PM ET games, and on what.

    python3.12 nfl/tools/qb_layer_study.py --write

WHY THIS IS SEPARATE FROM THE BOARD, AND WHAT IT IS NOT

The board pipeline refuses at `player_draws` because the `receiving` and
`rushing` layers are absent (see 2026-09-27_FEATURE_BUILD_BLOCKER.md). The QB
layer, by contrast, PASSES. So there is real QB model output for today's games
that no board carries.

**This output is an INTERMEDIATE QUANTITY, not a complete Week-3 projection**,
and the distinction is in the code rather than in taste:

  * `qb_slate` returns `draws` -- twelve metrics, each an (n_qb x m) array. It
    is a distribution, not a point forecast;
  * downstream, `apply_r2_level` RE-RUNS QB V1 at the level D1 and QB3 already
    own, apportioning the level from the team budget by largest remainder. So
    the level in this artifact is QB V1's own draw and is NOT the level the
    sealed board would carry;
  * the sealed `player_draws` contract declares the `qb` layer with metrics
    ('att','cmp','pyds','ptd','int'). Nothing here is sealed, because the run
    refuses before sealing.

Quote it as "the QB layer's pre-R2 draws", never as the model's projection.

IT CONTAINS NO 2026 INFORMATION, AND FOR A DIFFERENT REASON THAN Q9

`qb_v1.slate_prospective` refuses if the frame holds any row at or after the
forecast ordinal -- for 2026 week 3 that is 202603 -- so 2026 weeks 1 and 2
(202601, 202602) are PERMITTED. Measured: the frame spans 202001 to 202518 and
holds **zero** 2026 rows. The ceiling here is therefore DATA ABSENCE, not
policy, and the same ordinal 202518 that blocks `participation_prior`. If 2026
QB rows existed, this layer would consume them with no code change.

Q9's arm A is the opposite case: it excludes the forecast season BY DESIGN.
Two layers, both pre-2026, for two different reasons. Only one is fixable by
arriving data.

COLD START IS OFF, SO SOME DK QUARTERBACKS GET NOTHING

`include_cold_start=False`, and a quarterback with no pre-2026 history has no
row. Those are listed by name rather than dropped: if one of them starts today,
the layer has nothing for the position that matters most.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import football_engine as FE            # noqa: E402
from nfl.production import qb_v1 as QBV1                          # noqa: E402
from sportsplatform.governance.outcome import Outcome, State      # noqa: E402

SPEC_VERSION = 'qb-layer-study-1'
BASELINE = _REPO / 'nfl/dfs/salaries/DK_WEEK3_EARLY_BASELINE.json'
OUT_JSON = _REPO / 'nfl/dfs/salaries/DK_WEEK3_QB_LAYER.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/DK_WEEK3_QB_LAYER.md'
SEASON, WEEK, M, SEED = 2026, 3, 200, 20260908
#: The metrics the sealed player_draws contract declares for the qb layer.
CONTRACT_METRICS = ('att', 'cmp', 'pyds', 'ptd', 'int')
PCTL = (5, 25, 50, 75, 95)


def _frame_span():
    """The QB frame's ordinal span, measured rather than assumed."""
    from nfl.production import derived as D
    a = D.artifacts()
    if a.state is not State.PASS:
        return None, a
    p = str(_REPO / 'nfl/research/qb2')
    if p not in sys.path:
        sys.path.insert(0, p)
    import qb2_lib as Q
    rows = Q.load()
    ords = sorted({r['ord'] for r in rows})
    return {'n_rows': len(rows), 'min_ord': ords[0], 'max_ord': ords[-1],
            'n_2026_rows': sum(1 for r in rows if r['ord'] >= 202600),
            'forecast_ordinal': SEASON * 100 + WEEK,
            'guard': 'slate_prospective refuses if any ord >= forecast '
                     'ordinal, so 202601 and 202602 WOULD be permitted',
            'reading': ('the frame holds zero 2026 rows, so the layer is '
                        'pre-2026 by DATA ABSENCE and not by policy')}, None


def study():
    if not BASELINE.exists():
        return Outcome.fail('SLATE_BASELINE_ABSENT', f'{BASELINE} missing')
    base = json.loads(BASELINE.read_text())
    rows = base['slate']['pool_rows']
    qb_rows = [r for r in rows if r['dk_pos'] == 'QB']
    players = [{'gsis_id': r['gsis_id'], 'team': r['team']}
               for r in qb_rows if r.get('gsis_id')]
    if not players:
        return Outcome.fail('NO_IDENTIFIED_QB',
                            'no DK quarterback carries a canonical id')

    span, err = _frame_span()
    if err is not None:
        return err

    o = FE.qb_slate(SEASON, WEEK, players, m=M, seed=SEED)
    if o.state is not State.PASS:
        return Outcome.fail(
            'QB_LAYER_DID_NOT_EXECUTE',
            f'{o.state.name}[{o.code}]: {(o.detail or "")[:200]}',
            qb_frame=span)
    v = o.value
    draws = v['draws']
    got = {r.get('gsis_id'): i for i, r in enumerate(v['rows'])}

    by_dk = {}
    for r in qb_rows:
        gid = r.get('gsis_id')
        i = got.get(gid)
        rec = {'dk_id': r['dk_id'], 'name': r['dk_name'], 'team': r['team'],
               'opponent': r.get('opponent'), 'salary': r['salary'],
               'gsis_id': gid, 'has_qb_layer_row': i is not None}
        if i is None:
            rec['why_absent'] = (
                'no row in the QB frame: no pre-2026 history and '
                'include_cold_start is False. UNKNOWN, not zero.')
        else:
            for k, arr in draws.items():
                a = np.asarray(arr, float)[i]
                rec[k] = {'mean': round(float(a.mean()), 4),
                          'sd': round(float(a.std(ddof=1)), 4),
                          'pctl': {str(q): round(float(np.percentile(a, q)), 4)
                                   for q in PCTL},
                          'in_sealed_contract': k in CONTRACT_METRICS}
        by_dk[r['dk_id']] = rec

    absent = [x for x in by_dk.values() if not x['has_qb_layer_row']]

    # MULTI-QB OVER-PREDICTION, QUANTIFIED RATHER THAN CITED. The layer draws
    # every rostered quarterback as though he played, with no start-probability
    # weighting, so a club's attempts sum scales with how many quarterbacks DK
    # listed -- a property of the salary file, not of football.
    have = [x for x in by_dk.values() if x['has_qb_layer_row']]
    tsum = {}
    for r in have:
        tsum.setdefault(r['team'], []).append(r)
    team_sums = {}
    for tm, qs in tsum.items():
        sa = sum(q['att']['mean'] for q in qs)
        top = max(q['att']['mean'] for q in qs)
        team_sums[tm] = {
            'n_qb_with_a_row': len(qs),
            'sum_attempt_mean': round(sa, 1),
            'sum_dropback_mean': round(sum(q['db']['mean'] for q in qs), 1),
            'top_qb_share_of_sum': round(top / sa, 3) if sa else None}
    sums = [v['sum_attempt_mean'] for v in team_sums.values()]
    implausible = [
        {'team': r['team'], 'name': r['name'], 'salary': r['salary'],
         'pyds_mean': r['pyds']['mean'], 'pyds_p95': r['pyds']['pctl']['95']}
        for r in have if r['pyds']['pctl']['95'] > 500]
    return Outcome.ok(
        'QB_LAYER_STUDY_BUILT',
        value={
            'artifact': 'DK_WEEK3_QB_LAYER', 'spec_version': SPEC_VERSION,
            'season': SEASON, 'week': WEEK, 'm_draws': M, 'seed': SEED,
            'qb_v1_spec_version': QBV1.SPEC_VERSION,
            'qb_frame_sha256': (o.evidence or {}).get('qb_frame_sha256'),
            'qb_frame': span,
            'known_limitations': list(QBV1.KNOWN_LIMITATIONS),
            'n_dk_qb': len(qb_rows),
            'n_with_qb_layer_row': len(qb_rows) - len(absent),
            'n_without_qb_layer_row': len(absent),
            'metrics_produced': sorted(draws),
            'metrics_in_sealed_contract': list(CONTRACT_METRICS),
            'OUTPUT_IS_AN_INTERMEDIATE_NOT_A_PROJECTION': (
                'qb_slate returns draws, a distribution. Downstream '
                'apply_r2_level RE-RUNS QB V1 at the level D1 and QB3 own, '
                'apportioned from the team budget by largest remainder, so the '
                'level here is QB V1 own draw and NOT the level a sealed board '
                'would carry. Nothing here is sealed: the run refuses at '
                'player_draws before sealing. Quote as "the QB layer pre-R2 '
                'draws", never as the model projection.'),
            'CONTAINS_NO_2026_INFORMATION': (
                'The frame spans 202001 to 202518 and holds zero 2026 rows, '
                'while the guard would permit 202601 and 202602. So this is '
                'pre-2026 by DATA ABSENCE, not by policy -- unlike Q9 arm A, '
                'which excludes the forecast season by design. It cannot know '
                'anything about weeks 1 and 2 or about today. If 2026 QB rows '
                'existed the layer would consume them with no code change.'),
            'COLD_START_IS_OFF': (
                f'{len(absent)} of {len(qb_rows)} DK quarterbacks have no row. '
                'If one of them starts today the layer has nothing for the '
                'position that matters most. Listed by name, never dropped.'),
            'team_attempt_sums': team_sums,
            'mean_team_attempt_sum': round(sum(sums) / len(sums), 1),
            'READ_THIS_BEFORE_QUOTING_ANY_NUMBER': (
                'These are NOT per-player expectations. Every rostered '
                'quarterback is drawn as though he played, with no '
                'start-probability weighting, so each row reads only as "if '
                'this man played the whole game". Measured consequence: the '
                f'mean team attempt sum is {round(sum(sums)/len(sums),1)} '
                'against a plausible real team value of roughly 30-35, and it '
                'scales with how many quarterbacks DK listed rather than with '
                'football -- CIN lists four and sums to '
                f'{team_sums.get("CIN",{}).get("sum_attempt_mean")}, MIA lists '
                f'two and sums to '
                f'{team_sums.get("MIA",{}).get("sum_attempt_mean")}. This is '
                'the declared multi_qb_over_prediction limitation, quantified. '
                'It is also exactly what apply_r2_level repairs downstream by '
                'apportioning the level from the team dropback budget, which '
                'is why "pre-R2" is the whole story and not a pedantic note.'),
            'implausible_upper_tails': implausible,
            'IMPLAUSIBLE_TAIL_NOTE': (
                'Rows whose p95 passing yards exceed 500 are recorded rather '
                'than clipped. A 1,036-yard p95 on a fourth-string passer is '
                'the declared discrete_low_count_intervals limitation showing '
                'itself on a thin history; clipping it would hide the '
                'limitation instead of reporting it.'),
            'quarterbacks': by_dk,
        },
        n_dk_qb=len(qb_rows), n_rows=len(qb_rows) - len(absent))


def markdown(v):
    L, A = [], None
    A = L.append
    A('# Week-3 Early Only — the QB layer, and exactly what it consumed\n')
    A(f"Spec `{v['qb_v1_spec_version']}`, study `{v['spec_version']}`, "
      f"{v['m_draws']} draws, seed {v['seed']}. "
      f"QB frame sha256 `{v['qb_frame_sha256']}`.\n")
    A('## This is an intermediate quantity, not a projection\n')
    A(v['OUTPUT_IS_AN_INTERMEDIATE_NOT_A_PROJECTION'] + '\n')
    A('## It contains no 2026 information\n')
    A(v['CONTAINS_NO_2026_INFORMATION'] + '\n')
    f = v['qb_frame']
    A(f"Measured: {f['n_rows']} frame rows, ordinals **{f['min_ord']} → "
      f"{f['max_ord']}**, **{f['n_2026_rows']} rows from 2026**. Forecast "
      f"ordinal {f['forecast_ordinal']}.\n")
    A('## Read this before quoting any number\n')
    A(v['READ_THIS_BEFORE_QUOTING_ANY_NUMBER'] + '\n')
    A('| team | QB with a row | sum att mean | sum dropback mean | top QB share |')
    A('|---|---|---|---|---|')
    for tm, s in sorted(v['team_attempt_sums'].items()):
        sh = s.get('top_qb_share_of_sum')
        shtxt = "—" if sh is None else f"{100 * sh:.0f}%"
        A(f"| {tm} | {s['n_qb_with_a_row']} | "
          f"{s['sum_attempt_mean']} | "
          f"{s['sum_dropback_mean']} | {shtxt} |")
    A('')
    if v['implausible_upper_tails']:
        A('**Implausible upper tails, recorded not clipped.** '
          + v['IMPLAUSIBLE_TAIL_NOTE'] + '\n')
        for r in v['implausible_upper_tails']:
            A(f"- {r['team']} {r['name']} (${r['salary']}): mean "
              f"{r['pyds_mean']:.1f}, p95 **{r['pyds_p95']:.0f}** passing yards")
        A('')
    A('## Coverage\n')
    A(f"{v['n_with_qb_layer_row']} of {v['n_dk_qb']} DK quarterbacks have a "
      f"QB-layer row; **{v['n_without_qb_layer_row']} do not**. "
      + v['COLD_START_IS_OFF'] + '\n')
    A(f"Declared limitations: {', '.join(v['known_limitations'])}.\n")
    A(f"Metrics produced: `{'`, `'.join(v['metrics_produced'])}`. "
      f"Of these, the sealed contract declares "
      f"`{'`, `'.join(v['metrics_in_sealed_contract'])}`.\n")
    qbs = sorted(v['quarterbacks'].values(),
                 key=lambda r: (r['team'], -r['salary']))
    A('\n## Quarterbacks with a QB-layer row\n')
    A('Mean and 5th–95th percentile over the draws. Pre-R2 level, pre-2026.\n')
    A('| team | opp | player | $ | att | cmp | pass yds | pass TD | int |')
    A('|---|---|---|---|---|---|---|---|---|')
    for r in qbs:
        if not r['has_qb_layer_row']:
            continue
        def c(k):
            d = r[k]
            return (f"{d['mean']:.1f} "
                    f"[{d['pctl']['5']:.0f}–{d['pctl']['95']:.0f}]")
        A(f"| {r['team']} | {r['opponent']} | {r['name']} | {r['salary']} | "
          f"{c('att')} | {c('cmp')} | {c('pyds')} | {c('ptd')} | {c('int')} |")
    A('\n## Quarterbacks with NO QB-layer row — UNKNOWN, not zero\n')
    A('| team | player | $ | why |')
    A('|---|---|---|---|')
    for r in qbs:
        if r['has_qb_layer_row']:
            continue
        A(f"| {r['team']} | {r['name']} | {r['salary']} | {r['why_absent']} |")
    A('')
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args(argv)
    o = study()
    if o.state is not State.PASS:
        print(f'{o.state.name} {o.code}: {o.detail}')
        return 1
    v = o.value
    print(f"{v['n_with_qb_layer_row']} of {v['n_dk_qb']} DK QB with a row; "
          f"{v['n_without_qb_layer_row']} without. "
          f"frame {v['qb_frame']['min_ord']}-{v['qb_frame']['max_ord']}, "
          f"{v['qb_frame']['n_2026_rows']} rows from 2026")
    if a.write:
        OUT_JSON.write_text(json.dumps(v, indent=1) + '\n')
        OUT_MD.write_text(markdown(v))
        print(f'wrote {OUT_JSON.relative_to(_REPO)}')
        print(f'wrote {OUT_MD.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
