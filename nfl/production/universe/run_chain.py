"""Run the football chain for one game and let the machine state the verdict.

WHY A RUNNER AND NOT A SCRIPT PER SLATE

Every layer already refuses in its own voice. What was missing was the single
place where those refusals become ONE answer, so that a delivery cannot be
written around them. This module runs universe -> role -> participation ->
allocation, converts each layer's Outcome into a gate result without
interpretation, and hands the set to `verdict.assess`. The first line of any
delivery is then generated, not composed.

A GATE NOBODY RAN IS NOT A GATE THAT PASSED. Layers that have not been built
yet -- the prop calibrator, the DFS field model -- are left ABSENT from the
results dict on purpose. `verdict.assess` resolves an absent required gate to
NOT_EVALUATED, which blocks. That is the correct state for work that does not
exist, and filling it with anything else would be the single most expensive
lie this system could tell itself.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import verdict as V                            # noqa: E402
from nfl.production.universe import allocation as AL               # noqa: E402
from nfl.production.universe import chronology as CH                # noqa: E402
from nfl.production.universe import coverage as CV                 # noqa: E402
from nfl.production.universe import participation as PA            # noqa: E402
from nfl.production.universe import player_universe as PU          # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from nfl.production.universe import support_state as S             # noqa: E402
from nfl.production.universe import usage_vintage as UV            # noqa: E402
from sportsplatform.governance.outcome import Outcome, State       # noqa: E402

SPEC_VERSION = 'nfl-football-chain-1'


def _iso(s):
    try:
        t = _dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def run(season: int, week: int, game_id: str, cut: str, *,
        inactive_ids=None, max_unresolved_fraction=None) -> dict:
    """Every layer, in order, with each one's outcome kept verbatim."""
    started = _dt.datetime.now(_dt.timezone.utc)
    out = {'spec_version': SPEC_VERSION, 'game_id': game_id, 'season': season,
           'week': week, 'information_cut': cut,
           'run_started_at': started.isoformat(),
           'ran_at': started.isoformat(),
           'inactives_supplied': bool(inactive_ids),
           'caller_proposed_max_unresolved_fraction': max_unresolved_fraction,
           'layers': {}, 'gates': {}}
    L, G = out['layers'], out['gates']

    # CHRONOLOGY FIRST, AND IT CAN STOP THE RUN. A cut the run has not
    # reached is not a tighter cut, it is a fabricated one, and every layer
    # below would inherit it. The 2026-09-21 artifact claimed a cut
    # fifty-one minutes after the run that wrote it and nothing objected,
    # because nothing compared the two fields.
    pre = CH.certify(cut, out['run_started_at'], sources=None)
    L['chronology_precheck'] = {'code': pre.code, 'state': pre.state.name}
    if pre.state is not State.PASS:
        G['CHRONOLOGY_CERTIFIED'] = V.from_outcome(pre)
        L['chronology_precheck']['violations'] = (pre.evidence or {}).get(
            'violations')
        for scope in ('football', 'prop_product', 'dfs_product'):
            out.setdefault('verdicts', {})[scope] = V.assess(G, scope=scope)
        out['verdict'] = out['verdicts']['football']
        return out

    uni = PU.build(season, week, game_id, cut, inactive_ids=inactive_ids)
    L['universe'] = {'code': uni.code, 'state': uni.state.name}
    if uni.state is not State.PASS:
        G['ROSTER_IDENTITY'] = V.from_outcome(uni)
        out['verdict'] = V.assess(G, scope='football')
        return out
    L['universe'].update(
        n_players=uni.evidence['n_players'],
        n_unaccounted=uni.evidence['n_unaccounted'],
        support_state_counts=uni.evidence['support_state_counts'],
        evidence_missing=uni.evidence['evidence_missing'])
    G['ROSTER_IDENTITY'] = (V.PASS if uni.evidence['n_unaccounted'] == 0
                            else V.FAIL)

    # FRESHNESS IS MEASURED AGAINST A GOVERNED REQUIREMENT, NOT AGAINST THE
    # EXISTENCE OF AN AGE. The previous gate passed whenever every source had
    # a calculable age, which greens a twenty-eight-hour injury file and a
    # three-day-old one alike.
    srcs = uni.evidence.get('sources') or {}
    fo = CH.check_freshness(cut, srcs)
    L['freshness'] = {'code': fo.code, 'state': fo.state.name,
                      'families': (fo.evidence or {}).get('families')}
    G['DATA_FRESHNESS'] = V.from_outcome(fo)

    # The full chronology certificate, now that the vintages are known.
    chrono = CH.certify(cut, out['run_started_at'], sources=srcs)
    L['chronology'] = {'code': chrono.code, 'state': chrono.state.name,
                       'certificate': chrono.value
                       or (chrono.evidence or {}).get('value'),
                       'violations': (chrono.evidence or {}).get('violations')}
    G['CHRONOLOGY_CERTIFIED'] = V.from_outcome(chrono)

    cov = CV.assess(uni.value, emitted_ids=None, emitted_by_layer=None)
    L['coverage'] = {'code': cov.code, 'state': cov.state.name}
    G['PLAYER_COVERAGE'] = V.from_outcome(cov)
    G['PER_CLUB_POSITION_COVERAGE'] = V.from_outcome(cov)
    G['PER_CLUB_LAYER_COVERAGE'] = V.from_outcome(cov)
    inact = CV.assert_no_inactive_survives(uni.value, emitted_ids=set())
    L['inactive_application'] = {'code': inact.code, 'state': inact.state.name}
    G['INACTIVE_APPLICATION'] = V.from_outcome(inact)

    uo = UV.usage_season(season, cut, before_week=week)
    L['usage_corpus'] = {'code': uo.code, 'state': uo.state.name}
    G['CURRENT_SEASON_INPUTS'] = V.from_outcome(uo)
    if uo.state is not State.PASS:
        out['verdict'] = V.assess(G, scope='football')
        return out
    L['usage_corpus'].update(
        blob=uo.evidence['blob'], store=uo.evidence['store'],
        n_games=uo.evidence['n_games'],
        accepted_panel_sees_n_games=uo.evidence[
            'accepted_panel_sees_n_games'],
        games_the_accepted_panel_cannot_see=uo.evidence[
            'games_the_accepted_panel_cannot_see'])
    usage = uo.value

    ro = RS.assign(uni.value, season=season, week=week, usage_rows=usage,
                   inactive_ids=inactive_ids)
    L['role'] = {'code': ro.code, 'state': ro.state.name}
    if ro.state is not State.PASS:
        G['ROLE_PLAUSIBILITY'] = V.from_outcome(ro)
        out['verdict'] = V.assess(G, scope='football')
        return out
    L['role'].update(role_counts=ro.evidence['role_counts'],
                     support_counts=ro.evidence['support_counts'],
                     conflict_counts=ro.evidence['conflict_counts'],
                     boundaries=ro.evidence['boundaries'])
    # THE POPULATION COMES FROM THE UNIVERSE, NOT FROM ROLE SUPPORT. Building
    # it from ROLE_SUPPORTED players and then asking whether they are
    # role-supported removed every problematic player from the denominator
    # before the test ran.
    rg = RS.assert_role_state_supported(ro.value, universe_rows=uni.value)
    L['role_gate'] = {'code': rg.code, 'state': rg.state.name,
                      'population_source': (rg.evidence or {}).get(
                          'population_source'),
                      'n_in_population': (rg.evidence or {}).get(
                          'n_in_population'),
                      'offending': (rg.evidence or {}).get('offending')}
    G['ROLE_PLAUSIBILITY'] = V.from_outcome(rg)

    snaps = RS.load_snaps(season, week)
    budget = PA.measure_budget(snaps.value) if snaps.state is State.PASS \
        else snaps
    po = PA.assess(ro.value, budget=(budget.value
                                     if budget.state is State.PASS else None),
                   snap_rows=(snaps.value if snaps.state is State.PASS
                              else None))
    L['participation'] = {'code': po.code, 'state': po.state.name,
                          'clubs': (po.evidence or {}).get('clubs')}
    prows = po.value or (po.evidence or {}).get('value') or []
    alloc_ids = {r['gsis_id'] for r in prows
                 if r['participation_state'] == PA.RESOLVED}
    pg = PA.assert_participation_supports_allocation(
        po, allocating_ids=alloc_ids,
        max_unresolved_fraction=max_unresolved_fraction)
    L['participation_gate'] = {
        'code': pg.code, 'state': pg.state.name,
        'governed_max_unresolved_fraction': (pg.evidence or {}).get(
            'governed_max_unresolved_fraction'),
        'governed_certification': (pg.evidence or {}).get(
            'governed_certification'),
        'caller_proposed_max_unresolved_fraction': (pg.evidence or {}).get(
            'caller_proposed_max_unresolved_fraction'),
        'caller_proposal_was_not_applied': (pg.evidence or {}).get(
            'caller_proposal_was_not_applied'),
        'club_unresolved_fraction': (pg.evidence or {}).get(
            'club_unresolved_fraction')}
    G['PARTICIPATION_COMPLETENESS'] = V.from_outcome(pg)

    L['allocation'] = {}
    alloc_states, redist_states = [], []
    for room in (RS.ROOM_TARGETS, RS.ROOM_CARRIES):
        ao = AL.allocate(po, usage, room=room)
        entry = {'code': ao.code, 'state': ao.state.name}
        if ao.state is State.PASS:
            entry['clubs'] = ao.evidence['clubs']
            entry['rows'] = ao.value
            cg = AL.assert_allocation_conserves(
                ao, consuming_ids={r['gsis_id'] for r in ao.value
                                   if r['allocation_state'] == AL.ALLOCATED})
            entry['gate'] = {'code': cg.code, 'state': cg.state.name}
            alloc_states.append(cg)
            # CONSERVATION IS NOT VALIDITY. The sum being one says the
            # opportunity was not lost; it says nothing about who received
            # it. That is a separate gate.
            rd = AL.assert_redistribution_supported(ao)
            entry['redistribution_gate'] = {
                'code': rd.code, 'state': rd.state.name,
                'offending': (rd.evidence or {}).get('offending')}
            redist_states.append(rd)
        L['allocation'][room] = entry
    G['OPPORTUNITY_CONSERVATION'] = (
        V.PASS if alloc_states and all(o.state is State.PASS
                                       for o in alloc_states)
        else V.FAIL if alloc_states else V.NOT_EVALUATED)
    G['REDISTRIBUTION_PLAUSIBILITY'] = (
        V.PASS if redist_states and all(o.state is State.PASS
                                        for o in redist_states)
        else V.BLOCKED if redist_states else V.NOT_EVALUATED)

    # GATES FOR WORK THAT DOES NOT EXIST ARE LEFT ABSENT, NOT FILLED.
    # verdict.assess resolves them to NOT_EVALUATED, which blocks. Writing
    # anything else here would be the most expensive lie available.
    out['gates_deliberately_absent'] = sorted(
        set(V.required_gates('dfs_product')) | set(
            V.required_gates('prop_product')) - set(G))
    for scope in ('football', 'prop_product', 'dfs_product'):
        out.setdefault('verdicts', {})[scope] = V.assess(G, scope=scope)
    out['verdict'] = out['verdicts']['football']
    return out


def render(out) -> str:
    lines = []
    for scope in ('football', 'prop_product', 'dfs_product'):
        o = (out.get('verdicts') or {}).get(scope)
        if o is not None:
            lines.append(V.render_status_line(o))
    return '\n'.join(lines)


def _plain(o):
    if isinstance(o, Outcome):
        return {'code': o.code, 'state': o.state.name,
                'value': o.value if isinstance(o.value, (dict, list)) else None,
                'evidence': {k: v for k, v in (o.evidence or {}).items()
                             if k != 'value'}}
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(x) for x in o]
    return o


def main(argv):
    if len(argv) < 5:
        print('usage: run_chain.py SEASON WEEK GAME_ID CUT '
              '[MAX_UNRESOLVED_FRACTION] [OUT.json]')
        return 2
    season, week, gid, cut = int(argv[1]), int(argv[2]), argv[3], argv[4]
    tol = float(argv[5]) if len(argv) > 5 and argv[5] not in ('-', '') \
        else None
    out = run(season, week, gid, cut, max_unresolved_fraction=tol)
    print(render(out))
    if len(argv) > 6:
        pathlib.Path(argv[6]).write_text(
            json.dumps(_plain(out), indent=1, default=str))
        print(f'\nwrote {argv[6]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
