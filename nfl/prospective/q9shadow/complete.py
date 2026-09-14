"""The COMPLETE paired shadow artifact: R8 and frozen Q9, one divergence point.

    python3.12 -m nfl.prospective.q9shadow.complete --season 2024

THE OWNER'S RULING, IMPLEMENTED RATHER THAN ARGUED WITH

Protocol section 2 is unchanged. A PARTIAL_PLAYER_COVERAGE artifact may be
scored diagnostically, counts toward no section-4 floor, and cannot support
promotion. A single-layer Q9 artifact is therefore not relabelled COMPLETE --
it is superseded by a paired artifact that is complete, or it stays partial and
says so.

    accepted production model   R8
    candidate                   frozen Q9
    same upstream inputs        one capture bundle, one set of hashes
    same appearance draws       drawn once, consumed by both arms
    same team-volume draws      drawn once, consumed by both arms
    only the target-allocation mechanism differs

WHICH LAYERS BELONG TO WHOM, AND THE GUARD THAT MAKES THE ANSWER COMPLETE

The nine required layers are NOT declared here. They come from
`nfl.research.completeness.LAYERS`, the module that already exists because a
twelve-game slate once reported "complete" while carrying only the
quarterback layer. Each of the nine is assigned to exactly one of:

  SHARED     Q9 does not touch it, so both arms must carry the SAME numbers.
             team volume, the three quarterback layers, and the carry
             allocation -- the accepted P4C system C, which Q9 leaves alone.
  ARM        downstream of target allocation, so the arms legitimately differ.
             targets, receptions, receiving yards, touchdown allocation.

`assert_partition_covers_required` refuses if the two sets do not exactly
cover the nine. A layer in neither would have no owner, and an unowned layer
is how "complete" starts meaning "complete apart from the bit nobody
assigned".

COMPLETENESS IS COMPUTED, NEVER ASSERTED. `completeness_value` runs the
governed `forecast_completeness` over the layer matrix and maps FULL to the
contract's COMPLETE and everything else to PARTIAL_PLAYER_COVERAGE. There is
no argument by which Q9 gets a different answer from any other forecast, and
the negative case is tested: drop one layer and COMPLETE must disappear.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State            # noqa: E402
from nfl.production.nonqb import frozen_priors as FP                    # noqa: E402
from nfl.production.nonqb import layers as PL                           # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                  # noqa: E402
from nfl.prospective.q9shadow import shadow as SH                       # noqa: E402
from nfl.research import completeness as CP                             # noqa: E402

SPEC_VERSION = 'q9-complete-paired-shadow-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
OUT = HERE / 'Q9_COMPLETE_SHADOW_PARITY.json'

# The single point at which the two arms are allowed to differ.
DIVERGENCE_POINT = 'receiving target allocation (nfl.research.q9.hurdle)'

# Q9 does not touch these, so both arms must carry identical numbers.
SHARED_LAYERS = {
    'team_volume': 'the team-volume layer is upstream of every allocation and '
                   'is drawn once; Q9 consumes its budget and does not change '
                   'it',
    'qb_attempts': 'the quarterback layer is a different allocation entirely',
    'qb_passing_yards': 'downstream of the QB layer, not of target allocation',
    'qb_td': 'downstream of the QB layer, not of target allocation',
    'carries': 'the accepted P4C carry allocation. Q9 changes TARGET '
               'allocation only, and the Q8 budget repair was REJECTED, so '
               'the carry path is unchanged',
}

# Downstream of target allocation, so the arms legitimately differ here.
ARM_LAYERS = {
    'targets': 'the divergence point itself',
    'receptions': 'drawn from each arm\'s own target draws',
    'receiving_yards': 'drawn from each arm\'s own receptions',
    'td_allocation': 'drawn from each arm\'s own receptions',
}

REQUIRED_LAYERS = CP.LAYER_NAMES
CONTRACT_COMPLETE = 'COMPLETE'
CONTRACT_PARTIAL = 'PARTIAL_PLAYER_COVERAGE'


def assert_partition_covers_required() -> Outcome:
    """SHARED and ARM must exactly cover the nine required layers."""
    shared, arm = set(SHARED_LAYERS), set(ARM_LAYERS)
    req = set(REQUIRED_LAYERS)
    both = sorted(shared & arm)
    unowned = sorted(req - shared - arm)
    undeclared = sorted((shared | arm) - req)
    if both or unowned or undeclared:
        return Outcome.fail(
            'Q9_LAYER_PARTITION_INCOMPLETE',
            f'the layer partition does not cover the required set exactly: '
            f'owned twice {both}, unowned {unowned}, not required '
            f'{undeclared}. An unowned layer is how "complete" comes to mean '
            f'"complete apart from the bit nobody assigned".',
            owned_twice=both, unowned=unowned, not_required=undeclared)
    return Outcome.ok(
        'Q9_LAYER_PARTITION_COVERS_REQUIRED',
        value={'shared': sorted(shared), 'arm': sorted(arm)},
        detail=f'{len(shared)} shared + {len(arm)} arm = '
               f'{len(req)} required layer(s)')


# ------------------------------------------------- the arm-side layer chain
def arm_layers(res, arm, season, ordinal=1, seed=CAND.SEED) -> Outcome:
    """Receptions, receiving yards and receiving TD from ONE arm's targets.

    The production layer functions are called; nothing is reimplemented, and
    each refuses on its own terms if a frozen prior is absent.
    """
    T = np.asarray(res['arms'][arm]['targets'], float)      # (draws, players)
    pids = list(res['players'])
    positions = [r['pos'] for r in res['rows']]
    m = T.shape[0]

    # THE RECEIVING CHAIN IS OPTIONAL HERE, AND THE REASON IS A GUARD WORKING.
    #
    # `frozen_priors.receiving_priors(Y)` refuses with
    # RECEIVING_FRAME_CARRIES_FORECAST_SEASON whenever the committed RC1 frame
    # holds a row from Y or later, because `pools()` would otherwise train on
    # the season being forecast. The frame runs through 2025, so the priors
    # are obtainable for 2026 and for NO historical slice -- measured:
    # 2026 PASS, 2025 FAIL, 2024 FAIL.
    #
    # So on a historical slice the arm chain stops at targets, and the
    # downstream layers are reported BLOCKED with that code rather than being
    # produced from a prior the guard refused. The layer matrix then reads
    # PARTIAL, truthfully. Live, where the priors ARE available, the same code
    # produces all four arm layers with no change.
    rp = FP.receiving_priors(season)
    tp = FP.td_priors(season, 'rec')
    if rp.state is not State.PASS or tp.state is not State.PASS:
        bad = rp if rp.state is not State.PASS else tp
        return Outcome.ok(
            'Q9_COMPLETE_ARM_LAYERS_TARGETS_ONLY',
            value={'targets': T.T,
                   'receptions': None, 'receiving_yards': None,
                   'receiving_td': None},
            detail=f'{arm}: targets only; the receiving chain is refused '
                   f'upstream by {bad.code}',
            arm=arm, n_players=len(pids), n_draws=m,
            receiving_chain_blocked_by=bad.code,
            receiving_chain_detail=(bad.detail or '')[:300])

    # The conversion layer wants a PASS upstream Outcome carrying the target
    # allocation. It is handed the arm's own targets and is told which arm, so
    # a mixed-up pair cannot go unnoticed in the evidence.
    tc = Outcome.ok('TARGETS_CARRIES_OK',
                    value={'share': None, 'other': None, 'mode': 'external',
                           'n_capped': 0},
                    test_only=True, arm=arm)
    conv = PL.receiving_conversion(tc, T.T, rp.value, pids, positions,
                                   ordinal, m=m, seed=seed)
    if conv.state is not State.PASS:
        return conv
    td = PL.td_layer(conv, T.T, dict(rp.value, **tp.value), pids, positions,
                     ordinal, m=m, seed=seed)
    if td.state is not State.PASS:
        return td
    return Outcome.ok(
        'Q9_COMPLETE_ARM_LAYERS_OK',
        value={'targets': T.T,
               'receptions': np.asarray(conv.value['receptions']),
               'receiving_yards': np.asarray(conv.value['rec_yards']),
               'receiving_td': np.asarray(td.value['rec_td'])},
        detail=f'{arm}: receptions, receiving yards and receiving TD chained '
               f'from this arm\'s own target draws',
        arm=arm, n_players=len(pids), n_draws=m,
        conversion_spec=conv.evidence.get('spec_version'),
        td_spec=td.evidence.get('spec_version'))


def _layer_state(arms_out, layer, blocked_by=None):
    """PASS only when a real draw matrix exists for the layer, in every arm.

    A layer that is absent names WHY it is absent. `BLOCKED_ARM_LAYER_ABSENT`
    with no cause is the shape of an absence read as a mere gap.
    """
    key = {'targets': 'targets', 'receptions': 'receptions',
           'receiving_yards': 'receiving_yards',
           'td_allocation': 'receiving_td'}[layer]
    for arm, v in arms_out.items():
        a = (v or {}).get(key)
        if a is None or np.asarray(a).size == 0:
            return f'BLOCKED:{blocked_by or "ARM_LAYER_ABSENT"}:{arm}'
    return 'PASS'


def matrix(arms_out, shared_states, blocked_by=None) -> dict:
    """The nine-layer matrix for the paired artifact. Computed, not declared."""
    out = {}
    for layer in REQUIRED_LAYERS:
        if layer in ARM_LAYERS:
            out[layer] = _layer_state(arms_out, layer, blocked_by)
        else:
            out[layer] = shared_states.get(layer, 'NOT_MODELED')
    return out


def completeness_value(mat) -> tuple:
    """(contract value, governed verdict). The governed verdict decides."""
    verdict = CP.forecast_completeness(mat)
    return ((CONTRACT_COMPLETE if verdict == 'FULL' else CONTRACT_PARTIAL),
            verdict)


def assert_single_divergence(arms_out, shared_draws=None) -> Outcome:
    """Shared layers identical between arms; arm layers actually differing.

    BOTH HALVES MATTER. If a shared layer differed the claim "only the target
    allocation differs" would be false. If an arm layer did NOT differ, the
    candidate would be doing nothing and the comparison would be measuring
    Monte Carlo noise.
    """
    names = sorted(arms_out)
    if len(names) != 2:
        return Outcome.fail('Q9_COMPLETE_NOT_A_PAIR',
                            f'{len(names)} arm(s): {names}')
    a, b = arms_out[names[0]], arms_out[names[1]]
    same, differ = [], []
    for key in ('targets', 'receptions', 'receiving_yards', 'receiving_td'):
        # A LAYER THAT WAS NOT PRODUCED IS SKIPPED, NOT COMPARED. Two Nones
        # compare equal, and comparing them would report "this arm layer is
        # identical" -- a refusal caused by a layer that does not exist.
        if a.get(key) is None or b.get(key) is None:
            continue
        (same if np.array_equal(np.asarray(a[key]), np.asarray(b[key]))
         else differ).append(key)
    problems = {}
    if same:
        problems['arm_layers_identical'] = same
    for label, arr in (shared_draws or {}).items():
        if not np.array_equal(np.asarray(arr[names[0]]),
                              np.asarray(arr[names[1]])):
            problems.setdefault('shared_upstream_differs', []).append(label)
    if problems:
        return Outcome.fail(
            'Q9_COMPLETE_DIVERGENCE_NOT_SINGLE',
            f'the pair does not differ in exactly one place: {problems}. '
            f'An identical arm layer means the candidate did nothing; a '
            f'differing shared input means the arms are not comparable.',
            **problems)
    return Outcome.ok(
        'Q9_COMPLETE_SINGLE_DIVERGENCE', value=DIVERGENCE_POINT,
        detail=f'{len(differ)} arm layer(s) differ ({differ}); '
               f'{len(shared_draws or {})} shared upstream input(s) identical',
        arm_layers_differing=differ,
        shared_upstream_identical=sorted(shared_draws or {}))


# ----------------------------------------------------------------- the run
def run(season=2024, n_team_games=4, n_draws=200, seed=CAND.SEED):
    part = assert_partition_covers_required()
    fr = SH.feature_rows(SH.HISTORICAL_FRAME, season=season)
    if fr.state is not State.PASS:
        return {'status': f'{fr.state.value}[{fr.code}]', 'detail': fr.detail,
                'partition': f'{part.state.value}[{part.code}]'}
    from nfl.research.q7 import panel as Q7P
    from nfl.research.q8 import audit as AUD
    q7 = Q7P.load_recv()
    rows, _ = AUD.attach_receiving(fr.value, q7)
    fit = SH.fit_for(rows, season, q7)
    if fit.state is not State.PASS:
        return {'status': f'{fit.state.value}[{fit.code}]',
                'detail': fit.detail}
    p_r8 = AUD.load_p_r8()
    groups = collections.defaultdict(list)
    for r in rows:
        if r['s'] == season:
            groups[(r['s'], r['w'], r['t'])].append(r)

    # THE SHARED LAYERS THIS PATH DOES NOT RUN, EACH NAMED.
    #
    # Not "missing": each has a declared owner elsewhere in production and a
    # stated reason it is absent from a research-slice paired build. The
    # honest consequence is that the artifact is PARTIAL today, and that is
    # what is reported -- not a relabel.
    shared_states = {
        'team_volume': 'NOT_MODELED_IN_PAIRED_RESEARCH_SLICE',
        'qb_attempts': 'NOT_MODELED_IN_PAIRED_RESEARCH_SLICE',
        'qb_passing_yards': 'NOT_MODELED_IN_PAIRED_RESEARCH_SLICE',
        'qb_td': 'NOT_MODELED_IN_PAIRED_RESEARCH_SLICE',
        'carries': 'NOT_MODELED_IN_PAIRED_RESEARCH_SLICE',
    }

    built, problems = [], []
    for gkey in sorted(groups)[:n_team_games]:
        g = groups[gkey]
        game_id = f'{gkey[0]}_{gkey[1]:02d}_{gkey[2]}'
        p_appear = {r['pid']: float(p_r8.get(
            (r['s'], r['w'], r['t'], r['pid']), 0.0)) for r in g}
        res = SH.forecast_team_game(g, fit.value, p_appear, game_id, seed,
                                    n_draws)
        if res.state is not State.PASS:
            problems.append({'game_id': game_id, 'state': res.state.value,
                             'code': res.code})
            continue
        arms_out, failed, chain_block = {}, None, None
        for arm in CAND.ARMS:
            al = arm_layers(res.value, arm, season, gkey[1], seed)
            if al.state is not State.PASS:
                failed = {'game_id': game_id, 'arm': arm,
                          'state': al.state.value, 'code': al.code,
                          'detail': (al.detail or '')[:200]}
                break
            arms_out[arm] = al.value
            chain_block = (chain_block
                           or al.evidence.get('receiving_chain_blocked_by'))
        if failed:
            problems.append(failed)
            continue
        shared = {'appearance_draws': {a: res.value['appearance']
                                       for a in CAND.ARMS},
                  'team_budget_draws': {a: res.value['budget']
                                        for a in CAND.ARMS},
                  'p_hurdle': {a: res.value['p_hurdle'] for a in CAND.ARMS}}
        div = assert_single_divergence(arms_out, shared)
        mat = matrix(arms_out, shared_states, chain_block)
        value, verdict = completeness_value(mat)
        built.append({
            'game_id': game_id, 'team': gkey[2], 'n_players': len(g),
            'n_draws': n_draws,
            'layer_matrix': mat,
            'governed_verdict': verdict,
            'contract_completeness': value,
            'single_divergence': f'{div.state.value}[{div.code}]',
            'arm_layers_differing': div.evidence.get('arm_layers_differing'),
            'shared_upstream_identical':
                div.evidence.get('shared_upstream_identical'),
            'mean_targets': {a: round(float(np.asarray(
                arms_out[a]['targets']).mean()), 5) for a in CAND.ARMS},
            'receiving_chain_blocked_by': chain_block,
            'mean_receptions': ({a: round(float(np.asarray(
                arms_out[a]['receptions']).mean()), 5) for a in CAND.ARMS}
                if not chain_block else None),
            'mean_receiving_yards': ({a: round(float(np.asarray(
                arms_out[a]['receiving_yards']).mean()), 4)
                for a in CAND.ARMS} if not chain_block else None),
        })

    # THE NEGATIVE CASE. A gate that never refuses is not a gate: a synthetic
    # all-PASS matrix must read COMPLETE, and dropping any ONE layer must take
    # it away. Both directions, because only one of them is the failure mode.
    full = {k: 'PASS' for k in REQUIRED_LAYERS}
    neg = {}
    for k in REQUIRED_LAYERS:
        broken = dict(full, **{k: 'BLOCKED_TEST'})
        neg[k] = completeness_value(broken)[0]
    gate_ok = (completeness_value(full)[0] == CONTRACT_COMPLETE
               and all(v == CONTRACT_PARTIAL for v in neg.values()))

    values = {b['contract_completeness'] for b in built}
    return {
        'artifact': 'NFL_Q9_COMPLETE_SHADOW_PARITY',
        'spec_version': SPEC_VERSION,
        'candidate': CAND.CANDIDATE_NAME,
        'promoted': False, 'shadow_only': True,
        'season': season, 'n_team_games_built': len(built),
        'n_draws': n_draws,

        'owner_ruling_implemented': {
            'protocol_section_2': 'UNCHANGED',
            'partial_artifacts': 'scored diagnostically; no section-4 credit; '
                                 'cannot support promotion',
            'relabelling': 'REFUSED -- a single-layer artifact is not called '
                           'COMPLETE',
            'route': 'a paired R8-vs-Q9 artifact that is complete, or a '
                     'truthful partial state',
        },

        'required_layers': list(REQUIRED_LAYERS),
        'required_layers_source': 'nfl.research.completeness.LAYERS',
        'layer_partition': {
            'shared': SHARED_LAYERS, 'arm': ARM_LAYERS,
            'check': f'{part.state.value}[{part.code}]',
            'detail': part.detail,
        },
        'divergence_point': DIVERGENCE_POINT,

        'completeness_gate': {
            'full_matrix_reads': completeness_value(full)[0],
            'one_layer_dropped_reads': neg,
            'gate_is_not_vacuous': bool(gate_ok),
            'note': 'a synthetic all-PASS matrix reads COMPLETE and dropping '
                    'any single required layer takes it away. Both directions '
                    'are checked because only one of them is the failure '
                    'mode.',
        },

        'shared_layers_not_run_here': shared_states,
        'arm_chain_blocker': {
            'code': sorted({b['receiving_chain_blocked_by'] for b in built
                            if b.get('receiving_chain_blocked_by')}) or None,
            'measured_priors_availability': {
                '2026': 'PASS', '2025': 'FAIL', '2024': 'FAIL'},
            'why': ('frozen_priors.receiving_priors refuses whenever the '
                    'committed RC1 frame holds a row from the forecast season '
                    'or later, because pools() would train on the season '
                    'being forecast. The frame runs through 2025, so the '
                    'priors exist for 2026 and for no historical slice. That '
                    'is a leakage guard working, and it is the reason the '
                    'downstream receiving layers are BLOCKED here rather '
                    'than produced from a refused prior.'),
            'consequence': ('the arm chain is demonstrable on the LIVE season '
                            'and not on a historical one. The same code '
                            'produces all four arm layers there with no '
                            'change.'),
        },
        'team_games': built,
        'problems': problems,

        'contract_completeness_today': (sorted(values)[0] if len(values) == 1
                                        else sorted(values)),
        'is_eligible_forecast_under_section_2': bool(
            values == {CONTRACT_COMPLETE}),
        'status': ('PAIRED_BUILD_OK' if built and all(
            b['single_divergence'].startswith('PASS') for b in built)
            else 'PAIRED_BUILD_FAILED' if built else 'NOTHING_BUILT'),
        'what_is_still_needed_for_COMPLETE': {
            'layers': sorted(shared_states),
            'owner': 'the production forecast path (nfl/production/'
                     'run_forecast.py) already produces team_volume and the '
                     'three QB layers on the live slate; `carries` needs the '
                     'non-QB chain, which is blocked at appearance by '
                     'INJURY_REPORT_INCOMPLETE',
            'composition': 'the complete artifact composes a production '
                           'forecast (shared layers) with the two '
                           'target-allocation arms (arm layers) on one set of '
                           'upstream draws. Nothing about that composition is '
                           'blocked by Q9',
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=2024)
    ap.add_argument('--team-games', type=int, default=4)
    ap.add_argument('--draws', type=int, default=200)
    a = ap.parse_args(argv)
    out = run(a.season, a.team_games, a.draws)
    OUT.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(f"status              : {out['status']}")
    print(f"partition           : "
          f"{out.get('layer_partition', {}).get('check')}")
    print(f"team-games built    : {out.get('n_team_games_built')}")
    print(f"completeness today  : {out.get('contract_completeness_today')}")
    print(f"eligible under S2   : "
          f"{out.get('is_eligible_forecast_under_section_2')}")
    print(f"gate not vacuous    : "
          f"{out.get('completeness_gate', {}).get('gate_is_not_vacuous')}")
    for b in (out.get('team_games') or [])[:3]:
        print(f"  {b['game_id']}/{b['team']}: {b['governed_verdict']} "
              f"{b['single_divergence']} differing="
              f"{b['arm_layers_differing']}")
    for p in (out.get('problems') or [])[:3]:
        print(f"  problem: {p}")
    print(f"written             : {OUT}")
    return 0 if out['status'] == 'PAIRED_BUILD_OK' else 1


if __name__ == '__main__':
    sys.exit(main())
